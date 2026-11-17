#!/bin/bash
set -u
child=''
trap 'if test -n "$child"; then kill -TERM "$child" 2>/dev/null || true; wait "$child" || true; fi; exit 0' TERM INT
while true; do
  python3 -u /opt/copilot/collector.py run &
  child=$!
  echo "$child" >/run/copilot-collector.pid
  wait "$child"
  echo "$(date -u +%FT%TZ) Collector exited with status $?; restarting in 3 seconds"
  sleep 3
done
