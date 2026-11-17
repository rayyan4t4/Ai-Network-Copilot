# Physical port map

| Node A | Port | Node B | Port | Purpose |
| --- | --- | --- | --- | --- |
| R-HQ | eth1 | SW-WAN | eth0 | Shared OSPF WAN |
| R-HQ | eth0 | MLS-HQ | eth0 | Routed /30 uplink |
| MLS-HQ | eth1 | SW-HQ-1 | eth0 | LACP member 1 |
| MLS-HQ | eth2 | SW-HQ-1 | eth1 | LACP member 2 |
| MLS-HQ | eth3 | SW-HQ-2 | eth0 | VLAN trunk 10 20 30 |
| SW-HQ-1 | eth2 | PC-HQ-ADMIN | eth0 | Access VLAN 10 |
| SW-HQ-1 | eth3 | PC-HQ-STAFF | eth0 | Access VLAN 20 |
| SW-HQ-2 | eth1 | PC-HQ-IT | eth0 | Access VLAN 30 |
| R-B1 | eth1 | SW-WAN | eth1 | Shared OSPF WAN |
| R-B1 | eth0 | MLS-B1 | eth0 | Routed /30 uplink |
| MLS-B1 | eth1 | SW-B1-1 | eth0 | LACP member 1 |
| MLS-B1 | eth2 | SW-B1-1 | eth1 | LACP member 2 |
| MLS-B1 | eth3 | SW-B1-2 | eth0 | VLAN trunk 10 20 30 |
| SW-B1-1 | eth2 | PC-B1-ADMIN | eth0 | Access VLAN 10 |
| SW-B1-1 | eth3 | PC-B1-STAFF | eth0 | Access VLAN 20 |
| SW-B1-2 | eth1 | PC-B1-IT | eth0 | Access VLAN 30 |
| R-B2 | eth1 | SW-WAN | eth2 | Shared OSPF WAN |
| R-B2 | eth0 | MLS-B2 | eth0 | Routed /30 uplink |
| MLS-B2 | eth1 | SW-B2-1 | eth0 | LACP member 1 |
| MLS-B2 | eth2 | SW-B2-1 | eth1 | LACP member 2 |
| MLS-B2 | eth3 | SW-B2-2 | eth0 | VLAN trunk 10 20 30 |
| SW-B2-1 | eth2 | PC-B2-ADMIN | eth0 | Access VLAN 10 |
| SW-B2-1 | eth3 | PC-B2-STAFF | eth0 | Access VLAN 20 |
| SW-B2-2 | eth1 | PC-B2-IT | eth0 | Access VLAN 30 |
| R-B3 | eth1 | SW-WAN | eth3 | Shared OSPF WAN |
| R-B3 | eth0 | MLS-B3 | eth0 | Routed /30 uplink |
| MLS-B3 | eth1 | SW-B3-1 | eth0 | LACP member 1 |
| MLS-B3 | eth2 | SW-B3-1 | eth1 | LACP member 2 |
| MLS-B3 | eth3 | SW-B3-2 | eth0 | VLAN trunk 10 20 30 |
| SW-B3-1 | eth2 | PC-B3-ADMIN | eth0 | Access VLAN 10 |
| SW-B3-1 | eth3 | PC-B3-STAFF | eth0 | Access VLAN 20 |
| SW-B3-2 | eth1 | PC-B3-IT | eth0 | Access VLAN 30 |
| SW-HQ-2 | eth2 | MON-HQ | eth0 | Monitoring server VLAN 30 |
