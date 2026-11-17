-- Post-study operational maintenance. Does not alter stored observations.
-- Each inventory device has at most one newest row, using the same timestamp
-- ordering as the original DISTINCT ON views. Devices without rows are omitted.
CREATE OR REPLACE VIEW telemetry.latest_probes AS
 SELECT p.*, clock_timestamp()-p.observed_at > interval '30 seconds' AS is_stale
 FROM inventory.devices d
 CROSS JOIN LATERAL (
  SELECT * FROM telemetry.probes WHERE device_id=d.device_id
  ORDER BY observed_at DESC LIMIT 1
 ) p;
CREATE OR REPLACE VIEW telemetry.latest_polls AS
 SELECT p.*, clock_timestamp()-p.observed_at > interval '90 seconds' AS is_stale
 FROM inventory.devices d
 CROSS JOIN LATERAL (
  SELECT * FROM telemetry.polls WHERE device_id=d.device_id
  ORDER BY observed_at DESC LIMIT 1
 ) p;
