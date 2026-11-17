"""Reconcile a stale controller only when every lab container is absent.

Does not restore data, modify experimental records, or issue provider requests.
Partial loss is deliberately left for inspection rather than closing live nodes.
"""
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from gns3_api import ROOT, VM, api
from lab_runtime import Lab


def reconciliation_needed(nodes, running_ids, all_ids, remote_projects, project_id):
    if any(n['status'] == 'started' and not n['properties'].get('container_id') for n in nodes):
        raise RuntimeError('Started node has no container identity; inspect before recovery.')
    expected = {n['properties'].get('container_id') for n in nodes
                if n['status'] == 'started'} - {None, ''}
    if not expected or expected <= running_ids:
        return False
    if expected & all_ids or project_id in remote_projects:
        raise RuntimeError('Partially available lab or remote project: inspect before recovery; no live project was closed.')
    return True


def main():
    lab = Lab()
    lab.load()
    lab.connect()
    try:
        _, output, _ = lab.run("sudo -n docker ps -a --no-trunc --format '{{.ID}} {{.State}}'")
        states = dict(line.split() for line in output.splitlines() if line.strip())
        with urllib.request.urlopen('http://' + VM + '/v2/projects', timeout=10) as reply:
            remote = {p['project_id'] for p in json.load(reply)}
        needed = reconciliation_needed(list(lab.nodes.values()),
                    {i for i, state in states.items() if state == 'running'},
                    set(states), remote, lab.pid)
        receipt = {'recorded_at': datetime.now(timezone.utc).isoformat(),
                   'project_id': lab.pid, 'controller_reconciled': needed,
                   'scope': 'Startup control only. No frozen diagnostic source or final study record changed.'}
        if needed:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup = ROOT / '.local/recovery' / ('startup-' + stamp)
            backup.mkdir(parents=True, exist_ok=False)
            project = api('/projects/' + lab.pid)
            shutil.copytree(Path(project['path']), backup / 'controller-project')
            (backup / 'nodes.json').write_text(json.dumps(list(lab.nodes.values()), indent=2))
            api('/projects/' + lab.pid + '/close', 'POST')
            lab.load()
            if any(n['status'] != 'stopped' for n in lab.nodes.values()):
                raise RuntimeError('Reload did not yield stopped nodes; refusing further automatic recovery.')
            receipt['backup'] = str(backup.relative_to(ROOT))
            print('Reopened stale controller project; existing persistent files retained.')
        target = ROOT / '.local/runtime/startup-check.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2))
        print('Controller/container startup consistency check passed.')
    finally:
        lab.close()


if __name__ == '__main__':
    main()
