-- Let the driver delete a ride that already has seat requests.
-- Cascade deletes those requests, which RLS blocks unless a delete policy exists.

DROP POLICY IF EXISTS ride_requests_delete ON community_hub.ride_requests;
CREATE POLICY ride_requests_delete ON community_hub.ride_requests
  FOR DELETE
  USING (
    community_hub.is_admin()
    OR requester_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM community_hub.ride_offers o
      WHERE o.id = offer_id AND o.added_by = auth.uid()
    )
  );

GRANT DELETE ON community_hub.ride_requests TO authenticated;

NOTIFY pgrst, 'reload schema';
