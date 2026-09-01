"""
Stage 3: State & Resource Predictor

Forecasts next-window system resource states (SoC CPU load, temperature, power draw,
and network bandwidth) using Exponentially Weighted Moving Average (EWMA) and trend
extrapolation. Feeds forecasted states into Stage 4 Decision Engine to prevent
thermal throttling and latency spikes on Raspberry Pi 3B+.
"""

from typing import Dict, Any, Optional, Union, List
from edge.config import (
    PREDICTOR_ALPHA,
    DEFAULT_THERMAL_LIMIT_C,
    THROTTLING_TEMP_WARNING_C,
    DEFAULT_BANDWIDTH_KBPS
)


class PredictorStage:
    """
    Stage 3 State & Resource Predictor.
    Applies EWMA forecasting and trend estimation to edge telemetry streams.
    """

    def __init__(
        self,
        alpha: float = PREDICTOR_ALPHA,
        beta: float = 0.2,
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

        # EWMA state estimates
        self.ewma_cpu: Optional[float] = None
        self.ewma_temp: Optional[float] = None
        self.ewma_power: Optional[float] = None
        self.ewma_bandwidth: Optional[float] = None

        # Trend / velocity estimates
        self.trend_temp: float = 0.0
        self.trend_cpu: float = 0.0

        # Previous raw measurements
        self.prev_temp: Optional[float] = None
        self.prev_cpu: Optional[float] = None

    def reset(self) -> None:
        """Resets all internal EWMA state baselines."""
        self.window_count = 0
        self.ewma_cpu = None
        self.ewma_temp = None
        self.ewma_power = None
        self.ewma_bandwidth = None
        self.trend_temp = 0.0
        self.trend_cpu = 0.0
        self.prev_temp = None
        self.prev_cpu = None

    def _extract_metrics(self, data: Any) -> Dict[str, Any]:
        """
        Robustly extracts system metrics from a dict, Stage 1 Window, or nested telemetry hub payload.
        """
        metrics = {
            "cpu_percent": 25.0,
            "cpu_temp_c": 45.0,
            "core_voltage_v": 1.25,
            "power_mw": 2000.0,
            "bandwidth_kbps": self.default_bandwidth_kbps,
            "throttled_hex": "0x0",
            "undervoltage_now": False,
            "throttled_now": False
        }

        if data is None:
            return metrics

        # Handle Stage 1 Window objects (extract from last sample or average)
        if hasattr(data, "data") and isinstance(data.data, (list, tuple)):
            if data.data:
                last_sample = data.data[-1]
                return self._extract_metrics(last_sample)
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

            # Top-level key overrides
            if "cpu_percent" in data:
                metrics["cpu_percent"] = float(data["cpu_percent"])
            elif "cpu_load" in data:
                metrics["cpu_percent"] = float(data["cpu_load"])

            if "cpu_temp_c" in data:
                metrics["cpu_temp_c"] = float(data["cpu_temp_c"])
            elif "temperature" in data and "cpu_temp_c" not in sys_info:
                # If environmental temperature is available and no CPU temp, use with baseline offset
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

            if "throttled_hex" in data:
                metrics["throttled_hex"] = str(data["throttled_hex"])
            if "undervoltage_now" in data:
                metrics["undervoltage_now"] = bool(data["undervoltage_now"])
            if "throttled_now" in data:
                metrics["throttled_now"] = bool(data["throttled_now"])

        return metrics

    def update(self, data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Ingests the current window measurement, updates EWMA state and trends,
        and returns the forecasted next-window resource prediction.
        """
        raw = self._extract_metrics(data)
        curr_cpu = raw["cpu_percent"]
        curr_temp = raw["cpu_temp_c"]
        curr_power = raw["power_mw"]
        curr_bw = raw["bandwidth_kbps"]

        # First update initializes EWMA baseline
        if self.ewma_cpu is None:
            self.ewma_cpu = curr_cpu
            self.ewma_temp = curr_temp
            self.ewma_power = curr_power
            self.ewma_bandwidth = curr_bw
            self.prev_cpu = curr_cpu
            self.prev_temp = curr_temp
        else:
            # Update trends (first difference smoothed)
            delta_temp = curr_temp - (self.prev_temp if self.prev_temp is not None else curr_temp)
            delta_cpu = curr_cpu - (self.prev_cpu if self.prev_cpu is not None else curr_cpu)

            self.trend_temp = self.beta * delta_temp + (1.0 - self.beta) * self.trend_temp
            self.trend_cpu = self.beta * delta_cpu + (1.0 - self.beta) * self.trend_cpu

            self.prev_temp = curr_temp
            self.prev_cpu = curr_cpu

            # Update EWMA states: x_hat = alpha * x + (1 - alpha) * x_hat
            self.ewma_cpu = self.alpha * curr_cpu + (1.0 - self.alpha) * self.ewma_cpu
            self.ewma_temp = self.alpha * curr_temp + (1.0 - self.alpha) * self.ewma_temp
            self.ewma_power = self.alpha * curr_power + (1.0 - self.alpha) * self.ewma_power
            self.ewma_bandwidth = self.alpha * curr_bw + (1.0 - self.alpha) * self.ewma_bandwidth

        self.window_count += 1

        # Forecast next window (combining EWMA level + trend trajectory)
        pred_cpu = max(0.0, min(100.0, self.ewma_cpu + self.trend_cpu))
        pred_temp = max(20.0, min(105.0, self.ewma_temp + self.trend_temp))
        pred_power = max(500.0, self.ewma_power)
        pred_bw = max(10.0, self.ewma_bandwidth)

        # Thermal and voltage headroom
        thermal_headroom = max(0.0, round(self.thermal_limit_c - pred_temp, 2))

        # Risk assessments for Raspberry Pi 3B+ SoC
        is_active_throttling = False
        if raw.get("throttled_now") or raw.get("arm_freq_capped_now") or raw.get("undervoltage_now"):
            is_active_throttling = True
        elif raw.get("throttled_hex") not in ("0x0", "0", None):
            try:
                val = int(str(raw["throttled_hex"]), 16)
                is_active_throttling = bool(val & 0b1111)  # Only active bits 0..3
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

        return {
            "predicted_cpu_load": round(pred_cpu, 2),
            "predicted_cpu_temp": round(pred_temp, 2),
            "predicted_power_mw": round(pred_power, 2),
            "predicted_bandwidth_kbps": round(pred_bw, 2),
            "thermal_headroom_c": thermal_headroom,
            "is_throttling_risk": throttling_risk,
            "is_undervoltage_risk": undervoltage_risk,
            "trend_temp": round(self.trend_temp, 3),
            "trend_cpu": round(self.trend_cpu, 3),
            "window_count": self.window_count
        }

    def predict(self, feature_vector_or_sample: Optional[Any] = None) -> Dict[str, Any]:
        """
        Returns next-window state forecast. If a new sample/vector is provided,
        updates the internal EWMA state before forecasting.
        """
        if feature_vector_or_sample is not None:
            return self.update(feature_vector_or_sample)
        
        # If no new sample, evaluate current state
        return self.update(None)


if __name__ == "__main__":
    print("=== Testing Stage 3: State & Resource Predictor ===")
    predictor = PredictorStage(alpha=0.3, warning_temp_c=70.0)

    # Simulated sequence: Baseline -> CPU Spike & Rapid Heating -> Network Drop
    test_sequence = [
        {"cpu_percent": 15.0, "cpu_temp_c": 42.0, "power_mw": 1800.0, "bandwidth_kbps": 1200.0, "core_voltage_v": 1.28},
        {"cpu_percent": 20.0, "cpu_temp_c": 43.5, "power_mw": 1900.0, "bandwidth_kbps": 1150.0, "core_voltage_v": 1.28},
        {"cpu_percent": 85.0, "cpu_temp_c": 58.0, "power_mw": 3200.0, "bandwidth_kbps": 900.0, "core_voltage_v": 1.24},
        {"cpu_percent": 95.0, "cpu_temp_c": 72.5, "power_mw": 3600.0, "bandwidth_kbps": 400.0, "core_voltage_v": 1.18, "throttled_now": True},
        {"cpu_percent": 90.0, "cpu_temp_c": 76.0, "power_mw": 3500.0, "bandwidth_kbps": 250.0, "core_voltage_v": 1.17, "throttled_now": True},
    ]

    for step_idx, sample in enumerate(test_sequence, start=1):
        forecast = predictor.update(sample)
        print(f"\n[Step {step_idx}] Input: CPU={sample['cpu_percent']}% | Temp={sample['cpu_temp_c']} deg C | BW={sample['bandwidth_kbps']} kbps")
        print(f"  -> Forecasted CPU Load:   {forecast['predicted_cpu_load']}%")
        print(f"  -> Forecasted SoC Temp:   {forecast['predicted_cpu_temp']} deg C (Trend: {forecast['trend_temp']:+0.2f} deg C/win)")
        print(f"  -> Forecasted Bandwidth:  {forecast['predicted_bandwidth_kbps']} kbps")
        print(f"  -> Thermal Headroom:      {forecast['thermal_headroom_c']} deg C")
        print(f"  -> Throttling Risk:       {forecast['is_throttling_risk']}")
        print(f"  -> Undervoltage Risk:     {forecast['is_undervoltage_risk']}")

    print("\nStage 3 Predictor test complete.")


