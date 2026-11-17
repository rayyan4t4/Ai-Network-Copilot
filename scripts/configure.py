"""Adopt an existing matching GNS3 lab; write only ignored local configuration."""
import argparse,getpass,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--vm-host',required=True);p.add_argument('--project-id',required=True)
    p.add_argument('--known-hosts',type=Path,required=True,help='Previously verified OpenSSH known_hosts file')
    a=p.parse_args();local=ROOT/'.local';local.mkdir(exist_ok=True)
    if not a.known_hosts.is_file():raise SystemExit('Verified known_hosts file not found.')
    cfg={'vm_host':a.vm_host,'vm_username':input('VM SSH username [gns3]: ').strip() or 'gns3',
         'vm_password':getpass.getpass('VM SSH password (saved only under ignored .local): '),
         'controller_url':'http://127.0.0.1:3080/v2'}
    (local/'lab.json').write_text(json.dumps(cfg,indent=2))
    if a.known_hosts.resolve()!=(local/'known_hosts').resolve():shutil.copy2(a.known_hosts,local/'known_hosts')
    from gns3_api import api
    from topology_model import NODES,LINKS,NAME,IMAGE
    project=api('/projects/'+a.project_id);nodes=api('/projects/'+a.project_id+'/nodes')
    actual={n['name']:n for n in nodes}
    if set(actual)!=set(NODES):raise SystemExit('Project does not match the expected 30-node topology; no deployment adopted.')
    manifest={'name':NAME,'project_id':a.project_id,'compute_id':nodes[0]['compute_id'],'vm_host':a.vm_host,'image':IMAGE,
              'project_path':project['path'],'project_filename':project.get('filename',NAME+'.gns3'),
              'nodes':{name:{**spec,'node_id':actual[name]['node_id']} for name,spec in NODES.items()},'links':LINKS}
    (local/'deployment.json').write_text(json.dumps(manifest,indent=2))
    runtime=local/'runtime';runtime.mkdir(exist_ok=True)
    (runtime/'runtime-settings.json').write_text(json.dumps({'engine':'evaluation','snapshot_interval_seconds':15,'export_interval_seconds':3}))
    (runtime/'evaluation-active.json').write_text(json.dumps({'active':True}))
    (local/'python-path.txt').write_text(sys.executable)
    print('Configured existing lab. Cloud consent/key are separate; automatic AI stays paused. See docs/setup.md.')
if __name__=='__main__':main()
