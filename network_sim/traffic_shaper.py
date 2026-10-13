"""
Traffic Shaper & Network Variability Controller

Cross-platform python manager for network simulation profiles:
- On Linux (e.g. Raspberry Pi / Cloud server): executes tc/netem commands or netem_profiles.sh
- On development hosts: provides software emulation parameters (simulated bandwidth kbps,
  latency ms, and packet drop probability) to test pipeline adaptability.
"""

import os
import shutil
import subprocess
from typing import Dict, Any, Optional


class TrafficShaper:
    """
    Manages network emulation profiles across hardware and software simulation environments.
    """

    PROFILES = {
        "normal":      {"bandwidth_kbps": 10000.0, "latency_ms": 5.0,   "loss_pct": 0.0},
        "4g_lte":      {"bandwidth_kbps": 15000.0, "latency_ms": 35.0,  "loss_pct": 0.1},
        "3g_hsdpa":    {"bandwidth_kbps": 2000.0,  "latency_ms": 90.0,  "loss_pct": 0.5},
        "2g_edge":     {"bandwidth_kbps": 150.0,   "latency_ms": 250.0, "loss_pct": 1.5},
        "satellite":   {"bandwidth_kbps": 600.0,   "latency_ms": 650.0, "loss_pct": 2.0},
        "congested":   {"bandwidth_kbps": 50.0,    "latency_ms": 450.0, "loss_pct": 8.0},
        "packet_loss": {"bandwidth_kbps": 5000.0,  "latency_ms": 20.0,  "loss_pct": 10.0},
    }

    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self.active_profile = "normal"
        self.is_linux = os.name != "nt" and shutil.which("tc") is not None

    def apply_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Applies network simulation profile.
        Returns profile metadata dictionary.
        """
        name = profile_name.lower()
        if name not in self.PROFILES:
            name = "normal"

        self.active_profile = name
        params = dict(self.PROFILES[name])
        params["profile_name"] = name
        params["is_native_tc"] = False

        if self.is_linux:
            script_path = os.path.join(os.path.dirname(__file__), "netem_profiles.sh")
            if os.path.exists(script_path):
                try:
                    res = subprocess.run(
                        ["sudo", "bash", script_path, name, self.interface],
                        capture_output=True,
                        text=True,
                        timeout=5.0
                    )
                    params["is_native_tc"] = res.returncode == 0
                except Exception:
                    pass

        return params

    def get_active_profile(self) -> Dict[str, Any]:
        """Returns the current network parameters."""
        p = dict(self.PROFILES.get(self.active_profile, self.PROFILES["normal"]))
        p["profile_name"] = self.active_profile
        return p

    def reset(self) -> Dict[str, Any]:
        """Restores unthrottled normal connection."""
        return self.apply_profile("normal")


if __name__ == "__main__":
    shaper = TrafficShaper()
    print("=== Testing Network Traffic Shaper ===")
    print(f"Linux tc Available: {shaper.is_linux}")
    prof = shaper.apply_profile("2g_edge")
    print(f"Applied 2G Edge: Bandwidth={prof['bandwidth_kbps']} kbps, Latency={prof['latency_ms']} ms, Loss={prof['loss_pct']}%")
    shaper.reset()
