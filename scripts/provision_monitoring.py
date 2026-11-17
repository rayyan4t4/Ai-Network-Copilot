"""Provision MON-HQ's persistent monitoring sources and private configuration."""
import json
from pathlib import Path
from gns3_api import ROOT,api
from lab_runtime import Lab
from topology_model import NODES,save_model
from node_configs import config

lab=Lab();lab.load();lab.connect()
try:
    node=lab.nodes['MON-HQ']
    if node['properties']['image']!='fyp-monitor:1.0':
        raise RuntimeError('MON-HQ must be created with fyp-monitor:1.0; GNS3 cannot change a Docker image in place.')
    if node['status']=='started':api(f'/projects/{lab.pid}/nodes/{node["node_id"]}/stop','POST')
    api(f'/projects/{lab.pid}/nodes/{node["node_id"]}','PUT',{'properties':{
        'extra_volumes':['/etc/fyp','/var/log/fyp','/var/lib/postgresql/fyp','/opt/copilot']}})
    api(f'/projects/{lab.pid}/nodes/{node["node_id"]}/start','POST');lab.refresh()
    lab.inside('MON-HQ','mkdir -p /opt/copilot /etc/fyp /var/log/fyp\n')
    for path in (ROOT/'collector').iterdir():
        if path.is_file() and path.suffix in ('.py','.sh','.sql','.conf'):
            lab.upload_node('MON-HQ','/opt/copilot/'+path.name,path.read_text(),0o755 if path.suffix=='.sh' else 0o644)
    lab.inside('MON-HQ','mkdir -p /opt/copilot/migrations\n')
    for path in (ROOT/'collector/migrations').glob('*.sql'):
        lab.upload_node('MON-HQ','/opt/copilot/migrations/'+path.name,path.read_text(),0o644)
    save_model()
    lab.upload_node('MON-HQ','/opt/copilot/inventory.json',(ROOT/'.local/topology/inventory.json').read_text(),0o644)
    cfg=json.loads((ROOT/'collector/config.example.json').read_text())
    cfg['snmp_community']=json.loads((ROOT/'.local/lab-secrets.json').read_text())['snmp_community']
    lab.upload_node('MON-HQ','/etc/fyp/collector.json',json.dumps(cfg,indent=2))
    text=config(NODES['MON-HQ'],{})
    (ROOT/'.local/configs').mkdir(parents=True,exist_ok=True)
    (ROOT/'.local/configs/MON-HQ.sh').write_text(text)
    lab.upload_node('MON-HQ','/etc/fyp/node.sh',text)
    _,out,err=lab.inside('MON-HQ','pkill -TERM -x rsyslogd || true\nsleep 1\n/bin/bash /etc/fyp/node.sh\n')
    print(out,flush=True)
    if err:print(err,flush=True)
    manifest=lab.manifest
    for name,n in lab.nodes.items():manifest['nodes'][name].update({'container_id':n['properties']['container_id'],'status':n['status'],'image':n['properties']['image']})
    (ROOT/'.local/deployment.json').write_text(json.dumps(manifest,indent=2))
    print('Monitoring node provisioned.',flush=True)
finally:lab.close()
