-- Teacher login usernames.
-- Safe to run more than once.

ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS username TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS
profiles_username_unique
ON public.profiles (LOWER(username))
WHERE username IS NOT NULL;

COMMENT ON COLUMN public.profiles.username IS
'Server-managed login username for staff accounts.';
