"""
Stage 4: Decoupled Pre-Execution Candidate Cost Estimator (Objective O4, Phase 11A)

Provides lightweight surrogate regression models that estimate performance metrics
(Compression Ratio, Execution Latency, Energy Proxy, Reconstruction Error)
for candidate codecs BEFORE executing compression:
  - Ratio: f_c(Entropy H, Variance, Data Type)
  - Latency: g_c(Data Length L, CPU Load)
  - Energy: h_c(Estimated Latency, Core Voltage, Power Proxy)
  - Error: 0.0 for lossless, calibrated lookup for lossy codecs

Enables single-pass compression execution (Approach a) rather than exhaustive
execution across all candidates (Approach b).
"""

import math
from typing import Dict, Any, List, Optional, Tuple


class PreExecutionCostEstimator:
    """
    Surrogate regression cost model estimating candidate codec metrics
    directly from Stage 2 feature vectors and Stage 3 resource forecasts.
    """

    CANDIDATE_CODECS = ["lz4", "zstd", "bzip2", "gzip", "delta_zlib", "none"]

    # Empirical baseline prior coefficients per codec
    # ratio = base_ratio * max(0.1, 1.0 - entropy_sensitivity * (H / H_max))
    # latency_ms_per_kb = base_lat * (1.0 + cpu_sensitivity * cpu_load_norm)
    CODEC_MODELS = {
        "lz4": {
            "base_ratio": 4.5,
            "entropy_sensitivity": 0.65,
            "base_lat_per_kb": 0.05,
            "cpu_sensitivity": 0.30,
            "energy_uj_per_kb": 50.0,
            "lossy": False,
            "default_level": 1
        },
        "zstd": {
            "base_ratio": 12.0,
            "entropy_sensitivity": 0.75,
            "base_lat_per_kb": 0.30,
            "cpu_sensitivity": 0.50,
            "energy_uj_per_kb": 350.0,
            "lossy": False,
            "default_level": 3
        },
        "bzip2": {
            "base_ratio": 10.0,
            "entropy_sensitivity": 0.70,
            "base_lat_per_kb": 0.50,
            "cpu_sensitivity": 0.60,
            "energy_uj_per_kb": 600.0,
            "lossy": False,
            "default_level": 9
        },
        "gzip": {
            "base_ratio": 6.5,
            "entropy_sensitivity": 0.60,
            "base_lat_per_kb": 0.25,
            "cpu_sensitivity": 0.40,
            "energy_uj_per_kb": 300.0,
            "lossy": False,
            "default_level": 6
        },
        "delta_zlib": {
            "base_ratio": 8.0,
            "entropy_sensitivity": 0.80,
            "base_lat_per_kb": 0.20,
            "cpu_sensitivity": 0.35,
            "energy_uj_per_kb": 250.0,
            "lossy": False,
            "default_level": 6
        },
        "none": {
            "base_ratio": 1.0,
            "entropy_sensitivity": 0.0,
            "base_lat_per_kb": 0.001,
            "cpu_sensitivity": 0.0,
            "energy_uj_per_kb": 1.0,
            "lossy": False,
            "default_level": 0
        }
    }

    def __init__(self, learning_rate: float = 0.05):
        self.learning_rate = float(learning_rate)
        # Deep copy models so online updates adapt instance state
        self.models: Dict[str, Dict[str, Any]] = {
            k: dict(v) for k, v in self.CODEC_MODELS.items()
        }
        self.total_updates = 0

    def estimate_candidate(
        self,
        codec: str,
        features: Dict[str, Any],
        predictions: Optional[Dict[str, Any]] = None,
        raw_size_bytes: int = 1024,
        level: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Estimates expected ratio, latency (ms), energy (uJ), and error
        for a single codec configuration before compression is executed.
        """
        c_name = codec.lower()
        model = self.models.get(c_name, self.models["none"])

        entropy = float(features.get("entropy", 1.5))
        max_h = 4.0 if features.get("data_type") != "image" else 8.0
        h_norm = max(0.0, min(1.0, entropy / max_h))

        preds = predictions or {}
        cpu_load = float(preds.get("predicted_cpu_load", 20.0)) / 100.0
        raw_kb = max(0.01, raw_size_bytes / 1024.0)

        # 1. Ratio Estimation: f_c(H)
        base_r = model["base_ratio"]
        sensitivity = model["entropy_sensitivity"]
        # Higher entropy drops ratio towards 1.0
        predicted_ratio = max(1.0, base_r * (1.0 - sensitivity * h_norm))

        # Special case: delta_zlib performs even better when variance is low
        if c_name == "delta_zlib":
            var = float(features.get("variance", 1.0))
            if var < 0.1:
                predicted_ratio *= 1.4

        # 2. Latency Estimation: g_c(L, CPU)
        base_lat_kb = model["base_lat_per_kb"]
        cpu_sens = model["cpu_sensitivity"]
        predicted_lat_ms = base_lat_kb * raw_kb * (1.0 + cpu_sens * cpu_load)

        # 3. Energy Estimation: h_c(Latency, Power)
        energy_rate = model["energy_uj_per_kb"]
        predicted_energy_uj = energy_rate * raw_kb * (1.0 + 0.5 * cpu_load)

        # 4. Error Estimation
        predicted_error = 0.0

        return {
            "codec": c_name,
            "estimated_ratio": round(predicted_ratio, 3),
            "estimated_latency_ms": round(predicted_lat_ms, 4),
            "estimated_energy_uj": round(predicted_energy_uj, 2),
            "estimated_error": predicted_error,
            "estimated_compressed_bytes": max(1, int(raw_size_bytes / predicted_ratio))
        }

    def estimate_all_candidates(
        self,
        features: Dict[str, Any],
        predictions: Optional[Dict[str, Any]] = None,
        raw_size_bytes: int = 1024,
        candidate_list: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Computes pre-execution estimates across all candidate codecs.
        """
        candidates = candidate_list or self.CANDIDATE_CODECS
        estimates = {}
        for c in candidates:
            estimates[c] = self.estimate_candidate(
                codec=c,
                features=features,
                predictions=predictions,
                raw_size_bytes=raw_size_bytes
            )
        return estimates

    def update_model(
        self,
        codec: str,
        features: Dict[str, Any],
        actual_outcome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Online gradient refinement of estimator coefficients from real measured outcomes.
        """
        c_name = codec.lower()
        if c_name not in self.models:
            return {}

        model = self.models[c_name]
        actual_ratio = float(actual_outcome.get("ratio", 1.0))
        actual_lat = float(actual_outcome.get("latency_ms", 0.1))
        actual_energy = float(actual_outcome.get("energy_uj", 50.0))

        raw_size = max(100, int(actual_outcome.get("raw_bytes", 1024)))
        raw_kb = raw_size / 1024.0

        # Estimate before update
        est = self.estimate_candidate(c_name, features, raw_size_bytes=raw_size)
        ratio_err = actual_ratio - est["estimated_ratio"]

        # Adapt base ratio towards observed performance
        model["base_ratio"] = max(1.0, model["base_ratio"] + self.learning_rate * ratio_err)

        # Adapt base latency rate
        meas_lat_per_kb = actual_lat / raw_kb
        model["base_lat_per_kb"] = max(0.0001, model["base_lat_per_kb"] + self.learning_rate * (meas_lat_per_kb - model["base_lat_per_kb"]))

        self.total_updates += 1
        return {
            "codec": c_name,
            "ratio_error": round(ratio_err, 4),
            "updated_base_ratio": round(model["base_ratio"], 3),
            "total_updates": self.total_updates
        }
