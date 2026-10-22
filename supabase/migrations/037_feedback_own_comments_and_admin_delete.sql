-- Members see and delete only their own feedback.
-- Admins see every comment and can delete any of them.

CREATE OR REPLACE FUNCTION public.list_feedback_suggestions()
RETURNS TABLE (
  id uuid,
  comment text,
  created_at timestamptz,
  updated_at timestamptz,
  deleted_at timestamptz,
  is_mine boolean,
  author_name text,
  phone text,
  email text,
  society_name text,
  tower_name text,
  flat_number text
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
  SELECT
    f.id,
    f.comment,
    f.created_at,
    f.updated_at,
    f.deleted_at,
    (f.added_by = auth.uid()) AS is_mine,
    CASE
      WHEN community_hub.is_admin() THEN NULLIF(
        trim(both ' ' FROM concat_ws(
          ' ',
          NULLIF(trim(COALESCE(p.title, '')), ''),
          NULLIF(trim(COALESCE(p.first_name, '')), ''),
          NULLIF(trim(COALESCE(p.last_name, '')), '')
        )),
        ''
      )
      ELSE NULL
    END AS author_name,
    CASE WHEN community_hub.is_admin() THEN p.phone ELSE NULL END AS phone,
    CASE WHEN community_hub.is_admin() THEN p.email ELSE NULL END AS email,
    CASE WHEN community_hub.is_admin() THEN s.name ELSE NULL END AS society_name,
    CASE WHEN community_hub.is_admin() THEN t.name ELSE NULL END AS tower_name,
    CASE WHEN community_hub.is_admin() THEN p.flat_number ELSE NULL END AS flat_number
  FROM community_hub.feedback_suggestions f
  JOIN community_hub.profiles p ON p.id = f.added_by
  LEFT JOIN community_hub.societies s ON s.id = COALESCE(f.society_id, p.society_id)
  LEFT JOIN community_hub.towers t ON t.id = p.tower_id
  WHERE (community_hub.is_approved_user() OR community_hub.is_admin())
    AND f.deleted_at IS NULL
    AND (
      community_hub.is_admin()
      OR f.added_by = auth.uid()
    )
  ORDER BY f.created_at DESC;
$$;

CREATE OR REPLACE FUNCTION public.soft_delete_feedback_suggestion(p_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_owner uuid;
  v_deleted timestamptz;
BEGIN
  IF NOT community_hub.is_approved_user() AND NOT community_hub.is_admin() THEN
    RAISE EXCEPTION 'You must be an approved member to delete feedback';
  END IF;

  SELECT f.added_by, f.deleted_at INTO v_owner, v_deleted
  FROM community_hub.feedback_suggestions f
  WHERE f.id = p_id;

  IF v_owner IS NULL THEN
    RAISE EXCEPTION 'Feedback was not found';
  END IF;
  IF NOT community_hub.is_admin() AND v_owner IS DISTINCT FROM auth.uid() THEN
    RAISE EXCEPTION 'You can only delete your own feedback';
  END IF;
  IF v_deleted IS NOT NULL THEN
    RETURN;
  END IF;

  UPDATE community_hub.feedback_suggestions
  SET deleted_at = now(),
      updated_at = now()
  WHERE id = p_id;
END;
$$;

NOTIFY pgrst, 'reload schema';
