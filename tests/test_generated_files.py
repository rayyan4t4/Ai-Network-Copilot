import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import topology_model

class GeneratedFilesTests(unittest.TestCase):
    def test_generated_topology_does_not_rewrite_reference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);reference=root/'lab/topology/inventory.json'
            reference.parent.mkdir(parents=True);reference.write_text('REFERENCE')
            with patch.object(topology_model,'ROOT',root):topology_model.save_model()
            self.assertEqual(reference.read_text(),'REFERENCE')
            generated=json.loads((root/'.local/topology/inventory.json').read_text())
            self.assertEqual(len(generated['nodes']),30)
            self.assertEqual(len(generated['links']),33)

if __name__=='__main__':unittest.main()
