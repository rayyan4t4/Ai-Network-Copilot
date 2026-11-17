"""Observe real live API freshness; never change its timestamps or thresholds."""
import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sample():
    began = time.monotonic()
    with urllib.request.urlopen('http://127.0.0.1:8765/api/state', timeout=15) as reply:
        state = json.load(reply)
    return {'at': datetime.now(timezone.utc).isoformat(), 'as_of': state['as_of'],
            'age_seconds': state['observation_age_seconds'], 'stale': state['is_stale'],
            'healthy': sum(d['state'] == 'healthy' for d in state['health']),
            'nodes': len(state['health']), 'bridge_status': state['bridge']['status'],
            'request_seconds': round(time.monotonic() - began, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=120)
    args = parser.parse_args()
    rows = []
    deadline = time.monotonic() + args.seconds
    while True:
        try:
            rows.append(sample())
        except Exception as error:
            rows.append({'at': datetime.now(timezone.utc).isoformat(), 'error_type': type(error).__name__})
        if time.monotonic() >= deadline:
            break
        time.sleep(2)
    versions = {r['as_of'] for r in rows if 'as_of' in r}
    passed = len(versions) >= 5 and all(not r.get('error_type') and not r['stale'] and
             r['healthy'] == r['nodes'] == 30 and r['bridge_status'] == 'ok' for r in rows)
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'passed': passed,
              'observation_seconds': args.seconds, 'distinct_exports': len(versions), 'samples': rows,
              'max_observation_age_seconds': max((r.get('age_seconds', 0) for r in rows), default=None),
              'scope': 'API freshness observation only, not browser rendering, human review or incident-to-display latency. Existing 45-second freshness rule unchanged.'}
    (ROOT / 'docs/verification/live/bridge-freshness.json').write_text(json.dumps(report, indent=2))
    print('Freshness observation:', passed, 'samples', len(rows), 'distinct exports', len(versions), 'maximum age', report['max_observation_age_seconds'])
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
