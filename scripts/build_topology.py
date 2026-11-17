"""Build and provision the authorized four-site topology without touching old labs."""
import json
import secrets
import shlex
from gns3_api import api, ROOT, VM, make_ssh_client
from topology_model import NAME, IMAGE, NODES, LINKS, save_model
from node_configs import config
import paramiko

save_model()
secret_path=ROOT/'.local/lab-secrets.json'
if not secret_path.exists(): secret_path.write_text(json.dumps({'snmp_community':secrets.token_hex(16)}))
community=json.loads(secret_path.read_text())['snmp_community']
compute=next(c for c in api('/computes') if c.get('host')==VM and c['connected'])
project=next((p for p in api('/projects') if p['name']==NAME),None)
if project is None: project=api('/projects','POST',{'name':NAME,'auto_close':False})
pid=project['project_id']
if project.get('status')!='opened': api(f'/projects/{pid}/open','POST')
nodes={n['name']:n for n in api(f'/projects/{pid}/nodes')}
boot="/bin/bash -c 'if test -f /etc/fyp/node.sh; then /bin/bash /etc/fyp/node.sh >> /etc/fyp/boot.log 2>&1; fi; exec /bin/bash'"
symbols={'router':':/symbols/router.svg','mls':':/symbols/multilayer_switch.svg','access1':':/symbols/ethernet_switch.svg','access2':':/symbols/ethernet_switch.svg','wan':':/symbols/ethernet_switch.svg','host':':/symbols/computer.svg','monitor':':/symbols/server.svg'}
for name,spec in NODES.items():
    if name not in nodes:
        nodes[name]=api(f'/projects/{pid}/nodes','POST',{
            'name':name,'node_type':'docker','compute_id':compute['compute_id'],
            'x':spec['x'],'y':spec['y'],'symbol':symbols[spec['role']],
            'properties':{'image':spec.get('image',IMAGE),'adapters':spec['adapters'],'start_command':boot,'extra_volumes':['/etc/fyp']+(['/var/log/fyp','/var/lib/postgresql/fyp','/opt/copilot'] if spec['role']=='monitor' else [])},
            'console_type':'telnet','console_auto_start':False})
        print('Created '+name,flush=True)
    else:
        assert nodes[name]['properties']['image']==spec.get('image',IMAGE), 'Existing node image differs; refusing to replace it.'
current_links=api(f'/projects/{pid}/links')
def key(endpoints):
    return frozenset((n['node_id'],n['adapter_number'],n['port_number']) for n in endpoints)
existing={key(l['nodes']) for l in current_links}
for link in LINKS:
    ends=[{'node_id':nodes[link['a']]['node_id'],'adapter_number':link['a_port'],'port_number':0},
          {'node_id':nodes[link['b']]['node_id'],'adapter_number':link['b_port'],'port_number':0}]
    if key(ends) not in existing: api(f'/projects/{pid}/links','POST',{'nodes':ends})
manifest={'name':NAME,'project_id':pid,'compute_id':compute['compute_id'],'vm_host':VM,'image':IMAGE,
          'nodes':{name:{'node_id':n['node_id'],**NODES[name]} for name,n in nodes.items()},'links':LINKS}
project_detail=api('/projects/'+pid)
manifest.update(project_path=project_detail['path'],project_filename=project_detail.get('filename',NAME+'.gns3'))
(ROOT/'.local/deployment.json').write_text(json.dumps(manifest,indent=2))
print(f'Wiring complete: {len(nodes)} nodes, {len(LINKS)} links.',flush=True)
macs={name:n['properties']['mac_address'] for name,n in nodes.items()}
configdir=ROOT/'.local/configs';configdir.mkdir(parents=True,exist_ok=True)
client=make_ssh_client()
logs=[]
def run(command, text=None):
    stdin,stdout,stderr=client.exec_command(command,timeout=100)
    if text is not None: stdin.write(text);stdin.flush();stdin.channel.shutdown_write()
    out=stdout.read().decode(errors='replace');err=stderr.read().decode(errors='replace')
    code=stdout.channel.recv_exit_status()
    if code: raise RuntimeError(f'{command}: {code}\n{out}\n{err}')
    return out+err
def upload(cid,path,text):
    run('sudo -n docker exec -i '+shlex.quote(cid)+' /bin/sh -c '+shlex.quote('umask 077; cat >'+path),text)
order={'wan':0,'router':1,'mls':2,'access1':3,'access2':3,'monitor':4,'host':5}
try:
    for name in sorted(nodes,key=lambda n:order[NODES[n]['role']]):
        n=api(f'/projects/{pid}/nodes/{nodes[name]["node_id"]}')
        if n['status']!='started': api(f'/projects/{pid}/nodes/{n["node_id"]}/start','POST')
        n=api(f'/projects/{pid}/nodes/{n["node_id"]}')
        cid=n['properties']['container_id']
        run('sudo -n docker exec '+shlex.quote(cid)+' mkdir -p /etc/fyp')
        text=config(NODES[name],macs)
        (configdir/(name+'.sh')).write_text(text)
        upload(cid,'/etc/fyp/secrets.sh','SNMP_COMMUNITY='+shlex.quote(community)+'\n')
        upload(cid,'/etc/fyp/node.sh',text)
        output=run('sudo -n docker exec '+shlex.quote(cid)+' /bin/bash /etc/fyp/node.sh')
        logs.append({'node':name,'output':output,'configured':True})
        print('Configured '+name,flush=True)
    final=api(f'/projects/{pid}/nodes')
    manifest['nodes']={n['name']:{**manifest['nodes'][n['name']], 'container_id':n['properties']['container_id'],'console':n['console'],'status':n['status'],'mac_address':n['properties']['mac_address']} for n in final}
    (ROOT/'.local/deployment.json').write_text(json.dumps(manifest,indent=2))
    print('FULL_TOPOLOGY_PROVISIONED',flush=True)
finally:
    dest=ROOT/'docs/verification/network';dest.mkdir(parents=True,exist_ok=True)
    (dest/'provisioning.json').write_text(json.dumps(logs,indent=2))
    client.close()
