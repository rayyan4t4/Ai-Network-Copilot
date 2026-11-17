CREATE SCHEMA IF NOT EXISTS incidents;
CREATE TABLE IF NOT EXISTS incidents.records (
 incident_id uuid PRIMARY KEY, fingerprint text NOT NULL, opened_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL, resolved_at timestamptz, state text NOT NULL,
 fault_class text NOT NULL, device_id text NOT NULL REFERENCES inventory.devices,
 interface_name text, package jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents.diagnoses (
 diagnosis_id uuid PRIMARY KEY, incident_id uuid NOT NULL REFERENCES incidents.records,
 recorded_at timestamptz NOT NULL, model text, model_version text, status text NOT NULL,
 prompt_hash text, request jsonb NOT NULL, response jsonb NOT NULL,
 validation jsonb NOT NULL, latency_ms integer, usage jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS incidents.rules_applied (
 incident_id uuid NOT NULL REFERENCES incidents.records, evidence_digest text NOT NULL,
 recorded_at timestamptz NOT NULL, rules jsonb NOT NULL,
 PRIMARY KEY(incident_id,evidence_digest)
);
ALTER TABLE incidents.diagnoses ADD COLUMN IF NOT EXISTS evidence_package jsonb NOT NULL DEFAULT '{}';
ALTER TABLE incidents.diagnoses ADD COLUMN IF NOT EXISTS audit jsonb NOT NULL DEFAULT '{}';
