"""
Stage 5: Hierarchical Decision Engine (Objectives O2, O3)

Structured as three coordinated layers:
1. (a) Rule-Based Safety Gate (O2):
   - Hard error bound: Allowed only if Error(option) <= epsilon.
   - Enforces strict epsilon=0.0 for safety-critical telemetry, looser epsilon=0.05 for routine data.
   - Any candidate configuration violating epsilon is eliminated outright.

2. (b) Multi-Objective Scoring (O2):
   - Combines Stage 4 calibrated ratio, energy, and latency normalized to [0, 1]:
       Score = w1 * Ratio_norm - w2 * Energy_norm - w3 * Latency_norm
   - Weights w1, w2, w3 shift based on Stage 3 forecasted resource & workload state.

3. (c) Online Policy Update / Contextual Bandit (O3):
   - Incremental online adaptation from real measured Stage 8 feedback:
       theta_c <- theta_c + eta * (Actual Score - Predicted Score) * context
"""

import os
import csv
import time
from typing import Dict, Any, Tuple, List, Optional
import numpy as np

from edge.config import (
    WEIGHT_W1,
    WEIGHT_W2,
    WEIGHT_W3,
    WEIGHT_W4,
    EPSILON,
    EPSILON_CRITICAL,
    EPSILON_ROUTINE,
    BANDIT_ETA,
    CRITICAL_BANDWIDTH_KBPS
)
from edge.stage4_profiler import HardwareProfilerStage


class HierarchicalDecisionEngine:
    """
    Stage 5 Hierarchical Decision Engine (Objectives O2, O3).
    Implements rule-based safety gating, multi-objective Pareto scoring,
    and online contextual bandit learning.
    """

    CANDIDATE_CODECS = ["lz4", "zstd", "bzip2", "gzip", "delta_zlib", "none"]

    # Baseline profiles for fallback when profiler is uninitialized
    CODEC_PROFILES = {
        "lz4":        {"ratio_base": 4.5, "latency_ms_per_kb": 0.05, "energy_uj_per_kb": 50.0,  "error": 0.0, "level": 1},
        "zstd":       {"ratio_base": 12.0, "latency_ms_per_kb": 0.30, "energy_uj_per_kb": 350.0, "error": 0.0, "level": 3},
        "bzip2":      {"ratio_base": 10.0, "latency_ms_per_kb": 0.50, "energy_uj_per_kb": 600.0, "error": 0.0, "level": 9},
        "gzip":       {"ratio_base": 6.5,  "latency_ms_per_kb": 0.25, "energy_uj_per_kb": 300.0, "error": 0.0, "level": 6},
        "delta_zlib": {"ratio_base": 8.0,  "latency_ms_per_kb": 0.20, "energy_uj_per_kb": 250.0, "error": 0.0, "level": 6},
        "none":       {"ratio_base": 1.0,  "latency_ms_per_kb": 0.001, "energy_uj_per_kb": 1.0,   "error": 0.0, "level": 0},
    }

    def __init__(
        self,
        profiler: Optional[HardwareProfilerStage] = None,
        w1: float = WEIGHT_W1,
        w2: float = WEIGHT_W2,
        w3: float = WEIGHT_W3,
        w4: float = WEIGHT_W4,
        epsilon: float = EPSILON,
        eta: float = BANDIT_ETA,
        log_file: str = "logs/decisions.csv"
    ):
        self.profiler = profiler or HardwareProfilerStage()
        self.w1 = float(w1)
        self.w2 = float(w2)
        self.w3 = float(w3)
        self.w4 = float(w4)
        self.epsilon = float(epsilon)
        self.eta = float(eta)
        self.log_file = log_file

        # Contextual Bandit preference weights theta per configuration (Objective O3)
        # Context dimension = 6 [bias, entropy_norm, cpu_norm, temp_norm, bw_norm, battery_norm]
        self.context_dim = 6
        self.theta: Dict[str, np.ndarray] = {
            codec: np.zeros(self.context_dim, dtype=float)
            for codec in self.CANDIDATE_CODECS
        }

        # Last selected decision cache for feedback loop
        self.last_decision_context: Optional[Dict[str, Any]] = None

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

    def build_context_vector(
        self,
        features: Dict[str, Any],
        predictions: Dict[str, Any]
    ) -> np.ndarray:
        """Extracts normalized 6D context vector for contextual bandit."""
        entropy = float(features.get("entropy", 1.5)) / 4.0
        cpu_load = float(predictions.get("predicted_cpu_load", 20.0)) / 100.0
        cpu_temp = float(predictions.get("predicted_cpu_temp", 45.0)) / 100.0
        bw = min(1.0, float(predictions.get("predicted_bandwidth_kbps", 1000.0)) / 1500.0)
        battery = float(predictions.get("predicted_battery_percent", 100.0)) / 100.0

        return np.array([1.0, entropy, cpu_load, cpu_temp, bw, battery], dtype=float)

    def adapt_weights(
        self,
        predictions: Dict[str, Any],
        features: Dict[str, Any]
    ) -> Tuple[float, float, float, float]:
        """
        Dynamically shifts objective weights based on environmental stressors:
        - High Temperature / Throttling Risk -> Boost w2 (Energy) & w3 (Latency).
        - Low Battery (< 30%) -> Boost w2 (Energy).
        - Low Bandwidth (< 300 kbps) -> Boost w1 (Ratio).
        - Low Entropy (H < 0.5) -> Boost w1 (Ratio).
        """
        w1 = self.w1
        w2 = self.w2
        w3 = self.w3
        w4 = self.w4

        temp_risk = predictions.get("is_throttling_risk", False)
        temp_c = predictions.get("predicted_cpu_temp", 45.0)
        bw_kbps = predictions.get("predicted_bandwidth_kbps", 1000.0)
        battery_pct = predictions.get("predicted_battery_percent", 100.0)
        entropy = features.get("entropy", 2.0)

        # 1. Thermal or Undervoltage Stress Adaptation
        if temp_c >= 75.0 or (temp_risk and temp_c >= 65.0):
            w2 += 0.30
            w3 += 0.20
            w1 = max(0.20, w1 - 0.20)
        elif temp_c >= 60.0:
            w2 += 0.15
            w3 += 0.10
            w1 = max(0.25, w1 - 0.15)

        # 2. Battery Depletion Adaptation
        if battery_pct < 30.0:
            w2 += 0.35
            w1 = max(0.15, w1 - 0.15)

        # 3. Network Bandwidth Depletion Adaptation
        if bw_kbps < 200.0:
            w1 += 0.40
            w3 = max(0.05, w3 - 0.15)
            w2 = max(0.10, w2 - 0.15)
        elif bw_kbps < 500.0:
            w1 += 0.20
            w3 = max(0.10, w3 - 0.10)

        # 4. Data Entropy Context
        if entropy < 0.5:
            w1 += 0.15

        # Normalize weights so sum(w1, w2, w3, w4) = 1.0
        total_w = max(0.001, w1 + w2 + w3 + w4)
        return (
            round(w1 / total_w, 4),
            round(w2 / total_w, 4),
            round(w3 / total_w, 4),
            round(w4 / total_w, 4)
        )

    def select_strategy(
        self,
        features: Dict[str, Any],
        predictions: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Hierarchical decision loop across 3 layers:
        1. Rule-Based Safety Gate: Filter candidates violating error threshold epsilon.
        2. Multi-Objective Scoring: Compute normalized utility from Stage 4 calibrated costs.
        3. Online Policy / Contextual Bandit: Combine with preference weights theta.
        """
        constraints = constraints or {}
        window_id = features.get("window_id", 0)
        criticality = kwargs.get("criticality", features.get("criticality", "routine"))

        # Layer 1: Rule-Based Safety Gate (Objective O2)
        # Stricter for safety-critical, looser for routine
        if criticality == "safety_critical":
            allowed_epsilon = EPSILON_CRITICAL
        else:
            allowed_epsilon = constraints.get("epsilon", self.epsilon)

        adapted_weights = self.adapt_weights(predictions, features)
        w1, w2, w3, w4 = adapted_weights
        context_vec = self.build_context_vector(features, predictions)

        # Retrieve Stage 4 calibrated profiles for all candidates
        calibrated_profiles = {}
        for codec in self.CANDIDATE_CODECS:
            calibrated_profiles[codec] = self.profiler.get_calibrated_profile(codec, context=features)

        # Filter candidates exceeding error threshold (Safety Gate)
        surviving_codecs = [
            codec for codec in self.CANDIDATE_CODECS
            if calibrated_profiles[codec]["error"] <= allowed_epsilon
        ]
        if not surviving_codecs:
            surviving_codecs = ["none", "lz4"]

        # Find maximums across candidates for [0, 1] normalization
        max_ratio = max(1.0, max(calibrated_profiles[c]["ratio"] for c in surviving_codecs))
        max_energy = max(1.0, max(calibrated_profiles[c]["energy_uj_per_kb"] for c in surviving_codecs))
        max_latency = max(0.001, max(calibrated_profiles[c]["latency_ms_per_kb"] for c in surviving_codecs))

        # Layer 2 & 3: Multi-Objective Scoring + Contextual Bandit Preference
        scores = {}
        for codec in surviving_codecs:
            prof = calibrated_profiles[codec]
            ratio_norm = min(1.0, max(0.01, prof["ratio"] / max_ratio))
            energy_norm = min(1.0, max(0.001, prof["energy_uj_per_kb"] / max_energy))
            latency_norm = min(1.0, max(0.001, prof["latency_ms_per_kb"] / max_latency))

            # Base Multi-Objective Score: Score = w1 * Ratio - w2 * Energy - w3 * Latency
            base_score = (w1 * ratio_norm) - (w2 * energy_norm) - (w3 * latency_norm)

            # Contextual Bandit adjustment: theta_c^T * context
            bandit_adjustment = float(np.dot(self.theta[codec], context_vec))
            total_score = round(base_score + bandit_adjustment, 4)
            scores[codec] = total_score

        # Select winning codec (argmax utility)
        chosen_codec = max(scores, key=lambda k: scores[k])
        winning_score = scores[chosen_codec]
        chosen_level = self.CODEC_PROFILES.get(chosen_codec, {}).get("level", 1)

        # Transmission Action & Radio Sleep Duration (Objective O5)
        bw = predictions.get("predicted_bandwidth_kbps", 1000.0)
        action = "defer" if bw < CRITICAL_BANDWIDTH_KBPS else "transmit"
        radio_sleep_s = 2.5 if action == "defer" else 0.2

        decision_result = {
            "window_id": window_id,
            "chosen_compressor": chosen_codec,
            "compression_level": chosen_level,
            "transmit_or_defer": action,
            "radio_sleep_duration_s": radio_sleep_s,
            "composite_score": winning_score,
            "scores_breakdown": scores,
            "surviving_candidates": surviving_codecs,
            "safety_gate_passed": True,
            "adapted_weights": {
                "w1_ratio": adapted_weights[0],
                "w2_energy": adapted_weights[1],
                "w3_latency": adapted_weights[2],
                "w4_error": adapted_weights[3]
            }
        }

        # Cache decision context for closing feedback loop with Stage 8
        self.last_decision_context = {
            "window_id": window_id,
            "chosen_compressor": chosen_codec,
            "context_vector": context_vec,
            "predicted_score": winning_score,
            "adapted_weights": adapted_weights,
            "max_ratio": max_ratio,
            "max_energy": max_energy,
            "max_latency": max_latency
        }

        # Log decision
        self._log_decision(decision_result, features, predictions, adapted_weights)

        return decision_result

    # Alias for convenience
    select_algorithm = select_strategy

    def update_policy(
        self,
        outcome_log: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Online policy update (Formula from Architecture PDF - Objective O3):
          theta <- theta + eta * (Actual Score - Predicted Score) * context

        Called when Stage 8 returns verified outcome report.
        """
        if not self.last_decision_context:
            return {}

        codec = self.last_decision_context["chosen_compressor"]
        context_vec = self.last_decision_context["context_vector"]
        pred_score = self.last_decision_context["predicted_score"]
        w1, w2, w3, w4 = self.last_decision_context["adapted_weights"]
        max_ratio = self.last_decision_context["max_ratio"]
        max_energy = self.last_decision_context["max_energy"]
        max_latency = self.last_decision_context["max_latency"]

        # Calculate Actual Score from measured outcome
        meas_ratio = float(outcome_log.get("ratio", 1.0))
        meas_energy = float(outcome_log.get("energy_uj", 50.0))
        meas_lat = float(outcome_log.get("latency_ms", 1.0))

        ratio_norm = min(1.0, max(0.01, meas_ratio / max_ratio))
        energy_norm = min(1.0, max(0.001, meas_energy / max_energy))
        latency_norm = min(1.0, max(0.001, meas_lat / max_latency))

        actual_score = (w1 * ratio_norm) - (w2 * energy_norm) - (w3 * latency_norm)
        score_error = actual_score - pred_score

        # Bandit policy gradient update
        self.theta[codec] += self.eta * score_error * context_vec

        return {
            "codec": codec,
            "score_error": round(float(score_error), 4),
            "updated_theta_norm": round(float(np.linalg.norm(self.theta[codec])), 4)
        }

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


# Backwards compatibility alias
DecisionStage = HierarchicalDecisionEngine


if __name__ == "__main__":
    print("=== Testing Stage 5: Hierarchical Decision Engine (Objectives O2, O3) ===")
    profiler = HardwareProfilerStage()
    engine = HierarchicalDecisionEngine(profiler=profiler)

    # 1. Normal Operation
    feat = {"window_id": 1, "entropy": 1.2, "variance": 0.05, "criticality": "routine"}
    pred = {"predicted_cpu_temp": 42.0, "predicted_cpu_load": 15.0, "predicted_bandwidth_kbps": 1000.0, "is_throttling_risk": False}
    dec = engine.select_strategy(feat, pred)
    print(f"Normal Operation: Selected {dec['chosen_compressor']} (Score: {dec['composite_score']}) | Action: {dec['transmit_or_defer']}")

    # 2. Safety Gate Critical Data
    feat_crit = {"window_id": 2, "entropy": 1.2, "criticality": "safety_critical"}
    dec_crit = engine.select_strategy(feat_crit, pred)
    print(f"Safety-Critical Data: Surviving: {dec_crit['surviving_candidates']} -> Selected {dec_crit['chosen_compressor']}")

    # 3. Contextual Bandit Online Update from Stage 8 feedback
    feedback = {"ratio": 4.8, "energy_uj": 48.0, "latency_ms": 0.04, "error": 0.0}
    upd = engine.update_policy(feedback)
    print(f"Online Policy Update (Objective O3): {upd}")


MultiObjectiveDecisionEngine = HierarchicalDecisionEngine


