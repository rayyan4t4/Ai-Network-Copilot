# Setup and operation

## Recorded-study mode

From the repository root, run `python app.py replay` and open http://127.0.0.1:8766. This starts the archived-result viewer only. It does not simulate current healthy timestamps, connect to GNS3 or call Gemini. Stop it before starting another viewer on the same port.

## Host and VM prerequisites

The tested control host is Windows with GNS3 2.2.61, VMware Workstation and Python 3.12. The GNS3 VM must expose its Docker-capable GNS3 API and SSH on its host-only interface. The reference VM address was 192.168.157.128; use your actual address. The host controller normally runs at http://127.0.0.1:3080/v2. Controller authentication is read from your local GNS3 configuration, or from `GNS3_API_USER`, `GNS3_API_PASSWORD` and `GNS3_API_URL`.

Create `.venv` and install `requirements.txt`. The monitor image contains Python, psycopg2 and PostgreSQL; these guest dependencies are different from the host SSH dependencies. No local language-model runtime or extra VM is required.

## Configure SSH trust and private settings

Keep private configuration under `.local`, which Git ignores. Copy `config.example.json` to `.local/lab.json`, set the VM address/user, and supply a VM password locally or through `GNS3_VM_PASSWORD`. An SSH key path may be supplied as `vm_key_file` instead. Never commit this file or API keys.

The automation uses strict known-host checking. Create `.local/known_hosts` only after comparing the VM's SSH host-key fingerprint against a trusted VM-console observation. You may collect a candidate with `ssh-keyscan`, then inspect it with `ssh-keygen -lf`; collecting a key alone does not establish its identity. Copy an existing previously verified entry when adopting the same VM.

## Option A: adopt an existing matching lab

For the original configured laptop, private configuration and deployment identity have already been migrated. Run `start.ps1` from this folder.

On another configured machine with the matching 30-node topology, use:

```powershell
.\.venv\Scripts\python.exe scripts/configure.py --vm-host YOUR_VM_IP --project-id YOUR_PROJECT_UUID --known-hosts PATH_TO_VERIFIED_KNOWN_HOSTS
.\.venv\Scripts\python.exe scripts/deploy_application.py
.\start.ps1
```

The configuration script checks the node names and saves actual controller paths/IDs privately. It requests the VM password through a hidden prompt. `deploy_application.py` adds the read-only export and incident schema without resetting existing observations. Do not run the full topology builder over a different existing lab.

## Option B: provision a fresh lab

After configuring the VM connection and verified host key, run these host commands in order:

```powershell
.\.venv\Scripts\python.exe scripts/build_images.py
.\.venv\Scripts\python.exe scripts/build_topology.py
.\.venv\Scripts\python.exe scripts/provision_monitoring.py
.\.venv\Scripts\python.exe scripts/deploy_application.py
.\start.ps1
```

The image builder runs Docker builds inside the existing GNS3 VM. It builds `fyp-network-node:1.0` and then `fyp-monitor:1.0`. Debian package repositories are used during fresh builds; later repository contents can differ from the original study binaries. The original tested images remain private backup archives; image identities are documented in the reference provenance. The release aliases on the original machine refer to the same tested image IDs.

Reference configuration examples are under `lab/configs`. Freshly generated inventory and node files are written under ignored `.local/topology` and `.local/configs`, so setup does not overwrite the published research reference.

The topology builder creates four sites, 30 nodes and 33 links; generates a private SNMP community; wires ports; and provisions persistent node scripts. The separate monitor provisioner installs collector code, inventory, PostgreSQL schema and operational migrations. All builds require an appropriate isolated laboratory environment. The included `network.gns3` is a wiring template, not a complete backup with stored volumes.

For a separate new controlled experiment, the profile setup script defines the declared telemetry cadence and WAN capacity. It is not required merely to view archived data. New acquisitions must use a separately identified research run; do not overwrite the published final dataset, reset its attempt ledger or present new model responses as original observations.

## Normal startup and checks

`start.ps1` checks actual VM containers against controller state and refuses ambiguous partial recovery. It starts the bridge, dashboard and study viewer in hidden windows, reusing matching instances. It refuses occupied application ports rather than silently replacing unrelated processes. Private service IDs and logs are under `.local`.

Open http://127.0.0.1:8765. A healthy baseline is 30/30 healthy, zero active incidents and a changing observation timestamp. Select a device in the topology or evidence filter, then a record to inspect its raw observation. A stale banner means current status is unknown; do not interpret it as healthy.

Use `python app.py status` for a current status check and `python app.py verify --live` for network, telemetry and freshness checks. A complete cold start may require two minutes for routing and monitoring to converge. The two-minute observation is a bounded availability check, not a guarantee against future sleep or overload.

## Gemini and data sharing

Archived results do not require an API key. For new investigations, place your own key in ignored `.local/gemini-key.txt`. Do not put it in source, screenshots or committed environment files. Rotate a key if it has been disclosed elsewhere.

Only after approving normalized incident summaries being sent to Google's Gemini API, create `.local/runtime/provider-consent.json` containing:

```json
{"normalized_incident_summaries_to_google": true}
```

The request projection includes normalized lab names, interfaces, evidence IDs, timestamps, topology context, gate information and curated guidance. IP addresses, raw logs, device configurations, lab credentials and injection ground truth are excluded. A consent file is a local authorization record; do not create it for another operator without their approval.

The recorded study used `gemini-3.5-flash-lite`; availability depends on your provider account. Live manual requests have a separate six-attempt daily bound. Billing settings are not changed. Automatic requests remain paused by default via `.local/runtime/evaluation-active.json`; the **Request investigation** button may request a new interpretation for an active sufficient incident. Do not equate archived success with a new key/provider check.

## Demonstrate a controlled fault

Use an isolated lab. In the **R-B1** GNS3 console, `ip link set eth0 down` creates a branch-uplink outage. Watch the live incident and its evidence. After the demonstration, restore it with `ip link set eth0 up`, allow routing/monitoring to converge and confirm 30/30 healthy again. This is new demonstration activity, not one of the archived 70 cases.

Do not run the full experiment harness for an ordinary viva. Archived examples are enough to compare approaches without repeated interventions or provider calls. Practice feedback must be marked as demonstration/QA data, not independent research judgments.

## Stop and recover

`stop.ps1` stops only saved services whose command paths match this repository. It leaves GNS3, PostgreSQL and the collector running. Shut down the network/VM separately, using a clean database and node shutdown when backing up. Private project and database backups include credentials and observations; keep them outside Git.

If port 8765/8766 is occupied, stop the correct earlier application instance first. If the VM address changes, update ignored local configuration. If SSH identity changes, verify its fingerprint before updating trust. If state is stale, inspect `.local/runtime/bridge-error.log`, VM reachability and collector/database status. Export failures remain visible; timestamp/freshness thresholds are not relaxed to hide them.

The local backend is deliberately not internet-facing. Production deployment needs a separate security and operations design.
