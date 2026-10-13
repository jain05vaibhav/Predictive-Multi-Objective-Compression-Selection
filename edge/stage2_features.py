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

try:
    import numpy as np
    HAS_NUMPY = True
except (ImportError, Exception):
    HAS_NUMPY = False


class FeatureExtractionStage:
    """
    Stage 2 Feature Extractor:
    Computes statistical and information-theoretic metrics on raw window telemetry
    (sensor readings, Raspberry Pi 3B+ SoC metrics) to guide Stage 4 multi-objective decision making.
    """

    def __init__(self, num_bins: int = 16):
        self.num_bins = num_bins

    def _extract_numeric_series(self, data: List[Any], feature_key: Optional[str] = None) -> List[float]:
        """
        Extracts a clean 1D list of floats from various sample structures
        (primitives, dicts, arrays).
        """
        if not data:
            return []

        first_sample = data[0]

        # Case 1: List of numeric values (int/float)
        if isinstance(first_sample, (int, float)):
            return [float(x) for x in data if isinstance(x, (int, float))]
        elif HAS_NUMPY and isinstance(first_sample, np.number):
            return [float(x) for x in data]

        # Case 2: List of telemetry dictionaries (e.g. DHT22 / RPi 3B+ system metrics)
        if isinstance(first_sample, dict):
            # If feature_key specified, extract it directly
            if feature_key and feature_key in first_sample:
                return [float(s[feature_key]) for s in data if s.get(feature_key) is not None and isinstance(s.get(feature_key), (int, float))]

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
                    return extracted

            # Preference order for primary numeric signal
            candidate_keys = [
                "temperature", "temperature_c", "cpu_temp_c", "cpu_percent",
                "core_voltage_v", "cpu_freq_mhz", "core_freq_mhz", "humidity"
            ]
            for key in candidate_keys:
                if key in first_sample and isinstance(first_sample[key], (int, float)):
                    return [float(s[key]) for s in data if s.get(key) is not None and isinstance(s.get(key), (int, float))]

            # Multi-sensor extraction for comprehensive information density fallback
            aggregated_series = []
            for s in data:
                for k in ["temperature", "humidity", "cpu_temp_c", "cpu_percent", "core_voltage_v"]:
                    if k in s and isinstance(s[k], (int, float)) and s[k] > 0.0:
                        aggregated_series.append(float(s[k]))
            if len(aggregated_series) >= 2:
                return aggregated_series

            # Fallback: extract the first numeric field found in the dict
            for k, v in first_sample.items():
                if isinstance(v, (int, float)):
                    return [float(s[k]) for s in data if s.get(k) is not None and isinstance(s.get(k), (int, float))]

        # Case 3: List of bytes/strings
        if isinstance(first_sample, (bytes, bytearray, str)):
            byte_values: List[float] = []
            for item in data:
                raw = item.encode("utf-8") if isinstance(item, str) else bytes(item)
                byte_values.extend([float(b) for b in raw])
            return byte_values

        return []

    def compute_shannon_entropy(self, series: Union[List[float], Any], num_bins: Optional[int] = None) -> float:
        """
        Computes Shannon entropy H = -sum(p_i * log2(p_i)) over discretized histogram bins.
        Returns 0.0 for uniform/constant series, and approaches log2(num_bins) for max entropy noise.
        """
        if len(series) == 0:
            return 0.0

        bins = num_bins if num_bins is not None else self.num_bins
        val_min, val_max = float(min(series)), float(max(series))

        # If constant signal (min == max), all probability is concentrated in one bin -> H = 0.0
        if math.isclose(val_min, val_max, rel_tol=1e-9, abs_tol=1e-9):
            return 0.0

        total_samples = len(series)
        bin_width = (val_max - val_min) / bins
        if bin_width == 0:
            return 0.0

        counts = [0] * bins
        for x in series:
            idx = int((x - val_min) / bin_width)
            if idx >= bins:
                idx = bins - 1
            elif idx < 0:
                idx = 0
            counts[idx] += 1

        probabilities = [c / total_samples for c in counts if c > 0]
        entropy = -sum(p * math.log2(p) for p in probabilities)
        return float(round(entropy, 4))

    def compute_variance(self, series: Union[List[float], Any]) -> float:
        """
        Computes statistical variance sigma^2 of the series (ddof=0).
        """
        n = len(series)
        if n <= 1:
            return 0.0
        mean_val = sum(series) / n
        var = sum((x - mean_val) ** 2 for x in series) / n
        return float(round(var, 4))

    def compute_rate_of_change(self, series: Union[List[float], Any]) -> float:
        """
        Computes mean step-to-step absolute difference: mean(|x[t] - x[t-1]|).
        """
        n = len(series)
        if n <= 1:
            return 0.0
        diff_sum = sum(abs(series[i] - series[i - 1]) for i in range(1, n))
        return float(round(diff_sum / (n - 1), 4))

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

        sample_count = len(raw_data) if isinstance(raw_data, list) else 1
        criticality = getattr(window, "criticality", "routine") if hasattr(window, "criticality") else (window.get("criticality", "routine") if isinstance(window, dict) else "routine")

        if data_type == "image":
            img_metrics = self.compute_image_features(raw_data)
            return {
                "window_id": window_id,
                "timestamp": timestamp,
                "data_type": "image",
                "criticality": criticality,
                "sample_count": sample_count,
                "entropy": img_metrics["entropy"],
                "variance": img_metrics["variance"],
                "rate_of_change": img_metrics["spatial_gradient_variance"],
                "spatial_gradient_variance": img_metrics["spatial_gradient_variance"],
                "mean_val": img_metrics["mean_intensity"],
                "min_val": 0.0,
                "max_val": 255.0
            }

        if data_type == "text":
            txt_metrics = self.compute_text_features(raw_data)
            return {
                "window_id": window_id,
                "timestamp": timestamp,
                "data_type": "text",
                "criticality": criticality,
                "sample_count": sample_count,
                "entropy": txt_metrics["entropy"],
                "variance": txt_metrics["variance"],
                "rate_of_change": txt_metrics["repetition_index"],
                "repetition_index": txt_metrics["repetition_index"],
                "ascii_ratio": txt_metrics["ascii_ratio"],
                "min_val": 0.0,
                "max_val": 255.0,
                "mean_val": 128.0
            }

        series = self._extract_numeric_series(raw_data, feature_key=feature_key)
        sample_count = len(raw_data) if isinstance(raw_data, list) else len(series)

        if len(series) == 0:
            return {
                "window_id": window_id,
                "timestamp": timestamp,
                "data_type": data_type,
                "criticality": criticality,
                "sample_count": sample_count,
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
            "criticality": criticality,
            "sample_count": sample_count,
            "entropy": entropy,
            "variance": variance,
            "rate_of_change": rate_of_change,
            "min_val": float(round(min(series), 4)),
            "max_val": float(round(max(series), 4)),
            "mean_val": float(round(sum(series) / sample_count, 4))
        }

    def compute_image_features(self, image_data: Any) -> Dict[str, float]:
        """
        Computes 2D spatial intensity entropy and spatial gradient variance on image bytes.
        """
        raw_bytes = b""
        if isinstance(image_data, (bytes, bytearray)):
            raw_bytes = bytes(image_data)
        elif isinstance(image_data, dict):
            raw_bytes = image_data.get("image_bytes", b"")
        elif isinstance(image_data, list) and image_data:
            first = image_data[0]
            if isinstance(first, dict):
                raw_bytes = first.get("image_bytes", b"")
            elif isinstance(first, (bytes, bytearray)):
                raw_bytes = bytes(first)

        if not raw_bytes:
            return {"entropy": 0.0, "variance": 0.0, "spatial_gradient_variance": 0.0, "mean_intensity": 0.0}

        sample_step = max(1, len(raw_bytes) // 4096)
        pixel_vals = [float(b) for b in raw_bytes[::sample_step]]
        n = len(pixel_vals)

        entropy = self.compute_shannon_entropy(pixel_vals, num_bins=256)
        variance = self.compute_variance(pixel_vals)
        grad_diffs = [abs(pixel_vals[i] - pixel_vals[i - 1]) for i in range(1, n)]
        grad_var = self.compute_variance(grad_diffs) if grad_diffs else 0.0
        mean_intensity = sum(pixel_vals) / n if n > 0 else 0.0

        return {
            "entropy": entropy,
            "variance": variance,
            "spatial_gradient_variance": grad_var,
            "mean_intensity": round(mean_intensity, 2)
        }

    def compute_text_features(self, text_data: Any) -> Dict[str, float]:
        """
        Computes byte-level entropy, 4-gram lexical repetition index,
        and printable ASCII ratio on text / log streams.
        """
        raw_str = ""
        if isinstance(text_data, str):
            raw_str = text_data
        elif isinstance(text_data, (bytes, bytearray)):
            raw_str = text_data.decode("utf-8", errors="ignore")
        elif isinstance(text_data, list):
            parts = []
            for item in text_data:
                if isinstance(item, dict):
                    parts.append(item.get("raw_text", str(item)))
                else:
                    parts.append(str(item))
            raw_str = "".join(parts)
        elif isinstance(text_data, dict):
            raw_str = text_data.get("raw_text", str(text_data))

        if not raw_str:
            return {"entropy": 0.0, "variance": 0.0, "repetition_index": 0.0, "ascii_ratio": 1.0}

        raw_bytes = raw_str.encode("utf-8")
        byte_vals = [float(b) for b in raw_bytes]
        entropy = self.compute_shannon_entropy(byte_vals, num_bins=256)
        variance = self.compute_variance(byte_vals)

        total_4grams = max(1, len(raw_str) - 3)
        if len(raw_str) >= 4:
            unique_4grams = len(set(raw_str[i:i+4] for i in range(total_4grams)))
            repetition_index = round(1.0 - (unique_4grams / total_4grams), 4)
        else:
            repetition_index = 0.0

        printable_count = sum(1 for c in raw_str if 32 <= ord(c) <= 126 or c in ('\n', '\r', '\t'))
        ascii_ratio = round(printable_count / max(1, len(raw_str)), 4)

        return {
            "entropy": entropy,
            "variance": variance,
            "repetition_index": repetition_index,
            "ascii_ratio": ascii_ratio
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
    import random
    random.seed(42)
    noise_data = [random.uniform(0.0, 100.0) for _ in range(1000)]
    noise_win = {"window_id": 3, "data": noise_data, "data_type": "numeric"}
    noise_feats = extractor.extract_features(noise_win)
    print(f"Uniform noise window (1000 samples, 16 bins): H={noise_feats['entropy']:.4f} (theoretical max ~ 4.0000)")
    print("Stage 2 execution complete.")


FeatureExtractor = FeatureExtractionStage

