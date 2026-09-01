"""
Cloud Outcome Store

Records verified ground-truth edge telemetry outcomes (compression ratio, execution time,
energy proxy, reconstruction error, transmission latency) to persistent CSV logs (logs/outcomes.csv)
and provides statistical aggregation for dashboards and online contextual bandit learners.
"""

import os
import csv
import time
from typing import Dict, Any, List, Optional


class OutcomeStore:
    """
    Persistent outcome recorder and query engine for cloud receiver.
    """

    DEFAULT_LOG_FILE = "logs/outcomes.csv"

    def __init__(self, log_file: str = DEFAULT_LOG_FILE):
        self.log_file = log_file
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Initializes outcomes CSV log directory and header."""
        try:
            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            if not os.path.exists(self.log_file):
                with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp", "window_id", "compressor", "compression_level",
                        "raw_bytes", "compressed_bytes", "ratio", "latency_ms",
                        "energy_uj", "error", "transfer_time_ms", "status"
                    ])
        except Exception:
            pass

    def record_outcome(self, outcome_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Appends an outcome record to the CSV log.
        """
        now = outcome_data.get("timestamp", time.time())
        window_id = outcome_data.get("window_id", 0)
        compressor = outcome_data.get("compressor", "lz4")
        level = outcome_data.get("compression_level", 1)
        raw_bytes = int(outcome_data.get("raw_bytes", 0))
        comp_bytes = int(outcome_data.get("compressed_bytes", 0))
        ratio = float(outcome_data.get("ratio", 1.0))
        latency_ms = float(outcome_data.get("latency_ms", 0.0))
        energy_uj = float(outcome_data.get("energy_uj", 0.0))
        error = float(outcome_data.get("error", 0.0))
        transfer_time = float(outcome_data.get("transfer_time_ms", 0.0))
        status = str(outcome_data.get("status", "verified"))

        row = [
            round(now, 3), window_id, compressor, level,
            raw_bytes, comp_bytes, round(ratio, 4), round(latency_ms, 4),
            round(energy_uj, 2), round(error, 6), round(transfer_time, 3), status
        ]

        try:
            with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception:
            pass

        return {
            "recorded": True,
            "window_id": window_id,
            "compressor": compressor,
            "ratio": ratio,
            "status": status
        }

    def get_recent_outcomes(self, n: int = 50) -> List[Dict[str, Any]]:
        """Reads the most recent n outcome records from the log file."""
        if not os.path.exists(self.log_file):
            return []

        records = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
            return records[-n:]
        except Exception:
            return []

    def get_summary_stats(self) -> Dict[str, Any]:
        """Calculates cumulative aggregate performance statistics."""
        records = self.get_recent_outcomes(n=10000)
        if not records:
            return {
                "total_windows": 0,
                "total_raw_bytes": 0,
                "total_compressed_bytes": 0,
                "overall_bandwidth_saved_pct": 0.0,
                "average_compression_ratio": 1.0,
                "average_latency_ms": 0.0,
                "average_energy_uj": 0.0
            }

        total_raw = sum(int(r.get("raw_bytes", 0)) for r in records)
        total_comp = sum(int(r.get("compressed_bytes", 0)) for r in records)
        ratios = [float(r.get("ratio", 1.0)) for r in records]
        latencies = [float(r.get("latency_ms", 0.0)) for r in records]
        energies = [float(r.get("energy_uj", 0.0)) for r in records]

        saved_pct = 0.0
        if total_raw > 0:
            saved_pct = round((1.0 - (total_comp / total_raw)) * 100.0, 2)

        return {
            "total_windows": len(records),
            "total_raw_bytes": total_raw,
            "total_compressed_bytes": total_comp,
            "overall_bandwidth_saved_pct": saved_pct,
            "average_compression_ratio": round(sum(ratios) / len(ratios), 3) if ratios else 1.0,
            "average_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
            "average_energy_uj": round(sum(energies) / len(energies), 2) if energies else 0.0
        }


if __name__ == "__main__":
    print("=== Testing Cloud Outcome Store ===")
    store = OutcomeStore(log_file="logs/test_outcomes.csv")

    store.record_outcome({
        "window_id": 1,
        "compressor": "lz4",
        "raw_bytes": 7200,
        "compressed_bytes": 1300,
        "ratio": 5.54,
        "latency_ms": 0.85,
        "energy_uj": 1700.0,
        "error": 0.0
    })

    store.record_outcome({
        "window_id": 2,
        "compressor": "zstd",
        "raw_bytes": 7200,
        "compressed_bytes": 480,
        "ratio": 15.0,
        "latency_ms": 1.95,
        "energy_uj": 3900.0,
        "error": 0.0
    })

    stats = store.get_summary_stats()
    print(f"Total Windows:     {stats['total_windows']}")
    print(f"Raw / Compressed:  {stats['total_raw_bytes']}B / {stats['total_compressed_bytes']}B")
    print(f"Bandwidth Saved:   {stats['overall_bandwidth_saved_pct']}%")
    print(f"Average Ratio:     {stats['average_compression_ratio']}x")

    # Clean up test file
    if os.path.exists("logs/test_outcomes.csv"):
        os.remove("logs/test_outcomes.csv")
    print("\nOutcome Store test complete.")

