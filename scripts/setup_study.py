"""Install the measured study cadence and common WAN capacity baseline."""
import json
import time
from datetime import datetime,timezone
from gns3_api import ROOT
from lab_runtime import Lab

profile=json.loads((ROOT/'evaluation/profile.json').read_text())
lab=Lab();lab.load();lab.connect()
try:
    control=ROOT/'.local/evaluation/control';control.mkdir(parents=True,exist_ok=True)
    if not (control/'maintenance.json').exists():
        _,state,_=lab.run('systemctl is-active apt-daily-upgrade.timer',check=False)
        (control/'maintenance.json').write_text(json.dumps({'upgrade_timer_was_active':state.strip()=='active'},indent=2))
    _,active,_=lab.run('systemctl show apt-daily-upgrade.service -p ActiveState --value')
    if active.strip() in ('active','activating','deactivating'):raise RuntimeError('Guest package maintenance must finish before study setup')
    lab.run('sudo -n systemctl stop apt-daily-upgrade.timer')
    print('Scheduled upgrade timer temporarily paused for the controlled measurement window.',flush=True)
    _,text,_=lab.inside('MON-HQ','cat /etc/fyp/collector.json\n')
    cfg=json.loads(text)
    private=ROOT/'.local/backups/profile/collector-before-study.json';private.parent.mkdir(parents=True,exist_ok=True)
    if not private.exists():private.write_text(text)
    cfg.update(poll_interval_seconds=profile['poll_interval_seconds'],probe_interval_seconds=profile['probe_interval_seconds'])
    cfg['capacity_overrides_bps']={f'R-B{i}:eth1':profile['effective_wan_capacity_bps'] for i in (1,2,3)}
    lab.upload_node('MON-HQ','/etc/fyp/collector.json',json.dumps(cfg,indent=2))
    lab.inside('MON-HQ','kill -TERM "$(cat /run/copilot-collector.pid)"\n')
    for i in (1,2,3):
        name=f'R-B{i}'
        command='tc qdisc replace dev eth1 root tbf rate 2mbit burst 32kb latency 100ms'
        lab.inside(name,command+'\n')
        path=ROOT/'.local/configs'/f'{name}.sh'
        script=path.read_text()
        if '# Study capacity baseline' not in script:
            script+='\n# Study capacity baseline\n'+command+'\n'
            path.write_text(script)
        lab.upload_node(name,'/etc/fyp/node.sh',script,0o755)
    lab.inside('R-HQ','''if ! test -f /run/fyp-eval-iperf.pid || ! kill -0 "$(cat /run/fyp-eval-iperf.pid)" 2>/dev/null; then
 iperf3 -s -D --pidfile /run/fyp-eval-iperf.pid
fi
''')
    (ROOT/'.local/runtime/runtime-settings.json').write_text(json.dumps({'engine':'evaluation','snapshot_interval_seconds':profile['snapshot_interval_seconds'],'export_interval_seconds':profile['export_interval_seconds']},indent=2))
    (ROOT/'.local/verification/study/study-profile.json').write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'profile':profile,
      'scope':'Same capacity and telemetry cadence apply to healthy, fault and insufficient-evidence cases; no label-dependent instrumentation.'},indent=2))
    print('Configured all three branch WANs at 2 Mbps and telemetry at 10/3/15 seconds.',flush=True)
finally:lab.close()
