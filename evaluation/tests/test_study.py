import copy,json,unittest
from pathlib import Path
from evaluation.engine import evaluate_gate,MATRIX,ospf_mode
from evaluation.protocol import mask,packet,score,prediction
from evaluation.model import request,SCHEMA
ROOT=Path(__file__).resolve().parents[2]
class StudyTests(unittest.TestCase):
    def test_each_critical_signal_blocks(self):
        for kind,spec in MATRIX['faults'].items():
            signals={k:['real-evidence'] for k in spec if k!='critical'}
            self.assertEqual(evaluate_gate(kind,signals)['status'],'sufficient')
            for critical in spec['critical']:
                missing=copy.deepcopy(signals);missing[critical]=[]
                self.assertEqual(evaluate_gate(kind,missing)['status'],'inconclusive')
    def test_contradiction_blocks(self):
        s={k:['x'] for k in MATRIX['faults']['interface_shutdown'] if k!='critical'}
        self.assertEqual(evaluate_gate('interface_shutdown',s,['conflict'])['status'],'inconclusive')
    def test_mask_leaves_original_unchanged(self):
        b={'events':[{'id':1}],'snapshots':[],'interfaces':[],'samples':[]}
        m=mask(b,'interface_shutdown');self.assertEqual(m['events'],[]);self.assertEqual(len(b['events']),1)
    def test_acl_mask_preserves_latest_only(self):
        b={'snapshots':[{'device_id':'A','observed_at':'2026-01-01'},{'device_id':'A','observed_at':'2026-02-01'}]}
        self.assertEqual(mask(b,'acl_fault')['snapshots'][0]['observed_at'],'2026-02-01')
    def test_ospf_reference_parsing(self):
        def s(text):return {'raw':{'frr_configuration':{'exit_code':0,'stdout':text}}}
        self.assertEqual(ospf_mode(s('router ospf\n passive-interface default\n no passive-interface eth0'),'eth0'),'active')
        self.assertEqual(ospf_mode(s('router ospf\n passive-interface eth0'),'eth0'),'passive')
        self.assertIsNone(ospf_mode({},'eth0'))
        self.assertEqual(ospf_mode(s('interface eth0\n no ip ospf passive\nexit\nrouter ospf\n passive-interface default'),'eth0'),'active')
    def test_approaches_share_model_input(self):
        p={'as_of':'now','facts':[],'candidates':[],'health_counts':{},'devices':['R-B1']}
        self.assertEqual(request(p,'full'),request(p,'no_gate'))
    def test_model_schema_does_not_force_candidate(self):
        self.assertIn('acl_fault',SCHEMA['properties']['fault_class']['enum']);self.assertNotIn('enum',SCHEMA['properties']['device_id'])
    def test_fault_abstention_wrong(self):
        t={'category':'ospf_loss','underlying_class':'ospf_loss','device_id':'R-B1','interface':'eth0'}
        self.assertFalse(score(t,{'status':'ok','prediction':prediction('inconclusive')})['exact_root_correct'])
    def test_error_not_correct_abstention(self):
        t={'category':'insufficient','underlying_class':'ospf_loss','device_id':'R-B1','interface':'eth0'}
        self.assertFalse(score(t,{'status':'provider_error'})['correct_abstention'])
    def test_exact_interface_required(self):
        t={'category':'ospf_loss','underlying_class':'ospf_loss','device_id':'R-B1','interface':'eth0'}
        self.assertFalse(score(t,{'status':'ok','prediction':prediction('ospf_loss','R-B1','eth1')})['exact_root_correct'])
    def test_healthy_error_accounted(self):
        t={'category':'healthy','underlying_class':'healthy','device_id':'','interface':''}
        self.assertTrue(score(t,{'status':'provider_error'})['detection_fp'])
    def test_live_pilot_missing_event_abstains(self):
        paths=list((ROOT/'research/pilot').glob('*/observations.json'))
        found=False
        for path in paths:
            b=json.loads(path.read_text());p=packet(b)
            if p['primary'] and p['primary']['fault_class']=='interface_shutdown' and not b['events']:
                found=True;self.assertEqual(p['primary']['gate']['status'],'inconclusive')
        self.assertTrue(found)
if __name__=='__main__':unittest.main()
