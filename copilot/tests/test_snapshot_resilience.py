import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from capture_network_snapshot import capture

class FakeLab:
    manifest={'nodes':{'R-B1':{'role':'router'},'R-B2':{'role':'router'}}}
    def inside(self,name,script):
        if name=='R-B1':raise RuntimeError('node unavailable')
        return 0,json.dumps({'observed_at':'2026-11-16T19:00:00+00:00','raw':{'addresses':{'exit_code':0,'stdout':'[]'}}}),''

class SnapshotResilienceTests(unittest.TestCase):
    def test_one_unavailable_node_does_not_hide_other_snapshots(self):
        rows=capture(FakeLab(),tolerate_errors=True)
        self.assertEqual(len(rows),2);self.assertIn('collection_error',rows[0]['raw']);self.assertIn('addresses',rows[1]['raw'])
    def test_explicit_strict_capture_still_reports_failure(self):
        with self.assertRaises(RuntimeError):capture(FakeLab())

if __name__=='__main__':unittest.main()
