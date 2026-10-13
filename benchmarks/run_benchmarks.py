"""
Phase 17: Comprehensive Benchmark Suite & Statistical Evaluation

Evaluates the Adaptive Multi-Objective Bandit Pipeline against 4 competitor baselines:
1. Baseline 1: Static Raw Passthrough (No compression)
2. Baseline 2: Static Fast Lossless (Always LZ4)
3. Baseline 3: Static High-Ratio Lossless (Always Zstandard / zlib-9)
4. Baseline 4: Fixed Heuristic / Rule-Based (Static if-else threshold rules)
5. Strategy 5: Adaptive Multi-Objective Bandit (Closed-loop online learning)

Produces statistical summary tables and records detailed run data to:
  logs/benchmark_results/benchmark_runs.csv
  logs/benchmark_results/benchmark_summary.json
"""

import os
import sys
import csv
import json
import time
import math
import random
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge.stage2_features import FeatureExtractionStage
from edge.stage3_predictor import StatePredictorStage
from edge.stage5_decision import DecisionStage
from edge.stage5_compression import CompressionStage


class BenchmarkHarness:
    """
    Automated benchmark runner for multi-objective compression policies.
    """

    STRATEGIES = [
        "static_raw",
        "static_fast",
        "static_high_ratio",
        "static_heuristic",
        "adaptive_bandit"
    ]

    def __init__(self, output_dir: str = "logs/benchmark_results"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.features_stage = FeatureExtractionStage()
        self.predictor_stage = StatePredictorStage()
        self.decision_stage = DecisionStage(log_file=os.path.join(self.output_dir, "benchmark_decisions.csv"))
        self.compression_stage = CompressionStage()

    def generate_synthetic_workload(self, num_windows: int = 50) -> List[Dict[str, Any]]:
        """
        Generates realistic multi-modal windows including periodic telemetry,
        bursty entropy spikes, structured text logs, and camera captures.
        """
        workload = []
        random.seed(42)

        for w_id in range(1, num_windows + 1):
            # Dynamic simulated environment conditions
            simulated_temp = 35.0 + 15.0 * math.sin(w_id / 8.0) + random.uniform(-2, 2)
            simulated_load = max(5.0, min(95.0, 30.0 + 25.0 * math.cos(w_id / 6.0) + random.uniform(-5, 5)))
            simulated_bw_kbps = max(50.0, 1200.0 - 500.0 * math.sin(w_id / 5.0) + random.uniform(-100, 100))

            # Alternate between data modalities
            modality = w_id % 3
            if modality == 0:
                # Numeric sensor telemetry
                samples = [
                    {
                        "temperature": 20.0 + random.uniform(0, 5) + 0.1 * i,
                        "humidity": 50.0 + random.uniform(-5, 5),
                        "pressure": 1013.25 + random.uniform(-2, 2),
                        "system": {
                            "cpu_temp_c": simulated_temp,
                            "cpu_percent": simulated_load,
                            "core_voltage_v": 1.25
                        }
                    }
                    for i in range(15)
                ]
                criticality = "routine" if w_id % 7 != 0 else "critical"
            elif modality == 1:
                # Text log stream
                samples = [
                    {
                        "log_line": f"2026-10-13 12:{i:02d}:00 INFO [Worker-{i % 3}] Packet processed successfully. Codec check ok.",
                        "service": "telemetry-agent",
                        "level": "INFO"
                    }
                    for i in range(12)
                ]
                criticality = "bulk"
            else:
                # High-entropy telemetry / image proxy
                samples = [
                    {
                        "pixel_block": [random.randint(0, 255) for _ in range(32)],
                        "ambient_lux": random.uniform(100, 800)
                    }
                    for _ in range(8)
                ]
                criticality = "routine"

            workload.append({
                "window_id": w_id,
                "samples": samples,
                "criticality": criticality,
                "env_temp": simulated_temp,
                "env_load": simulated_load,
                "env_bw_kbps": simulated_bw_kbps,
                "deadline_ms": 30.0  # Latency deadline for deadline-adherence metric
            })

        return workload

    def run_benchmark(self, num_windows: int = 50) -> Dict[str, Any]:
        """
        Executes all 5 candidate strategies over the workload under identical conditions.
        """
        workload = self.generate_synthetic_workload(num_windows)
        detailed_records = []
        strategy_stats = {s: [] for s in self.STRATEGIES}

        print(f"=== Starting Multi-Objective Compression Benchmark ({num_windows} Windows) ===")

        for item in workload:
            w_id = item["window_id"]
            samples = item["samples"]
            criticality = item["criticality"]
            bw_kbps = item["env_bw_kbps"]
            deadline_ms = item["deadline_ms"]

            # Edge feature extraction & state forecasting
            features = self.features_stage.extract_features(samples)
            forecast = self.predictor_stage.predict_next_state({
                "cpu_percent": item["env_load"],
                "cpu_temp_c": item["env_temp"],
                "bandwidth_kbps": bw_kbps
            })

            # Run each strategy
            for strategy in self.STRATEGIES:
                chosen_codec = "lz4"
                level = 1

                if strategy == "static_raw":
                    chosen_codec = "none"
                elif strategy == "static_fast":
                    chosen_codec = "lz4"
                elif strategy == "static_high_ratio":
                    chosen_codec = "zstd" if "zstd" in self.compression_stage.AVAILABLE_CODECS else "gzip"
                elif strategy == "static_heuristic":
                    # Fixed rule-based thresholding without learning
                    entropy = features.get("entropy", 0.0)
                    temp = forecast.get("predicted_cpu_temp", 40.0)
                    if temp > 65.0 or entropy > 5.5:
                        chosen_codec = "lz4"
                    elif bw_kbps < 300.0:
                        chosen_codec = "zstd" if "zstd" in self.compression_stage.AVAILABLE_CODECS else "gzip"
                    else:
                        chosen_codec = "lz4"
                elif strategy == "adaptive_bandit":
                    dec = self.decision_stage.select_algorithm(
                        features,
                        forecast,
                        criticality=criticality
                    )
                    chosen_codec = dec.get("chosen_compressor", "lz4")
                    level = dec.get("compression_level", 1)

                # Execute compression
                t0 = time.perf_counter_ns()
                comp_res = self.compression_stage.compress(samples, codec=chosen_codec, level=level)
                t1 = time.perf_counter_ns()

                raw_bytes = comp_res.get("raw_size_bytes", len(json.dumps(samples).encode("utf-8")))
                comp_bytes = comp_res.get("compressed_size_bytes", len(comp_res.get("compressed_payload", b"")))
                ratio = round(raw_bytes / max(1, comp_bytes), 4)
                exec_time_ms = comp_res.get("execution_time_ms", (t1 - t0) / 1_000_000.0)
                energy_uj = comp_res.get("cpu_energy_proxy_uj", 0.0)

                # Simulated network transmission latency
                # Latency (ms) = (comp_bytes * 8 / (bw_kbps * 1000)) * 1000
                tx_latency_ms = (comp_bytes * 8.0) / max(1.0, bw_kbps)
                total_latency_ms = exec_time_ms + tx_latency_ms
                deadline_met = (total_latency_ms <= deadline_ms)

                # Closed-loop update for adaptive bandit
                if strategy == "adaptive_bandit":
                    self.decision_stage.update_policy({
                        "ratio": ratio,
                        "latency_ms": exec_time_ms,
                        "energy_uj": energy_uj,
                        "error": 0.0
                    })

                record = {
                    "window_id": w_id,
                    "strategy": strategy,
                    "codec": chosen_codec,
                    "raw_bytes": raw_bytes,
                    "compressed_bytes": comp_bytes,
                    "ratio": ratio,
                    "exec_time_ms": round(exec_time_ms, 3),
                    "energy_uj": round(energy_uj, 2),
                    "energy_per_raw_byte": round(energy_uj / max(1, raw_bytes), 4),
                    "tx_latency_ms": round(tx_latency_ms, 3),
                    "total_latency_ms": round(total_latency_ms, 3),
                    "deadline_met": int(deadline_met),
                    "criticality": criticality
                }
                detailed_records.append(record)
                strategy_stats[strategy].append(record)

        # Aggregate summary metrics
        summary = {}
        for strat, runs in strategy_stats.items():
            n = len(runs)
            tot_raw = sum(r["raw_bytes"] for r in runs)
            tot_comp = sum(r["compressed_bytes"] for r in runs)
            avg_ratio = sum(r["ratio"] for r in runs) / n
            avg_exec = sum(r["exec_time_ms"] for r in runs) / n
            avg_energy = sum(r["energy_uj"] for r in runs) / n
            avg_energy_byte = sum(r["energy_per_raw_byte"] for r in runs) / n
            avg_total_lat = sum(r["total_latency_ms"] for r in runs) / n
            deadline_rate = (sum(r["deadline_met"] for r in runs) / n) * 100.0
            bandwidth_saved = ((1.0 - (tot_comp / max(1, tot_raw))) * 100.0)

            summary[strat] = {
                "sample_count": n,
                "total_raw_bytes": tot_raw,
                "total_compressed_bytes": tot_comp,
                "bandwidth_saved_pct": round(bandwidth_saved, 2),
                "avg_compression_ratio": round(avg_ratio, 3),
                "avg_exec_time_ms": round(avg_exec, 3),
                "avg_energy_uj": round(avg_energy, 2),
                "avg_energy_per_raw_byte": round(avg_energy_byte, 4),
                "avg_total_latency_ms": round(avg_total_lat, 3),
                "deadline_adherence_pct": round(deadline_rate, 2)
            }

        # Save runs CSV
        csv_path = os.path.join(self.output_dir, "benchmark_runs.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            if detailed_records:
                writer = csv.DictWriter(f, fieldnames=detailed_records[0].keys())
                writer.writeheader()
                writer.writerows(detailed_records)

        # Save summary JSON
        json_path = os.path.join(self.output_dir, "benchmark_summary.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        self._print_summary_table(summary)
        return summary

    def _print_summary_table(self, summary: Dict[str, Any]) -> None:
        """Pretty-prints comparative benchmark results."""
        print("\n" + "=" * 90)
        print(f"{'Strategy':<24} | {'Ratio':<7} | {'BW Saved':<10} | {'Avg Energy':<12} | {'Energy/Byte':<12} | {'Deadline %':<10}")
        print("-" * 90)
        for strat, s in summary.items():
            print(
                f"{strat:<24} | "
                f"{s['avg_compression_ratio']:>6.2f}x | "
                f"{s['bandwidth_saved_pct']:>8.1f}% | "
                f"{s['avg_energy_uj']:>9.1f} uJ | "
                f"{s['avg_energy_per_raw_byte']:>9.4f} uJ | "
                f"{s['deadline_adherence_pct']:>8.1f}%"
            )
        print("=" * 90 + "\n")


if __name__ == "__main__":
    harness = BenchmarkHarness()
    harness.run_benchmark(num_windows=50)
