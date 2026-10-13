"""
Stage 4: Self-Calibrating Hardware Profiler (Objective O4) & Controller Overhead Reporter (Section 2.12)

Maintains a live-updated calibration table of real, measured costs for each candidate
(compressor, level) configuration conditioned on context (data type & entropy bucket):
  C_bar_k <- C_bar_k + beta * (C_measured - C_bar_k)

Continuously refreshed from real on-device measurements:
- Energy drawn (via SoC electrical/energy model and execution time)
- CPU load during compression
- Radio wake-time observed during transmission
- Reconstruction error

Also reports controller computational & memory overhead (Section 2.12):
- Controller CPU time & RAM consumed by Stages 2-5 on Raspberry Pi
- Worst-case observed decision latency across all windows
"""

import os
import csv
import time
from typing import Dict, Any, Optional, Tuple, List
import psutil

from edge.config import PROFILER_BETA


class HardwareProfilerStage:
    """
    Stage 4 Self-Calibrating Hardware Profiler (Objective O4).
    Maintains adaptive empirical cost tables and tracks controller runtime overhead.
    """

    CANDIDATE_CODECS = ["lz4", "zstd", "bzip2", "gzip", "delta_zlib", "none"]

    # Baseline seed priors per KB on ARM Cortex-A53 / BCM2837 SoC
    SEED_PROFILES = {
        "lz4":        {"ratio": 4.5, "latency_ms_per_kb": 0.05, "energy_uj_per_kb": 50.0,  "error": 0.000000, "level": 1},
        "zstd":       {"ratio": 12.0, "latency_ms_per_kb": 0.30, "energy_uj_per_kb": 350.0, "error": 0.000000, "level": 3},
        "bzip2":      {"ratio": 10.0, "latency_ms_per_kb": 0.50, "energy_uj_per_kb": 600.0, "error": 0.000000, "level": 9},
        "gzip":       {"ratio": 6.5,  "latency_ms_per_kb": 0.25, "energy_uj_per_kb": 300.0, "error": 0.000000, "level": 6},
        "delta_zlib": {"ratio": 8.0,  "latency_ms_per_kb": 0.20, "energy_uj_per_kb": 250.0, "error": 0.000000, "level": 6},
        "none":       {"ratio": 1.0,  "latency_ms_per_kb": 0.001, "energy_uj_per_kb": 1.0,   "error": 0.000000, "level": 0},
    }

    CONTEXT_BUCKETS = [
        "numeric_low",    # H < 1.0
        "numeric_med",    # 1.0 <= H <= 2.5
        "numeric_high",   # H > 2.5
        "text_med",       # text stream
        "image_med"       # camera frame
    ]

    def __init__(
        self,
        beta: float = PROFILER_BETA,
        overhead_log_file: str = "logs/controller_overhead.csv"
    ):
        self.beta = float(beta)
        self.overhead_log_file = overhead_log_file
        self.process = psutil.Process()

        # Initialize calibration table for each context bucket
        self.calibration_table: Dict[str, Dict[str, Dict[str, float]]] = {}
        self._init_calibration_table()

        # Controller overhead tracking (Section 2.12)
        self.total_controller_windows = 0
        self.worst_case_decision_latency_ms: float = 0.0
        self._window_start_cpu_time: float = 0.0
        self._window_start_perf: float = 0.0

        self._ensure_log_file()

    def _init_calibration_table(self) -> None:
        """Initializes calibration table with seed empirical profiles across context buckets."""
        for bucket in self.CONTEXT_BUCKETS:
            self.calibration_table[bucket] = {}
            for codec, seed in self.SEED_PROFILES.items():
                entry = dict(seed)
                # Scale initial ratio estimates based on bucket entropy prior
                if "low" in bucket:
                    entry["ratio"] = round(seed["ratio"] * 1.3, 2)
                    if codec == "delta_zlib":
                        entry["ratio"] = round(entry["ratio"] * 1.5, 2)
                elif "high" in bucket:
                    entry["ratio"] = max(1.05, round(seed["ratio"] * 0.5, 2))
                entry["updates_count"] = 0
                self.calibration_table[bucket][codec] = entry

    def _ensure_log_file(self) -> None:
        """Ensures directory and header exist for controller overhead metrics."""
        try:
            log_dir = os.path.dirname(self.overhead_log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            if not os.path.exists(self.overhead_log_file):
                with open(self.overhead_log_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp", "window_id", "controller_cpu_time_ms",
                        "controller_ram_mb", "decision_latency_ms",
                        "worst_case_decision_latency_ms"
                    ])
        except Exception:
            pass

    @staticmethod
    def get_context_bucket(features: Optional[Dict[str, Any]]) -> str:
        """Categorizes current window into a discrete context bucket."""
        if not features:
            return "numeric_med"
        data_type = str(features.get("data_type", "numeric")).lower()
        entropy = float(features.get("entropy", 1.5))

        if data_type == "image":
            return "image_med"
        if data_type == "text":
            return "text_med"

        if entropy < 1.0:
            return "numeric_low"
        elif entropy > 2.5:
            return "numeric_high"
        return "numeric_med"

    def get_calibrated_profile(
        self,
        codec: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Retrieves the live calibrated cost estimates for a given compressor option
        under current workload context.
        """
        bucket = self.get_context_bucket(context)
        bucket_data = self.calibration_table.get(bucket, self.calibration_table["numeric_med"])
        profile = bucket_data.get(codec, self.SEED_PROFILES.get(codec, self.SEED_PROFILES["lz4"]))
        return dict(profile)

    def update_calibration(
        self,
        codec: str,
        measured: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Applies Moving Average Calibration Update (Formula from Architecture PDF):
          C_bar_k <- C_bar_k + beta * (C_measured - C_bar_k)

        Inputs:
          measured: {"ratio": float, "latency_ms": float, "energy_uj": float, "error": float, "raw_size_bytes": int}
        """
        bucket = self.get_context_bucket(context)
        if bucket not in self.calibration_table:
            bucket = "numeric_med"
        if codec not in self.calibration_table[bucket]:
            return {}

        current = self.calibration_table[bucket][codec]

        raw_size = max(1, int(measured.get("raw_size_bytes", measured.get("raw_bytes", 1024))))
        kb = raw_size / 1024.0

        meas_ratio = float(measured.get("ratio", current["ratio"]))
        meas_lat_total = float(measured.get("latency_ms", measured.get("execution_time_ms", current["latency_ms_per_kb"] * kb)))
        meas_energy_total = float(measured.get("energy_uj", current["energy_uj_per_kb"] * kb))
        meas_error = float(measured.get("error", measured.get("reconstruction_error", current["error"])))

        # Normalize per-KB
        meas_lat_per_kb = max(0.0001, meas_lat_total / max(0.1, kb))
        meas_energy_per_kb = max(0.1, meas_energy_total / max(0.1, kb))

        # Formula update: C_bar <- C_bar + beta * (C_meas - C_bar)
        beta = self.beta
        new_ratio = current["ratio"] + beta * (meas_ratio - current["ratio"])
        new_lat = current["latency_ms_per_kb"] + beta * (meas_lat_per_kb - current["latency_ms_per_kb"])
        new_energy = current["energy_uj_per_kb"] + beta * (meas_energy_per_kb - current["energy_uj_per_kb"])
        new_error = current["error"] + beta * (meas_error - current["error"])

        current["ratio"] = round(new_ratio, 4)
        current["latency_ms_per_kb"] = round(new_lat, 4)
        current["energy_uj_per_kb"] = round(new_energy, 2)
        current["error"] = round(new_error, 6)
        current["updates_count"] = current.get("updates_count", 0) + 1

        return dict(current)

    def get_calibration_table(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Returns the full live calibration table snapshot."""
        return self.calibration_table

    # -------------------------------------------------------------------------
    # Controller Overhead Reporting (Section 2.12)
    # -------------------------------------------------------------------------

    def start_controller_window(self) -> None:
        """Starts timing the controller overhead across Stages 2–5."""
        self._window_start_perf = time.perf_counter()
        try:
            times = self.process.cpu_times()
            self._window_start_cpu_time = times.user + times.system
        except Exception:
            self._window_start_cpu_time = 0.0

    def record_controller_overhead(
        self,
        window_id: int,
        decision_latency_ms: float
    ) -> Dict[str, Any]:
        """
        Calculates and records the controller's computational and memory overhead:
        - CPU time consumed by Stages 2–5
        - RAM resident memory (RSS MB)
        - Worst-case observed decision latency
        """
        self.total_controller_windows += 1

        # Track worst-case observed decision latency
        if decision_latency_ms > self.worst_case_decision_latency_ms:
            self.worst_case_decision_latency_ms = round(decision_latency_ms, 3)

        # Compute controller CPU time
        cpu_time_ms = 0.0
        try:
            times = self.process.cpu_times()
            end_cpu = times.user + times.system
            cpu_time_ms = max(0.0, (end_cpu - self._window_start_cpu_time) * 1000.0)
        except Exception:
            cpu_time_ms = max(0.0, (time.perf_counter() - self._window_start_perf) * 1000.0)

        # Memory usage in MB (Resident Set Size)
        ram_mb = 0.0
        try:
            mem = self.process.memory_info()
            ram_mb = round(mem.rss / (1024.0 * 1024.0), 2)
        except Exception:
            pass

        report = {
            "window_id": window_id,
            "controller_cpu_time_ms": round(cpu_time_ms, 3),
            "controller_ram_mb": ram_mb,
            "decision_latency_ms": round(decision_latency_ms, 3),
            "worst_case_decision_latency_ms": self.worst_case_decision_latency_ms
        }

        # Persist to log file
        try:
            with open(self.overhead_log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    round(time.time(), 3),
                    window_id,
                    report["controller_cpu_time_ms"],
                    report["controller_ram_mb"],
                    report["decision_latency_ms"],
                    report["worst_case_decision_latency_ms"]
                ])
        except Exception:
            pass

        return report


if __name__ == "__main__":
    print("=== Testing Stage 4: Self-Calibrating Hardware Profiler (Objective O4) ===")
    profiler = HardwareProfilerStage(beta=0.15)

    context = {"data_type": "numeric", "entropy": 0.5}
    initial_zstd = profiler.get_calibrated_profile("zstd", context)
    print(f"Initial calibrated ZSTD profile in 'numeric_low':")
    print(f"  Ratio: {initial_zstd['ratio']}x | Latency: {initial_zstd['latency_ms_per_kb']} ms/KB | Energy: {initial_zstd['energy_uj_per_kb']} uJ/KB")

    # Simulate real feedback outcome from Stage 8 (Window execution measured on device)
    measured_feedback = {
        "raw_size_bytes": 4096,
        "ratio": 14.5,
        "latency_ms": 1.10,
        "energy_uj": 1200.0,
        "error": 0.000000
    }
    updated_zstd = profiler.update_calibration("zstd", measured_feedback, context)
    print(f"\nAfter Stage 8 real measurement feedback update (beta=0.15):")
    print(f"  Ratio: {updated_zstd['ratio']}x | Latency: {updated_zstd['latency_ms_per_kb']} ms/KB | Energy: {updated_zstd['energy_uj_per_kb']} uJ/KB | Updates: {updated_zstd['updates_count']}")

    # Test Section 2.12 Overhead Reporting
    profiler.start_controller_window()
    time.sleep(0.01)  # simulate decision execution
    overhead = profiler.record_controller_overhead(window_id=1, decision_latency_ms=0.85)
    print(f"\nController Overhead (Section 2.12):")
    print(f"  CPU Time: {overhead['controller_cpu_time_ms']} ms | RAM: {overhead['controller_ram_mb']} MB | Worst Latency: {overhead['worst_case_decision_latency_ms']} ms")
