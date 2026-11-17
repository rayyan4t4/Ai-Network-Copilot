import math
import threading
import unittest
from unittest.mock import Mock, patch
from live.worker import LiveBridge, export_once


class LiveBridgeTests(unittest.TestCase):
    def test_slow_snapshot_does_not_block_export(self):
        entered, release, exported, stop = (threading.Event() for _ in range(4))
        def snapshot():
            entered.set()
            release.wait(3)
        def export():
            self.assertTrue(entered.wait(1))
            exported.set()
            stop.set()
        bridge = LiveBridge(snapshot, export, configuration=lambda: {}, record=Mock())
        runner = threading.Thread(target=bridge.run, args=(stop,))
        runner.start()
        try:
            self.assertTrue(exported.wait(1), 'Export waited for the blocked snapshot')
            self.assertFalse(release.is_set())
        finally:
            release.set()
            stop.set()
            runner.join(2)
        self.assertFalse(runner.is_alive())

    def test_snapshot_failure_does_not_mark_telemetry_unavailable(self):
        unavailable, timing = Mock(), Mock()
        bridge = LiveBridge(on_export_error=unavailable, record=timing)
        bridge.perform('snapshot', Mock(side_effect=TimeoutError()))
        unavailable.assert_not_called()
        self.assertFalse(timing.call_args.args[2])

    def test_export_failure_still_marks_bridge_unavailable(self):
        unavailable = Mock()
        bridge = LiveBridge(on_export_error=unavailable, record=Mock())
        bridge.perform('export', Mock(side_effect=TimeoutError()))
        unavailable.assert_called_once()

    def test_export_reuses_frozen_cycle_without_inline_snapshots(self):
        with patch('live.worker.Lab') as lab, patch('live.worker.cycle') as frozen:
            export_once()
            frozen.assert_called_once_with(lab.return_value, last_snapshot=math.inf)
            lab.return_value.close.assert_called_once()

    def test_export_connection_closes_after_failure(self):
        with patch('live.worker.Lab') as lab, patch('live.worker.cycle', side_effect=RuntimeError()):
            with self.assertRaises(RuntimeError):
                export_once()
            lab.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
