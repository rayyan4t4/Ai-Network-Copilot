import json,unittest
from pathlib import Path
from copilot.provider import build_request
class LiveMatrixAdapterTests(unittest.TestCase):
    def test_study_candidate_requires_updated_critical_signals(self):
        package={'fault_class':'ospf_loss','device_id':'R-B1','interface':'eth0','affected_devices':[],'topology_path':[],
          'as_of':'2026-11-17T00:00:00+00:00','gate':{'matrix_version':'study-final-1'},'facts':[]}
        req=build_request(package)
        self.assertIn('configuration_change',req['critical_signal_names'])
        package['gate']['matrix_version']='pilot-1';legacy=build_request(package)
        self.assertNotIn('configuration_change',legacy['critical_signal_names'])
if __name__=='__main__':unittest.main()
