"""
Unit Tests for Stage 3 AR(1) Autoregressive Forecasting & Multi-Step Horizons
"""

import unittest
from edge.stage3_predictor import PredictorStage


class TestStage3AR1(unittest.TestCase):

    def setUp(self):
        self.predictor = PredictorStage(history_len=15)

    def test_ar1_parameter_estimation_stationary(self):
        """Autoregressive lag-1 correlation phi is correctly clamped within stationarity bounds [-0.95, 0.95]."""
        # Linear increasing series
        history = [20.0 + i * 2.0 for i in range(10)]
        c, phi, var = self.predictor.compute_ar1_params(history)

        self.assertGreater(phi, 0.0)
        self.assertLessEqual(phi, 0.95)
        self.assertGreater(var, 0.0)

    def test_multistep_forecast_convergence(self):
        """Multi-step ahead forecasts (k=1, 2, 3) are produced and track historical trajectory."""
        for temp in [40.0, 42.0, 44.0, 46.0, 48.0, 50.0]:
            res = self.predictor.update({"cpu_temp_c": temp, "cpu_percent": 15.0})

        ar1_forecasts = res["ar1_forecasts"]
        self.assertIn("cpu_temp", ar1_forecasts)
        self.assertIn(1, ar1_forecasts["cpu_temp"])
        self.assertIn(2, ar1_forecasts["cpu_temp"])
        self.assertIn(3, ar1_forecasts["cpu_temp"])

        # Horizon method works
        k1 = self.predictor.forecast_horizon("cpu_temp", steps=1)
        k2 = self.predictor.forecast_horizon("cpu_temp", steps=2)
        self.assertGreater(k1, 0.0)
        self.assertGreater(k2, 0.0)

    def test_volatility_tracking(self):
        """Volatility reflects variance of signal in rolling window."""
        # Feed high-volatility alternating signal
        for v in [10.0, 90.0, 10.0, 90.0, 10.0, 90.0]:
            res = self.predictor.update({"cpu_percent": v, "cpu_temp_c": 50.0})

        volatility = res["volatility"]
        self.assertIn("cpu_load", volatility)
        self.assertGreater(volatility["cpu_load"], 100.0)


if __name__ == "__main__":
    unittest.main()
