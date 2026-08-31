"""
Stage 2: Feature Extraction (Raspberry Pi 3B+)

Compresses each acquired Window into a compact feature vector containing:
- Shannon Entropy (H): measures information density & compressibility
- Variance (sigma^2): measures signal fluctuation / dispersion
- Rate of Change: measures mean step-to-step absolute difference
- Data type tag & metadata
"""

import math
from typing import List, Dict, Any, Union, Optional
import numpy as np


class FeatureExtractionStage:
    """
    Stage 2 Feature Extractor:
    Computes statistical and information-theoretic metrics on raw window telemetry
    (sensor readings, Raspberry Pi 3B+ SoC metrics) to guide Stage 4 multi-objective decision making.
    """

    def __init__(self, num_bins: int = 16):
        self.num_bins = num_bins

    def _extract_numeric_series(self, data: List[Any], feature_key: Optional[str] = None) -> np.ndarray:
        """
        Extracts a clean 1D numpy float array from various sample structures
        (primitives, dicts, arrays).
        """
        if not data:
            return np.array([], dtype=float)

        first_sample = data[0]

        # Case 1: List of numeric values (int/float)
        if isinstance(first_sample, (int, float, np.number)):
            return np.array(data, dtype=float)

        # Case 2: List of telemetry dictionaries (e.g. DHT22 / RPi 3B+ system metrics)
        if isinstance(first_sample, dict):
            # If feature_key specified, extract it directly
            if feature_key and feature_key in first_sample:
                return np.array([float(s[feature_key]) for s in data if s.get(feature_key) is not None], dtype=float)

            # Check nested sections if feature_key is specified (e.g. "system.cpu_temp_c" or "cpu_temp_c")
            if feature_key:
                extracted = []
                for s in data:
                    val = None
                    if feature_key in s:
                        val = s[feature_key]
                    elif "system" in s and isinstance(s["system"], dict) and feature_key in s["system"]:
                        val = s["system"][feature_key]
                    elif "dht22" in s and isinstance(s["dht22"], dict) and feature_key in s["dht22"]:
                        val = s["dht22"][feature_key]
                    if val is not None and isinstance(val, (int, float)):
                        extracted.append(float(val))
                if extracted:
                    return np.array(extracted, dtype=float)

            # Preference order for primary numeric signal
            candidate_keys = [
                "temperature", "temperature_c", "cpu_temp_c", "cpu_percent",
                "core_voltage_v", "cpu_freq_mhz", "core_freq_mhz", "humidity"
            ]
            for key in candidate_keys:
                if key in first_sample and isinstance(first_sample[key], (int, float)):
                    return np.array([float(s[key]) for s in data if s.get(key) is not None], dtype=float)

            # Fallback: extract the first numeric field found in the dict
            for k, v in first_sample.items():
                if isinstance(v, (int, float)):
                    return np.array([float(s[k]) for s in data if s.get(k) is not None and isinstance(s.get(k), (int, float))], dtype=float)

        # Case 3: List of bytes/strings
        if isinstance(first_sample, (bytes, bytearray, str)):
            byte_values = []
            for item in data:
                raw = item.encode("utf-8") if isinstance(item, str) else bytes(item)
                byte_values.extend(list(raw))
            return np.array(byte_values, dtype=float)

        return np.array([], dtype=float)

    def compute_shannon_entropy(self, series: np.ndarray, num_bins: Optional[int] = None) -> float:
        """
        Computes Shannon entropy H = -sum(p_i * log2(p_i)) over discretized histogram bins.
        Returns 0.0 for uniform/constant series, and approaches log2(num_bins) for max entropy noise.
        """
        if len(series) == 0:
            return 0.0

        bins = num_bins if num_bins is not None else self.num_bins

        # If constant signal (min == max), all probability is concentrated in one bin -> H = 0.0
        val_min, val_max = float(np.min(series)), float(np.max(series))
        if math.isclose(val_min, val_max, rel_tol=1e-9, abs_tol=1e-9):
            return 0.0

        # Construct histogram counts
        counts, _ = np.histogram(series, bins=bins, range=(val_min, val_max))
        total_samples = len(series)

        # Calculate probability distribution p_i
        probabilities = counts[counts > 0] / total_samples

        # Shannon entropy calculation
        entropy = -np.sum(probabilities * np.log2(probabilities))
        return float(round(entropy, 4))

    def compute_variance(self, series: np.ndarray) -> float:
        """
        Computes statistical variance sigma^2 of the series.
        """
        if len(series) <= 1:
            return 0.0
        return float(round(np.var(series, ddof=0), 4))

    def compute_rate_of_change(self, series: np.ndarray) -> float:
        """
        Computes mean step-to-step absolute difference: mean(|x[t] - x[t-1]|).
        """
        if len(series) <= 1:
            return 0.0
        diffs = np.abs(np.diff(series))
        return float(round(np.mean(diffs), 4))

    def extract_features(
        self,
        window: Union[Dict[str, Any], Any],
        feature_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extracts feature vector from a Window object or dictionary.
        
        INPUT: Window (from Stage 1)
        OUTPUT: feature_vector = {
            "entropy": float,
            "variance": float,
            "rate_of_change": float,
            "data_type": str,
            "window_id": int,
            "sample_count": int,
            "min_val": float,
            "max_val": float,
            "mean_val": float
        }
        """
        # Handle dict or Window object
        if hasattr(window, "data"):
            raw_data = window.data
            data_type = getattr(window, "data_type", "numeric")
            window_id = getattr(window, "window_id", 0)
            timestamp = getattr(window, "timestamp", 0.0)
        elif isinstance(window, dict):
            raw_data = window.get("data", [])
            data_type = window.get("data_type", "numeric")
            window_id = window.get("window_id", 0)
            timestamp = window.get("timestamp", 0.0)
        else:
            raw_data = window if isinstance(window, list) else [window]
            data_type = "numeric"
            window_id = 0
            timestamp = 0.0

        series = self._extract_numeric_series(raw_data, feature_key=feature_key)
        sample_count = len(series)

        if sample_count == 0:
            return {
                "window_id": window_id,
                "timestamp": timestamp,
                "data_type": data_type,
                "sample_count": 0,
                "entropy": 0.0,
                "variance": 0.0,
                "rate_of_change": 0.0,
                "min_val": 0.0,
                "max_val": 0.0,
                "mean_val": 0.0
            }

        entropy = self.compute_shannon_entropy(series)
        variance = self.compute_variance(series)
        rate_of_change = self.compute_rate_of_change(series)

        return {
            "window_id": window_id,
            "timestamp": timestamp,
            "data_type": data_type,
            "sample_count": sample_count,
            "entropy": entropy,
            "variance": variance,
            "rate_of_change": rate_of_change,
            "min_val": float(round(np.min(series), 4)),
            "max_val": float(round(np.max(series), 4)),
            "mean_val": float(round(np.mean(series), 4))
        }


if __name__ == "__main__":
    print("=== Stage 2: Feature Extraction Standalone Test ===")
    extractor = FeatureExtractionStage(num_bins=16)

    # 1. Constant Window Test (Compressible, Entropy -> 0)
    const_win = {"window_id": 1, "data": [24.0] * 50, "data_type": "numeric"}
    const_feats = extractor.extract_features(const_win)
    print(f"Constant window: H={const_feats['entropy']:.4f}, var={const_feats['variance']:.4f}, roc={const_feats['rate_of_change']:.4f}")

    # 2. Linear Ramp Window Test (Step = 1.0)
    ramp_win = {"window_id": 2, "data": [float(i) for i in range(50)], "data_type": "numeric"}
    ramp_feats = extractor.extract_features(ramp_win)
    print(f"Linear ramp window: H={ramp_feats['entropy']:.4f}, var={ramp_feats['variance']:.4f}, roc={ramp_feats['rate_of_change']:.4f}")

    # 3. Uniform Random Noise Window Test (High Entropy -> log2(16) = 4.0)
    np.random.seed(42)
    noise_win = {"window_id": 3, "data": list(np.random.uniform(0, 100, 1000)), "data_type": "numeric"}
    noise_feats = extractor.extract_features(noise_win)
    print(f"Uniform noise window (1000 samples, 16 bins): H={noise_feats['entropy']:.4f} (theoretical max ~ 4.0000)")
    print("Stage 2 execution complete.")
