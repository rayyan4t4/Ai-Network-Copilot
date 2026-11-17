CREATE SCHEMA IF NOT EXISTS inventory;
CREATE SCHEMA IF NOT EXISTS telemetry;
CREATE SCHEMA IF NOT EXISTS operations;

CREATE TABLE IF NOT EXISTS inventory.devices (
 device_id text PRIMARY KEY, hostname text NOT NULL UNIQUE, site text NOT NULL,
 role text NOT NULL, management_ip inet, aliases jsonb NOT NULL DEFAULT '[]',
 monitored boolean NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS inventory.links (
 link_id text PRIMARY KEY, a_device text REFERENCES inventory.devices,
 a_interface text NOT NULL, b_device text REFERENCES inventory.devices,
 b_interface text NOT NULL, purpose text NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory.interfaces (
 interface_id text PRIMARY KEY, device_id text NOT NULL REFERENCES inventory.devices,
 name text NOT NULL, current_ifindex integer NOT NULL,
 capacity_bps bigint, capacity_source text NOT NULL DEFAULT 'snmp',
 UNIQUE(device_id,name)
);
CREATE TABLE IF NOT EXISTS telemetry.polls (
 poll_id uuid PRIMARY KEY, device_id text NOT NULL REFERENCES inventory.devices,
 observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source text NOT NULL DEFAULT 'snmp', status text NOT NULL CHECK(status IN ('ok','timeout','error')),
 error text, raw jsonb NOT NULL DEFAULT '{}', collector_version text NOT NULL
);
CREATE INDEX IF NOT EXISTS polls_device_time ON telemetry.polls(device_id,observed_at DESC);
CREATE TABLE IF NOT EXISTS telemetry.interface_samples (
 poll_id uuid NOT NULL REFERENCES telemetry.polls, interface_id text NOT NULL REFERENCES inventory.interfaces,
 observed_at timestamptz NOT NULL, ifindex integer NOT NULL, admin_status integer, oper_status integer,
 in_octets numeric(20,0), out_octets numeric(20,0), in_errors numeric(20,0), out_errors numeric(20,0),
 counter_bits integer, speed_bps bigint, sysuptime_ticks bigint, discontinuity_ticks bigint,
 interval_s double precision, in_bps double precision, out_bps double precision,
 in_utilization_pct double precision, out_utilization_pct double precision,
 rate_status text NOT NULL, PRIMARY KEY(poll_id,interface_id)
);
CREATE INDEX IF NOT EXISTS samples_interface_time ON telemetry.interface_samples(interface_id,observed_at DESC);
CREATE TABLE IF NOT EXISTS telemetry.device_health (
 poll_id uuid PRIMARY KEY REFERENCES telemetry.polls, sysuptime_ticks bigint,
 reported_name text, memory_total_kib bigint, memory_available_kib bigint,
 cpu_busy_pct double precision, resource_scope text NOT NULL DEFAULT 'shared_guest_host_resources'
);
CREATE TABLE IF NOT EXISTS telemetry.probes (
 probe_id uuid PRIMARY KEY, device_id text NOT NULL REFERENCES inventory.devices,
 observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source_ip inet NOT NULL, status text NOT NULL CHECK(status IN ('ok','timeout','error')),
 rtt_ms double precision, raw text NOT NULL
);
CREATE INDEX IF NOT EXISTS probes_device_time ON telemetry.probes(device_id,observed_at DESC);
CREATE TABLE IF NOT EXISTS telemetry.syslog_events (
 event_id uuid PRIMARY KEY, device_id text REFERENCES inventory.devices,
 event_time timestamptz, received_at timestamptz NOT NULL, ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source_ip inet, reported_hostname text, program text, severity integer,
 message text NOT NULL, raw text NOT NULL, identity_status text NOT NULL,
 parse_error text, file_generation uuid NOT NULL, byte_offset bigint NOT NULL,
 UNIQUE(file_generation,byte_offset)
);
CREATE INDEX IF NOT EXISTS syslog_device_time ON telemetry.syslog_events(device_id,received_at DESC);
CREATE TABLE IF NOT EXISTS telemetry.config_snapshots (
 snapshot_id uuid PRIMARY KEY, device_id text NOT NULL REFERENCES inventory.devices,
 observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source text NOT NULL DEFAULT 'authorized_readonly_console', raw jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS operations.checkpoints (
 service text PRIMARY KEY, file_identity text NOT NULL, generation uuid NOT NULL,
 byte_offset bigint NOT NULL, updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS operations.heartbeats (
 service text PRIMARY KEY, updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 status text NOT NULL, detail jsonb NOT NULL DEFAULT '{}'
);
CREATE OR REPLACE VIEW telemetry.latest_interfaces AS
 SELECT *, clock_timestamp()-observed_at > interval '90 seconds' AS is_stale
 FROM (SELECT DISTINCT ON (interface_id) * FROM telemetry.interface_samples
       ORDER BY interface_id,observed_at DESC) latest;
CREATE OR REPLACE VIEW telemetry.latest_probes AS
 SELECT *, clock_timestamp()-observed_at > interval '30 seconds' AS is_stale
 FROM (SELECT DISTINCT ON (device_id) * FROM telemetry.probes
       ORDER BY device_id,observed_at DESC) latest;
CREATE OR REPLACE VIEW telemetry.latest_polls AS
 SELECT *, clock_timestamp()-observed_at > interval '90 seconds' AS is_stale
 FROM (SELECT DISTINCT ON (device_id) * FROM telemetry.polls
       ORDER BY device_id,observed_at DESC) latest;
