"""Local GNS3 inspection and bootstrap helpers. Credentials are never printed."""
import configparser
import json
import os
from pathlib import Path
import sys
import urllib.request
import base64
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / '.local' / 'lab.json'
CONFIG = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
sys.path.insert(0, CONFIG.get('python_libraries', str(ROOT / '.local' / 'python')))
VM = os.environ.get('GNS3_VM_HOST', CONFIG.get('vm_host', '192.168.157.128'))

def make_ssh_client():
    import paramiko
    client = paramiko.SSHClient()
    client.load_host_keys(str(ROOT / '.local' / 'known_hosts'))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    password = os.environ.get('GNS3_VM_PASSWORD', CONFIG.get('vm_password'))
    key = CONFIG.get('vm_key_file')
    if not password and not key:
        raise RuntimeError('Configure a VM password or SSH key in ignored .local/lab.json or GNS3_VM_PASSWORD.')
    client.connect(VM, username=CONFIG.get('vm_username', 'gns3'), password=password,
                   key_filename=key, look_for_keys=False, allow_agent=False, timeout=15)
    return client

def api_request(path, method='GET', data=None):
    cfg = configparser.ConfigParser(interpolation=None)
    default_config = Path(os.environ.get('APPDATA', str(Path.home()/'.config'))) / 'GNS3/2.2/gns3_server.ini'
    cfg.read(CONFIG.get('controller_config', str(default_config)))
    user = os.environ.get('GNS3_API_USER', cfg.get('Server', 'user', fallback=''))
    password = os.environ.get('GNS3_API_PASSWORD', cfg.get('Server', 'password', fallback=''))
    auth = base64.b64encode(f'{user}:{password}'.encode()).decode()
    return urllib.request.Request(os.environ.get('GNS3_API_URL', CONFIG.get('controller_url', 'http://127.0.0.1:3080/v2')).rstrip('/') + path,
        data=None if data is None else json.dumps(data).encode(), method=method,
        headers={'Authorization': 'Basic ' + auth, 'Content-Type':'application/json'})
def api(path, method='GET', data=None):
    req=api_request(path,method,data)
    try:
        with urllib.request.urlopen(req, timeout=25) as reply:
            body = reply.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'GNS3 {error.code}: {error.read().decode()}') from None

def safe_compute(c):
    return {k:c.get(k) for k in ('compute_id','name','host','port','connected','last_error','cpu_usage_percent','memory_usage_percent')}

def ssh(command):
    client = make_ssh_client()
    _, out, err = client.exec_command(command, timeout=180)
    print(out.read().decode(errors='replace'))
    errors = err.read().decode(errors='replace')
    if errors: print(errors, file=sys.stderr)
    status = out.channel.recv_exit_status()
    client.close()
    return status

if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'status':
        print(json.dumps([safe_compute(c) for c in api('/computes')], indent=2))
    elif action == 'connect':
        before = next(c for c in api('/computes') if c['compute_id'] == 'vm')
        backup = ROOT / '.local' / 'vm_compute_before.json'
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists(): backup.write_text(json.dumps(before, indent=2))
        existing = next((c for c in api('/computes') if c.get('host') == VM and c.get('port') == 80), None)
        result = existing or api('/computes', 'POST', {'name':'FYP GNS3 VM Direct','host':VM,'port':80,'protocol':'http'})
        print(json.dumps(safe_compute(result), indent=2))
    elif action == 'inspect-guest':
        sys.exit(ssh('free -m; df -h / /opt/gns3; nproc; docker version --format "{{.Server.Version}}"; docker images --format "{{.Repository}}:{{.Tag}}"; command -v ovs-vsctl; ls /lib/modules/$(uname -r)/kernel/net/openvswitch 2>/dev/null; ip -br addr'))
    elif action == 'guest-file':
        command = Path(sys.argv[2]).read_text()
        sys.exit(ssh(command))
