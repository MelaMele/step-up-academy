
const headers = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Headers": "authorization, content-type",
  "Access-Control-Allow-Methods": "GET, OPTIONS"
};

const reply = (statusCode, body, extraHeaders = {}) => ({
  statusCode,
  headers: { ...headers, ...extraHeaders },
  body: JSON.stringify(body)
});

const getCorsHeaders = (event) => {
  const origin = event.headers?.origin || event.headers?.Origin;
  const allowedOrigin = process.env.TEACHER_PORTAL_ORIGIN;

  if (origin && allowedOrigin && origin === allowedOrigin) {
    return {
      "Access-Control-Allow-Origin": allowedOrigin,
      "Vary": "Origin"
    };
  }

  return {};
};

export const handler = async (event) => {
  const corsHeaders = getCorsHeaders(event);

  if (event.httpMethod === "OPTIONS") {
    return reply(204, {}, corsHeaders);
  }

  if (event.httpMethod !== "GET") {
    return reply(405, {
      success: false,
      message: "Method not allowed"
    }, corsHeaders);
  }

  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const anonKey = process.env.SUPABASE_ANON_KEY;

  if (!supabaseUrl || !serviceKey || !anonKey) {
    return reply(500, {
      success: false,
      message: "Server configuration is incomplete."
    }, corsHeaders);
  }

  const authHeader =
    event.headers?.authorization ||
    event.headers?.Authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return reply(401, {
      success: false,
      message: "Authentication required."
    }, corsHeaders);
  }

  const accessToken = authHeader.slice(7);

  const restHeaders = {
    apikey: serviceKey,
    Authorization: `Bearer ${serviceKey}`,
    "Content-Type": "application/json"
  };

  try {
    // 1. Verify the logged-in user
    const authResponse = await fetch(
      `${supabaseUrl}/auth/v1/user`,
      {
        headers: {
          apikey: anonKey,
          Authorization: `Bearer ${accessToken}`
        }
      }
    );

    if (!authResponse.ok) {
      return reply(401, {
        success: false,
        message: "Invalid or expired login session."
      }, corsHeaders);
    }

    const authUser = await authResponse.json();
    const userId = authUser.id;

    // 2. Get the user's profile
    const profileUrl = new URL(
      `${supabaseUrl}/rest/v1/profiles`
    );

    profileUrl.searchParams.set("select", "id,full_name,username,role,is_active,must_change_password");
    profileUrl.searchParams.set("id", `eq.${userId}`);
    profileUrl.searchParams.set("limit", "1");

    const profileResponse = await fetch(profileUrl, {
      headers: restHeaders
    });

    if (!profileResponse.ok) {
      throw new Error("Could not load profile.");
    }

    const profiles = await profileResponse.json();
    const profile = profiles[0];

    if (!profile || profile.role !== "teacher" || !profile.is_active) {
      return reply(403, {
        success: false,
        message: "Active teacher account required."
      }, corsHeaders);
    }

    if (profile.must_change_password) {
      return reply(403, {
        success: false,
        must_change_password: true,
        message: "Please change your temporary password first."
      }, corsHeaders);
    }

    // 3. Find the teacher record linked to this profile
    const teacherUrl = new URL(
      `${supabaseUrl}/rest/v1/teachers`
    );

    teacherUrl.searchParams.set(
      "select",
      "id,employee_number,full_name,phone,email,is_active"
    );
    teacherUrl.searchParams.set(
      "profile_id",
      `eq.${userId}`
    );
    teacherUrl.searchParams.set("limit", "1");

    const teacherResponse = await fetch(teacherUrl, {
      headers: restHeaders
    });

    if (!teacherResponse.ok) {
      throw new Error("Could not load teacher record.");
    }

    const teachers = await teacherResponse.json();
    const teacher = teachers[0];

    if (!teacher || !teacher.is_active) {
      return reply(403, {
        success: false,
        message: "Active teacher record not found."
      }, corsHeaders);
    }

    // 4. Find the current academic year
    const yearUrl = new URL(
      `${supabaseUrl}/rest/v1/academic_years`
    );

    yearUrl.searchParams.set(
      "select",
      "id,year_name,start_date,end_date"
    );
    yearUrl.searchParams.set("is_current", "eq.true");
    yearUrl.searchParams.set("limit", "1");

    const yearResponse = await fetch(yearUrl, {
      headers: restHeaders
    });

    if (!yearResponse.ok) {
      throw new Error("Could not load academic year.");
    }

    const years = await yearResponse.json();
    const academicYear = years[0] || null;

    if (!academicYear) {
      return reply(200, {
        success: true,
        teacher: {
          full_name: profile.full_name,
          username: profile.username,
          employee_number: teacher.employee_number
        },
        academic_year: null,
        assignments: []
      }, corsHeaders);
    }

    // 5. Get this teacher's assignments for the current year
    const assignmentUrl = new URL(
      `${supabaseUrl}/rest/v1/teacher_assignments`
    );

    assignmentUrl.searchParams.set(
      "select",
      "id,classes(id,grade_name,section),subjects(id,subject_name,subject_code,grade_name)"
    );
    assignmentUrl.searchParams.set(
      "teacher_id",
      `eq.${teacher.id}`
    );
    assignmentUrl.searchParams.set(
      "academic_year_id",
      `eq.${academicYear.id}`
    );

    const assignmentResponse = await fetch(assignmentUrl, {
      headers: restHeaders
    });

    if (!assignmentResponse.ok) {
      throw new Error("Could not load teacher assignments.");
    }

    const assignmentRows = await assignmentResponse.json();

    const assignments = assignmentRows.map((item) => ({
      id: item.id,
      class_id: item.classes?.id || null,
      class_name: item.classes
        ? `${item.classes.grade_name} ${item.classes.section}`
        : "Unknown class",
      subject_id: item.subjects?.id || null,
      subject_name: item.subjects?.subject_name || "Unknown subject",
      subject_code: item.subjects?.subject_code || null,
      grade_name: item.subjects?.grade_name || null
    }));

    return reply(200, {
      success: true,
      teacher: {
        full_name: profile.full_name,
        username: profile.username,
        employee_number: teacher.employee_number,
        phone: teacher.phone
      },
      academic_year: academicYear,
      assignments
    }, corsHeaders);

  } catch (error) {
    console.error("Teacher dashboard error:", error);

    return reply(500, {
      success: false,
      message: "Unable to load teacher dashboard."
    }, corsHeaders);
  }
};
