-- Admin checkbox to show the Feedback/Suggestion tab to members.
-- Off until an admin enables it. Admins always see the tab.

INSERT INTO community_hub.app_feature_flags (key, enabled)
VALUES ('feedback_tab', false)
ON CONFLICT (key) DO NOTHING;

NOTIFY pgrst, 'reload schema';
