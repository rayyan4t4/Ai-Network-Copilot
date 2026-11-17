"""Offline integrity and scoring check for the published research release."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evaluation.freeze import verify
from evaluation.protocol import score

def main():
    manifest=verify();schedule=json.loads((ROOT/'research/control/final-schedule.json').read_text())
    expected=json.loads((ROOT/'research/results.json').read_text());checks=[]
    for approach in ['B1','B2','no_gate','full']:
        roots=abstentions=errors=0
        for case in schedule:
            r=json.loads((ROOT/'research/final'/case['case_id']/(approach+'.json')).read_text())
            s=score(case,r);roots+=bool(s['exact_root_correct']);abstentions+=bool(s['correct_abstention']);errors+=bool(s['error'])
        counts=expected['metrics'][approach]['counts']
        assert (roots,abstentions,errors)==(counts.get('exact_root_correct',0),counts.get('correct_abstention',0),counts.get('error',0)),approach
        checks.append({'approach':approach,'exact_roots':roots,'correct_abstentions':abstentions,'errors':errors})
    provenance=json.loads((ROOT/'research/migration-provenance.json').read_text())
    raw=[r for r in provenance['files'] if r['release'].startswith('research/final/')]
    assert len(raw)==490
    assert all(hashlib.sha256((ROOT/r['release']).read_bytes()).hexdigest()==r['source_sha256'] for r in raw)
    print('PASS release source lock:',len(manifest['sha256']),'files')
    print('PASS unchanged final study files:',len(raw),'— 70 cases, 280 approach outputs')
    print(json.dumps(checks,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
