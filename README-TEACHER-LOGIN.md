# Step Up Academy — Teacher Login (isolated deployment package)

This directory is intentionally separate from the repository's existing Flask application. It is prepared for a separate Netlify site and must not be merged into `main` or published until reviewed and tested.

## Included
- `index.html`: current Supabase-based admin interface copied from the teacher-management update package.
- `netlify/functions/create-teacher-account.mjs`: server-side account creation endpoint. It validates the caller's Supabase access token and checks that the caller is an active `admin` profile before using the service-role key.
- `supabase/migrations/202611120001_teacher_login_username.sql`: adds a unique, nullable `profiles.username` column.
- `step_up_academy_logo.jpeg`: school logo asset.

## Required deployment environment variables
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (secret; server-side only)

Never add the service-role key to `index.html`, browser JavaScript, Git, or a public environment variable.

## Database setup
Run the SQL migration in the Supabase SQL Editor before enabling the function.

## Important limitations in this first backend stage
- The frontend does not yet call this endpoint or provide teacher username/password login.
- The endpoint returns the generated temporary password once to the authorized administrator. Deliver it to the teacher securely; do not store or screenshot it in a public place.
- Teacher first-login password-change enforcement and teacher-only dashboard authorization are a separate required stage before production use.
- The `.test` email suffix is an internal Supabase Auth identifier, not a real mailbox. Verify the project's Auth email validation accepts it in a test project before production use.
- Deploy this folder as a separate Netlify site with its base directory set to `teacher-portal`; do not change the existing site's publish directory or GitHub `main` branch.
