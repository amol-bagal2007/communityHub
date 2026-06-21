-- Residents must confirm staying within society.

UPDATE community_hub.profiles
SET staying_within_society = true
WHERE role = 'resident' AND staying_within_society = false;

ALTER TABLE community_hub.profiles
  ADD CONSTRAINT profiles_resident_staying_check
  CHECK (role <> 'resident' OR staying_within_society = true);
