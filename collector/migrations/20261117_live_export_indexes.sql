-- Post-study indexes for the unchanged bounded read-only export queries.
-- No observation values, timestamps or diagnostic thresholds change.
CREATE INDEX IF NOT EXISTS polls_latest_export_cover
 ON telemetry.polls(device_id,observed_at DESC)
 INCLUDE(poll_id,received_at,status,error,collector_version);
CREATE INDEX IF NOT EXISTS samples_observation_time
 ON telemetry.interface_samples(observed_at DESC);
CREATE INDEX IF NOT EXISTS probes_observation_time
 ON telemetry.probes(observed_at DESC);
CREATE INDEX IF NOT EXISTS snapshots_observation_time
 ON telemetry.config_snapshots(observed_at DESC);
