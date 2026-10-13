"""
Cloud Outcome Store

Records verified ground-truth edge telemetry outcomes (compression ratio, execution time,
energy proxy, reconstruction error, transmission latency) to persistent CSV logs (logs/outcomes.csv)
and provides statistical aggregation for dashboards and online contextual bandit learners.
"""

import os
import csv
import time
import sqlite3
from typing import Dict, Any, List, Optional, Tuple


class OutcomeStore:
    """
    Persistent outcome recorder and query engine for cloud receiver.
    Supports dual-sink storage: local SQLite relational database (logs/outcomes.db)
    and append-only CSV logs (logs/outcomes.csv).
    """

    DEFAULT_LOG_FILE = "logs/outcomes.csv"
    DEFAULT_DB_FILE = "logs/outcomes.db"

    def __init__(self, log_file: str = DEFAULT_LOG_FILE, db_file: Optional[str] = None):
        self.log_file = log_file
        if db_file is None:
            if log_file == self.DEFAULT_LOG_FILE:
                self.db_file = self.DEFAULT_DB_FILE
            else:
                self.db_file = os.path.splitext(log_file)[0] + ".db"
        else:
            self.db_file = db_file
        self._ensure_log_file()
        self._ensure_sqlite_db()

    def _ensure_sqlite_db(self) -> None:
        """Initializes SQLite database and tables."""
        try:
            db_dir = os.path.dirname(self.db_file)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS outcomes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        window_id INTEGER,
                        compressor TEXT,
                        compression_level INTEGER,
                        raw_bytes INTEGER,
                        compressed_bytes INTEGER,
                        ratio REAL,
                        latency_ms REAL,
                        energy_uj REAL,
                        error REAL,
                        transfer_time_ms REAL,
                        status TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bandit_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        window_id INTEGER,
                        codec TEXT,
                        score_error REAL,
                        updated_theta_norm REAL,
                        actual_reward REAL
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_window_id ON outcomes(window_id)")
                conn.commit()
        except Exception:
            pass

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
                        "timestamp", "window_id", "data_type", "criticality",
                        "compressor", "compression_level", "raw_bytes", "compressed_bytes",
                        "ratio", "latency_ms", "energy_uj", "error", "transfer_time_ms", "status"
                    ])
        except Exception:
            pass

    def record_outcome(self, outcome_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Appends an outcome record to the CSV log.
        """
        now = outcome_data.get("timestamp", time.time())
        window_id = outcome_data.get("window_id", 0)
        data_type = outcome_data.get("data_type", "image" if int(outcome_data.get("raw_bytes", 0)) > 100000 else "numeric")
        criticality = outcome_data.get("criticality", "routine")
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
            round(now, 3), window_id, data_type, criticality,
            compressor, level, raw_bytes, comp_bytes, round(ratio, 4),
            round(latency_ms, 4), round(energy_uj, 2), round(error, 6),
            round(transfer_time, 3), status
        ]

        try:
            with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception:
            pass

        # Also persist to SQLite
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO outcomes (
                        timestamp, window_id, compressor, compression_level,
                        raw_bytes, compressed_bytes, ratio, latency_ms,
                        energy_uj, error, transfer_time_ms, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    round(now, 3), window_id, compressor, level,
                    raw_bytes, comp_bytes, round(ratio, 4), round(latency_ms, 4),
                    round(energy_uj, 2), round(error, 6), round(transfer_time, 3), status
                ))
                conn.commit()
        except Exception:
            pass

        return {
            "recorded": True,
            "window_id": window_id,
            "compressor": compressor,
            "ratio": ratio,
            "status": status
        }

    def record_bandit_history(
        self,
        window_id: int,
        codec: str,
        score_error: float,
        updated_theta_norm: float,
        actual_reward: float = 0.0
    ) -> bool:
        """Records an online bandit gradient learning step into SQLite."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO bandit_history (
                        timestamp, window_id, codec, score_error,
                        updated_theta_norm, actual_reward
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    round(time.time(), 3), window_id, codec,
                    round(score_error, 4), round(updated_theta_norm, 4), round(actual_reward, 4)
                ))
                conn.commit()
            return True
        except Exception:
            return False

    def query_db(self, query: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        """Executes a custom SQL query against the SQLite outcomes database."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def get_recent_outcomes(self, n: int = 50) -> List[Dict[str, Any]]:
        """Reads the most recent n outcome records from the log file (with SQLite fallback)."""
        if os.path.exists(self.log_file):
            records = []
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        records.append(row)
                return records[-n:]
            except Exception:
                pass

        # Fallback to SQLite
        sql_rows = self.query_db("SELECT * FROM outcomes ORDER BY id DESC LIMIT ?", (n,))
        if sql_rows:
            return list(reversed(sql_rows))
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

