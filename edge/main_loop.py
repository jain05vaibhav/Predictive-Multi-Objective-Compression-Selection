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
        cloud_host: Optional[str] = None,
        cloud_port: int = 8765,
        source: Optional[Any] = None,
        scenario_shift: bool = False
    ):
        self.scenario_shift = scenario_shift
        self.stage1 = AcquisitionStage(window_size=window_size, source=source)
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

        # Inject simulated scenario shifts if enabled for live demonstration
        scenario_label = "Live Hardware"
        if self.scenario_shift:
            phase = self.cycle_count % 9
            if phase in (4, 5, 6):
                scenario_label = "Simulated Bandwidth Congestion (120 kbps)"
                predictions["predicted_bandwidth_kbps"] = 120.0
            elif phase in (7, 8, 0):
                scenario_label = "Simulated SoC Thermal Spike (78.0 °C)"
                predictions["predicted_cpu_temp"] = 78.0
                predictions["is_throttling_risk"] = True
            else:
                scenario_label = "Normal Operational Baseline (1000 kbps, 39.0 °C)"
                predictions["predicted_bandwidth_kbps"] = 1000.0

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
            "scenario": scenario_label,
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
                scen = res.get("scenario", "Live Hardware")
                latest = win.data[-1] if win.data else {}
                
                # Formulate human-readable decision reason
                reasons = []
                if p.get('predicted_cpu_temp', 0.0) >= 70.0 or p.get('is_throttling_risk', False):
                    reasons.append("Thermal/CPU Stress (Boosted Energy/Latency Weights)")
                elif p.get('predicted_bandwidth_kbps', 1000.0) < 200.0:
                    reasons.append("Bandwidth Depletion (Boosted Compression Ratio Weight)")
                elif f.get('entropy', 2.0) < 0.5:
                    reasons.append("Low Shannon Entropy H<0.5 (Boosted Delta Encoding)")
                else:
                    reasons.append("Balanced Multi-Objective Tradeoff")
                factor_reason = " + ".join(reasons)

                print(f"\n[Window #{res['cycle']} | {time.strftime('%H:%M:%S')} | Scenario: {scen}]")
                print(f"  [1. Sensors]  DHT22: {latest.get('temperature', 0.0):.1f} deg C, {latest.get('humidity', 0.0):.1f} % | SoC Temp: {p['predicted_cpu_temp']:.1f} deg C | BW: {p.get('predicted_bandwidth_kbps', 1000.0):.0f} kbps")
                print(f"  [2. Features] Entropy H: {f['entropy']:.4f} | Variance: {f['variance']:.4f}")
                print(f"  [3. Forecast] Next CPU: {p['predicted_cpu_load']:.1f} % | Headroom: {p['thermal_headroom_c']:.1f} deg C | Risk: {p['is_throttling_risk']}")
                print(f"  [4. Decision] Selected Codec: {d['chosen_compressor'].upper()} (Score: {d['composite_score']:+.3f}) | Drivers: {factor_reason}")
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
    parser.add_argument("--scenario-shift", action="store_true", help="Simulate dynamic real-world condition shifts across cycles (Normal -> Congestion -> Thermal)")
    args = parser.parse_args()

    pipeline = EdgePipeline(
        window_size=args.window_size,
        cloud_host=args.cloud_host,
        cloud_port=args.cloud_port,
        scenario_shift=args.scenario_shift
    )
    pipeline.run_loop(max_cycles=args.windows, delay_s=args.delay)
