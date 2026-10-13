"""
Stage 3: Predictive Forecasting Module (Objective O1)

Forecasts near-future conditions along two parallel tracks using Exponentially
Weighted Moving Average (EWMA):
1. Resource Track:
   - Forecasts SoC CPU load (%), SoC temperature (°C), available bandwidth (kbps),
     and battery/energy reserve (%).
2. Workload Track ("Future Sensing Workload"):
   - Forecasts the upcoming trend in the feature vector itself (predicted Shannon
     entropy H, variance, and compressibility trajectory).

EWMA Formula (reused for both tracks):
  x_hat_{t+1} = alpha * x_t + (1 - alpha) * x_hat_t
"""

from typing import Dict, Any, Optional, Union, List
from edge.config import (
    PREDICTOR_ALPHA,
    PREDICTOR_BETA,
    DEFAULT_THERMAL_LIMIT_C,
    THROTTLING_TEMP_WARNING_C,
    DEFAULT_BANDWIDTH_KBPS
)


class PredictorStage:
    """
    Stage 3 Predictive Forecasting Module (Objective O1).
    Maintains dual-track EWMA forecasting for resource availability and workload trend.
    """

    def __init__(
        self,
        alpha: float = PREDICTOR_ALPHA,
        beta: float = PREDICTOR_BETA,
        thermal_limit_c: float = DEFAULT_THERMAL_LIMIT_C,
        warning_temp_c: float = THROTTLING_TEMP_WARNING_C,
        default_bandwidth_kbps: float = DEFAULT_BANDWIDTH_KBPS
    ):
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.thermal_limit_c = float(thermal_limit_c)
        self.warning_temp_c = float(warning_temp_c)
        self.default_bandwidth_kbps = float(default_bandwidth_kbps)

        self.window_count = 0

        # Track 1: Resource Forecast EWMA States
        self.ewma_cpu: Optional[float] = None
        self.ewma_temp: Optional[float] = None
        self.ewma_power: Optional[float] = None
        self.ewma_bandwidth: Optional[float] = None
        self.ewma_battery: Optional[float] = None

        # Track 2: Workload Forecast EWMA States (Objective O1)
        self.ewma_entropy: Optional[float] = None
        self.ewma_variance: Optional[float] = None
        self.ewma_roc: Optional[float] = None

        # Trend / Velocity Estimates (Holt's second order)
        self.trend_temp: float = 0.0
        self.trend_cpu: float = 0.0
        self.trend_entropy: float = 0.0

        # Previous measurements
        self.prev_temp: Optional[float] = None
        self.prev_cpu: Optional[float] = None
        self.prev_entropy: Optional[float] = None

    def reset(self) -> None:
        """Resets all internal EWMA state baselines across both tracks."""
        self.window_count = 0
        self.ewma_cpu = None
        self.ewma_temp = None
        self.ewma_power = None
        self.ewma_bandwidth = None
        self.ewma_battery = None

        self.ewma_entropy = None
        self.ewma_variance = None
        self.ewma_roc = None

        self.trend_temp = 0.0
        self.trend_cpu = 0.0
        self.trend_entropy = 0.0

        self.prev_temp = None
        self.prev_cpu = None
        self.prev_entropy = None

    def _extract_metrics(self, data: Any) -> Dict[str, Any]:
        """
        Robustly extracts system and workload metrics from a dict, Stage 1 Window,
        or Stage 2 feature vector.
        """
        metrics = {
            "cpu_percent": 25.0,
            "cpu_temp_c": 45.0,
            "core_voltage_v": 1.25,
            "power_mw": 2000.0,
            "bandwidth_kbps": self.default_bandwidth_kbps,
            "battery_percent": 100.0,
            "entropy": 1.5,
            "variance": 0.05,
            "rate_of_change": 0.02,
            "throttled_hex": "0x0",
            "undervoltage_now": False,
            "throttled_now": False
        }

        if data is None:
            return metrics

        # Handle Stage 1 Window objects (extract from last sample)
        if hasattr(data, "data") and isinstance(data.data, (list, tuple)):
            if data.data:
                last_sample = data.data[-1]
                extracted = self._extract_metrics(last_sample)
                # If window has sample count, estimate data rate
                return extracted
            return metrics

        # Handle raw dictionary payloads
        if isinstance(data, dict):
            # Nested system section
            sys_info = data.get("system", {})
            if isinstance(sys_info, dict):
                if "cpu_percent" in sys_info:
                    metrics["cpu_percent"] = float(sys_info["cpu_percent"])
                if "cpu_temp_c" in sys_info:
                    metrics["cpu_temp_c"] = float(sys_info["cpu_temp_c"])
                if "core_voltage_v" in sys_info:
                    metrics["core_voltage_v"] = float(sys_info["core_voltage_v"])
                if "power_mw" in sys_info:
                    metrics["power_mw"] = float(sys_info["power_mw"])
                if "throttled_hex" in sys_info:
                    metrics["throttled_hex"] = str(sys_info["throttled_hex"])
                if "undervoltage_now" in sys_info:
                    metrics["undervoltage_now"] = bool(sys_info["undervoltage_now"])
                if "throttled_now" in sys_info:
                    metrics["throttled_now"] = bool(sys_info["throttled_now"])

            # Direct key overrides for resource metrics
            if "cpu_percent" in data:
                metrics["cpu_percent"] = float(data["cpu_percent"])
            elif "cpu_load" in data:
                metrics["cpu_percent"] = float(data["cpu_load"])

            if "cpu_temp_c" in data:
                metrics["cpu_temp_c"] = float(data["cpu_temp_c"])
            elif "temperature" in data and "cpu_temp_c" not in sys_info:
                metrics["cpu_temp_c"] = float(data["temperature"]) + 15.0

            if "core_voltage_v" in data:
                metrics["core_voltage_v"] = float(data["core_voltage_v"])
            elif "voltage_v" in data:
                metrics["core_voltage_v"] = float(data["voltage_v"])

            if "power_mw" in data:
                metrics["power_mw"] = float(data["power_mw"])

            if "bandwidth_kbps" in data:
                metrics["bandwidth_kbps"] = float(data["bandwidth_kbps"])
            elif "bandwidth" in data:
                metrics["bandwidth_kbps"] = float(data["bandwidth"])

            if "battery_percent" in data:
                metrics["battery_percent"] = float(data["battery_percent"])
            elif "battery" in data:
                metrics["battery_percent"] = float(data["battery"])

            if "throttled_hex" in data:
                metrics["throttled_hex"] = str(data["throttled_hex"])
            if "undervoltage_now" in data:
                metrics["undervoltage_now"] = bool(data["undervoltage_now"])
            if "throttled_now" in data:
                metrics["throttled_now"] = bool(data["throttled_now"])

            # Workload features (from Stage 2)
            if "entropy" in data:
                metrics["entropy"] = float(data["entropy"])
            if "variance" in data:
                metrics["variance"] = float(data["variance"])
            if "rate_of_change" in data:
                metrics["rate_of_change"] = float(data["rate_of_change"])

        return metrics

    def update(
        self,
        data: Optional[Any] = None,
        features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingests the current window measurement and features, updates EWMA state
        and trends across both tracks, and returns the dual-track forecast.
        """
        raw = self._extract_metrics(data)

        # Merge explicit features if provided separately
        if features and isinstance(features, dict):
            if "entropy" in features:
                raw["entropy"] = float(features["entropy"])
            if "variance" in features:
                raw["variance"] = float(features["variance"])
            if "rate_of_change" in features:
                raw["rate_of_change"] = float(features["rate_of_change"])

        # Track 1: Resource signals
        curr_cpu = raw["cpu_percent"]
        curr_temp = raw["cpu_temp_c"]
        curr_power = raw["power_mw"]
        curr_bw = raw["bandwidth_kbps"]
        curr_battery = raw["battery_percent"]

        # Track 2: Workload signals
        curr_entropy = raw["entropy"]
        curr_var = raw["variance"]
        curr_roc = raw["rate_of_change"]

        # First update initializes baseline states
        if self.ewma_cpu is None:
            self.ewma_cpu = curr_cpu
            self.ewma_temp = curr_temp
            self.ewma_power = curr_power
            self.ewma_bandwidth = curr_bw
            self.ewma_battery = curr_battery

            self.ewma_entropy = curr_entropy
            self.ewma_variance = curr_var
            self.ewma_roc = curr_roc

            self.prev_cpu = curr_cpu
            self.prev_temp = curr_temp
            self.prev_entropy = curr_entropy
        else:
            # First difference velocity estimates
            delta_temp = curr_temp - (self.prev_temp if self.prev_temp is not None else curr_temp)
            delta_cpu = curr_cpu - (self.prev_cpu if self.prev_cpu is not None else curr_cpu)
            delta_entropy = curr_entropy - (self.prev_entropy if self.prev_entropy is not None else curr_entropy)

            self.trend_temp = self.beta * delta_temp + (1.0 - self.beta) * self.trend_temp
            self.trend_cpu = self.beta * delta_cpu + (1.0 - self.beta) * self.trend_cpu
            self.trend_entropy = self.beta * delta_entropy + (1.0 - self.beta) * self.trend_entropy

            self.prev_temp = curr_temp
            self.prev_cpu = curr_cpu
            self.prev_entropy = curr_entropy

            # Update Track 1 (Resource) EWMA states: x_hat = alpha * x + (1 - alpha) * x_hat
            self.ewma_cpu = self.alpha * curr_cpu + (1.0 - self.alpha) * self.ewma_cpu
            self.ewma_temp = self.alpha * curr_temp + (1.0 - self.alpha) * self.ewma_temp
            self.ewma_power = self.alpha * curr_power + (1.0 - self.alpha) * self.ewma_power
            self.ewma_bandwidth = self.alpha * curr_bw + (1.0 - self.alpha) * self.ewma_bandwidth
            self.ewma_battery = self.alpha * curr_battery + (1.0 - self.alpha) * (self.ewma_battery or curr_battery)

            # Update Track 2 (Workload) EWMA states: x_hat = alpha * x + (1 - alpha) * x_hat
            self.ewma_entropy = self.alpha * curr_entropy + (1.0 - self.alpha) * (self.ewma_entropy or curr_entropy)
            self.ewma_variance = self.alpha * curr_var + (1.0 - self.alpha) * (self.ewma_variance or curr_var)
            self.ewma_roc = self.alpha * curr_roc + (1.0 - self.alpha) * (self.ewma_roc or curr_roc)

        self.window_count += 1

        # Forecast calculations (level + trend extrapolation)
        pred_cpu = max(0.0, min(100.0, self.ewma_cpu + self.trend_cpu))
        pred_temp = max(20.0, min(105.0, self.ewma_temp + self.trend_temp))
        pred_power = max(500.0, self.ewma_power)
        pred_bw = max(10.0, self.ewma_bandwidth)
        pred_battery = max(0.0, min(100.0, self.ewma_battery or 100.0))

        pred_entropy = max(0.0, min(4.0, (self.ewma_entropy or 1.5) + self.trend_entropy))
        pred_var = max(0.0, self.ewma_variance or 0.0)

        # Workload trend categorization
        if self.trend_entropy > 0.05:
            workload_trend = "rising"
        elif self.trend_entropy < -0.05:
            workload_trend = "falling"
        else:
            workload_trend = "steady"

        # Thermal and voltage headroom
        thermal_headroom = max(0.0, round(self.thermal_limit_c - pred_temp, 2))

        # Hardware risk assessments for Raspberry Pi 3B+ SoC
        is_active_throttling = False
        if raw.get("throttled_now") or raw.get("arm_freq_capped_now") or raw.get("undervoltage_now"):
            is_active_throttling = True
        elif raw.get("throttled_hex") not in ("0x0", "0", None):
            try:
                val = int(str(raw["throttled_hex"]), 16)
                is_active_throttling = bool(val & 0b1111)
            except Exception:
                pass

        throttling_risk = bool(
            pred_temp >= self.warning_temp_c
            or is_active_throttling
        )

        undervoltage_risk = bool(
            raw.get("core_voltage_v", 1.25) < 1.20
            or raw.get("undervoltage_now", False)
        )

        resource_forecast = {
            "battery_percent": round(pred_battery, 1),
            "cpu_load": round(pred_cpu, 2),
            "bandwidth_kbps": round(pred_bw, 2),
            "cpu_temp": round(pred_temp, 2),
            "power_mw": round(pred_power, 2),
            "thermal_headroom_c": thermal_headroom,
            "is_throttling_risk": throttling_risk,
            "is_undervoltage_risk": undervoltage_risk
        }

        workload_forecast = {
            "predicted_entropy": round(pred_entropy, 4),
            "predicted_variance": round(pred_var, 4),
            "entropy_trend": workload_trend,
            "trend_entropy_slope": round(self.trend_entropy, 4)
        }

        return {
            # Structured dual-track forecast sections (Objective O1)
            "resource_forecast": resource_forecast,
            "workload_forecast": workload_forecast,

            # Flat backwards-compatible keys
            "predicted_cpu_load": round(pred_cpu, 2),
            "predicted_cpu_temp": round(pred_temp, 2),
            "predicted_power_mw": round(pred_power, 2),
            "predicted_bandwidth_kbps": round(pred_bw, 2),
            "predicted_battery_percent": round(pred_battery, 1),
            "predicted_entropy": round(pred_entropy, 4),
            "predicted_variance": round(pred_var, 4),
            "thermal_headroom_c": thermal_headroom,
            "is_throttling_risk": throttling_risk,
            "is_undervoltage_risk": undervoltage_risk,
            "trend_temp": round(self.trend_temp, 3),
            "trend_cpu": round(self.trend_cpu, 3),
            "trend_entropy": round(self.trend_entropy, 4),
            "workload_trend": workload_trend,
            "window_count": self.window_count
        }

    def predict(
        self,
        feature_vector_or_sample: Optional[Any] = None,
        features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Returns next-window state forecast. If a new sample/vector is provided,
        updates internal EWMA state before forecasting.
        """
        if feature_vector_or_sample is not None:
            return self.update(feature_vector_or_sample, features=features)
        return self.update(None, features=features)


if __name__ == "__main__":
    print("=== Testing Stage 3: Predictive Forecasting Module (Objective O1) ===")
    predictor = PredictorStage(alpha=0.3, warning_temp_c=70.0)

    test_samples = [
        {"cpu_percent": 15.0, "cpu_temp_c": 42.0, "bandwidth_kbps": 1200.0, "battery_percent": 98.0, "entropy": 0.4},
        {"cpu_percent": 22.0, "cpu_temp_c": 44.0, "bandwidth_kbps": 1150.0, "battery_percent": 97.5, "entropy": 0.6},
        {"cpu_percent": 80.0, "cpu_temp_c": 60.0, "bandwidth_kbps": 900.0,  "battery_percent": 95.0, "entropy": 1.4},
        {"cpu_percent": 95.0, "cpu_temp_c": 72.0, "bandwidth_kbps": 400.0,  "battery_percent": 93.0, "entropy": 2.8},
    ]

    for idx, s in enumerate(test_samples, start=1):
        fc = predictor.update(s)
        print(f"\n[Window #{idx}]")
        print(f"  Resource Track: CPU={fc['predicted_cpu_load']}% | Temp={fc['predicted_cpu_temp']}°C | BW={fc['predicted_bandwidth_kbps']}kbps | Batt={fc['predicted_battery_percent']}%")
        print(f"  Workload Track: Predicted H={fc['predicted_entropy']} (Trend: {fc['workload_trend']})")
        print(f"  Throttling Risk: {fc['is_throttling_risk']}")
