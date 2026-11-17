import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
"""Safety cases for startup recovery, without a real controller or Docker."""
import unittest
from check_lab_startup import reconciliation_needed


class StartupSafety(unittest.TestCase):
    def nodes(self, *ids):
        return [{'status': 'started', 'properties': {'container_id': i}} for i in ids]

    def test_healthy_lab_is_untouched(self):
        self.assertFalse(reconciliation_needed(self.nodes('a', 'b'), {'a', 'b'}, {'a', 'b'}, {'p'}, 'p'))

    def test_complete_stale_state_can_reconcile(self):
        self.assertTrue(reconciliation_needed(self.nodes('a', 'b'), set(), {'unrelated'}, set(), 'p'))

    def test_partial_loss_never_closes_live_lab(self):
        with self.assertRaises(RuntimeError):
            reconciliation_needed(self.nodes('a', 'b'), {'a'}, {'a'}, set(), 'p')

    def test_existing_stopped_container_is_preserved(self):
        with self.assertRaises(RuntimeError):
            reconciliation_needed(self.nodes('a'), set(), {'a'}, set(), 'p')

    def test_remote_project_is_preserved(self):
        with self.assertRaises(RuntimeError):
            reconciliation_needed(self.nodes('a'), set(), set(), {'p'}, 'p')

    def test_normally_stopped_nodes_need_no_reconciliation(self):
        self.assertFalse(reconciliation_needed([{'status': 'stopped', 'properties': {}}], set(), set(), set(), 'p'))

    def test_unknown_identity_never_triggers_recovery(self):
        with self.assertRaises(RuntimeError):
            reconciliation_needed(self.nodes(None), set(), set(), set(), 'p')


if __name__ == '__main__':
    unittest.main()
