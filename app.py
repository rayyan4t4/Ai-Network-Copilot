"""Project entry point: recorded study, tests, live status and verification."""
import argparse,json,runpy,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['replay','test','status','verify'])
    p.add_argument('--live',action='store_true',help='Include the connected GNS3 network and telemetry checks')
    args=p.parse_args()
    if args.command=='replay':
        print('Recorded study: http://127.0.0.1:8766 — archived observations; no VM or API key needed.',flush=True)
        runpy.run_module('evaluation.service',run_name='__main__');return 0
    if args.command=='test':
        suites=['collector/tests','copilot/tests','evaluation/tests','live/tests','tests']
        return max(subprocess.run([sys.executable,'-m','unittest','discover','-s',s,'-v'],cwd=ROOT).returncode for s in suites)
    if args.command=='status':
        with urllib.request.urlopen('http://127.0.0.1:8765/api/state',timeout=15) as reply:s=json.load(reply)
        print(json.dumps({'as_of':s.get('as_of'),'healthy':sum(h['state']=='healthy' for h in s.get('health',[])),
          'nodes':len(s.get('health',[])),'stale':s.get('is_stale',True),'age_seconds':s.get('observation_age_seconds'),
          'bridge':s.get('bridge'),'automatic_AI':s.get('provider',{}).get('automatic_diagnosis')},indent=2))
        return 0 if not s.get('is_stale',True) and len(s.get('health',[]))==30 and all(h['state']=='healthy' for h in s['health']) else 1
    scripts=['scripts/verify_release.py']
    if args.live:scripts+=['scripts/verify_network.py','scripts/verify_telemetry.py','scripts/check_freshness.py']
    for script in scripts:
        rc=subprocess.run([sys.executable,script],cwd=ROOT).returncode
        if rc:return rc
    return 0
if __name__=='__main__':raise SystemExit(main())
