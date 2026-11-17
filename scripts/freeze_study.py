"""One-time preregistration after pilots, before final observations."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from run_study import save,schedule,now
from evaluation.protocol import packet,mask,CLASSES
from evaluation.engine import analyze
out=ROOT/'research/freeze.json'
if out.exists():raise RuntimeError('Already frozen; do not replace the preregistration')
checks=[]
for kind in CLASSES+['healthy','insufficient']:
    matches=[]
    for ctl in (ROOT/'.local/evaluation/control/pilot').glob('*.json'):
        if '.attempts.' in ctl.name:continue
        truth=json.loads(ctl.read_text())
        if truth['category']!=kind or not truth.get('complete'):continue
        b=json.loads((ROOT/'research/pilot'/truth['case_id']/'observations.json').read_text());p=packet(b)
        valid=(p['primary'] is None) if kind=='healthy' else bool(p['primary'] and p['primary']['fault_class']==truth['underlying_class'] and p['primary']['gate']['status']==('inconclusive' if kind=='insufficient' else 'sufficient'))
        if valid:matches.append(truth['case_id'])
    checks.append({'category':kind,'valid_live_pilot_ids':matches,'passed':bool(matches)})
    if not matches:raise RuntimeError('No valid pilot for '+kind)
for kind in CLASSES:
    truth=next(json.loads(p.read_text()) for p in (ROOT/'.local/evaluation/control/pilot').glob('*.json') if '.attempts.' not in p.name and json.loads(p.read_text()).get('category')==kind and json.loads(p.read_text()).get('complete') and packet(json.loads((ROOT/'research/pilot'/json.loads(p.read_text())['case_id']/'observations.json').read_text()))['primary']['gate']['status']=='sufficient')
    b=json.loads((ROOT/'research/pilot'/truth['case_id']/'original.json').read_text());p=packet(mask(b,kind));passed=bool(p['primary'] and p['primary']['gate']['status']=='inconclusive')
    checks.append({'mask_for':kind,'passed':passed})
    if not passed:raise RuntimeError('Mask does not produce insufficiency: '+kind)
test=subprocess.run([sys.executable,'-m','unittest','discover','-s','evaluation/tests','-v'],cwd=ROOT,capture_output=True,text=True)
save(ROOT/'.local/verification/study/test-results.json',{'passed':test.returncode==0,'output':test.stdout+test.stderr,'at':now()})
if test.returncode:raise RuntimeError('Tests failed')
schedule_path=ROOT/'.local/evaluation/control/final-schedule.json';save(schedule_path,schedule())
for name in ('matrix','profile'):
    p=ROOT/'evaluation'/f'{name}.json';data=json.loads(p.read_text());data['version']='study-final-1'
    if name=='matrix':data['frozen_for_final_trials']=True
    save(p,data)
paths=['evaluation/engine.py','evaluation/protocol.py','evaluation/model.py','evaluation/freeze.py','evaluation/matrix.json','evaluation/profile.json','evaluation/baseline.json','evaluation/methods.md','scripts/run_study.py','scripts/compare_study.py','scripts/analyze_study.py','copilot/knowledge.json','copilot/monitor_export.py','copilot/worker.py','collector/collector.py','.local/evaluation/control/final-schedule.json']
paths += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'lab/configs').glob('*.sh')]
save(out,{'frozen_at':now(),'seed':20261117,'cases':70,'approaches':['B1','B2','no_gate','full'],'pilot_checks':checks,'sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in paths},'ground_truth_location':'Private control directory, excluded from diagnostic adapters','reviewers':'Two real independent human reviewers required; not supplied by agents','browser_display_latency':'Unverified after browser origin access rejection; no synthetic acknowledgements'})
print('FROZEN',out,'checks',len(checks))
