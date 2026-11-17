"""Shared control helpers for this project's existing GNS3 lab only."""
import json
import shlex
import time
from gns3_api import ROOT, VM, api, make_ssh_client
import paramiko

class Lab:
    def __init__(self):
        self.manifest=json.loads((ROOT/'.local/deployment.json').read_text())
        self.pid=self.manifest['project_id']
        self.nodes={}
        self.client=None
    def load(self):
        try: project=api('/projects/'+self.pid)
        except RuntimeError:
            path=self.manifest['project_path']+'\\'+self.manifest['project_filename']
            project=api('/projects/load','POST',{'path':path})
        if project['status']!='opened':api('/projects/'+self.pid+'/open','POST')
        self.refresh()
    def refresh(self):
        self.nodes={n['name']:n for n in api(f'/projects/{self.pid}/nodes')}
    def connect(self):
        self.client=make_ssh_client()
        return self
    def run(self,command,text=None,check=True,timeout=180):
        i,o,e=self.client.exec_command(command,timeout=timeout)
        if text is not None:i.write(text);i.flush();i.channel.shutdown_write()
        out=o.read().decode(errors='replace');err=e.read().decode(errors='replace')
        code=o.channel.recv_exit_status()
        if code and check:raise RuntimeError(f'Guest command failed ({code}): {out}\n{err}')
        return code,out,err
    def inside(self,name,script,check=True,timeout=180):
        cid=self.nodes[name]['properties']['container_id']
        return self.run('sudo -n docker exec -i '+shlex.quote(cid)+' /bin/bash -s',script,check,timeout)
    def upload_guest(self,path,data,mode=0o600):
        s=self.client.open_sftp()
        with s.file(path,'wb') as f:f.write(data.encode() if isinstance(data,str) else data)
        s.chmod(path,mode);s.close()
    def upload_node(self,name,path,data,mode=0o600):
        # Stream into the selected container; never print file contents.
        cid=self.nodes[name]['properties']['container_id']
        self.run('sudo -n docker exec -i '+shlex.quote(cid)+' /bin/sh -c '+shlex.quote('umask 077; cat >'+path),data)
        self.run('sudo -n docker exec '+shlex.quote(cid)+' chmod '+oct(mode)[2:]+' '+shlex.quote(path))
    def start(self):
        order={'wan':0,'router':1,'mls':2,'access1':3,'access2':3,'monitor':4,'host':5}
        for name in sorted(self.nodes,key=lambda n:order[self.manifest['nodes'][n]['role']]):
            if self.nodes[name]['status']!='started':
                api(f'/projects/{self.pid}/nodes/{self.nodes[name]["node_id"]}/start','POST')
                print('Started '+name,flush=True)
        self.refresh()
    def close(self):
        if self.client:self.client.close()

if __name__=='__main__':
    lab=Lab();lab.load();lab.start()
    print('Nodes started:',sum(n['status']=='started' for n in lab.nodes.values()),flush=True)
