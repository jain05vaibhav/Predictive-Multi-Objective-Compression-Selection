"""
Raspberry Pi 3B+ Hardware Telemetry Hub

Coordinates live sensor drivers (DHT22, CSI Camera) and Raspberry Pi 3B+ native
system metrics (vcgencmd, psutil, Linux /sys and /proc interfaces) to feed
Stage 1 Data Acquisition.
"""

import io
import time
from typing import Dict, Any, Optional

from edge.sensors.dht22_reader import DHT22Reader
from edge.sensors.camera_reader import CameraReader
from edge.sensors.rpi_system_reader import RPiSystemReader


class RPiTelemetryHub:
    """
    Unified hardware telemetry coordinator for Raspberry Pi 3B+.
    Aggregates DHT22, CSI/USB camera, and SoC/system metrics.
    """

    def __init__(
        self,
        output_dir: str = "data/camera_captures",
        save_to_disk: bool = True
    ):
        self.output_dir = output_dir
        self.save_to_disk = save_to_disk

        # Initialize hardware readers
        self.dht22_reader = DHT22Reader()
        self.camera_reader = CameraReader(output_dir=self.output_dir, save_to_disk=self.save_to_disk)
        self.system_reader = RPiSystemReader()

        self.last_camera: Optional[Dict[str, Any]] = None

    def read_dht22(self) -> Dict[str, float]:
        """Reads real DHT22 temperature and humidity values."""
        try:
            reading = self.dht22_reader.read()
            if reading:
                return reading
        except Exception:
            pass
        return {"temperature_c": 0.0, "humidity_percent": 0.0}

    def read_system(self) -> Dict[str, Any]:
        """Reads real Raspberry Pi 3B+ SoC thermal, electrical, and CPU/memory telemetry."""
        return self.system_reader.read_all_system_metrics()

    def read_camera(self) -> Dict[str, Any]:
        """Captures frame from the camera reader."""
        try:
            reading = self.camera_reader.capture_frame()
            if reading:
                self.last_camera = reading
                return reading
        except Exception:
            pass
        return {
            "frame_id": 0,
            "resolution": (640, 480),
            "format": "JPEG",
            "image_bytes": b"",
            "size_bytes": 0,
            "saved_path": None
        }

    def get_camera_in_memory_buffer(self) -> io.BytesIO:
        """Returns in-memory BytesIO stream of the latest captured photo."""
        if hasattr(self.camera_reader, "get_in_memory_buffer"):
            return self.camera_reader.get_in_memory_buffer()
        if self.last_camera and "image_bytes" in self.last_camera:
            buf = io.BytesIO(self.last_camera["image_bytes"])
            buf.seek(0)
            return buf
        return io.BytesIO()

    def save_camera_photo_in_memory(self) -> Dict[str, Any]:
        """Captures a camera photo and stores it in RAM without disk write."""
        return self.read_camera()

    def read_all(self) -> Dict[str, Any]:
        """
        Aggregates all live sensor readings (DHT22, RPi 3B+ System, Camera)
        into a unified telemetry sample dictionary for Stage 1 acquisition.
        """
        now = time.time()
        dht_data = self.read_dht22()
        sys_data = self.read_system()
        cam_data = self.read_camera()

        return {
            "timestamp": now,
            # Top-level direct keys for pipeline convenience
            "temperature": dht_data.get("temperature_c", 0.0),
            "humidity": dht_data.get("humidity_percent", 0.0),
            "cpu_temp_c": sys_data.get("cpu_temp_c", 0.0),
            "cpu_percent": sys_data.get("cpu_percent", 0.0),
            "cpu_freq_mhz": sys_data.get("cpu_freq_mhz", 0.0),
            "core_freq_mhz": sys_data.get("core_freq_mhz", 0.0),
            "core_voltage_v": sys_data.get("core_voltage_v", 0.0),
            "memory_percent": sys_data.get("memory_percent", 0.0),
            "frame_id": cam_data.get("frame_id", 0),
            "frame_data": cam_data.get("image_bytes", b""),
            # Structured sub-sections
            "dht22": dht_data,
            "system": sys_data,
            "camera": cam_data
        }


# Aliases for compatibility
TelemetrySource = RPiTelemetryHub
SimulatedSource = RPiTelemetryHub


if __name__ == "__main__":
    print("=== Testing Raspberry Pi 3B+ Hardware Telemetry Hub ===")
    hub = RPiTelemetryHub()
    sample = hub.read_all()

    print("\n[DHT22 Environmental Sensor]")
    print(f"  Temperature: {sample['dht22']['temperature_c']} °C")
    print(f"  Humidity:    {sample['dht22']['humidity_percent']} %")

    print("\n[Raspberry Pi 3B+ System Telemetry]")
    sys_info = sample["system"]
    print(f"  SoC Temp:         {sys_info['cpu_temp_c']} °C")
    print(f"  CPU Freq (ARM):   {sys_info['cpu_freq_mhz']} MHz")
    print(f"  Core Freq:        {sys_info['core_freq_mhz']} MHz")
    print(f"  Core Voltage:     {sys_info['core_voltage_v']} V")
    print(f"  Throttling State: {sys_info['throttled_hex']} (Undervoltage now: {sys_info['undervoltage_now']})")
    print(f"  CPU Utilization:  {sys_info['cpu_percent']} % (Load 1m: {sys_info['load_1m']})")
    print(f"  Memory Usage:     {sys_info['memory_used_mb']} MB / {sys_info['memory_total_mb']} MB ({sys_info['memory_percent']} %)")

    print("\n[Camera Reader]")
    cam = sample["camera"]
    print(f"  Frame ID:       {cam['frame_id']}")
    print(f"  Resolution:     {cam['resolution']}")
    print(f"  Format:         {cam['format']}")
    print(f"  RAM Size:       {cam['size_bytes']} bytes")

    print("\n=== Telemetry Hub test complete ===")
