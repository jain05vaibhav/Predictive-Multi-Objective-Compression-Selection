"""
Stage 5: Dynamic Compression Execution Engine

Implements real candidate compression codecs (LZ4, Zstandard, Bzip2, Gzip/Deflate,
Delta-Zlib, and Passthrough) with high-resolution execution timing, size ratios,
CPU energy estimation, and lossless decompression verification.
"""

import bz2
import json
import time
import zlib
from typing import Dict, Any, Optional, Union, List, Tuple

# Optional external high-speed codec bindings with pure standard library fallbacks
try:
    import lz4.frame as lz4_frame  # type: ignore
    LZ4_AVAILABLE = True
except ImportError:
    lz4_frame = None
    LZ4_AVAILABLE = False

try:
    import zstandard as zstd  # type: ignore
    ZSTD_AVAILABLE = True
except ImportError:
    zstd = None
    ZSTD_AVAILABLE = False


def delta_encode_bytes(raw_bytes: bytes) -> bytes:
    """
    Computes first-order consecutive differences (d_t = x_t - x_{t-1} mod 256)
    on raw byte streams to maximize redundancy on continuous sensor telemetry.
    """
    if not raw_bytes:
        return b""
    encoded = bytearray(len(raw_bytes))
    encoded[0] = raw_bytes[0]
    for i in range(1, len(raw_bytes)):
        encoded[i] = (raw_bytes[i] - raw_bytes[i - 1]) & 0xFF
    return bytes(encoded)


def delta_decode_bytes(delta_bytes: bytes) -> bytes:
    """
    Inverts first-order byte differences to reconstruct the original stream.
    """
    if not delta_bytes:
        return b""
    decoded = bytearray(len(delta_bytes))
    decoded[0] = delta_bytes[0]
    for i in range(1, len(delta_bytes)):
        decoded[i] = (decoded[i - 1] + delta_bytes[i]) & 0xFF
    return bytes(decoded)


class CompressionStage:
    """
    Stage 5 Dynamic Compression Engine.
    Executes and profiles candidate codecs on edge telemetry payloads.
    """

    AVAILABLE_CODECS = ["lz4", "zstd", "bzip2", "gzip", "delta_zlib", "none"]

    def __init__(self, default_codec: str = "lz4", power_proxy_mw: float = 2000.0):
        self.default_codec = default_codec.lower()
        self.power_proxy_mw = float(power_proxy_mw)

    def _serialize_payload(self, data: Any) -> bytes:
        """
        Standardizes diverse input formats (Window objects, dicts, lists, strings, bytes)
        into raw bytes ready for compression.
        """
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if hasattr(data, "to_bytes") and callable(data.to_bytes):
            return data.to_bytes()
        if isinstance(data, (dict, list)):
            return json.dumps(data, separators=(",", ":"), default=str).encode("utf-8")
        return str(data).encode("utf-8")

    def compress(
        self,
        data: Any,
        codec: Optional[str] = None,
        level: int = 1,
        window_id: int = 0
    ) -> Dict[str, Any]:
        """
        Compresses input payload using the specified codec and returns a performance report.
        """
        raw_bytes = self._serialize_payload(data)
        raw_size = len(raw_bytes)
        chosen_codec = (codec or self.default_codec).lower()

        t_start = time.perf_counter_ns()
        compressed_bytes = self._execute_compress(raw_bytes, chosen_codec, level)
        t_end = time.perf_counter_ns()

        exec_ns = max(1, t_end - t_start)
        exec_ms = exec_ns / 1_000_000.0
        comp_size = len(compressed_bytes)
        ratio = round(raw_size / max(1, comp_size), 4)
        savings_pct = round((1.0 - (comp_size / max(1, raw_size))) * 100.0, 2)

        # Estimated CPU energy proxy in microjoules: Power (mW) * time (s) * 1000
        # Energy (uJ) = (mW) * (ms)
        energy_uj = round(self.power_proxy_mw * exec_ms, 2)
        throughput_mbps = round((raw_size * 8.0) / (exec_ns / 1000.0), 2)

        return {
            "window_id": window_id,
            "compressor_used": chosen_codec,
            "compression_level": level,
            "raw_size_bytes": raw_size,
            "compressed_size_bytes": comp_size,
            "compression_ratio": ratio,
            "space_savings_percent": savings_pct,
            "execution_time_ms": round(exec_ms, 4),
            "throughput_mbps": throughput_mbps,
            "cpu_energy_proxy_uj": energy_uj,
            "compressed_payload": compressed_bytes
        }

    def _execute_compress(self, raw_bytes: bytes, codec: str, level: int) -> bytes:
        """Internal compressor dispatcher."""
        if codec in ("none", "passthrough"):
            return raw_bytes

        if codec == "lz4":
            if LZ4_AVAILABLE and lz4_frame is not None:
                return lz4_frame.compress(raw_bytes, compression_level=max(0, min(16, level)))
            # Fallback to fast zlib level 1 if lz4 package not installed
            return zlib.compress(raw_bytes, level=1)

        if codec in ("zstd", "zstandard"):
            if ZSTD_AVAILABLE and zstd is not None:
                cctx = zstd.ZstdCompressor(level=max(1, min(19, level)))
                return cctx.compress(raw_bytes)
            # Fallback to balanced zlib level 6
            return zlib.compress(raw_bytes, level=6)

        if codec in ("bzip2", "bz2"):
            return bz2.compress(raw_bytes, compresslevel=max(1, min(9, level)))

        if codec in ("gzip", "zlib", "deflate"):
            return zlib.compress(raw_bytes, level=max(1, min(9, level)))

        if codec in ("delta_zlib", "delta"):
            delta_stream = delta_encode_bytes(raw_bytes)
            return zlib.compress(delta_stream, level=max(1, min(9, level)))

        # Default fallback
        return zlib.compress(raw_bytes, level=1)

    def decompress(self, compressed_payload: bytes, codec: str) -> bytes:
        """
        Decompresses payload back to original raw bytes.
        """
        codec = codec.lower()
        if codec in ("none", "passthrough"):
            return compressed_payload

        if codec == "lz4":
            if LZ4_AVAILABLE and lz4_frame is not None:
                try:
                    return lz4_frame.decompress(compressed_payload)
                except Exception:
                    pass
            # Try zlib fallback decompression
            return zlib.decompress(compressed_payload)

        if codec in ("zstd", "zstandard"):
            if ZSTD_AVAILABLE and zstd is not None:
                try:
                    dctx = zstd.ZstdDecompressor()
                    return dctx.decompress(compressed_payload)
                except Exception:
                    pass
            return zlib.decompress(compressed_payload)

        if codec in ("bzip2", "bz2"):
            return bz2.decompress(compressed_payload)

        if codec in ("gzip", "zlib", "deflate"):
            return zlib.decompress(compressed_payload)

        if codec in ("delta_zlib", "delta"):
            raw_delta = zlib.decompress(compressed_payload)
            return delta_decode_bytes(raw_delta)

        # Fallback
        return zlib.decompress(compressed_payload)

    def verify_lossless(self, original_data: Any, codec: str) -> bool:
        """
        Verifies exact byte-for-byte lossless reconstruction for a given codec.
        """
        raw_bytes = self._serialize_payload(original_data)
        res = self.compress(raw_bytes, codec=codec)
        decompressed = self.decompress(res["compressed_payload"], codec=codec)
        return raw_bytes == decompressed

    def benchmark_all_codecs(self, data: Any) -> Dict[str, Dict[str, Any]]:
        """
        Profiles the given payload across all available candidate codecs.
        """
        results = {}
        for codec_name in self.AVAILABLE_CODECS:
            res = self.compress(data, codec=codec_name)
            is_valid = self.verify_lossless(data, codec=codec_name)
            results[codec_name] = {
                "ratio": res["compression_ratio"],
                "raw_bytes": res["raw_size_bytes"],
                "compressed_bytes": res["compressed_size_bytes"],
                "latency_ms": res["execution_time_ms"],
                "throughput_mbps": res["throughput_mbps"],
                "energy_uj": res["cpu_energy_proxy_uj"],
                "lossless": is_valid
            }
        return results

    def compress_payload(self, raw_window: Any, decision: Any) -> Dict[str, Any]:
        """
        Pipeline integration adapter accepting (Window, Decision) tuple or object.
        """
        codec = "lz4"
        level = 1
        window_id = 0

        if isinstance(decision, tuple) and len(decision) >= 1:
            codec = str(decision[0])
            if len(decision) >= 2 and isinstance(decision[1], int):
                level = decision[1]
        elif isinstance(decision, dict):
            codec = decision.get("chosen_compressor", "lz4")
            level = decision.get("compression_level", 1)
            window_id = decision.get("window_id", 0)

        if hasattr(raw_window, "window_id"):
            window_id = getattr(raw_window, "window_id")

        return self.compress(raw_window, codec=codec, level=level, window_id=window_id)


if __name__ == "__main__":
    print("=== Testing Stage 5: Dynamic Compression Execution Engine ===")
    comp_engine = CompressionStage()

    # Generate structured synthetic environmental telemetry payload (50 samples)
    sample_window = [
        {
            "timestamp": 1788200000.0 + i * 0.1,
            "temperature": 23.5 + (i * 0.02),
            "humidity": 60.0 + (i * 0.05),
            "cpu_temp_c": 38.5 + (i * 0.01),
            "cpu_percent": 15.0 + (i % 5),
            "core_voltage_v": 1.25,
            "memory_percent": 26.5
        }
        for i in range(50)
    ]

    print(f"\nBenchmarking Candidate Codecs on Window Payload (50 samples)...")
    bench_results = comp_engine.benchmark_all_codecs(sample_window)

    print("\n" + "=" * 80)
    print(f"{'Codec':<12} | {'Raw (B)':<8} | {'Comp (B)':<8} | {'Ratio':<7} | {'Time (ms)':<10} | {'Throughput':<12} | {'Energy (uJ)':<10} | {'Valid'}")
    print("-" * 80)
    for codec, metrics in bench_results.items():
        print(f"{codec:<12} | {metrics['raw_bytes']:<8} | {metrics['compressed_bytes']:<8} | {metrics['ratio']:<7.3f} | {metrics['latency_ms']:<10.4f} | {metrics['throughput_mbps']:<7.1f} Mbps | {metrics['energy_uj']:<10.2f} | {metrics['lossless']}")
    print("=" * 80)

    print("\nStage 5 Compression test complete.")

