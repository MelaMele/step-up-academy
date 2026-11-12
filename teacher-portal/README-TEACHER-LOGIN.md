# Step Up Academy – Teacher Login Portal

## Overview
This project provides the teacher account management
and login backend for Step Up Academy.

## Project Structure

teacher-portal/
├── index.html
├── netlify.toml
├── README-TEACHER-LOGIN.md
├── step_up_academy_logo.jpeg
├── netlify/
│   └── functions/
│       └── create-teacher-account.mjs
└── supabase/
    └── migrations/
        └── 202611120001_teacher_login_username.sql

## Technologies
- HTML
- JavaScript
- Supabase Authentication
- Supabase Database
- Netlify Functions

## Security
- Only authorized administrators can create teacher accounts.
- Service role keys must remain on the server.
- Never expose secret keys in frontend JavaScript.
- Teacher accounts must have the teacher role.
- Teachers should change their temporary password
  when the first-login process is implemented and enabled.

## Deployment
Deploy the teacher-portal directory as a separate
Netlify site.

Configure these environment variables in Netlify:

SUPABASE_URL

SUPABASE_SERVICE_ROLE_KEY

Never commit secret values to GitHub.

## Important
The frontend and backend integration must be tested
before production use.
