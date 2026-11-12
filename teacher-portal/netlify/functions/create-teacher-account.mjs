
const headers = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json"
};

const reply = (statusCode, body) => ({
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
      ...(body ? { "Content-Type": "application/json" } : {})
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
  if (request.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers, body: "" };
  }

  if (request.httpMethod !== "POST") {
    return reply(405, { error: "Method not allowed" });
  }

  const projectUrl = process.env.SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!projectUrl || !serviceKey) {
    return reply(500, {
      error: "Server Supabase configuration is incomplete."
    });
  }

  const authorization =
    request.headers.authorization ||
    request.headers.Authorization ||
    "";

  const match = authorization.match(/^Bearer\s+(.+)$/i);

  if (!match) {
    return reply(401, {
      error: "Sign in as an administrator first."
    });
  }

  let input;

  try {
    input = JSON.parse(request.body || "{}");
  } catch {
    return reply(400, { error: "Invalid JSON request." });
  }

  const teacherId = String(input.teacher_id || "").trim();

  if (!/^[0-9a-f-]{36}$/i.test(teacherId)) {
    return reply(400, {
      error: "A valid teacher record is required."
    });
  }

  try {
    // Validate the caller's access token.
    const caller = await supabaseRequest("/auth/v1/user", {
      token: match[1],
      serviceKey,
      projectUrl
    });

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
      });
    }

    const teachers = await supabaseRequest(
      `/rest/v1/teachers?id=eq.${encodeURIComponent(teacherId)}&select=id,profile_id,full_name,employee_number,is_active`,
      { serviceKey, projectUrl }
    );

    const teacher = teachers?.[0];

    if (!teacher) {
      return reply(404, {
        error: "Teacher record was not found."
      });
    }

    if (!teacher.is_active) {
      return reply(409, {
        error: "This teacher is inactive. Activate the teacher before creating a login."
      });
    }

    if (teacher.profile_id) {
      return reply(409, {
        error: "This teacher is already linked to a login account."
      });
    }

    const base = makeBaseUsername(teacher.full_name);
    let username = base;

    for (let suffix = 2; suffix < 10000; suffix++) {
      const existing = await supabaseRequest(
        `/rest/v1/profiles?username=ilike.${encodeURIComponent(username)}&select=id&limit=1`,
        { serviceKey, projectUrl }
      );

      if (!existing?.length) break;

      username = `${base.slice(0, 27 - String(suffix).length)}${suffix}`;
    }

    const authEmail = `${username}@stepupacademy.test`;

    const temporaryPassword =
      `SuA-${crypto.randomUUID()}-${crypto.randomUUID()}!`;

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

    const userId = created?.id;

    if (!userId) {
      throw new Error("Supabase did not return the new user ID.");
    }

    try {
      await supabaseRequest(
        `/rest/v1/profiles?id=eq.${encodeURIComponent(userId)}`,
        {
          method: "PATCH",
          serviceKey,
          projectUrl,
          body: {
            role: "teacher",
            username
          }
        }
      );

      await supabaseRequest(
        `/rest/v1/teachers?id=eq.${encodeURIComponent(teacherId)}`,
        {
          method: "PATCH",
          serviceKey,
          projectUrl,
          body: {
            profile_id: userId
          }
        }
      );
    } catch (linkError) {
      // Roll back the Auth account if database linking fails.
      try {
        await supabaseRequest(
          `/auth/v1/admin/users/${encodeURIComponent(userId)}`,
          {
            method: "DELETE",
            serviceKey,
            projectUrl
          }
        );
      } catch {
        // Keep the original linking error.
      }

      throw linkError;
    }

    return reply(200, {
      success: true,
      teacher_name: teacher.full_name,
      username,
      temporary_password: temporaryPassword,
      note: "Show this temporary password to the teacher once. The teacher must change it after signing in."
    });

  } catch (error) {
    const status = error.status === 401 ? 401 : 500;

    return reply(status, {
      error: error.message ||
        "Could not create teacher account."
    });
  }
};
