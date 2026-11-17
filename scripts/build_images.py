"""Build the two open-source lab images in the configured GNS3 VM."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from gns3_api import make_ssh_client

def main():
    client=make_ssh_client()
    try:
        def run(command):
            _,out,err=client.exec_command(command,timeout=1800)
            text=out.read().decode();error=err.read().decode();code=out.channel.recv_exit_status()
            if code:raise RuntimeError('Image build failed: '+error[-1500:])
            print(text[-1200:])
        guest='/opt/gns3/projects/copilot-image-build';run('mkdir -p '+guest)
        s=client.open_sftp()
        try:
            for name in ['Dockerfile','Dockerfile.monitor']:s.put(str(ROOT/'lab/images/network-node'/name),guest+'/'+name)
        finally:s.close()
        run('sudo -n docker build -t fyp-network-node:1.0 -f '+guest+'/Dockerfile '+guest+' >'+guest+'/network-build.log 2>&1')
        run('sudo -n docker build -t fyp-monitor:1.0 -f '+guest+'/Dockerfile.monitor '+guest+' >'+guest+'/monitor-build.log 2>&1')
        print('Built fyp-network-node:1.0 and fyp-monitor:1.0. Logs remain in '+guest)
    finally:client.close()
if __name__=='__main__':main()
