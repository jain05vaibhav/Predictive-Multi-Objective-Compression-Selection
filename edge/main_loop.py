"""
Edge Main Loop Orchestrator (Raspberry Pi 3B+ Edge Node)

Runs continuous autonomous edge cycles:
Stage 1 (Acquisition) -> Stage 2 (Features) -> Stage 3 (Predictor) ->
Stage 4 (Decision Engine) -> Stage 5 (Dynamic Compression) -> Stage 6 (Network Transmission)

Zero UI / Zero Server overhead: Designed specifically for resource-constrained edge hardware.
"""

import time
import argparse
from typing import Dict, Any, Optional

from edge.stage1_acquisition import AcquisitionStage, Window
from edge.stage2_features import FeatureExtractionStage
from edge.stage3_predictor import PredictorStage
from edge.stage4_decision import DecisionStage
from edge.stage5_compression import CompressionStage
from edge.stage6_transmission import TransmissionStage
from edge.config import WINDOW_SIZE_N, DEFAULT_SAMPLE_TIMEOUT


class EdgePipeline:
    """
    Autonomous lightweight 6-stage edge pipeline coordinator running on the Raspberry Pi.
    """

    def __init__(
        self,
        window_size: int = 5,
        sample_timeout: float = DEFAULT_SAMPLE_TIMEOUT,
        cloud_host: Optional[str] = None,
        cloud_port: int = 8765
    ):
        self.stage1 = AcquisitionStage(window_size=window_size, max_wait_time=sample_timeout)
        self.stage2 = FeatureExtractionStage()
        self.stage3 = PredictorStage()
        self.stage4 = DecisionStage()
        self.stage5 = CompressionStage()
        
        # Configure transmission: network socket if cloud_host provided, otherwise simulated/local
        enable_net = bool(cloud_host is not None)
        target_host = cloud_host or "127.0.0.1"
        self.stage6 = TransmissionStage(host=target_host, port=cloud_port, enable_network=enable_net)
        self.cycle_count = 0



    def run_window_cycle(self) -> Dict[str, Any]:
        """Runs a single end-to-end pipeline cycle across edge stages for one window."""
        self.cycle_count += 1
        
        # 1. Stage 1: Acquire Window
        window = self.stage1.acquire_window()
        
        # 2. Stage 2: Extract Features
        features = self.stage2.extract_features(window)
        
        # 3. Stage 3: Forecast Next State
        predictions = self.stage3.predict(window)

        # 4. Stage 4: Multi-Objective Decision Engine
        decision = self.stage4.select_strategy(features, predictions)
        # Enrich decision with feature & prediction telemetry for network transmission
        decision["entropy"] = features.get("entropy", 0.0)
        decision["variance"] = features.get("variance", 0.0)
        decision["predicted_cpu_temp"] = predictions.get("predicted_cpu_temp", 0.0)
        decision["predicted_cpu_load"] = predictions.get("predicted_cpu_load", 0.0)
        decision["predicted_bw_kbps"] = predictions.get("predicted_bandwidth_kbps", 1000.0)
        decision["throttling_risk"] = predictions.get("is_throttling_risk", False)

        # 5. Stage 5: Dynamic Compression Execution
        compressed = self.stage5.compress_payload(window, decision)

        # 6. Stage 6: Network Transmission & Deferral Manager
        tx_report = self.stage6.transmit(compressed, decision=decision)
        
        return {
            "cycle": self.cycle_count,
            "window": window,
            "features": features,
            "prediction": predictions,
            "decision": decision,
            "compressed": compressed,
            "transmission": tx_report
        }

    def run_loop(self, max_cycles: Optional[int] = None, delay_s: float = 0.5):
        """Runs the continuous autonomous loop until interrupted or max_cycles reached."""
        print("=== Starting Autonomous Edge Compression Pipeline (Press Ctrl+C to stop) ===")
        try:
            while max_cycles is None or self.cycle_count < max_cycles:
                res = self.run_window_cycle()
                win = res["window"]
                f = res["features"]
                p = res["prediction"]
                d = res["decision"]
                c = res["compressed"]
                tx = res["transmission"]
                latest = win.data[-1] if win.data else {}
                
                print(f"\n[Window #{res['cycle']} | {time.strftime('%H:%M:%S')}]")
                print(f"  [1. Sensors]  DHT22: {latest.get('temperature', 0.0):.1f} deg C, {latest.get('humidity', 0.0):.1f} % | SoC Temp: {p['predicted_cpu_temp']:.1f} deg C")
                print(f"  [2. Features] Entropy H: {f['entropy']:.4f} | Variance: {f['variance']:.4f}")
                print(f"  [3. Forecast] Next CPU: {p['predicted_cpu_load']:.1f} % | Headroom: {p['thermal_headroom_c']:.1f} deg C | Risk: {p['is_throttling_risk']}")
                print(f"  [4. Decision] Selected Codec: {d['chosen_compressor'].upper()} (Score: {d['composite_score']:+.3f}) | Action: {d['transmit_or_defer']}")
                print(f"  [5. Compress] Size: {c['raw_size_bytes']}B -> {c['compressed_size_bytes']}B | Ratio: {c['compression_ratio']:.2f}x (Saved: {c['space_savings_percent']}%) | Time: {c['execution_time_ms']:.3f} ms")
                print(f"  [6. Transmit] Status: {tx['status']} | Bytes Sent: {tx['bytes_transmitted']}B | Queue Backlog: {tx['queue_depth']}")
                
                if delay_s > 0:
                    time.sleep(delay_s)
        except KeyboardInterrupt:
            print("\nPipeline execution stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Edge Pipeline Runner (Raspberry Pi)")
    parser.add_argument("--windows", type=int, default=None, help="Maximum number of windows to run (default: continuous)")
    parser.add_argument("--window-size", type=int, default=5, help="Number of samples per window (default: 5)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between windows in seconds (default: 0.5)")
    parser.add_argument("--cloud-host", type=str, default=None, help="Remote Cloud Receiver IP / Hostname (e.g. 192.168.1.50)")
    parser.add_argument("--cloud-port", type=int, default=8765, help="Remote Cloud Receiver Port (default: 8765)")
    args = parser.parse_args()

    pipeline = EdgePipeline(
        window_size=args.window_size,
        cloud_host=args.cloud_host,
        cloud_port=args.cloud_port
    )
    pipeline.run_loop(max_cycles=args.windows, delay_s=args.delay)



