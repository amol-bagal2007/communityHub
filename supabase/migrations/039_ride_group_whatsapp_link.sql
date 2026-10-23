-- Optional WhatsApp group invite link on a ride offer.

ALTER TABLE community_hub.ride_offers
  ADD COLUMN IF NOT EXISTS group_whatsapp_link TEXT;

NOTIFY pgrst, 'reload schema';
