"""
Edge Main Loop Orchestrator

Runs continuous autonomous edge cycles across:
Stage 1 (Acquisition) -> Stage 2 (Features) -> Stage 3 (Predictor) ->
Stage 4 (Decision Engine) -> Stage 5 (Dynamic Compression) -> Stage 6 (Transmission)
"""

import time
import argparse
from typing import Dict, Any, Optional

from edge.stage1_acquisition import AcquisitionStage, Window
from edge.stage2_features import FeatureExtractionStage
from edge.stage3_predictor import PredictorStage
from edge.stage4_decision import DecisionStage
from edge.stage5_compression import CompressionStage
from edge.config import WINDOW_SIZE_N, DEFAULT_SAMPLE_TIMEOUT


class EdgePipeline:
    """
    Autonomous pipeline coordinator running on Raspberry Pi 3B+ edge node.
    """

    def __init__(
        self,
        window_size: int = 5,
        sample_timeout: float = DEFAULT_SAMPLE_TIMEOUT,
        use_hardware: bool = True
    ):
        self.stage1 = AcquisitionStage(window_size=window_size, sample_timeout=sample_timeout, use_hardware=use_hardware)
        self.stage2 = FeatureExtractionStage()
        self.stage3 = PredictorStage()
        self.stage4 = DecisionStage()
        self.stage5 = CompressionStage()
        self.cycle_count = 0

    def run_window_cycle(self) -> Dict[str, Any]:
        """Runs a single end-to-end pipeline cycle for one window."""
        self.cycle_count += 1
        
        # 1. Acquire Window
        window = self.stage1.acquire_window()
        
        # 2. Extract Features
        features = self.stage2.extract_features(window)
        
        # 3. Forecast Next State
        predictions = self.stage3.predict(window)

        # 4. Multi-Objective Decision Engine
        decision = self.stage4.select_strategy(features, predictions)

        # 5. Dynamic Compression Execution
        compressed = self.stage5.compress_payload(window, decision)
        
        return {
            "cycle": self.cycle_count,
            "window": window,
            "features": features,
            "prediction": predictions,
            "decision": decision,
            "compressed": compressed
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
                latest = win.data[-1] if win.data else {}
                
                print(f"\n[Window #{res['cycle']} | {time.strftime('%H:%M:%S')}]")
                print(f"  [Sensors]  DHT22: {latest.get('temperature', 0.0):.1f} deg C, {latest.get('humidity', 0.0):.1f} % | SoC Temp: {p['predicted_cpu_temp']:.1f} deg C")
                print(f"  [Features] Entropy H: {f['entropy']:.4f} | Variance: {f['variance']:.4f}")
                print(f"  [Forecast] Next CPU: {p['predicted_cpu_load']:.1f} % | Headroom: {p['thermal_headroom_c']:.1f} deg C | Risk: {p['is_throttling_risk']}")
                print(f"  [Decision] Selected Codec: {d['chosen_compressor'].upper()} (Score: {d['composite_score']:+.3f}) | Action: {d['transmit_or_defer']}")
                print(f"  [Compress] Size: {c['raw_size_bytes']}B -> {c['compressed_size_bytes']}B | Ratio: {c['compression_ratio']:.2f}x (Saved: {c['space_savings_percent']}%) | Time: {c['execution_time_ms']:.3f} ms")
                
                if delay_s > 0:
                    time.sleep(delay_s)
        except KeyboardInterrupt:
            print("\nPipeline execution stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Edge Pipeline Runner")
    parser.add_argument("--windows", type=int, default=None, help="Maximum number of windows to run (default: continuous)")
    parser.add_argument("--window-size", type=int, default=5, help="Number of samples per window (default: 5)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between windows in seconds (default: 0.5)")
    args = parser.parse_args()

    pipeline = EdgePipeline(window_size=args.window_size)
    pipeline.run_loop(max_cycles=args.windows, delay_s=args.delay)


