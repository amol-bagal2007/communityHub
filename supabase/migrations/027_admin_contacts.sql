-- Public-safe admin contact details for disclaimer + Contact tab (anon + members).

CREATE OR REPLACE FUNCTION public.get_admin_contacts()
RETURNS TABLE (
  first_name text,
  last_name text,
  title text,
  phone text,
  email text
)
LANGUAGE sql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
  SELECT
    p.first_name,
    p.last_name,
    p.title,
    p.phone,
    p.email
  FROM community_hub.profiles p
  WHERE p.role = 'admin'
    AND p.status = 'approved'
  ORDER BY p.first_name, p.last_name;
$$;

REVOKE ALL ON FUNCTION public.get_admin_contacts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_admin_contacts() TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
