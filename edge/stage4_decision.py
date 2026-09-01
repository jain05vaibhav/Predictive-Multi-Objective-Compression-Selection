"""
Stage 4: Multi-Objective Decision Engine

Selects the Pareto-optimal compression algorithm (and transmission action) for each
window by solving an error-bounded multi-objective optimization problem:
  Score(c) = w1 * Ratio_norm - w2 * Energy_norm - w3 * Latency_norm - w4 * Error_norm

Dynamically adapts objective weights under thermal stress, undervoltage, and network
degradation to prevent edge node thermal throttling and minimize transmission latency.
"""

import os
import csv
import time
from typing import Dict, Any, Tuple, List, Optional
from edge.config import (
    WEIGHT_W1,
    WEIGHT_W2,
    WEIGHT_W3,
    WEIGHT_W4,
    EPSILON
)


class DecisionStage:
    """
    Stage 4 Multi-Objective Decision Engine.
    Evaluates candidate codecs and selects winning strategy with adaptive Pareto scoring.
    """

    CANDIDATE_CODECS = ["lz4", "zstd", "bzip2", "gzip", "delta_zlib", "none"]

    # Baseline empirical profile models on ARM Cortex-A53 (per KB of telemetry payload)
    CODEC_PROFILES = {
        "lz4":        {"ratio_base": 4.5, "latency_ms_per_kb": 0.15, "energy_uj_per_kb": 250.0, "error": 0.0, "level": 1},
        "zstd":       {"ratio_base": 12.0, "latency_ms_per_kb": 0.40, "energy_uj_per_kb": 600.0, "error": 0.0, "level": 3},
        "bzip2":      {"ratio_base": 10.0, "latency_ms_per_kb": 0.50, "energy_uj_per_kb": 750.0, "error": 0.0, "level": 9},
        "gzip":       {"ratio_base": 6.5,  "latency_ms_per_kb": 0.35, "energy_uj_per_kb": 500.0, "error": 0.0, "level": 6},
        "delta_zlib": {"ratio_base": 7.5,  "latency_ms_per_kb": 0.30, "energy_uj_per_kb": 450.0, "error": 0.0, "level": 6},
        "none":       {"ratio_base": 1.0,  "latency_ms_per_kb": 0.001, "energy_uj_per_kb": 1.0,  "error": 0.0, "level": 0},
    }

    def __init__(
        self,
        w1: float = WEIGHT_W1,
        w2: float = WEIGHT_W2,
        w3: float = WEIGHT_W3,
        w4: float = WEIGHT_W4,
        epsilon: float = EPSILON,
        log_file: str = "logs/decisions.csv"
    ):
        self.w1 = float(w1)
        self.w2 = float(w2)
        self.w3 = float(w3)
        self.w4 = float(w4)
        self.epsilon = float(epsilon)
        self.log_file = log_file

        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Initializes decision logging directory and CSV header."""
        try:
            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            if not os.path.exists(self.log_file):
                with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp", "window_id", "chosen_compressor", "compression_level",
                        "transmit_or_defer", "composite_score", "entropy", "variance",
                        "predicted_cpu_temp", "predicted_cpu_load", "predicted_bw_kbps",
                        "throttling_risk", "w1_ratio", "w2_energy", "w3_latency", "w4_error"
                    ])
        except Exception:
            pass

    def adapt_weights(
        self,
        predictions: Dict[str, Any],
        features: Dict[str, Any]
    ) -> Tuple[float, float, float, float]:
        """
        Dynamically adapts objective weights based on environmental stressors:
        - High Temperature / Throttling Risk -> Boost w2 (Energy) & w3 (Latency) to protect SoC.
        - Low Bandwidth (< 300 kbps) -> Boost w1 (Ratio) to shrink wireless packets.
        - High Redundancy (Low Entropy H < 0.5) -> Boost w1 (Ratio).
        """
        w1 = self.w1
        w2 = self.w2
        w3 = self.w3
        w4 = self.w4

        temp_risk = predictions.get("is_throttling_risk", False)
        temp_c = predictions.get("predicted_cpu_temp", 45.0)
        bw_kbps = predictions.get("predicted_bandwidth_kbps", 1000.0)
        entropy = features.get("entropy", 2.0)

        # 1. Thermal or Undervoltage Stress Adaptation
        if temp_risk or temp_c >= 70.0:
            w2 += 0.35  # Heavily penalize energy / CPU draw
            w3 += 0.20  # Penalize high compression latency
            w1 = max(0.10, w1 - 0.35)
        elif temp_c >= 60.0:
            w2 += 0.15
            w3 += 0.10
            w1 = max(0.15, w1 - 0.15)

        # 2. Network Bandwidth Depletion Adaptation
        if bw_kbps < 200.0:
            w1 += 0.40  # Heavily prioritize compression ratio to shrink transmission
            w3 = max(0.05, w3 - 0.15)
            w2 = max(0.10, w2 - 0.15)
        elif bw_kbps < 500.0:
            w1 += 0.20
            w3 = max(0.10, w3 - 0.10)

        # 3. Data Entropy Context
        if entropy < 0.2:
            w1 += 0.10  # Maximum potential for compression

        # Normalize weights so sum(w) = 1.0
        total_w = max(0.001, w1 + w2 + w3 + w4)
        return (
            round(w1 / total_w, 4),
            round(w2 / total_w, 4),
            round(w3 / total_w, 4),
            round(w4 / total_w, 4)
        )

    def evaluate_codec_utility(
        self,
        codec: str,
        features: Dict[str, Any],
        predictions: Dict[str, Any],
        weights: Tuple[float, float, float, float]
    ) -> float:
        """
        Computes composite normalized Pareto utility score for a given candidate codec.
        """
        w1, w2, w3, w4 = weights
        profile = self.CODEC_PROFILES.get(codec, self.CODEC_PROFILES["lz4"])
        entropy = features.get("entropy", 2.0)

        # Expected ratio modulated by entropy H (0.0 <= H <= 4.0)
        # Low entropy -> higher actual ratio; High entropy -> lower ratio
        entropy_factor = max(0.2, (4.0 - entropy) / 2.0)
        expected_ratio = profile["ratio_base"] * (1.0 if codec == "none" else entropy_factor)
        if codec == "delta_zlib" and entropy < 0.5:
            expected_ratio *= 1.5  # Delta encoding excels on low-entropy repetitive series

        # Normalize metrics to [0, 1] range across candidates
        ratio_norm = min(1.0, expected_ratio / 20.0)
        energy_norm = min(1.0, profile["energy_uj_per_kb"] / 1000.0)
        latency_norm = min(1.0, profile["latency_ms_per_kb"] / 1.0)
        error_norm = profile["error"]

        score = (w1 * ratio_norm) - (w2 * energy_norm) - (w3 * latency_norm) - (w4 * error_norm)
        return round(score, 4)

    def select_strategy(
        self,
        features: Dict[str, Any],
        predictions: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main decision engine entry point.
        Evaluates candidate codecs, applies adapted Pareto utility scoring, and logs decision.
        """
        constraints = constraints or {}
        max_error = constraints.get("epsilon", self.epsilon)
        window_id = features.get("window_id", 0)

        # 1. Adapt weights dynamically
        adapted_weights = self.adapt_weights(predictions, features)

        # 2. Evaluate all eligible candidates (satisfying error <= epsilon)
        scores = {}
        for codec in self.CANDIDATE_CODECS:
            profile = self.CODEC_PROFILES[codec]
            if profile["error"] <= max_error:
                scores[codec] = self.evaluate_codec_utility(codec, features, predictions, adapted_weights)

        # 3. Select winning codec (argmax utility)
        if not scores:
            chosen_codec = "lz4"
            winning_score = 0.5
        else:
            chosen_codec = max(scores, key=lambda k: scores[k])
            winning_score = scores[chosen_codec]

        chosen_level = self.CODEC_PROFILES.get(chosen_codec, {}).get("level", 1)

        # 4. Determine transmission action (transmit vs defer)
        bw = predictions.get("predicted_bandwidth_kbps", 1000.0)
        action = "defer" if bw < 30.0 else "transmit"

        decision_result = {
            "window_id": window_id,
            "chosen_compressor": chosen_codec,
            "compression_level": chosen_level,
            "transmit_or_defer": action,
            "composite_score": winning_score,
            "scores_breakdown": scores,
            "adapted_weights": {
                "w1_ratio": adapted_weights[0],
                "w2_energy": adapted_weights[1],
                "w3_latency": adapted_weights[2],
                "w4_error": adapted_weights[3]
            }
        }

        # 5. Log decision context for post-60% learning / contextual bandits
        self._log_decision(decision_result, features, predictions, adapted_weights)

        return decision_result

    def _log_decision(
        self,
        decision: Dict[str, Any],
        features: Dict[str, Any],
        predictions: Dict[str, Any],
        weights: Tuple[float, float, float, float]
    ) -> None:
        """Appends decision record to CSV log."""
        try:
            with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    round(time.time(), 3),
                    decision.get("window_id", 0),
                    decision.get("chosen_compressor", "lz4"),
                    decision.get("compression_level", 1),
                    decision.get("transmit_or_defer", "transmit"),
                    decision.get("composite_score", 0.0),
                    round(features.get("entropy", 0.0), 4),
                    round(features.get("variance", 0.0), 4),
                    round(predictions.get("predicted_cpu_temp", 0.0), 2),
                    round(predictions.get("predicted_cpu_load", 0.0), 2),
                    round(predictions.get("predicted_bandwidth_kbps", 0.0), 2),
                    predictions.get("is_throttling_risk", False),
                    weights[0], weights[1], weights[2], weights[3]
                ])
        except Exception:
            pass


if __name__ == "__main__":
    print("=== Testing Stage 4: Multi-Objective Decision Engine ===")
    decision_engine = DecisionStage()

    # Scenario 1: Normal Routine Telemetry (Balanced weights)
    feat_normal = {"window_id": 1, "entropy": 1.2, "variance": 0.05}
    pred_normal = {"predicted_cpu_temp": 42.0, "predicted_cpu_load": 15.0, "predicted_bandwidth_kbps": 1000.0, "is_throttling_risk": False}
    dec_normal = decision_engine.select_strategy(feat_normal, pred_normal)
    print("\n[Scenario 1: Normal Operation]")
    print(f"  -> Chosen Codec:     {dec_normal['chosen_compressor']} (Level: {dec_normal['compression_level']})")
    print(f"  -> Action:           {dec_normal['transmit_or_defer']}")
    print(f"  -> Score Breakdown:  {dec_normal['scores_breakdown']}")

    # Scenario 2: Thermal Stress on Raspberry Pi 3B+ (SoC Temp = 75 deg C, Throttling Risk)
    feat_hot = {"window_id": 2, "entropy": 1.5, "variance": 0.1}
    pred_hot = {"predicted_cpu_temp": 75.0, "predicted_cpu_load": 90.0, "predicted_bandwidth_kbps": 1000.0, "is_throttling_risk": True}
    dec_hot = decision_engine.select_strategy(feat_hot, pred_hot)
    print("\n[Scenario 2: Thermal Stress on SoC (75 deg C)]")

    print(f"  -> Adapted Weights:  Energy={dec_hot['adapted_weights']['w2_energy']}, Latency={dec_hot['adapted_weights']['w3_latency']}, Ratio={dec_hot['adapted_weights']['w1_ratio']}")
    print(f"  -> Chosen Codec:     {dec_hot['chosen_compressor']} (Fast, Low CPU)")
    print(f"  -> Score Breakdown:  {dec_hot['scores_breakdown']}")

    # Scenario 3: Bandwidth Depletion (Weak signal / cell edge: 100 kbps)
    feat_low_bw = {"window_id": 3, "entropy": 0.8, "variance": 0.02}
    pred_low_bw = {"predicted_cpu_temp": 45.0, "predicted_cpu_load": 20.0, "predicted_bandwidth_kbps": 100.0, "is_throttling_risk": False}
    dec_low_bw = decision_engine.select_strategy(feat_low_bw, pred_low_bw)
    print("\n[Scenario 3: Bandwidth Constrained (100 kbps)]")
    print(f"  -> Adapted Weights:  Ratio={dec_low_bw['adapted_weights']['w1_ratio']}, Latency={dec_low_bw['adapted_weights']['w3_latency']}")
    print(f"  -> Chosen Codec:     {dec_low_bw['chosen_compressor']} (High Compression Ratio)")
    print(f"  -> Score Breakdown:  {dec_low_bw['scores_breakdown']}")

    print("\nStage 4 Decision Engine test complete.")

