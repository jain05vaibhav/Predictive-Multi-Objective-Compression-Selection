"""
Cloud Database Interface (Objective O4, Phase 16)

Provides ACID SQLite storage and query interfaces for edge telemetry outcomes,
codec performance statistics, Pareto frontier computation, and online bandit history.
"""

import os
import sqlite3
from typing import Dict, Any, List, Optional, Tuple


DEFAULT_DB_PATH = "logs/outcomes.db"


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Returns an active SQLite connection with row dict factories."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def query_outcomes(
    limit: int = 100,
    offset: int = 0,
    compressor: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH
) -> List[Dict[str, Any]]:
    """Fetches verified outcome records with optional codec filtering."""
    if not os.path.exists(db_path):
        return []

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if compressor:
            cursor.execute(
                "SELECT * FROM outcomes WHERE compressor = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (compressor, limit, offset)
            )
        else:
            cursor.execute(
                "SELECT * FROM outcomes ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        return [dict(row) for row in cursor.fetchall()]


def query_codec_performance_summary(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Computes aggregated performance summary grouped by compression algorithm:
    Average ratio, average latency (ms), average energy (uJ), total raw bytes, and count.
    """
    if not os.path.exists(db_path):
        return []

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                compressor,
                COUNT(*) as sample_count,
                ROUND(AVG(ratio), 3) as avg_ratio,
                ROUND(AVG(latency_ms), 3) as avg_latency_ms,
                ROUND(AVG(energy_uj), 2) as avg_energy_uj,
                ROUND(AVG(error), 6) as avg_error,
                SUM(raw_bytes) as total_raw_bytes,
                SUM(compressed_bytes) as total_compressed_bytes
            FROM outcomes
            GROUP BY compressor
            ORDER BY avg_ratio DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def query_bandit_history(limit: int = 100, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves online contextual bandit weight update history."""
    if not os.path.exists(db_path):
        return []

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM bandit_history ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]


def compute_pareto_points(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Calculates empirical Pareto frontier points (maximizing Compression Ratio, minimizing Energy).
    """
    summary = query_codec_performance_summary(db_path)
    if not summary:
        return []

    # Sort descending by ratio
    sorted_codecs = sorted(summary, key=lambda x: x["avg_ratio"], reverse=True)
    pareto_set = []
    min_energy_seen = float("inf")

    for c in sorted_codecs:
        energy = c["avg_energy_uj"]
        if energy < min_energy_seen:
            pareto_set.append(c)
            min_energy_seen = energy

    return pareto_set


if __name__ == "__main__":
    print("=== Testing Cloud Database Queries ===")
    summary = query_codec_performance_summary()
    print(f"Aggregated Codec Stats: {len(summary)} algorithms found")
    for s in summary:
        print(f"  {s['compressor']:<12}: Ratio={s['avg_ratio']}x, Latency={s['avg_latency_ms']}ms, Energy={s['avg_energy_uj']}uJ")
