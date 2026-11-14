
const allowedOrigin = process.env.TEACHER_PORTAL_ORIGIN || "";

function getHeaders(origin = "") {
  const headers = {
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    "Vary": "Origin"
  };

  if (allowedOrigin && origin === allowedOrigin) {
    headers["Access-Control-Allow-Origin"] = allowedOrigin;
  }

  return headers;
}

function reply(statusCode, body, headers) {
  return {
    statusCode,
    headers,
    body: JSON.stringify(body)
  };
}

async function readResponse(response) {
  const text = await response.text();

  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

export const handler = async (event) => {
  const origin =
    event.headers?.origin ||
    event.headers?.Origin ||
    "";

  const headers = getHeaders(origin);

  if (allowedOrigin && origin && origin !== allowedOrigin) {
    return reply(403, {
      error: "Origin not allowed."
    }, headers);
  }

  if (event.httpMethod === "OPTIONS") {
    return {
      statusCode: 204,
      headers,
      body: ""
    };
  }

  if (event.httpMethod !== "POST") {
    return reply(405, {
      error: "Method not allowed."
    }, headers);
  }

  const projectUrl = (
    process.env.SUPABASE_URL || ""
  ).replace(/\/+$/, "");

  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const anonKey = process.env.SUPABASE_ANON_KEY;

  if (!projectUrl || !serviceKey || !anonKey) {
    return reply(500, {
      error: "Server authentication configuration is incomplete."
    }, headers);
  }

  const authHeader =
    event.headers?.authorization ||
    event.headers?.Authorization ||
    "";

  const tokenMatch = authHeader.match(/^Bearer\s+(.+)$/i);

  if (!tokenMatch) {
    return reply(401, {
      error: "Authentication required."
    }, headers);
  }

  const accessToken = tokenMatch[1].trim();

  let input;

  try {
    input = JSON.parse(event.body || "{}");
  } catch {
    return reply(400, {
      error: "Invalid request."
    }, headers);
  }

  const newPassword = String(input.new_password || "");

  if (newPassword.length < 8 || newPassword.length > 128) {
    return reply(400, {
      error: "Password must contain between 8 and 128 characters."
    }, headers);
  }

  try {
    // 1. Verify the authenticated user.
    const userResponse = await fetch(
      `${projectUrl}/auth/v1/user`,
      {
        method: "GET",
        headers: {
          apikey: anonKey,
          Authorization: `Bearer ${accessToken}`
        }
      }
    );

    const authUser = await readResponse(userResponse);

    if (!userResponse.ok || !authUser?.id) {
      return reply(401, {
        error: "Your session is invalid or expired. Please sign in again."
      }, headers);
    }

    // 2. Verify active teacher profile.
    const profileUrl = new URL(
      `${projectUrl}/rest/v1/profiles`
    );

    profileUrl.searchParams.set("id", `eq.${authUser.id}`);
    profileUrl.searchParams.set(
      "select",
      "id,role,is_active,must_change_password"
    );

    const profileResponse = await fetch(profileUrl, {
      method: "GET",
      headers: {
        apikey: serviceKey,
        Authorization: `Bearer ${serviceKey}`
      }
    });

    if (!profileResponse.ok) {
      throw new Error("Profile verification failed.");
    }

    const profiles = await readResponse(profileResponse);

    const profile =
      Array.isArray(profiles) && profiles.length === 1
        ? profiles[0]
        : null;

    if (
      !profile ||
      profile.role !== "teacher" ||
      profile.is_active !== true
    ) {
      return reply(403, {
        error: "This account is not authorized to change a teacher password."
      }, headers);
    }

    // 3. Update the password using the Auth Admin API.
    const passwordResponse = await fetch(
      `${projectUrl}/auth/v1/admin/users/${encodeURIComponent(authUser.id)}`,
      {
        method: "PUT",
        headers: {
          apikey: serviceKey,
          Authorization: `Bearer ${serviceKey}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          password: newPassword
        })
      }
    );

    if (!passwordResponse.ok) {
      return reply(400, {
        error: "Password update failed. Please try again."
      }, headers);
    }

    // 4. Mark first-login password change as completed.
    const updateProfileUrl = new URL(
      `${projectUrl}/rest/v1/profiles`
    );

    updateProfileUrl.searchParams.set(
      "id",
      `eq.${authUser.id}`
    );

    updateProfileUrl.searchParams.set(
      "role",
      "eq.teacher"
    );

    updateProfileUrl.searchParams.set(
      "is_active",
      "eq.true"
    );

    const updateProfileResponse = await fetch(
      updateProfileUrl,
      {
        method: "PATCH",
        headers: {
          apikey: serviceKey,
          Authorization: `Bearer ${serviceKey}`,
          "Content-Type": "application/json",
          Prefer: "return=representation"
        },
        body: JSON.stringify({
          must_change_password: false
        })
      }
    );

    const updatedProfiles =
      await readResponse(updateProfileResponse);

    if (
      !updateProfileResponse.ok ||
      !Array.isArray(updatedProfiles) ||
      updatedProfiles.length !== 1
    ) {
      return reply(500, {
        error: "Password changed, but account setup could not be completed. Please contact the administrator."
      }, headers);
    }

    return reply(200, {
      success: true,
      must_change_password: false,
      message: "Password changed successfully."
    }, headers);

  } catch (error) {
    console.error("Teacher password change error:", error);

    return reply(500, {
      error: "Unable to change password right now. Please try again later."
    }, headers);
  }
};
