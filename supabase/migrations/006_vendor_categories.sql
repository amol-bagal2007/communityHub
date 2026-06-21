-- Admin-maintained vendor categories; vendors reference category_id instead of free text.

CREATE TABLE community_hub.vendor_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE community_hub.vendors
  ADD COLUMN category_id UUID REFERENCES community_hub.vendor_categories(id) ON DELETE SET NULL;

INSERT INTO community_hub.vendor_categories (name)
SELECT DISTINCT trim(category)
FROM community_hub.vendors
WHERE category IS NOT NULL AND trim(category) <> ''
ON CONFLICT (name) DO NOTHING;

UPDATE community_hub.vendors v
SET category_id = vc.id
FROM community_hub.vendor_categories vc
WHERE v.category IS NOT NULL
  AND trim(v.category) = vc.name;

ALTER TABLE community_hub.vendors DROP COLUMN category;

INSERT INTO community_hub.vendor_categories (name) VALUES
  ('Plumber'),
  ('Electrician'),
  ('Carpenter'),
  ('Housekeeping'),
  ('Security'),
  ('Other')
ON CONFLICT (name) DO NOTHING;

ALTER TABLE community_hub.vendor_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY vendor_categories_read ON community_hub.vendor_categories
  FOR SELECT
  USING (community_hub.is_approved_user() OR community_hub.is_admin());

CREATE POLICY vendor_categories_admin_all ON community_hub.vendor_categories
  FOR ALL
  USING (community_hub.is_admin())
  WITH CHECK (community_hub.is_admin());
