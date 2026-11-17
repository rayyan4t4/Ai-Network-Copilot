"""Post-study live bridge; slow snapshots cannot block telemetry publication.

The frozen export/analysis/lifecycle/persistence cycle is reused unchanged.
Snapshot observations keep their original times; existing freshness rules apply.
"""
import json
import logging
import math
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from lab_runtime import Lab
from capture_network_snapshot import capture
from copilot.worker import STATE, cycle, atomic


def settings():
    p = STATE / 'runtime-settings.json'
    return json.loads(p.read_text()) if p.exists() else {}


def snapshot_once():
    lab = Lab()
    try:
        lab.load()
        lab.connect()
        observations = capture(lab, tolerate_errors=True)
        lab.upload_node('MON-HQ', '/opt/copilot/console-snapshots-async.json', json.dumps(observations))
        lab.inside('MON-HQ', 'python3 /opt/copilot/import_snapshots.py /opt/copilot/console-snapshots-async.json\n')
    finally:
        lab.close()


def export_once():
    lab = Lab()
    try:
        lab.load()
        lab.connect()
        # Infinity disables only the frozen cycle's inline snapshot branch.
        # Export, analysis, lifecycle and persistence still run unchanged.
        cycle(lab, last_snapshot=math.inf)
    finally:
        lab.close()


def export_failed():
    path = STATE / 'state.json'
    if path.exists():
        state = json.loads(path.read_text(encoding='utf-8'))
        state['bridge'] = {'status': 'error', 'updated_at': datetime.now(timezone.utc).isoformat(),
                          'error': 'Lab export unavailable; displayed observations may be stale.'}
        atomic(path, state)


class LiveBridge:
    def __init__(self, snapshot_job=snapshot_once, export_job=export_once,
                 on_export_error=export_failed, configuration=settings, record=None):
        self.snapshot_job, self.export_job = snapshot_job, export_job
        self.on_export_error, self.configuration = on_export_error, configuration
        self.record = record or self.record_timing

    @staticmethod
    def record_timing(phase, duration, success):
        # Two threads append separate records; a shared lock prevents interleaving.
        with _timing_lock, (STATE / 'bridge-timings.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'phase': phase,
                               'duration_seconds': round(duration, 3), 'success': success}) + '\n')

    def perform(self, phase, job):
        began, success = time.monotonic(), False
        try:
            job()
            success = True
        except Exception as error:
            logging.error('%s cycle failed: %s', phase, type(error).__name__)
            if phase == 'export':
                self.on_export_error()
        finally:
            self.record(phase, time.monotonic() - began, success)

    def snapshots(self, stop):
        while not stop.is_set():
            self.perform('snapshot', self.snapshot_job)
            stop.wait(self.configuration().get('snapshot_interval_seconds', 45))

    def run(self, stop):
        thread = threading.Thread(target=self.snapshots, args=(stop,), daemon=True, name='readonly-snapshots')
        thread.start()
        try:
            while not stop.is_set():
                self.perform('export', self.export_job)
                stop.wait(self.configuration().get('export_interval_seconds', 10))
        finally:
            stop.set()
            thread.join(timeout=1)


_timing_lock = threading.Lock()
if __name__ == '__main__':
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    LiveBridge().run(stop)
