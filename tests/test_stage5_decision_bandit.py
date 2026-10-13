"""
Unit Tests for Stage 5: Hierarchical Decision Engine & Online Policy Update (Objectives O2, O3)
"""

import os
import unittest
import numpy as np
from edge.stage5_decision import HierarchicalDecisionEngine
from edge.stage4_profiler import HardwareProfilerStage


class TestStage5DecisionBandit(unittest.TestCase):

    def setUp(self):
        self.test_log_file = "logs/test_decision_bandit.csv"
        self.profiler = HardwareProfilerStage()
        self.engine = HierarchicalDecisionEngine(
            profiler=self.profiler,
            log_file=self.test_log_file
        )

    def tearDown(self):
        if os.path.exists(self.test_log_file):
            try:
                os.remove(self.test_log_file)
            except Exception:
                pass

    def test_rule_based_safety_gate_enforces_epsilon(self):
        """
        Layer (a) Safety Gate: Configurations violating epsilon are eliminated outright.
        """
        # Artificially set bzip2 calibrated error to 0.08 in profiler
        context = {"data_type": "numeric", "entropy": 1.5, "criticality": "routine"}
        self.profiler.calibration_table["numeric_med"]["bzip2"]["error"] = 0.08

        pred = {"predicted_cpu_temp": 45.0, "predicted_cpu_load": 20.0, "predicted_bandwidth_kbps": 1000.0}
        dec = self.engine.select_strategy(context, pred, constraints={"epsilon": 0.05})

        self.assertNotIn("bzip2", dec["surviving_candidates"])
        self.assertIn(dec["chosen_compressor"], dec["surviving_candidates"])

    def test_safety_gate_strict_epsilon_for_safety_critical_telemetry(self):
        """
        Safety-critical telemetry forces epsilon=0.000000.
        """
        # Inject small lossy error 0.001 to gzip
        self.profiler.calibration_table["numeric_med"]["gzip"]["error"] = 0.001

        context = {"data_type": "numeric", "entropy": 1.5, "criticality": "safety_critical"}
        pred = {"predicted_cpu_temp": 42.0, "predicted_cpu_load": 15.0, "predicted_bandwidth_kbps": 1000.0}
        dec = self.engine.select_strategy(context, pred)

        self.assertNotIn("gzip", dec["surviving_candidates"])

    def test_battery_depleted_weight_adaptation(self):
        """Under low battery (<30%), w2 (Energy) is boosted heavily."""
        feat = {"window_id": 1, "entropy": 1.2}
        pred = {
            "predicted_cpu_temp": 40.0,
            "predicted_cpu_load": 15.0,
            "predicted_bandwidth_kbps": 1000.0,
            "predicted_battery_percent": 18.0
        }
        dec = self.engine.select_strategy(feat, pred)
        weights = dec["adapted_weights"]

        self.assertGreater(weights["w2_energy"], weights["w1_ratio"])

    def test_contextual_bandit_online_policy_gradient_update(self):
        """
        Objective O3: Online policy update shifts preference weights theta from Stage 8 feedback:
          theta <- theta + eta * (Actual Score - Predicted Score) * context
        """
        feat = {"window_id": 10, "entropy": 1.0}
        pred = {"predicted_cpu_temp": 45.0, "predicted_cpu_load": 25.0, "predicted_bandwidth_kbps": 800.0}
        dec = self.engine.select_strategy(feat, pred)
        codec = dec["chosen_compressor"]

        initial_theta = np.copy(self.engine.theta[codec])

        # Stage 8 reports high outcome (measured ratio 15.0) -> positive surprise
        feedback = {
            "ratio": 15.0,
            "energy_uj": 40.0,
            "latency_ms": 0.05,
            "error": 0.0
        }
        res = self.engine.update_policy(feedback)

        updated_theta = self.engine.theta[codec]
        self.assertFalse(np.array_equal(initial_theta, updated_theta))
        self.assertIn("score_error", res)


if __name__ == "__main__":
    unittest.main()
