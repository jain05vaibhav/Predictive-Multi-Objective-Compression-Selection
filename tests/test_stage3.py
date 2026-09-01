"""
Unit Tests for Stage 3: State & Resource Predictor
"""

import unittest
from edge.stage3_predictor import PredictorStage
from edge.stage1_acquisition import Window


class TestStage3Predictor(unittest.TestCase):

    def setUp(self):
        self.predictor = PredictorStage(
            alpha=0.3,
            beta=0.2,
            thermal_limit_c=80.0,
            warning_temp_c=70.0,
            default_bandwidth_kbps=1000.0
        )

    def test_ewma_initialization_sets_baseline(self):
        """First measurement should set the initial baseline without lag."""
        sample = {
            "cpu_percent": 30.0,
            "cpu_temp_c": 50.0,
            "power_mw": 2100.0,
            "bandwidth_kbps": 1000.0,
            "core_voltage_v": 1.25
        }
        res = self.predictor.update(sample)

        self.assertEqual(res["predicted_cpu_load"], 30.0)
        self.assertEqual(res["predicted_cpu_temp"], 50.0)
        self.assertEqual(res["predicted_power_mw"], 2100.0)
        self.assertEqual(res["predicted_bandwidth_kbps"], 1000.0)
        self.assertEqual(res["thermal_headroom_c"], 30.0)
        self.assertFalse(res["is_throttling_risk"])
        self.assertFalse(res["is_undervoltage_risk"])
        self.assertEqual(res["window_count"], 1)

    def test_ewma_smoothing_response_to_step_change(self):
        """Verify standard EWMA math: x_hat = 0.3 * x_new + 0.7 * x_old."""
        # Initial baseline
        self.predictor.update({"cpu_percent": 10.0, "cpu_temp_c": 40.0})

        # Step input
        # Note: beta=0.2, delta_cpu = 90.0, trend_cpu = 0.2 * 90 = 18.0
        # ewma_cpu = 0.3 * 100.0 + 0.7 * 10.0 = 37.0
        # pred_cpu = 37.0 + 18.0 = 55.0
        res = self.predictor.update({"cpu_percent": 100.0, "cpu_temp_c": 40.0})

        self.assertGreater(res["predicted_cpu_load"], 10.0)
        self.assertLess(res["predicted_cpu_load"], 100.0)
        self.assertEqual(res["window_count"], 2)

    def test_thermal_throttling_alarm_when_exceeding_warning_temp(self):
        """Forecasted temperature >= warning_temp_c (70°C) must trigger throttling risk."""
        self.predictor.update({"cpu_temp_c": 65.0, "core_voltage_v": 1.25})
        res = self.predictor.update({"cpu_temp_c": 75.0, "core_voltage_v": 1.25})

        self.assertGreaterEqual(res["predicted_cpu_temp"], 70.0)
        self.assertTrue(res["is_throttling_risk"])
        self.assertLessEqual(res["thermal_headroom_c"], 10.0)

    def test_throttling_risk_triggered_by_vcgencmd_bits(self):
        """Direct throttled_hex bitmask or flag triggers throttling risk even at lower temp."""
        sample = {
            "cpu_temp_c": 50.0,
            "core_voltage_v": 1.25,
            "throttled_hex": "0x50005"
        }
        res = self.predictor.update(sample)

        self.assertTrue(res["is_throttling_risk"])

    def test_undervoltage_alarm_when_core_voltage_drops(self):
        """Core voltage below 1.20V triggers undervoltage alarm."""
        sample = {
            "cpu_temp_c": 45.0,
            "core_voltage_v": 1.15
        }
        res = self.predictor.update(sample)

        self.assertTrue(res["is_undervoltage_risk"])

    def test_trend_calculation_on_heating_curve(self):
        """Consecutive rising temperature measurements produce a positive trend slope."""
        self.predictor.update({"cpu_temp_c": 40.0})
        self.predictor.update({"cpu_temp_c": 45.0})
        res = self.predictor.update({"cpu_temp_c": 50.0})

        self.assertGreater(res["trend_temp"], 0.0)

    def test_resilience_to_missing_fields_and_window_objects(self):
        """Predictor handles empty dicts, nested telemetry, and Stage 1 Window objects safely."""
        # 1. Empty dict
        res_empty = self.predictor.update({})
        self.assertIn("predicted_cpu_load", res_empty)

        # 2. Nested system section
        nested = {
            "system": {
                "cpu_percent": 45.0,
                "cpu_temp_c": 52.0,
                "core_voltage_v": 1.24
            }
        }
        res_nested = self.predictor.update(nested)
        self.assertAlmostEqual(res_nested["predicted_cpu_temp"], 52.0, delta=5.0)

        # 3. Stage 1 Window object
        win = Window(
            window_id=1,
            data=[{"cpu_percent": 60.0, "cpu_temp_c": 55.0}],
            data_type="numeric"
        )
        res_win = self.predictor.predict(win)
        self.assertIn("predicted_cpu_load", res_win)

    def test_reset_clears_history_and_baselines(self):
        """reset() clears all EWMA states and counters."""
        self.predictor.update({"cpu_percent": 90.0, "cpu_temp_c": 80.0})
        self.assertEqual(self.predictor.window_count, 1)

        self.predictor.reset()
        self.assertEqual(self.predictor.window_count, 0)
        self.assertIsNone(self.predictor.ewma_cpu)
        self.assertIsNone(self.predictor.ewma_temp)


if __name__ == "__main__":
    unittest.main()

