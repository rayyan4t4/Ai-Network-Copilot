"""Check that repository organization preserves the recorded diagnostic inputs."""
import json,unittest
from pathlib import Path
from evaluation.protocol import packet,b1
from evaluation.model import request
ROOT=Path(__file__).resolve().parents[1]

class MigrationTests(unittest.TestCase):
    def test_all_recorded_model_inputs_unchanged(self):
        checked=0
        for case in (ROOT/'research/final').iterdir():
            bundle=json.loads((case/'observations.json').read_text())
            package=packet(bundle)
            for approach in ['B2','no_gate','full']:
                archived=json.loads((case/(approach+'.json')).read_text())
                if archived.get('request'):
                    with self.subTest(case=case.name,approach=approach):
                        self.assertEqual(request(package,approach),archived['request'])
                    checked+=1
        self.assertGreater(checked,100)

    def test_direct_baseline_predictions_unchanged(self):
        checked=0
        for case in (ROOT/'research/final').iterdir():
            bundle=json.loads((case/'observations.json').read_text())
            archived=json.loads((case/'B1.json').read_text())
            with self.subTest(case=case.name):self.assertEqual(b1(bundle),archived['prediction'])
            checked+=1
        self.assertEqual(checked,70)

if __name__=='__main__':unittest.main()
