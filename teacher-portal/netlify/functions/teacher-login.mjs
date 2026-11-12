
const allowedOrigin = process.env.TEACHER_PORTAL_ORIGIN || "";

function getHeaders(origin = "") {
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
    return reply(405, { error: "Method not allowed." }, headers);
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

  let input;

  try {
    input = JSON.parse(request.body || "{}");
  } catch {
    return reply(400, { error: "Invalid request." }, headers);
  }

  const username = String(input.username || "").trim().toLowerCase();
  const password = String(input.password || "");

  if (
    !/^[a-z0-9][a-z0-9._-]{1,39}$/.test(username) ||
    !password ||
    password.length > 256
  ) {
    return reply(400, {
      error: "Please enter a valid username and password."
    }, headers);
  }

  try {
    // 1. Find the username in the server-side profiles table.
    const profileUrl =
      `${projectUrl}/rest/v1/profiles` +
      `?username=ilike.${encodeURIComponent(username)}` +
      `&select=id,full_name,username,role,is_active,must_change_password`;

    const profileResponse = await fetch(profileUrl, {
      method: "GET",
      headers: {
        apikey: serviceKey,
        Authorization: `Bearer ${serviceKey}`
      }
    });

    if (!profileResponse.ok) {
      throw new Error("Profile lookup failed.");
    }

    const profiles = await readResponse(profileResponse);
    const profile = Array.isArray(profiles) && profiles.length === 1
      ? profiles[0]
      : null;

    // Use the same generic message for unknown and inactive accounts.
    if (
      !profile ||
      profile.role !== "teacher" ||
      profile.is_active !== true
    ) {
      return reply(401, {
        error: "Invalid username or password."
      }, headers);
    }

    // 2. Sign in using the synthetic email created for this username.
    const authEmail = `${profile.username}@stepupacademy.test`;

    const signInResponse = await fetch(
      `${projectUrl}/auth/v1/token?grant_type=password`,
      {
        method: "POST",
        headers: {
          apikey: anonKey,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          email: authEmail,
          password
        })
      }
    );

    const authData = await readResponse(signInResponse);

    if (
      !signInResponse.ok ||
      !authData?.access_token ||
      !authData?.user?.id ||
      authData.user.id !== profile.id
    ) {
      return reply(401, {
        error: "Invalid username or password."
      }, headers);
    }

    // 3. Return only the authenticated teacher's session information.
    return reply(200, {
      success: true,
      access_token: authData.access_token,
      token_type: authData.token_type || "bearer",
      expires_in: authData.expires_in,
      full_name: profile.full_name || "Teacher",
      username: profile.username,
      must_change_password: profile.must_change_password === true
    }, headers);

  } catch (error) {
    // Do not expose database or authentication internals to the browser.
    return reply(500, {
      error: "Unable to sign in right now. Please try again later."
    }, headers);
  }
};
