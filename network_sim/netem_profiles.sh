#!/usr/bin/env bash
# ==============================================================================
# Network Variability Simulation Tool (Linux Traffic Control & Netem)
#
# Simulates dynamic IoT edge wireless conditions (4G LTE, 3G HSDPA, 2G Edge,
# High Latency Satellite, and Congested Dropouts) on Raspberry Pi or Cloud VM.
#
# Usage:
#   sudo ./network_sim/netem_profiles.sh [profile_name] [interface]
#
# Available Profiles:
#   normal / reset   - Clears all traffic control rules (full wire speed)
#   4g_lte           - 15 Mbps rate, 35ms RTT (+-5ms jitter), 0.1% loss
#   3g_hsdpa         - 2.0 Mbps rate, 90ms RTT (+-15ms jitter), 0.5% loss
#   2g_edge          - 150 kbps rate, 250ms RTT (+-40ms jitter), 1.5% loss
#   satellite        - 600 kbps rate, 650ms RTT (+-50ms jitter), 2.0% loss
#   congested        - 50 kbps rate, 450ms RTT (+-100ms jitter), 8.0% loss
#   packet_loss      - 10% packet drop rate
#   high_jitter      - 120ms RTT (+-80ms jitter)
#   status / show    - Displays active qdisc configuration
# ==============================================================================

set -euo pipefail

PROFILE="${1:-status}"
IFACE="${2:-eth0}"

# Auto-detect wireless interface if default eth0 does not exist
if ! ip link show "$IFACE" >/dev/null 2>&1; then
    IFACE=$(ip -br link | awk '$1 !~ "lo" {print $1; exit}')
    IFACE="${IFACE:-wlan0}"
fi

function clear_rules() {
    echo "[NETEM] Clearing traffic control qdisc on interface ${IFACE}..."
    sudo tc qdisc del dev "${IFACE}" root 2>/dev/null || true
}

function show_status() {
    echo "=== Active Traffic Control Rules (${IFACE}) ==="
    tc qdisc show dev "${IFACE}"
}

case "${PROFILE}" in
    normal|reset|clear)
        clear_rules
        echo "[NETEM] Wire link restored to unthrottled baseline."
        ;;

    4g_lte)
        clear_rules
        echo "[NETEM] Applying 4G LTE Profile (15 Mbps, 35ms latency, 0.1% loss)..."
        sudo tc qdisc add dev "${IFACE}" root handle 1: netem delay 35ms 5ms loss 0.1%
        sudo tc qdisc add dev "${IFACE}" parent 1: handle 10: tbf rate 15mbit burst 32kbit latency 400ms
        ;;

    3g_hsdpa)
        clear_rules
        echo "[NETEM] Applying 3G HSDPA Profile (2.0 Mbps, 90ms latency, 0.5% loss)..."
        sudo tc qdisc add dev "${IFACE}" root handle 1: netem delay 90ms 15ms loss 0.5%
        sudo tc qdisc add dev "${IFACE}" parent 1: handle 10: tbf rate 2mbit burst 16kbit latency 400ms
        ;;

    2g_edge)
        clear_rules
        echo "[NETEM] Applying 2G Edge Profile (150 kbps, 250ms latency, 1.5% loss)..."
        sudo tc qdisc add dev "${IFACE}" root handle 1: netem delay 250ms 40ms loss 1.5%
        sudo tc qdisc add dev "${IFACE}" parent 1: handle 10: tbf rate 150kbit burst 8kbit latency 600ms
        ;;

    satellite)
        clear_rules
        echo "[NETEM] Applying Satellite Link Profile (600 kbps, 650ms latency, 2.0% loss)..."
        sudo tc qdisc add dev "${IFACE}" root handle 1: netem delay 650ms 50ms loss 2.0%
        sudo tc qdisc add dev "${IFACE}" parent 1: handle 10: tbf rate 600kbit burst 12kbit latency 1200ms
        ;;

    congested)
        clear_rules
        echo "[NETEM] Applying Critical Congestion Profile (50 kbps, 450ms latency, 8.0% loss)..."
        sudo tc qdisc add dev "${IFACE}" root handle 1: netem delay 450ms 100ms loss 8.0%
        sudo tc qdisc add dev "${IFACE}" parent 1: handle 10: tbf rate 50kbit burst 4kbit latency 1000ms
        ;;

    packet_loss)
        clear_rules
        echo "[NETEM] Applying 10% Random Packet Loss Profile..."
        sudo tc qdisc add dev "${IFACE}" root netem loss 10%
        ;;

    high_jitter)
        clear_rules
        echo "[NETEM] Applying High Jitter Profile (120ms +-80ms)..."
        sudo tc qdisc add dev "${IFACE}" root netem delay 120ms 80ms distribution normal
        ;;

    status|show)
        show_status
        exit 0
        ;;

    *)
        echo "Error: Unknown profile '${PROFILE}'."
        echo "Available options: normal, 4g_lte, 3g_hsdpa, 2g_edge, satellite, congested, packet_loss, high_jitter, status"
        exit 1
        ;;
esac

echo "[NETEM] Profile applied successfully."
show_status
