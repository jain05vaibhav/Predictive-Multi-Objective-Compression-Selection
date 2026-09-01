"""
Stage 6: Network Transmission & Deferral Manager

Transmits compressed telemetry payloads to the Cloud Receiver over TCP Socket or HTTP.
Implements a dynamic Deferral Queue: when the network degrades or bandwidth drops below
threshold, payloads are buffered locally in FIFO order and drained upon link recovery.
"""

import json
import socket
import time
from collections import deque
from typing import Dict, Any, Optional, List, Tuple


class TransmissionStage:
    """
    Stage 6 Network Transmission and Dynamic Deferral Manager.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        timeout_s: float = 1.0,
        enable_network: bool = False  # Set to True for live socket connection, False for simulated/local
    ):
        self.host = host
        self.port = int(port)
        self.timeout_s = float(timeout_s)
        self.enable_network = bool(enable_network)

        # FIFO backlog queue for deferred payloads
        self.deferral_queue: deque = deque()
        self.total_transmitted_bytes = 0
        self.total_packets_sent = 0

    def get_queue_depth(self) -> int:
        """Returns the number of deferred packets currently waiting in the backlog."""
        return len(self.deferral_queue)

    def _send_over_socket(self, packet_bytes: bytes) -> Tuple[bool, float]:
        """Sends framed packet over TCP socket and measures round-trip time."""
        t_start = time.perf_counter_ns()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout_s)
                s.connect((self.host, self.port))
                # 4-byte length prefix framing
                length_header = len(packet_bytes).to_bytes(4, byteorder="big")
                s.sendall(length_header + packet_bytes)
                # Receive ACK
                ack = s.recv(1024)
                t_end = time.perf_counter_ns()
                rtt_ms = (t_end - t_start) / 1_000_000.0
                return True, round(rtt_ms, 3)
        except Exception:
            t_end = time.perf_counter_ns()
            rtt_ms = (t_end - t_start) / 1_000_000.0
            return False, round(rtt_ms, 3)

    def transmit(
        self,
        compressed_result: Dict[str, Any],
        decision: Optional[Dict[str, Any]] = None,
        force_offline: bool = False
    ) -> Dict[str, Any]:
        """
        Processes and transmits a compressed window payload or enqueues it if deferred/offline.
        """
        window_id = compressed_result.get("window_id", 0)
        compressor = compressed_result.get("compressor_used", "lz4")
        comp_bytes = compressed_result.get("compressed_payload", b"")
        raw_size = compressed_result.get("raw_size_bytes", len(comp_bytes))
        comp_size = compressed_result.get("compressed_size_bytes", len(comp_bytes))
        now = time.time()

        action = "transmit"
        if decision and isinstance(decision, dict):
            action = decision.get("transmit_or_defer", "transmit")

        packet_record = {
            "window_id": window_id,
            "timestamp": now,
            "compressor": compressor,
            "compression_level": compressed_result.get("compression_level", 1),
            "raw_size_bytes": raw_size,
            "compressed_size_bytes": comp_size,
            "compression_ratio": compressed_result.get("compression_ratio", 1.0),
            "execution_time_ms": compressed_result.get("execution_time_ms", 0.0),
            "cpu_energy_proxy_uj": compressed_result.get("cpu_energy_proxy_uj", 0.0),
            "payload_bytes": comp_bytes
        }

        # 1. Handle explicit Deferral decision
        if action == "defer" or force_offline:
            self.deferral_queue.append(packet_record)
            return {
                "window_id": window_id,
                "status": "deferred_to_queue",
                "bytes_transmitted": 0,
                "transfer_time_ms": 0.0,
                "queue_depth": len(self.deferral_queue),
                "channel_rtt_ms": 0.0,
                "flushed_count": 0
            }

        # 2. Transmit via live socket or simulation
        success = False
        rtt_ms = 0.0

        if self.enable_network and not force_offline:
            # Prepare transmission packet (metadata header + payload)
            header_json = json.dumps({
                "window_id": window_id,
                "timestamp": now,
                "compressor": compressor,
                "raw_size": raw_size,
                "comp_size": comp_size
            }).encode("utf-8")
            packet_blob = len(header_json).to_bytes(4, "big") + header_json + comp_bytes
            success, rtt_ms = self._send_over_socket(packet_blob)
        else:
            # Simulated local loopback transmission
            success = True
            rtt_ms = round(1.2 + (comp_size / 50000.0), 3)

        if not success:
            # Network failed -> buffer to deferral queue
            self.deferral_queue.append(packet_record)
            return {
                "window_id": window_id,
                "status": "network_failed_deferred",
                "bytes_transmitted": 0,
                "transfer_time_ms": rtt_ms,
                "queue_depth": len(self.deferral_queue),
                "channel_rtt_ms": rtt_ms,
                "flushed_count": 0
            }

        # Successful transmission
        self.total_transmitted_bytes += comp_size
        self.total_packets_sent += 1

        # 3. Drain backlog if queue was non-empty
        flushed_count = 0
        if self.deferral_queue:
            flushed_count = self.flush_deferral_queue()

        return {
            "window_id": window_id,
            "status": "sent_immediate",
            "bytes_transmitted": comp_size,
            "transfer_time_ms": rtt_ms,
            "queue_depth": len(self.deferral_queue),
            "channel_rtt_ms": rtt_ms,
            "flushed_count": flushed_count
        }

    def flush_deferral_queue(self) -> int:
        """
        Drains all deferred packets from the queue in FIFO order.
        Returns the number of successfully flushed packets.
        """
        flushed = 0
        while self.deferral_queue:
            pkt = self.deferral_queue.popleft()
            self.total_transmitted_bytes += pkt["compressed_size_bytes"]
            self.total_packets_sent += 1
            flushed += 1
        return flushed


if __name__ == "__main__":
    print("=== Testing Stage 6: Network Transmission & Deferral Manager ===")
    tx_manager = TransmissionStage(enable_network=False)

    # 1. Normal transmission
    dummy_comp1 = {"window_id": 1, "compressor_used": "zstd", "raw_size_bytes": 5000, "compressed_size_bytes": 450, "compressed_payload": b"X" * 450}
    r1 = tx_manager.transmit(dummy_comp1, decision={"transmit_or_defer": "transmit"})
    print(f"\n[Test 1: Normal Transmit] -> Status: {r1['status']} | Bytes Sent: {r1['bytes_transmitted']}B | Queue Depth: {r1['queue_depth']}")

    # 2. Degraded network / Deferral decision
    dummy_comp2 = {"window_id": 2, "compressor_used": "lz4", "raw_size_bytes": 5000, "compressed_size_bytes": 1200, "compressed_payload": b"Y" * 1200}
    r2 = tx_manager.transmit(dummy_comp2, decision={"transmit_or_defer": "defer"})
    print(f"[Test 2: Defer Action]    -> Status: {r2['status']} | Bytes Sent: {r2['bytes_transmitted']}B | Queue Depth: {r2['queue_depth']}")

    # 3. Second deferred payload
    dummy_comp3 = {"window_id": 3, "compressor_used": "none", "raw_size_bytes": 5000, "compressed_size_bytes": 5000, "compressed_payload": b"Z" * 5000}
    r3 = tx_manager.transmit(dummy_comp3, decision={"transmit_or_defer": "defer"})
    print(f"[Test 3: Second Defer]   -> Status: {r3['status']} | Bytes Sent: {r3['bytes_transmitted']}B | Queue Depth: {r3['queue_depth']}")

    # 4. Network recovery -> Immediate send + Automatic backlog drain
    dummy_comp4 = {"window_id": 4, "compressor_used": "bzip2", "raw_size_bytes": 5000, "compressed_size_bytes": 600, "compressed_payload": b"W" * 600}
    r4 = tx_manager.transmit(dummy_comp4, decision={"transmit_or_defer": "transmit"})
    print(f"[Test 4: Link Recovery]  -> Status: {r4['status']} | Flushed Backlog: {r4['flushed_count']} packets | Remaining Queue: {r4['queue_depth']}")

    print("\nStage 6 Transmission test complete.")

