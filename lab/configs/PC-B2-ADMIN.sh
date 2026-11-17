#!/bin/bash
set -eu
trap 'echo "BOOT_FAIL node=$HOSTNAME line=$LINENO command=$BASH_COMMAND" >&2' ERR
hostname PC-B2-ADMIN
source /etc/fyp/secrets.sh
for attempt in $(seq 1 15); do ip link show eth0 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth0 up
ip link set lo up
cat >/etc/fyp/dhcp-hook.sh <<'FYP_CONFIG'
#!/bin/sh
set -eu
case "$1" in
  deconfig) ip -4 addr flush dev "$interface" ;;
  bound|renew)
    ip -4 addr flush dev "$interface"
    ip addr add "$ip/24" dev "$interface"
    ip link set "$interface" up
    if [ -n "${router:-}" ]; then ip route replace default via "${router%% *}" dev "$interface"; fi
    printf '%s\n' "$ip" >/etc/fyp/lease-ip
    ;;
esac
FYP_CONFIG
chmod 755 /etc/fyp/dhcp-hook.sh
if ! pgrep -x udhcpc >/dev/null; then udhcpc -b -i eth0 -p /run/udhcpc.pid -s /etc/fyp/dhcp-hook.sh -t 5 -T 2; fi
