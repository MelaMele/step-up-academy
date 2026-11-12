
import { randomUUID } from "node:crypto";

const allowedOrigin = process.env.TEACHER_PORTAL_ORIGIN || "";

const getHeaders = (origin = "") => {
  const headers = {
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Content-Type": "application/json",
    "Vary": "Origin"
  };

  if (allowedOrigin && origin === allowedOrigin) {
    headers["Access-Control-Allow-Origin"] = allowedOrigin;
  }

  return headers;
};

const reply = (statusCode, body, headers) => ({
  statusCode,
  headers,
  body: JSON.stringify(body)
});

function makeBaseUsername(name) {
  const value = String(name || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ".")
    .replace(/^\.+|\.+$/g, "")
    .slice(0, 28);

  return value || "teacher";
}

async function supabaseRequest(
  path,
  {
    method = "GET",
    token,
    body,
    serviceKey,
    projectUrl
  } = {}
) {
  const response = await fetch(`${projectUrl}${path}`, {
    method,
    headers: {
      apikey: serviceKey,
      Authorization: `Bearer ${token || serviceKey}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(method === "PATCH"
        ? { Prefer: "return=representation" }
        : {})
    },
    ...(body ? { body: JSON.stringify(body) } : {})
  });

  const text = await response.text();
  let data;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { message: text };
  }

  if (!response.ok) {
    const error = new Error(
      data?.msg ||
      data?.message ||
      data?.error_description ||
      `Supabase request failed (${response.status})`
    );
    error.status = response.status;
    throw error;
  }

  return data;
}

export default async (request) => {
  const origin = request.headers?.origin || "";
  const headers = getHeaders(origin);

  if (allowedOrigin && origin && origin !== allowedOrigin) {
    return reply(403, { error: "Origin not allowed." }, headers);
  }

  if (request.httpMethod === "OPTIONS") {
    return {
      statusCode: 204,
      headers,
      body: ""
    };
  }

  if (request.httpMethod !== "POST") {
    return reply(405, {
      error: "Method not allowed."
    }, headers);
  }

  const projectUrl = (
    process.env.SUPABASE_URL || ""
  ).replace(/\/+$/, "");

  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!projectUrl || !serviceKey) {
    return reply(500, {
      error: "Server Supabase configuration is incomplete."
    }, headers);
  }

  const authorization =
    request.headers?.authorization ||
    request.headers?.Authorization ||
    "";

  const match = authorization.match(/^Bearer\s+(.+)$/i);

  if (!match) {
    return reply(401, {
      error: "Sign in as an administrator first."
    }, headers);
  }

  let input;

  try {
    input = JSON.parse(request.body || "{}");
  } catch {
    return reply(400, {
      error: "Invalid JSON request."
    }, headers);
  }

  const teacherId = String(input.teacher_id || "").trim();

  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  if (!uuidPattern.test(teacherId)) {
    return reply(400, {
      error: "A valid teacher record is required."
    }, headers);
  }

  let createdUserId = null;

  try {
    // 1. Validate the administrator's access token.
    const caller = await supabaseRequest("/auth/v1/user", {
      token: match[1],
      serviceKey,
      projectUrl
    });

    if (!caller?.id) {
      return reply(401, {
        error: "Invalid login session."
      }, headers);
    }

    // 2. Confirm active administrator role.
    const profiles = await supabaseRequest(
      `/rest/v1/profiles?id=eq.${encodeURIComponent(caller.id)}&select=id,role,is_active`,
      { serviceKey, projectUrl }
    );

    if (
      !profiles?.[0] ||
      profiles[0].role !== "admin" ||
      profiles[0].is_active !== true
    ) {
      return reply(403, {
        error: "Only an active administrator can create teacher accounts."
      }, headers);
    }

    // 3. Find the teacher record.
    const teachers = await supabaseRequest(
      `/rest/v1/teachers?id=eq.${encodeURIComponent(teacherId)}&select=id,profile_id,full_name,employee_number,is_active`,
      { serviceKey, projectUrl }
    );

    const teacher = teachers?.[0];

    if (!teacher) {
      return reply(404, {
        error: "Teacher record was not found."
      }, headers);
    }

    if (teacher.is_active !== true) {
      return reply(409, {
        error: "Activate this teacher before creating a login."
      }, headers);
    }

    if (teacher.profile_id) {
      return reply(409, {
        error: "This teacher already has a linked login account."
      }, headers);
    }

    // 4. Generate an available username.
    const base = makeBaseUsername(teacher.full_name);
    let username = "";
    let available = false;

    for (let suffix = 1; suffix <= 9999; suffix++) {
      const candidate = suffix === 1
        ? base
        : `${base.slice(0, 27 - String(suffix).length)}.${suffix}`;

      const existing = await supabaseRequest(
        `/rest/v1/profiles?username=ilike.${encodeURIComponent(candidate)}&select=id&limit=1`,
        { serviceKey, projectUrl }
      );

      if (!existing?.length) {
        username = candidate;
        available = true;
        break;
      }
    }

    if (!available) {
      return reply(409, {
        error: "Could not generate a unique username. Please try again."
      }, headers);
    }

    // 5. Create the Auth account.
    // The teacher signs in using username + password.
    const authEmail = `${username}@stepupacademy.test`;

    const temporaryPassword =
      `SuA-${randomUUID()}-${randomUUID()}!`;

    const created = await supabaseRequest(
      "/auth/v1/admin/users",
      {
        method: "POST",
        serviceKey,
        projectUrl,
        body: {
          email: authEmail,
          password: temporaryPassword,
          email_confirm: true,
          user_metadata: {
            full_name: teacher.full_name
          }
        }
      }
    );

    createdUserId = created?.id;

    if (!createdUserId) {
      throw new Error("Account creation could not be verified.");
    }

    // 6. Link the profile and enforce first-login password change.
    const updatedProfiles = await supabaseRequest(
      `/rest/v1/profiles?id=eq.${encodeURIComponent(createdUserId)}`,
      {
        method: "PATCH",
        serviceKey,
        projectUrl,
        body: {
          role: "teacher",
          username,
          must_change_password: true
        }
      }
    );

    if (!Array.isArray(updatedProfiles) ||
        updatedProfiles.length !== 1) {
      throw new Error("Teacher profile could not be linked.");
    }

    // 7. Link the teacher record only if it is still unlinked.
    const updatedTeachers = await supabaseRequest(
      `/rest/v1/teachers?id=eq.${encodeURIComponent(teacherId)}&profile_id=is.null`,
      {
        method: "PATCH",
        serviceKey,
        projectUrl,
        body: {
          profile_id: createdUserId
        }
      }
    );

    if (!Array.isArray(updatedTeachers) ||
        updatedTeachers.length !== 1) {
      throw new Error("Teacher record could not be linked.");
    }

    // 8. Return the temporary password only once.
    return reply(200, {
      success: true,
      teacher_name: teacher.full_name,
      username,
      temporary_password: temporaryPassword,
      must_change_password: true,
      note: "Give this temporary password to the teacher securely. It must be changed at first login."
    }, headers);

  } catch (error) {
    // Roll back the Auth account if database linking failed.
    if (createdUserId) {
      try {
        await supabaseRequest(
          `/auth/v1/admin/users/${encodeURIComponent(createdUserId)}`,
          {
            method: "DELETE",
            serviceKey,
            projectUrl
          }
        );
      } catch {
        // Preserve the original error.
      }
    }

    const status =
      error.status === 401 ? 401 :
      error.status === 409 ? 409 : 500;

    return reply(status, {
      error: status === 401
        ? "Your administrator session is invalid. Please sign in again."
        : status === 409
          ? "This account may already exist. Refresh and check the teacher record."
          : "Could not safely create the teacher account. Please try again or contact the system administrator."
    }, headers);
  }
};
