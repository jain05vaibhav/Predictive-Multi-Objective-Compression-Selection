"""
AURA-EDGE Multi-Objective File Compression Engine

Applies the 8-stage predictive multi-objective compression pipeline
to arbitrary files (CSV, JSON, LOG, BIN, PNG/JPG, TXT, etc.).
Extracts file entropy and byte features, selects Pareto-optimal codec,
benchmarks candidate algorithms, and validates lossless reconstruction.
"""

import os
import math
import time
from typing import Dict, Any, List, Optional
from edge.stage2_features import FeatureExtractionStage
from edge.stage5_decision import HierarchicalDecisionEngine
from edge.stage6_compression import CompressionStage


class FileCompressionEngine:
    """End-to-end multi-objective compression engine for arbitrary files."""

    def __init__(self):
        self.feature_extractor = FeatureExtractionStage()
        self.decision_engine = HierarchicalDecisionEngine()
        self.compression_stage = CompressionStage()

    def analyze_file(self, file_bytes: bytes, filename: str = "data.bin") -> Dict[str, Any]:
        """
        Analyzes byte distribution, Shannon entropy H, and characteristics of an arbitrary file.
        """
        raw_size = len(file_bytes)
        if raw_size == 0:
            return {
                "filename": filename,
                "raw_size_bytes": 0,
                "entropy": 0.0,
                "variance": 0.0,
                "unique_bytes_ratio": 0.0,
                "modality": "empty"
            }

        # Shannon Entropy H
        counts = [0] * 256
        for b in file_bytes:
            counts[b] += 1

        entropy = 0.0
        unique_bytes = 0
        for c in counts:
            if c > 0:
                p = c / raw_size
                entropy -= p * math.log2(p)
                unique_bytes += 1

        # Mean and Variance
        mean_val = sum(b for b in file_bytes) / raw_size
        variance = sum((b - mean_val) ** 2 for b in file_bytes) / raw_size

        # Inferred Modality
        ext = os.path.splitext(filename)[1].lower()
        if ext in [".csv", ".tsv", ".dat"]:
            modality = "numeric"
        elif ext in [".json", ".xml", ".txt", ".log", ".yaml"]:
            modality = "text_telemetry"
        elif ext in [".png", ".jpg", ".jpeg", ".bmp"]:
            modality = "image"
        else:
            modality = "binary"

        return {
            "filename": filename,
            "raw_size_bytes": raw_size,
            "entropy": round(entropy, 4),
            "variance": round(variance, 4),
            "unique_bytes": unique_bytes,
            "unique_bytes_ratio": round(unique_bytes / 256.0, 4),
            "modality": modality
        }

    def recommend_codec(
        self,
        features: Dict[str, Any],
        system_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs Stage 5 Multi-Objective Decision Engine to find the Pareto-optimal codec.
        """
        ctx = {
            "predicted_cpu_temp": 42.0,
            "predicted_cpu_load": 15.0,
            "predicted_bandwidth_kbps": 1200.0,
            "battery_percent": 95.0,
            "is_throttling_risk": False
        }
        if system_context:
            ctx.update(system_context)

        feat_dict = {
            "entropy": features.get("entropy", 1.5),
            "variance": features.get("variance", 0.1),
            "data_type": features.get("modality", "numeric"),
            "criticality": "routine"
        }

        decision = self.decision_engine.select_strategy(feat_dict, ctx)
        return decision

    def compress_file(
        self,
        file_bytes: bytes,
        codec: Optional[str] = None,
        system_context: Optional[Dict[str, Any]] = None,
        benchmark_all: bool = True,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes multi-objective compression on arbitrary file bytes.
        Returns compression results, benchmark matrix across all codecs,
        and decompressed lossless integrity verification.
        """
        features = self.analyze_file(file_bytes)
        raw_size = len(file_bytes)
        out_filename = filename or "payload.bin"

        if raw_size == 0:
            return {
                "features": features,
                "chosen_codec": "none",
                "compressed_size_bytes": 0,
                "compression_ratio": 1.0,
                "latency_ms": 0.0,
                "reconstruction_error": 0.0,
                "benchmark": []
            }

        # Determine recommended codec if not specified
        recommendation = self.recommend_codec(features, system_context)
        chosen_codec = codec or recommendation.get("chosen_compressor", "lz4")

        # Execute chosen codec
        comp_res = self.compression_stage.compress(file_bytes, codec=chosen_codec)
        comp_bytes = comp_res.get("compressed_payload", b"")
        t_comp = comp_res.get("execution_time_ms", 0.0)

        comp_size = len(comp_bytes)
        ratio = comp_res.get("compression_ratio", round(raw_size / max(1, comp_size), 4))

        # Lossless Verification (Decompress)
        t_dec0 = time.perf_counter_ns()
        decomp_bytes = self.compression_stage.decompress(comp_bytes, codec=chosen_codec)
        t_decomp = (time.perf_counter_ns() - t_dec0) / 1_000_000.0

        is_lossless = (decomp_bytes == file_bytes)
        error = 0.0 if is_lossless else 1.0

        throughput_mb_s = comp_res.get("throughput_mbps", round((raw_size / (1024 * 1024)) / max(0.0001, t_comp / 1000.0), 2))
        saved_bytes = raw_size - comp_size
        saved_pct = comp_res.get("space_savings_percent", round((saved_bytes / max(1, raw_size)) * 100.0, 2))

        # Benchmark all codecs if requested
        benchmark = []
        if benchmark_all:
            candidates = ["lz4", "zstd", "delta_zlib", "gzip", "bzip2", "none"]
            for cand in candidates:
                try:
                    c_res = self.compression_stage.compress(file_bytes, codec=cand)
                    c_payload = c_res.get("compressed_payload", b"")
                    c_size = len(c_payload)
                    c_ratio = c_res.get("compression_ratio", round(raw_size / max(1, c_size), 4))
                    c_ms = c_res.get("execution_time_ms", 0.0)
                    c_thru = c_res.get("throughput_mbps", 0.0)
                    c_saved = c_res.get("space_savings_percent", round(((raw_size - c_size) / max(1, raw_size)) * 100.0, 2))
                    energy_uj = c_res.get("cpu_energy_proxy_uj", round(c_ms * 120.0, 1))

                    benchmark.append({
                        "codec": cand,
                        "compressed_size_bytes": c_size,
                        "ratio": c_ratio,
                        "latency_ms": round(c_ms, 3),
                        "throughput_mb_s": round(c_thru, 2),
                        "saved_pct": round(c_saved, 2),
                        "energy_proxy_uj": round(energy_uj, 1),
                        "is_chosen": (cand == chosen_codec)
                    })
                except Exception:
                    pass
                    pass

        return {
            "features": features,
            "recommendation": recommendation,
            "chosen_codec": chosen_codec,
            "raw_size_bytes": raw_size,
            "compressed_size_bytes": comp_size,
            "compression_ratio": ratio,
            "latency_ms": round(t_comp, 3),
            "decompress_latency_ms": round(t_decomp, 3),
            "throughput_mb_s": throughput_mb_s,
            "saved_bytes": saved_bytes,
            "saved_bandwidth_percent": saved_pct,
            "reconstruction_error": error,
            "is_lossless": is_lossless,
            "compressed_payload": comp_bytes,
            "filename": out_filename,
            "benchmark": benchmark
        }
