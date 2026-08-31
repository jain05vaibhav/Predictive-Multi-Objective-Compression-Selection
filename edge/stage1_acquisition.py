"""
Stage 1: Data Acquisition & Windowing

Turns a continuous sensor telemetry stream into discrete, uniformly-sized
windows (size N or max wait time T_max) for downstream feature extraction,
prediction, and compression.
"""

import time
import json
from typing import List, Dict, Any, Optional, Union
from edge.config import WINDOW_SIZE_N
from edge.sensors.simulated_source import SimulatedSource


class Window:
    """
    Encapsulates a discrete window of acquired sensor data.
    """
    def __init__(
        self,
        window_id: int,
        data: List[Any],
        data_type: str = "numeric",
        timestamp: Optional[float] = None
    ):
        self.window_id = window_id
        self.data = data
        self.data_type = data_type
        self.timestamp = timestamp if timestamp is not None else time.time()

    @property
    def sample_count(self) -> int:
        return len(self.data)

    def to_dict(self) -> Dict[str, Any]:
        """Converts Window object to dictionary representation."""
        return {
            "window_id": self.window_id,
            "timestamp": self.timestamp,
            "data_type": self.data_type,
            "sample_count": self.sample_count,
            "data": self.data
        }

    def to_bytes(self) -> bytes:
        """
        Serializes the window payload into raw bytes for Stage 5 compression.
        Handles dicts, primitives, text, and raw byte arrays.
        """
        if self.data_type == "image":
            # If data is a list of frame dicts or image bytes
            if self.data and isinstance(self.data[0], dict) and "image_bytes" in self.data[0]:
                return b"".join(item["image_bytes"] for item in self.data)
            elif self.data and isinstance(self.data[0], (bytes, bytearray)):
                return b"".join(self.data)
        
        # Default JSON UTF-8 byte serialization for numeric/text telemetry
        return json.dumps(self.data, default=str).encode("utf-8")

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item == "sample_count":
            return self.sample_count
        raise KeyError(f"Window has no property '{item}'")

    def __repr__(self) -> str:
        return f"<Window id={self.window_id} type='{self.data_type}' samples={self.sample_count} ts={self.timestamp:.2f}>"


class AcquisitionStage:
    """
    Stage 1 Acquisition Engine:
    Samples from physical or simulated sensors and partitions the continuous stream
    into discrete Window objects of size N (or when T_max expires).
    """

    def __init__(
        self,
        source: Optional[Any] = None,
        window_size: int = WINDOW_SIZE_N,
        max_wait_time: float = 5.0,
        data_type: str = "numeric"
    ):
        # Prefer the actual Raspberry Pi DHT22 path by default; automatically falls back
        # to simulation if hardware initialization fails or the sensor libraries are missing.
        self.source = source if source is not None else SimulatedSource(use_real_hardware=True)
        self.window_size = window_size
        self.max_wait_time = max_wait_time
        self.data_type = data_type
        self.window_counter = 0

    def read_sample(self, source_override: Optional[Any] = None) -> Any:
        """
        Reads a single sample from the active sensor source.
        """
        active_source = source_override if source_override is not None else self.source

        if callable(active_source):
            return active_source()
        
        # Check standard SimulatedSource / Sensor interface
        if hasattr(active_source, "read_all"):
            return active_source.read_all()
        elif hasattr(active_source, "read"):
            return active_source.read()
        elif hasattr(active_source, "capture_frame"):
            return active_source.capture_frame()
        elif isinstance(active_source, (list, tuple)):
            if len(active_source) > 0:
                return active_source.pop(0) if isinstance(active_source, list) else active_source[0]
            return None
        
        raise ValueError(f"Unsupported sensor source type: {type(active_source)}")

    def acquire_window(
        self,
        source: Optional[Any] = None,
        window_size: Optional[int] = None,
        timeout: Optional[float] = None,
        data_type: Optional[str] = None
    ) -> Window:
        """
        Gathers samples until window_size is reached or timeout expires.
        Returns a structured Window object.
        """
        n = window_size if window_size is not None else self.window_size
        t_max = timeout if timeout is not None else self.max_wait_time
        d_type = data_type if data_type is not None else self.data_type

        buffer: List[Any] = []
        start_time = time.time()

        while len(buffer) < n and (time.time() - start_time) < t_max:
            sample = self.read_sample(source_override=source)
            if sample is not None:
                buffer.append(sample)
            else:
                # If stream is exhausted, break early
                break

        self.window_counter += 1
        window = Window(
            window_id=self.window_counter,
            data=buffer,
            data_type=d_type,
            timestamp=start_time
        )
        return window

    def stream_windows(self, max_windows: Optional[int] = None, sample_interval: float = 0.01):
        """
        Generator that continuously emits Window objects.
        """
        count = 0
        while max_windows is None or count < max_windows:
            window = self.acquire_window()
            yield window
            count += 1
            if sample_interval > 0:
                time.sleep(sample_interval)


if __name__ == "__main__":
    print("=== Stage 1: Data Acquisition Standalone Test ===")
    stage1 = AcquisitionStage(window_size=10, max_wait_time=2.0)
    print(f"Acquiring 3 windows with window_size={stage1.window_size}...")

    for w in stage1.stream_windows(max_windows=3, sample_interval=0.05):
        print(f"Emitted {w}")
        if w.data:
            sample_preview = w.data[0]
            cam_preview = sample_preview.get("camera", {})
            print(f"  First sample preview:")
            print(f"    - Temperature: {sample_preview.get('temperature', 'N/A')} °C")
            print(f"    - Humidity:    {sample_preview.get('humidity', 'N/A')} %")
            print(f"    - Power Rail:  {sample_preview.get('voltage_v', 'N/A')} V, {sample_preview.get('current_ma', 'N/A')} mA, {sample_preview.get('power_mw', 'N/A')} mW")
            print(f"    - Camera:      Frame #{cam_preview.get('frame_id', 'N/A')} | "
                  f"Format: {cam_preview.get('format', 'JPEG')} | "
                  f"Resolution: {cam_preview.get('resolution', (640, 480))} | "
                  f"Payload Size: {cam_preview.get('size_bytes', len(cam_preview.get('image_bytes', b'')))} bytes")
            print(f"  Serialized Window Byte Size: {len(w.to_bytes())} bytes")
    print("Stage 1 execution complete.")

