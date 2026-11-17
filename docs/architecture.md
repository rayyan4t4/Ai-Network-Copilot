# Architecture and topology diagrams

The diagrams describe the implemented lab. They are editable Mermaid source. Full topology ports and purposes come from the saved deployment manifest.

## Investigation pipeline

```mermaid
flowchart LR
 A[SNMP Syslog probes and read only snapshots] --> B[PostgreSQL source evidence]
 B --> C[Normalization and topology correlation]
 C --> D[Evidence sufficiency gate]
 D -->|sufficient| E[Normalized Gemini interpretation]
 D -->|missing critical evidence| F[Inconclusive and missing observations]
 E --> G[Dashboard and fixed read only checks]
 F --> G
 G --> H[Human feedback stored without learning]
```

The trusted injection harness is outside the diagnostic application. Ground truth is stored separately and does not enter correlation or model requests.

## Full GNS3 topology

```mermaid
flowchart TB
 n0["SW-WAN"]
 n1["R-HQ"]
 n2["MLS-HQ"]
 n3["SW-HQ-1"]
 n4["SW-HQ-2"]
 n5["PC-HQ-ADMIN"]
 n6["PC-HQ-STAFF"]
 n7["PC-HQ-IT"]
 n8["R-B1"]
 n9["MLS-B1"]
 n10["SW-B1-1"]
 n11["SW-B1-2"]
 n12["PC-B1-ADMIN"]
 n13["PC-B1-STAFF"]
 n14["PC-B1-IT"]
 n15["R-B2"]
 n16["MLS-B2"]
 n17["SW-B2-1"]
 n18["SW-B2-2"]
 n19["PC-B2-ADMIN"]
 n20["PC-B2-STAFF"]
 n21["PC-B2-IT"]
 n22["R-B3"]
 n23["MLS-B3"]
 n24["SW-B3-1"]
 n25["SW-B3-2"]
 n26["PC-B3-ADMIN"]
 n27["PC-B3-STAFF"]
 n28["PC-B3-IT"]
 n29["MON-HQ"]
 n1 ---|"eth1 to eth0"| n0
 n1 ---|"eth0 to eth0"| n2
 n2 ---|"eth1 to eth0"| n3
 n2 ---|"eth2 to eth1"| n3
 n2 ---|"eth3 to eth0"| n4
 n3 ---|"eth2 to eth0"| n5
 n3 ---|"eth3 to eth0"| n6
 n4 ---|"eth1 to eth0"| n7
 n8 ---|"eth1 to eth1"| n0
 n8 ---|"eth0 to eth0"| n9
 n9 ---|"eth1 to eth0"| n10
 n9 ---|"eth2 to eth1"| n10
 n9 ---|"eth3 to eth0"| n11
 n10 ---|"eth2 to eth0"| n12
 n10 ---|"eth3 to eth0"| n13
 n11 ---|"eth1 to eth0"| n14
 n15 ---|"eth1 to eth2"| n0
 n15 ---|"eth0 to eth0"| n16
 n16 ---|"eth1 to eth0"| n17
 n16 ---|"eth2 to eth1"| n17
 n16 ---|"eth3 to eth0"| n18
 n17 ---|"eth2 to eth0"| n19
 n17 ---|"eth3 to eth0"| n20
 n18 ---|"eth1 to eth0"| n21
 n22 ---|"eth1 to eth3"| n0
 n22 ---|"eth0 to eth0"| n23
 n23 ---|"eth1 to eth0"| n24
 n23 ---|"eth2 to eth1"| n24
 n23 ---|"eth3 to eth0"| n25
 n24 ---|"eth2 to eth0"| n26
 n24 ---|"eth3 to eth0"| n27
 n25 ---|"eth1 to eth0"| n28
 n4 ---|"eth2 to eth0"| n29
```

The paired uplinks form LACP. The WAN is a shared switched segment. Each site uses ADMIN, STAFF and IT VLANs, with expected policy blocks documented in the report.