-- Member feedback and suggestions. Other members see the comment only.
-- The author can edit or soft-delete their own row. Admins see author details.

CREATE TABLE IF NOT EXISTS community_hub.feedback_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  comment TEXT NOT NULL CHECK (
    char_length(trim(comment)) > 0 AND char_length(comment) <= 5000
  ),
  added_by UUID NOT NULL REFERENCES community_hub.profiles(id) ON DELETE CASCADE,
  society_id UUID REFERENCES community_hub.societies(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS feedback_suggestions_society_created_idx
  ON community_hub.feedback_suggestions (society_id, created_at DESC);
CREATE INDEX IF NOT EXISTS feedback_suggestions_added_by_idx
  ON community_hub.feedback_suggestions (added_by);

ALTER TABLE community_hub.feedback_suggestions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON community_hub.feedback_suggestions FROM PUBLIC, anon, authenticated;

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

CREATE OR REPLACE FUNCTION public.post_feedback_suggestion(p_comment text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_id uuid;
  v_comment text := trim(COALESCE(p_comment, ''));
  v_society uuid;
BEGIN
  IF NOT community_hub.is_approved_user() AND NOT community_hub.is_admin() THEN
    RAISE EXCEPTION 'You must be an approved member to post feedback';
  END IF;
  IF v_comment = '' THEN
    RAISE EXCEPTION 'Feedback comments are required';
  END IF;
  IF char_length(v_comment) > 5000 THEN
    RAISE EXCEPTION 'Feedback comments cannot exceed 5000 characters';
  END IF;

  SELECT pr.society_id INTO v_society
  FROM community_hub.profiles pr
  WHERE pr.id = auth.uid();

  INSERT INTO community_hub.feedback_suggestions (comment, added_by, society_id)
  VALUES (v_comment, auth.uid(), v_society)
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.update_feedback_suggestion(p_id uuid, p_comment text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'community_hub', 'public'
AS $$
DECLARE
  v_comment text := trim(COALESCE(p_comment, ''));
  v_owner uuid;
  v_deleted timestamptz;
BEGIN
  IF NOT community_hub.is_approved_user() AND NOT community_hub.is_admin() THEN
    RAISE EXCEPTION 'You must be an approved member to edit feedback';
  END IF;
  IF v_comment = '' THEN
    RAISE EXCEPTION 'Feedback comments are required';
  END IF;
  IF char_length(v_comment) > 5000 THEN
    RAISE EXCEPTION 'Feedback comments cannot exceed 5000 characters';
  END IF;

  SELECT f.added_by, f.deleted_at INTO v_owner, v_deleted
  FROM community_hub.feedback_suggestions f
  WHERE f.id = p_id;

  IF v_owner IS NULL THEN
    RAISE EXCEPTION 'Feedback was not found';
  END IF;
  IF v_owner IS DISTINCT FROM auth.uid() THEN
    RAISE EXCEPTION 'You can only edit your own feedback';
  END IF;
  IF v_deleted IS NOT NULL THEN
    RAISE EXCEPTION 'Deleted feedback cannot be edited';
  END IF;

  UPDATE community_hub.feedback_suggestions
  SET comment = v_comment,
      updated_at = now()
  WHERE id = p_id;
END;
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

REVOKE ALL ON FUNCTION public.list_feedback_suggestions() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.post_feedback_suggestion(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.update_feedback_suggestion(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.soft_delete_feedback_suggestion(uuid) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.list_feedback_suggestions() TO authenticated;
GRANT EXECUTE ON FUNCTION public.post_feedback_suggestion(text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.update_feedback_suggestion(uuid, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.soft_delete_feedback_suggestion(uuid) TO authenticated;

NOTIFY pgrst, 'reload schema';
