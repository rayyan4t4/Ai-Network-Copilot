#!/bin/bash
set -eu
PGDATA=/var/lib/postgresql/fyp/data
mkdir -p /run/postgresql "$PGDATA" /var/log/fyp
chown postgres:postgres /run/postgresql
# GNS3 archive extraction can change file ownership; restore the database's
# expected owner before starting an existing cluster as well as a fresh one.
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"
if ! test -s "$PGDATA/PG_VERSION"; then
  runuser -u postgres -- /usr/lib/postgresql/15/bin/initdb -D "$PGDATA" --auth-local=peer --auth-host=scram-sha-256 --encoding=UTF8 --locale=C.UTF-8
fi
cat >"$PGDATA/copilot.conf" <<'PGCONF'
listen_addresses = ''
unix_socket_directories = '/run/postgresql'
shared_buffers = '32MB'
work_mem = '2MB'
maintenance_work_mem = '16MB'
max_connections = 12
max_wal_size = '128MB'
min_wal_size = '32MB'
timezone = 'UTC'
PGCONF
if ! grep -q "include = 'copilot.conf'" "$PGDATA/postgresql.conf"; then
  printf "\ninclude = 'copilot.conf'\n" >>"$PGDATA/postgresql.conf"
fi
touch /var/log/fyp/postgresql.log
chown postgres:postgres /var/log/fyp/postgresql.log
if ! pg_isready -q -h /run/postgresql; then
  runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D "$PGDATA" -l /var/log/fyp/postgresql.log -w -t 45 start
fi
runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -h /run/postgresql -d postgres <<'SQL'
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='root') THEN
  CREATE ROLE root LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
 END IF;
END $$;
SQL
if ! runuser -u postgres -- psql -X -h /run/postgresql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='copilot'" | grep -qx 1; then
  runuser -u postgres -- createdb -h /run/postgresql -O root copilot
fi
psql -X -v ON_ERROR_STOP=1 -h /run/postgresql -U root -d copilot -f /opt/copilot/schema.sql
# Post-study operational migrations are separate from frozen diagnostic code.
for migration in /opt/copilot/migrations/*.sql; do
  test -f "$migration" || continue
  psql -X -v ON_ERROR_STOP=1 -h /run/postgresql -U root -d copilot -f "$migration"
done
python3 /opt/copilot/collector.py inventory
supervisor_pid=$(pgrep -f '^/bin/bash /opt/copilot/supervise.sh$' | head -n 1 || true)
if test -z "$supervisor_pid"; then
  nohup /bin/bash /opt/copilot/supervise.sh >>/var/log/fyp/collector.log 2>&1 </dev/null &
  echo $! >/run/copilot-supervisor.pid
else
  echo "$supervisor_pid" >/run/copilot-supervisor.pid
fi
echo 'PostgreSQL and telemetry supervisor started.'
if test -f /opt/copilot/app/bootstrap.sh; then
  /bin/bash /opt/copilot/app/bootstrap.sh
fi
