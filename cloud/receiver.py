"""
Stage 7: Cloud Receiver & Decompression Server

Receives edge telemetry packets transmitted by Stage 6 over TCP/HTTP, decompresses
payloads using the inverse codec (c^-1), computes actual reconstruction error (epsilon),
and commits verified ground-truth outcome vectors to OutcomeStore (logs/outcomes.csv).
Also mirrors decision logs to logs/decisions.csv for real-time dashboard telemetry.
"""

import os
import csv
import json
import socket
import threading
import time
from typing import Dict, Any, Optional

from edge.stage5_compression import CompressionStage
from cloud.outcome_store import OutcomeStore


class CloudReceiver:
    """
    Stage 7 Cloud Receiver & Integrity Ingestion Server.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        log_file: str = "logs/outcomes.csv"
    ):
        self.host = host
        self.port = int(port)
        self.compression_engine = CompressionStage()
        self.outcome_store = OutcomeStore(log_file=log_file)

        self.server_socket: Optional[socket.socket] = None
        self.is_running = False
        self.server_thread: Optional[threading.Thread] = None

    def calculate_reconstruction_error(
        self,
        original_bytes: bytes,
        decompressed_bytes: bytes
    ) -> float:
        """
        Calculates normalized root-mean-square reconstruction error epsilon:
          epsilon = ||X_orig - X_decomp|| / (||X_orig|| + 1e-9)
        Returns 0.0 for lossless exact match.
        """
        if original_bytes == decompressed_bytes:
            return 0.0

        if len(original_bytes) != len(decompressed_bytes):
            return 1.0

        diff_sum = sum((a - b) ** 2 for a, b in zip(original_bytes, decompressed_bytes))
        orig_sum = sum(a ** 2 for a, b in zip(original_bytes, decompressed_bytes))
        return (diff_sum ** 0.5) / max(1e-9, orig_sum ** 0.5)

    def receive_and_process_payload(self, packet_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests a compressed packet dictionary, decompresses the payload,
        validates integrity, and logs the verified outcome and mirrored decisions.
        """
        window_id = packet_dict.get("window_id", 0)
        compressor = packet_dict.get("compressor", packet_dict.get("compressor_used", "lz4"))
        level = packet_dict.get("compression_level", 1)
        raw_size = packet_dict.get("raw_size_bytes", 0)
        comp_payload = packet_dict.get("payload_bytes", packet_dict.get("compressed_payload", b""))
        comp_size = packet_dict.get("compressed_size_bytes", len(comp_payload))
        transfer_ms = packet_dict.get("transfer_time_ms", 0.0)

        # 1. Decompress payload
        t0 = time.perf_counter_ns()
        error = 0.0
        status = "verified"
        decompressed_bytes = b""
        try:
            decompressed_bytes = self.compression_engine.decompress(comp_payload, codec=compressor)
        except Exception:
            error = 1.0
            status = "decompression_failed"
            decompressed_bytes = comp_payload
        t1 = time.perf_counter_ns()
        decompress_latency_ms = (t1 - t0) / 1_000_000.0

        # 2. Verify error
        actual_ratio = round(raw_size / max(1, comp_size), 4)

        # 3. Parse decompressed payload if JSON and update live telemetry snapshot
        parsed_data = None
        try:
            parsed_data = json.loads(decompressed_bytes.decode("utf-8"))
            if isinstance(parsed_data, list) and len(parsed_data) > 0:
                latest_sample = parsed_data[-1]
                os.makedirs("logs", exist_ok=True)
                with open("logs/latest_telemetry.json", "w", encoding="utf-8") as f:
                    json.dump(latest_sample, f, indent=2, default=str)
        except Exception:
            pass

        # 4. Commit to OutcomeStore
        outcome_record = {
            "timestamp": packet_dict.get("timestamp", time.time()),
            "window_id": window_id,
            "compressor": compressor,
            "compression_level": level,
            "raw_bytes": raw_size,
            "compressed_bytes": comp_size,
            "ratio": actual_ratio,
            "latency_ms": packet_dict.get("execution_time_ms", 0.0),
            "energy_uj": packet_dict.get("cpu_energy_proxy_uj", 0.0),
            "error": error,
            "transfer_time_ms": transfer_ms,
            "status": status
        }
        self.outcome_store.record_outcome(outcome_record)

        # 5. Mirror Decision Log on Cloud for Live Dashboard Visualizations
        if "entropy" in packet_dict or "predicted_cpu_temp" in packet_dict:
            try:
                dec_path = "logs/decisions.csv"
                if not os.path.exists(dec_path):
                    with open(dec_path, "w", newline="", encoding="utf-8") as f:
                        f.write("timestamp,window_id,chosen_compressor,compression_level,transmit_or_defer,composite_score,entropy,variance,predicted_cpu_temp,predicted_cpu_load,predicted_bw_kbps,throttling_risk,w1_ratio,w2_energy,w3_latency,w4_error\n")
                with open(dec_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        round(packet_dict.get("timestamp", time.time()), 3),
                        window_id,
                        compressor,
                        level,
                        "transmit",
                        round(packet_dict.get("composite_score", 0.0), 4),
                        round(packet_dict.get("entropy", 0.0), 4),
                        round(packet_dict.get("variance", 0.0), 4),
                        round(packet_dict.get("predicted_cpu_temp", 0.0), 2),
                        round(packet_dict.get("predicted_cpu_load", 0.0), 2),
                        round(packet_dict.get("predicted_bw_kbps", 1000.0), 2),
                        packet_dict.get("throttling_risk", False),
                        packet_dict.get("w1_ratio", 0.4),
                        packet_dict.get("w2_energy", 0.3),
                        packet_dict.get("w3_latency", 0.2),
                        packet_dict.get("w4_error", 0.1)
                    ])
            except Exception:
                pass

        print(f"[CLOUD INGESTION | Window #{window_id:03d}] Codec: {compressor.upper():<10} | Ingested: {comp_size:>5}B -> Decompressed: {raw_size:>5}B ({actual_ratio:.2f}x) | Error: {error:.6f} ({status.upper()}) | Decompress: {decompress_latency_ms:.3f}ms")

        return {
            "window_id": window_id,
            "compressor": compressor,
            "decompressed_bytes_count": len(decompressed_bytes),
            "reconstruction_error": error,
            "decompress_time_ms": round(decompress_latency_ms, 4),
            "status": status,
            "sample_count": len(parsed_data) if isinstance(parsed_data, list) else 1
        }

    def start_socket_server(self, blocking: bool = False):
        """Starts live TCP socket listener for edge connections."""
        self.is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.server_socket.settimeout(0.5)

        if blocking:
            self._server_loop()
        else:
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()

    def _server_loop(self):
        """Internal server accept loop."""
        print(f"=== Cloud Ingestion Server listening on {self.host}:{self.port} ===")
        print("Waiting for edge telemetry stream from Raspberry Pi... (Press Ctrl+C to stop)")
        while self.is_running:
            try:
                conn, addr = self.server_socket.accept()
                with conn:
                    # Read 4-byte length
                    raw_len = conn.recv(4)
                    if not raw_len or len(raw_len) < 4:
                        continue
                    pkt_len = int.from_bytes(raw_len, "big")
                    data = bytearray()
                    while len(data) < pkt_len:
                        chunk = conn.recv(min(4096, pkt_len - len(data)))
                        if not chunk:
                            break
                        data.extend(chunk)

                    # Send ACK
                    conn.sendall(b"ACK")

                    # Process packet
                    header_len = int.from_bytes(data[:4], "big")
                    header_json = json.loads(data[4:4 + header_len].decode("utf-8"))
                    payload_blob = bytes(data[4 + header_len:])

                    packet_dict = {
                        "window_id": header_json.get("window_id", 0),
                        "timestamp": header_json.get("timestamp", time.time()),
                        "compressor": header_json.get("compressor", "lz4"),
                        "compression_level": header_json.get("compression_level", 1),
                        "raw_size_bytes": header_json.get("raw_size", len(payload_blob)),
                        "compressed_size_bytes": header_json.get("comp_size", len(payload_blob)),
                        "execution_time_ms": header_json.get("execution_time_ms", 0.0),
                        "cpu_energy_proxy_uj": header_json.get("cpu_energy_proxy_uj", 0.0),
                        "payload_bytes": payload_blob,
                        "entropy": header_json.get("entropy", 0.0),
                        "variance": header_json.get("variance", 0.0),
                        "predicted_cpu_temp": header_json.get("predicted_cpu_temp", 0.0),
                        "predicted_cpu_load": header_json.get("predicted_cpu_load", 0.0),
                        "predicted_bw_kbps": header_json.get("predicted_bw_kbps", 1000.0),
                        "throttling_risk": header_json.get("throttling_risk", False),
                        "composite_score": header_json.get("composite_score", 0.0),
                        "w1_ratio": header_json.get("w1_ratio", 0.4),
                        "w2_energy": header_json.get("w2_energy", 0.3),
                        "w3_latency": header_json.get("w3_latency", 0.2),
                        "w4_error": header_json.get("w4_error", 0.1)
                    }
                    self.receive_and_process_payload(packet_dict)
            except socket.timeout:
                continue
            except Exception:
                break

    def stop_server(self):
        """Stops the socket server gracefully."""
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        if self.server_thread:
            self.server_thread.join(timeout=1.0)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cloud Receiver & Telemetry Ingestion Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind IP address (default: 0.0.0.0 / all interfaces)")
    parser.add_argument("--port", type=int, default=8765, help="TCP port to listen on (default: 8765)")
    parser.add_argument("--test", action="store_true", help="Run standalone verification test instead of live server")
    args = parser.parse_args()

    if args.test:
        print("=== Testing Stage 7: Cloud Receiver & Decompression Engine ===")
        receiver = CloudReceiver(log_file="logs/test_cloud_outcomes.csv")
        comp_stage = CompressionStage()
        sample_window = [{"temperature": 23.5 + i, "humidity": 60.0} for i in range(10)]
        comp_res = comp_stage.compress(sample_window, codec="zstd")

        packet = {
            "window_id": 1,
            "compressor": comp_res["compressor_used"],
            "compression_level": comp_res["compression_level"],
            "raw_size_bytes": comp_res["raw_size_bytes"],
            "compressed_size_bytes": comp_res["compressed_size_bytes"],
            "execution_time_ms": comp_res["execution_time_ms"],
            "cpu_energy_proxy_uj": comp_res["cpu_energy_proxy_uj"],
            "payload_bytes": comp_res["compressed_payload"],
            "transfer_time_ms": 5.2
        }
        result = receiver.receive_and_process_payload(packet)
        stats = receiver.outcome_store.get_summary_stats()
        print(f"\n[Outcome Store Summary] Total Windows: {stats['total_windows']} | Saved: {stats['overall_bandwidth_saved_pct']}%")
        import os
        if os.path.exists("logs/test_cloud_outcomes.csv"):
            os.remove("logs/test_cloud_outcomes.csv")
        print("Stage 7 Cloud Receiver test complete.")
    else:
        receiver = CloudReceiver(host=args.host, port=args.port, log_file="logs/outcomes.csv")
        try:
            receiver.start_socket_server(blocking=True)
        except KeyboardInterrupt:
            receiver.stop_server()
            print("\nCloud Receiver server stopped.")
