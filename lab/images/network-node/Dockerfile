FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    frr frr-snmp snmpd snmp iproute2 iputils-ping \
    openvswitch-switch dnsmasq-base nftables rsyslog iperf3 procps \
    ca-certificates curl tcpdump udhcpc \
    && rm -rf /var/lib/apt/lists/*
CMD ["/bin/bash"]
