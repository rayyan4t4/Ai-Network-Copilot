#!/bin/bash
set -eu
id -u copilot_reader >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin copilot_reader
runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -h /run/postgresql -d copilot <<'SQL'
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='copilot_reader') THEN
  CREATE ROLE copilot_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 2;
 END IF;
END $$;
GRANT CONNECT ON DATABASE copilot TO copilot_reader;
GRANT USAGE ON SCHEMA inventory,telemetry,operations TO copilot_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA inventory,telemetry TO copilot_reader;
GRANT SELECT ON operations.heartbeats TO copilot_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE root IN SCHEMA inventory,telemetry GRANT SELECT ON TABLES TO copilot_reader;
ALTER ROLE copilot_reader SET default_transaction_read_only=on;
ALTER ROLE copilot_reader SET statement_timeout='10s';
SQL
psql -X -v ON_ERROR_STOP=1 -h /run/postgresql -U root -d copilot -f /opt/copilot/app/schema.sql
