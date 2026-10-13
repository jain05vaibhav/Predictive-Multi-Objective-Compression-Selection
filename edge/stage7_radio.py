"""
Stage 7: Radio Duty-Cycle & Transmission Co-Scheduler (Objective O5)

Jointly schedules the wireless radio's sleep/wake duty cycle alongside the
transmit-now-or-defer decision produced by Stage 5:
- When transmitting: wakes radio, frames and sends payload over TCP socket,
  and measures radio wake-time and transmission latency.
- When deferring: enqueues payload in local FIFO queue and commands the radio
  transceiver to sleep for extended intervals, saving radio power.
- Receives Stage 8 closed-loop outcome log in the TCP ACK response to feed back
  into Stage 4 (calibration table) and Stage 5 (contextual bandit policy).
"""

import os
import json
import socket
import time
from collections import deque
from typing import Dict, Any, Optional, List, Tuple

from edge.config import RADIO_BASE_SLEEP_S, RADIO_DEFERRED_SLEEP_S


class RadioTransmissionStage:
    """
    Stage 7 Radio Duty-Cycle & Transmission Co-Scheduler (Objective O5).
    """

    RADIO_STATE_ACTIVE = "ACTIVE"
    RADIO_STATE_SLEEP = "SLEEP"

    # Radio power baseline on Raspberry Pi 3B+ (Broadcom BCM43438 WiFi/BLE chip)
    # Active TX/RX power ~ 800 mW; Sleep/Power-save mode ~ 50 mW
    RADIO_ACTIVE_POWER_MW = 800.0
    RADIO_SLEEP_POWER_MW = 50.0

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        timeout_s: float = 1.0,
        enable_network: bool = False
    ):
        self.host = host
        self.port = int(port)
        self.timeout_s = float(timeout_s)
        self.enable_network = bool(enable_network)

        # FIFO backlog queue for deferred payloads
        self.deferral_queue: deque = deque()
        self.total_transmitted_bytes = 0
        self.total_packets_sent = 0

        # Radio duty-cycle metrics (Objective O5)
        self.radio_state = self.RADIO_STATE_ACTIVE
        self.total_wake_time_ms = 0.0
        self.total_sleep_time_s = 0.0
        self.total_radio_energy_saved_uj = 0.0

        # Closed-loop feedback channel from Stage 8 Cloud Receiver
        self.latest_cloud_control: Dict[str, Any] = {}
        self.latest_outcome_log: Optional[Dict[str, Any]] = None

    def get_queue_depth(self) -> int:
        """Returns the number of deferred packets currently waiting in the backlog."""
        return len(self.deferral_queue)

    def _send_over_socket(self, packet_bytes: bytes) -> Tuple[bool, float, Optional[Dict[str, Any]]]:
        """
        Sends framed packet over TCP socket, measures latency, and parses Stage 8 feedback ACK.
        """
        t_start = time.perf_counter_ns()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout_s)
                s.connect((self.host, self.port))

                # 4-byte length prefix framing
                length_header = len(packet_bytes).to_bytes(4, byteorder="big")
                s.sendall(length_header + packet_bytes)

                # Receive Stage 8 Cloud Response (ACK + Outcome Log + Overrides)
                resp = s.recv(8192)
                t_end = time.perf_counter_ns()
                rtt_ms = (t_end - t_start) / 1_000_000.0

                feedback_payload = None
                if resp:
                    try:
                        resp_json = json.loads(resp.decode("utf-8"))
                        if isinstance(resp_json, dict):
                            if "overrides" in resp_json:
                                self.latest_cloud_control = resp_json["overrides"]
                            if "outcome_log" in resp_json:
                                self.latest_outcome_log = resp_json["outcome_log"]
                                feedback_payload = resp_json["outcome_log"]
                    except Exception:
                        pass

                return True, round(rtt_ms, 3), feedback_payload
        except Exception:
            t_end = time.perf_counter_ns()
            rtt_ms = (t_end - t_start) / 1_000_000.0
            return False, round(rtt_ms, 3), None

    def transmit(
        self,
        compressed_result: Dict[str, Any],
        decision: Optional[Dict[str, Any]] = None,
        forecasted_state: Optional[Dict[str, Any]] = None,
        force_offline: bool = False
    ) -> Dict[str, Any]:
        """
        Jointly schedules radio sleep/wake duty cycle and transmits or buffers the payload.
        """
        window_id = compressed_result.get("window_id", 0)
        compressor = compressed_result.get("compressor_used", "lz4")
        comp_bytes = compressed_result.get("compressed_payload", b"")
        raw_size = compressed_result.get("raw_size_bytes", len(comp_bytes))
        comp_size = compressed_result.get("compressed_size_bytes", len(comp_bytes))
        now = time.time()

        action = "transmit"
        sleep_duration_s = RADIO_BASE_SLEEP_S
        if decision and isinstance(decision, dict):
            action = decision.get("transmit_or_defer", "transmit")
            sleep_duration_s = decision.get("radio_sleep_duration_s", RADIO_BASE_SLEEP_S)

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
            "local_reconstruction_error": compressed_result.get("local_reconstruction_error", 0.0),
            "entropy": decision.get("entropy", 0.0) if decision else 0.0,
            "variance": decision.get("variance", 0.0) if decision else 0.0,
            "predicted_cpu_temp": decision.get("predicted_cpu_temp", 0.0) if decision else 0.0,
            "predicted_cpu_load": decision.get("predicted_cpu_load", 0.0) if decision else 0.0,
            "predicted_bw_kbps": decision.get("predicted_bw_kbps", 1000.0) if decision else 1000.0,
            "throttling_risk": decision.get("throttling_risk", False) if decision else False,
            "composite_score": decision.get("composite_score", 0.0) if decision else 0.0,
            "payload_bytes": comp_bytes
        }

        # ---------------------------------------------------------------------
        # Case A: Transmission Deferral (Objective O5: Extended Radio Sleep)
        # ---------------------------------------------------------------------
        if action == "defer" or force_offline:
            self.deferral_queue.append(packet_record)
            self.radio_state = self.RADIO_STATE_SLEEP
            self.total_sleep_time_s += sleep_duration_s

            # Energy saved by sleeping the radio transceiver:
            # P_saved (mW) = P_active - P_sleep; E_saved (uJ) = P_saved * t_sleep * 1000
            radio_energy_saved_uj = (self.RADIO_ACTIVE_POWER_MW - self.RADIO_SLEEP_POWER_MW) * sleep_duration_s * 1000.0
            self.total_radio_energy_saved_uj += radio_energy_saved_uj

            return {
                "status": "deferred_to_queue",
                "window_id": window_id,
                "action": "defer",
                "radio_state": self.RADIO_STATE_SLEEP,
                "radio_sleep_duration_s": sleep_duration_s,
                "radio_wake_time_ms": 0.0,
                "radio_energy_saved_uj": round(radio_energy_saved_uj, 2),
                "queue_depth": len(self.deferral_queue),
                "bytes_transmitted": 0,
                "transfer_time_ms": 0.0,
                "feedback_outcome": None
            }

        # ---------------------------------------------------------------------
        # Case B: Transmit Immediate (Radio Wake & Network Burst)
        # ---------------------------------------------------------------------
        self.radio_state = self.RADIO_STATE_ACTIVE
        t_wake_start = time.perf_counter()

        # Wire packet framing: [4B Header Len] [Header JSON] [Binary Payload]
        header_dict = {k: v for k, v in packet_record.items() if k != "payload_bytes"}
        header_bytes = json.dumps(header_dict).encode("utf-8")
        wire_packet = len(header_bytes).to_bytes(4, byteorder="big") + header_bytes + comp_bytes

        transfer_time_ms = 0.0
        success = True
        feedback_report = None

        if self.enable_network:
            success, transfer_time_ms, feedback_report = self._send_over_socket(wire_packet)

        t_wake_ms = max(0.01, (time.perf_counter() - t_wake_start) * 1000.0)
        self.total_wake_time_ms += t_wake_ms

        if not success:
            # Network failure -> buffer into deferral queue
            self.deferral_queue.append(packet_record)
            self.radio_state = self.RADIO_STATE_SLEEP
            return {
                "status": "deferred_to_queue",
                "window_id": window_id,
                "action": "buffered",
                "radio_state": self.RADIO_STATE_SLEEP,
                "radio_sleep_duration_s": RADIO_DEFERRED_SLEEP_S,
                "radio_wake_time_ms": round(t_wake_ms, 3),
                "radio_energy_saved_uj": 0.0,
                "queue_depth": len(self.deferral_queue),
                "bytes_transmitted": 0,
                "transfer_time_ms": transfer_time_ms,
                "feedback_outcome": None
            }

        self.total_transmitted_bytes += comp_size
        self.total_packets_sent += 1

        # Check if backlog needs draining upon link active
        drained_count = 0
        if len(self.deferral_queue) > 0:
            drained_count = self._flush_backlog_queue()

        # Radio duty cycle ratio
        total_time_ms = self.total_wake_time_ms + (self.total_sleep_time_s * 1000.0)
        duty_cycle_pct = round((self.total_wake_time_ms / max(1.0, total_time_ms)) * 100.0, 2)

        return {
            "status": "sent_immediate",
            "window_id": window_id,
            "action": "transmit",
            "radio_state": self.RADIO_STATE_ACTIVE,
            "radio_sleep_duration_s": sleep_duration_s,
            "radio_wake_time_ms": round(t_wake_ms, 3),
            "duty_cycle_percent": duty_cycle_pct,
            "total_radio_energy_saved_uj": round(self.total_radio_energy_saved_uj, 2),
            "queue_depth": len(self.deferral_queue),
            "flushed_count": drained_count,
            "drained_backlog_count": drained_count,
            "bytes_transmitted": comp_size,
            "transfer_time_ms": transfer_time_ms,
            "feedback_outcome": feedback_report
        }

    def _flush_backlog_queue(self) -> int:
        """Drains queued backlog packets in FIFO order upon network recovery."""
        drained = 0
        while self.deferral_queue:
            item = self.deferral_queue.popleft()
            header_dict = {k: v for k, v in item.items() if k != "payload_bytes"}
            header_bytes = json.dumps(header_dict).encode("utf-8")
            wire_packet = len(header_bytes).to_bytes(4, byteorder="big") + header_bytes + item["payload_bytes"]
            if self.enable_network:
                ok, _, feedback = self._send_over_socket(wire_packet)
                if not ok:
                    self.deferral_queue.appendleft(item)
                    break
                if feedback:
                    self.latest_outcome_log = feedback
            self.total_transmitted_bytes += len(wire_packet)
            self.total_packets_sent += 1
            drained += 1
        return drained


# Backwards compatibility alias
TransmissionStage = RadioTransmissionStage


if __name__ == "__main__":
    print("=== Testing Stage 7: Radio Duty-Cycle & Transmission Co-Scheduler (Objective O5) ===")
    stage7 = RadioTransmissionStage(enable_network=False)

    fake_comp = {
        "window_id": 1,
        "compressor_used": "lz4",
        "raw_size_bytes": 1000,
        "compressed_size_bytes": 250,
        "compression_ratio": 4.0,
        "execution_time_ms": 0.5,
        "cpu_energy_proxy_uj": 100.0,
        "compressed_payload": b"PACKET_BLOB"
    }

    # Test 1: Immediate Send (Active Radio)
    res_tx = stage7.transmit(fake_comp, decision={"transmit_or_defer": "transmit", "radio_sleep_duration_s": 0.2})
    print(f"Transmit Result: Status={res_tx['status']}, Radio={res_tx['radio_state']}, Wake Time={res_tx['radio_wake_time_ms']}ms")

    # Test 2: Deferral Send (Low-Power Radio Sleep)
    res_defer = stage7.transmit(fake_comp, decision={"transmit_or_defer": "defer", "radio_sleep_duration_s": 2.5})
    print(f"Defer Result: Status={res_defer['status']}, Radio={res_defer['radio_state']}, Energy Saved={res_defer['radio_energy_saved_uj']}uJ, Queue Depth={res_defer['queue_depth']}")
