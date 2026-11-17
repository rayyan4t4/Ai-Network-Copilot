"""Record exact image/package versions, clock bounds and resource observations."""
import hashlib
import importlib.metadata
import json
import time
from datetime import datetime,timezone
from gns3_api import ROOT,api
from lab_runtime import Lab

lab=Lab();lab.load();lab.connect()
try:
    data={'recorded_at':datetime.now(timezone.utc).isoformat(),'gns3':api('/version')}
    _,images,_=lab.run("sudo -n docker image inspect fyp-network-node:1.0 fyp-monitor:1.0 --format '{{json .}}'")
    data['images']=[{k:obj[k] for k in ('Id','RepoTags','Created','Architecture','Os','Size')} for obj in map(json.loads,images.splitlines())]
    data['packages']={}
    for node in ('R-HQ','MON-HQ'):
        _,out,_=lab.inside(node,"dpkg-query -W -f='${binary:Package}\t${Version}\n'")
        data['packages'][node]=dict(line.split('\t',1) for line in out.splitlines())
    data['controller_python']={d.metadata['Name']:d.version for d in importlib.metadata.distributions(path=[str(ROOT/'.local/python')])}
    (ROOT/'collector/controller-requirements.lock.txt').write_text(''.join(f'{n}=={v}\n' for n,v in sorted(data['controller_python'].items())))
    _,out,_=lab.run('uname -a; python3 --version; sudo -n docker version --format "{{.Server.Version}}"; systemctl show gns3.service -p MainPID -p ActiveEnterTimestamp')
    data['guest_runtime']=out
    before=time.time();_,out,_=lab.run('date -u +%s.%N; timedatectl show -p NTPSynchronized');after=time.time()
    guest=float(out.splitlines()[0]);data['clock']={'controller_before_epoch':before,'controller_after_epoch':after,
      'guest_epoch':guest,'guest_minus_controller_midpoint_s':guest-(before+after)/2,'round_trip_s':after-before,'sync_status':out.splitlines()[1:]}
    _,out,_=lab.run("free -m; df -h /opt/gns3; sudo -n docker stats --no-stream --format '{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}'")
    data['resources']=out
    sources={}
    for folder in ('collector','scripts','lab/configs','lab/images'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    data['source_sha256']=sources
    dest=ROOT/'docs/verification/telemetry';dest.mkdir(parents=True,exist_ok=True)
    (dest/'environment-lock.json').write_text(json.dumps(data,indent=2))
    print('Recorded exact package/image versions and clock/resource bounds.',flush=True)
finally:lab.close()
