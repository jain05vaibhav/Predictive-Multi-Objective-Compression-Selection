"""
Edge Main Loop Orchestrator (Raspberry Pi 3B+ / Broadcom BCM2837 SoC)

Coordinates the closed-loop 8-stage architecture defined in the System Architecture specification:
  Stage 1 (Acquisition) -> Stage 2 (Features) -> Stage 3 (Dual-Track Predictor, O1) ->
  Stage 4 (Self-Calibrating Profiler & Overhead, O4, 2.12) ->
  Stage 5 (Hierarchical Decision Engine & Online Policy, O2, O3) ->
  Stage 6 (Dynamic Compression Execution) ->
  Stage 7 (Joint Radio Duty-Cycle Co-Scheduler & Transmission, O5) ->
  Stage 8 (Cloud Feedback Loop: Updates Stage 4 & Stage 5)

Hardware Grounded: Real sensor ingestion (DHT22, CSI Camera, SoC telemetry) and
zero-overhead autonomous edge controller execution.
"""

import os
import time
import argparse
from typing import Dict, Any, Optional

from edge.stage1_acquisition import AcquisitionStage, Window
from edge.stage2_features import FeatureExtractionStage
from edge.stage3_predictor import PredictorStage
from edge.stage4_profiler import HardwareProfilerStage
from edge.stage5_decision import HierarchicalDecisionEngine
from edge.stage6_compression import CompressionStage
from edge.stage7_radio import RadioTransmissionStage
from edge.config import WINDOW_SIZE_N, DEFAULT_SAMPLE_TIMEOUT


class EdgePipeline:
    """
    Autonomous closed-loop edge controller orchestrator running on Raspberry Pi.
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
        self.stage4 = HardwareProfilerStage()
        self.stage5 = HierarchicalDecisionEngine(profiler=self.stage4)
        self.stage6 = CompressionStage()

        # Network transmission / socket configuration
        enable_net = bool(cloud_host is not None)
        target_host = cloud_host or "127.0.0.1"
        self.stage7 = RadioTransmissionStage(host=target_host, port=cloud_port, enable_network=enable_net)

        # Backwards compatibility alias references
        self.transmission_stage = self.stage7
        self.decision_stage = self.stage5
        self.compression_stage = self.stage6

        self.cycle_count = 0

    def run_window_cycle(self) -> Dict[str, Any]:
        """
        Executes one complete closed-loop cycle across Stages 1–8 for one data window.
        """
        self.cycle_count += 1

        # ---------------------------------------------------------------------
        # 1. Stage 1: Data Acquisition & Windowing
        # ---------------------------------------------------------------------
        window = self.stage1.acquire_window()

        # Start timing controller overhead across Stages 2–5 (Section 2.12)
        self.stage4.start_controller_window()

        # ---------------------------------------------------------------------
        # 2. Stage 2: Feature Extraction
        # ---------------------------------------------------------------------
        features = self.stage2.extract_features(window)

        # ---------------------------------------------------------------------
        # 3. Stage 3: Predictive Forecasting Module (Objective O1)
        # ---------------------------------------------------------------------
        predictions = self.stage3.predict(window, features=features)

        # Process Live Remote Overrides (from Streamlit Dashboard)
        scenario_label = "Live Hardware Stream"
        cloud_overrides = getattr(self.stage7, "latest_cloud_control", {})
        if cloud_overrides and cloud_overrides.get("enabled", False):
            scenario_label = "Dashboard Manual Override"
            if "override_cpu_temp" in cloud_overrides and cloud_overrides["override_cpu_temp"] is not None:
                predictions["predicted_cpu_temp"] = float(cloud_overrides["override_cpu_temp"])
                if float(cloud_overrides["override_cpu_temp"]) >= 70.0:
                    predictions["is_throttling_risk"] = True
            if "override_bandwidth_kbps" in cloud_overrides and cloud_overrides["override_bandwidth_kbps"] is not None:
                predictions["predicted_bandwidth_kbps"] = float(cloud_overrides["override_bandwidth_kbps"])
            if "override_entropy" in cloud_overrides and cloud_overrides["override_entropy"] is not None:
                features["entropy"] = float(cloud_overrides["override_entropy"])
        elif self.scenario_shift:
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

        # ---------------------------------------------------------------------
        # 4. Stage 5: Hierarchical Decision Engine (Objectives O2, O3)
        # ---------------------------------------------------------------------
        t_dec_start = time.perf_counter()
        decision = self.stage5.select_strategy(features, predictions)
        decision_latency_ms = (time.perf_counter() - t_dec_start) * 1000.0

        # Stop controller window and record overhead (Section 2.12)
        overhead_report = self.stage4.record_controller_overhead(
            window_id=window.window_id,
            decision_latency_ms=decision_latency_ms
        )

        # Enrich decision with telemetry metadata for Stage 7 transmission
        decision["entropy"] = features.get("entropy", 0.0)
        decision["variance"] = features.get("variance", 0.0)
        decision["predicted_cpu_temp"] = predictions.get("predicted_cpu_temp", 0.0)
        decision["predicted_cpu_load"] = predictions.get("predicted_cpu_load", 0.0)
        decision["predicted_bw_kbps"] = predictions.get("predicted_bandwidth_kbps", 1000.0)
        decision["throttling_risk"] = predictions.get("is_throttling_risk", False)

        # ---------------------------------------------------------------------
        # 5. Stage 6: Compression Execution
        # ---------------------------------------------------------------------
        compressed = self.stage6.compress_payload(window, decision)

        # ---------------------------------------------------------------------
        # 6. Stage 7: Joint Radio Duty-Cycle Co-Scheduler & Transmission (O5)
        # ---------------------------------------------------------------------
        tx_report = self.stage7.transmit(compressed, decision=decision, forecasted_state=predictions)

        # ---------------------------------------------------------------------
        # 7. Stage 8: Closed-Loop Feedback Update (Objectives O3, O4)
        # ---------------------------------------------------------------------
        feedback_outcome = tx_report.get("feedback_outcome")
        if not feedback_outcome:
            # Local fallback feedback from Stages 6 & 7
            feedback_outcome = {
                "window_id": window.window_id,
                "compressor": compressed.get("compressor_used", "lz4"),
                "raw_size_bytes": compressed.get("raw_size_bytes", 1024),
                "ratio": compressed.get("compression_ratio", 1.0),
                "latency_ms": compressed.get("execution_time_ms", 1.0),
                "energy_uj": compressed.get("cpu_energy_proxy_uj", 50.0),
                "error": compressed.get("local_reconstruction_error", 0.0)
            }

        # Update Stage 4 Profiler Moving-Average Calibration Table (O4)
        profiler_update = self.stage4.update_calibration(
            codec=compressed["compressor_used"],
            measured=feedback_outcome,
            context=features
        )

        # Update Stage 5 Contextual Bandit Online Policy (O3)
        bandit_update = self.stage5.update_policy(
            outcome_log=feedback_outcome,
            context=features
        )

        return {
            "cycle": self.cycle_count,
            "scenario": scenario_label,
            "window": window,
            "features": features,
            "prediction": predictions,
            "decision": decision,
            "compressed": compressed,
            "transmission": tx_report,
            "controller_overhead": overhead_report,
            "profiler_update": profiler_update,
            "bandit_update": bandit_update
        }

    def run_loop(self, max_cycles: Optional[int] = None, delay_s: float = 0.5):
        """Runs the continuous autonomous loop until interrupted or max_cycles reached."""
        print("=== Autonomous Edge Controller Running (Raspberry Pi 3B+ SoC) ===")
        print("Pipeline: Acquisition -> Features -> Predictor (O1) -> Profiler (O4) -> Decision (O2,O3) -> Compress -> Radio Duty Cycle (O5) -> Cloud Feedback")
        try:
            while max_cycles is None or self.cycle_count < max_cycles:
                res = self.run_window_cycle()
                win = res["window"]
                f = res["features"]
                p = res["prediction"]
                d = res["decision"]
                c = res["compressed"]
                tx = res["transmission"]
                ov = res["controller_overhead"]
                scen = res.get("scenario", "Live Hardware")
                latest = win.data[-1] if win.data else {}

                print(f"\n[Window #{res['cycle']:03d} | {time.strftime('%H:%M:%S')} | Scenario: {scen}]")
                print(f"  [Sensors & SoC]   DHT22: {latest.get('temperature', 0.0):.1f}°C, {latest.get('humidity', 0.0):.1f}% | SoC Temp: {p['predicted_cpu_temp']:.1f}°C | Batt: {p.get('predicted_battery_percent', 100.0):.1f}% | BW: {p.get('predicted_bandwidth_kbps', 1000.0):.0f} kbps")
                print(f"  [O1: Forecast]    Next CPU: {p['predicted_cpu_load']:.1f}% | Predicted H: {p.get('predicted_entropy', f['entropy']):.4f} (Trend: {p.get('workload_trend', 'steady')}) | Throttling Risk: {p['is_throttling_risk']}")
                print(f"  [O2,O3: Decision] Selected Codec: {d['chosen_compressor'].upper()} (L{d['compression_level']}) | Score: {d['composite_score']:+.4f} | Action: {d['transmit_or_defer'].upper()}")
                print(f"  [Compression]     Size: {c['raw_size_bytes']}B -> {c['compressed_size_bytes']}B | Ratio: {c['compression_ratio']:.2f}x (Saved: {c['space_savings_percent']}%) | Local Error: {c.get('local_reconstruction_error', 0.0):.6f}")
                print(f"  [O5: Radio Duty]  Radio State: {tx['radio_state']} | Wake: {tx['radio_wake_time_ms']:.2f}ms | Duty: {tx.get('duty_cycle_percent', 10.0)}% | Radio Energy Saved: {tx.get('total_radio_energy_saved_uj', 0.0):.1f} uJ | Queue: {tx['queue_depth']}")
                print(f"  [2.12: Overhead]  Controller CPU: {ov['controller_cpu_time_ms']:.2f}ms | RAM: {ov['controller_ram_mb']}MB | Worst Dec Latency: {ov['worst_case_decision_latency_ms']:.2f}ms")

                if delay_s > 0:
                    time.sleep(delay_s)
        except KeyboardInterrupt:
            print("\nPipeline execution stopped by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Edge Controller Runner (Raspberry Pi 3B+)")
    parser.add_argument("--windows", type=int, default=None, help="Maximum number of windows to run (default: continuous)")
    parser.add_argument("--window-size", type=int, default=5, help="Number of samples per window (default: 5)")
    parser.add_argument("--cloud-host", type=str, default=None, help="Cloud receiver IP/hostname for network transmission")
    parser.add_argument("--cloud-port", type=int, default=8765, help="Cloud receiver TCP port (default: 8765)")
    parser.add_argument("--scenario-shift", action="store_true", help="Enable cyclic scenario shift (Normal -> Congestion -> Thermal)")
    parser.add_argument("--delay", type=float, default=0.5, help="Loop delay in seconds (default: 0.5s)")

    args = parser.parse_args()

    pipeline = EdgePipeline(
        window_size=args.window_size,
        cloud_host=args.cloud_host,
        cloud_port=args.cloud_port,
        scenario_shift=args.scenario_shift
    )
    pipeline.run_loop(max_cycles=args.windows, delay_s=args.delay)
