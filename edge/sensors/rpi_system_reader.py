"""
Raspberry Pi 3B+ Native System Telemetry Reader

Retrieves real hardware system telemetry directly from the Raspberry Pi 3B+ using:
- vcgencmd (VideoCore GPU/SoC interface: temp, clocks, core & SDRAM voltages, throttling/undervoltage)
- Linux /sys & /proc filesystem interfaces (/sys/class/thermal, /proc/stat, /proc/loadavg)
- psutil (CPU utilization, CPU frequency, load averages, memory statistics)
"""

import os
import re
import shutil
import subprocess
from typing import Dict, Any, Optional, Tuple
import psutil

from edge.config import RPI_VCGENCMD_BIN


class RPiSystemReader:
    """
    Reads hardware performance, thermal, electrical, and throttling telemetry
    from a Raspberry Pi 3B+ (BCM2837 SoC).
    """

    def __init__(self, vcgencmd_path: Optional[str] = None):
        self.vcgencmd_bin = vcgencmd_path or shutil.which(RPI_VCGENCMD_BIN) or "/usr/bin/vcgencmd"
        self.vcgencmd_available = self._check_vcgencmd()

    def _check_vcgencmd(self) -> bool:
        """Checks if the vcgencmd utility is executable on the current system."""
        try:
            res = subprocess.run(
                [self.vcgencmd_bin, "version"],
                capture_output=True,
                text=True,
                timeout=1.5
            )
            return res.returncode == 0
        except Exception:
            return False

    def _exec_vcgencmd(self, command: str) -> Optional[str]:
        """Executes a vcgencmd command and returns its trimmed stdout string."""
        if not self.vcgencmd_available:
            return None
        try:
            args = [self.vcgencmd_bin] + command.split()
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=1.5
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    # -------------------------------------------------------------------------
    # Parsing Helpers (Stateless & Unit-Testable)
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_temp_output(raw_str: str) -> Optional[float]:
        """
        Parses output like "temp=42.8'C" -> 42.8
        """
        if not raw_str:
            return None
        match = re.search(r"temp=([\d.]+)", raw_str)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def parse_clock_output(raw_str: str) -> Optional[float]:
        """
        Parses output like "frequency(45)=1400000000" -> 1400.0 (in MHz)
        """
        if not raw_str:
            return None
        match = re.search(r"frequency\(\d+\)=(\d+)", raw_str)
        if match:
            try:
                hz = float(match.group(1))
                return round(hz / 1_000_000.0, 2)  # Convert to MHz
            except ValueError:
                pass
        return None

    @staticmethod
    def parse_volts_output(raw_str: str) -> Optional[float]:
        """
        Parses output like "volt=1.2000V" -> 1.2000
        """
        if not raw_str:
            return None
        match = re.search(r"volt=([\d.]+)V?", raw_str)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def parse_throttled_output(raw_str: str) -> Dict[str, Any]:
        """
        Parses output like "throttled=0x0" or "throttled=0x50005" and decodes bit flags:
        Bit 0  (0x1):     Under-voltage detected now
        Bit 1  (0x2):     ARM frequency capped now
        Bit 2  (0x4):     Currently throttled
        Bit 3  (0x8):     Soft temperature limit active now
        Bit 16 (0x10000): Under-voltage has occurred since boot
        Bit 17 (0x20000): ARM frequency capping has occurred
        Bit 18 (0x40000): Throttling has occurred
        Bit 19 (0x80000): Soft temperature limit has occurred
        """
        defaults = {
            "throttled_hex": "0x0",
            "throttled_raw": 0,
            "undervoltage_now": False,
            "arm_freq_capped_now": False,
            "throttled_now": False,
            "soft_temp_limit_now": False,
            "undervoltage_occurred": False,
            "arm_freq_capped_occurred": False,
            "throttling_occurred": False,
            "soft_temp_limit_occurred": False
        }
        if not raw_str:
            return defaults

        match = re.search(r"throttled=(0x[0-9a-fA-F]+|\d+)", raw_str)
        if not match:
            return defaults

        raw_val = match.group(1)
        val = int(raw_val, 16) if raw_val.startswith("0x") else int(raw_val)

        return {
            "throttled_hex": hex(val),
            "throttled_raw": val,
            "undervoltage_now": bool(val & 0x1),
            "arm_freq_capped_now": bool(val & 0x2),
            "throttled_now": bool(val & 0x4),
            "soft_temp_limit_now": bool(val & 0x8),
            "undervoltage_occurred": bool(val & 0x10000),
            "arm_freq_capped_occurred": bool(val & 0x20000),
            "throttling_occurred": bool(val & 0x40000),
            "soft_temp_limit_occurred": bool(val & 0x80000)
        }

    # -------------------------------------------------------------------------
    # Metric Acquisition Methods
    # -------------------------------------------------------------------------

    def read_soc_temperature(self) -> float:
        """
        Reads the Broadcom BCM2837 SoC temperature in °C via vcgencmd,
        falling back to Linux /sys/class/thermal/thermal_zone0/temp or psutil.
        """
        # 1. Try vcgencmd measure_temp
        raw = self._exec_vcgencmd("measure_temp")
        if raw:
            parsed = self.parse_temp_output(raw)
            if parsed is not None:
                return parsed

        # 2. Try Linux sysfs thermal zone 0
        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(thermal_path):
            try:
                with open(thermal_path, "r") as f:
                    millidegrees = float(f.read().strip())
                    return round(millidegrees / 1000.0, 2)
            except Exception:
                pass

        # 3. Try psutil sensors_temperatures
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name in ["cpu_thermal", "soc_thermal", "coretemp"]:
                        if name in temps and len(temps[name]) > 0:
                            return round(temps[name][0].current, 2)
                    # Use first available temperature sensor
                    for key, entries in temps.items():
                        if entries:
                            return round(entries[0].current, 2)
        except Exception:
            pass

        return 0.0

    def read_cpu_frequency(self) -> float:
        """
        Reads ARM CPU frequency in MHz via vcgencmd, falling back to sysfs/psutil.
        """
        # 1. Try vcgencmd measure_clock arm
        raw = self._exec_vcgencmd("measure_clock arm")
        if raw:
            parsed = self.parse_clock_output(raw)
            if parsed is not None:
                return parsed

        # 2. Try Linux cpufreq sysfs
        cpufreq_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
        if os.path.exists(cpufreq_path):
            try:
                with open(cpufreq_path, "r") as f:
                    khz = float(f.read().strip())
                    return round(khz / 1000.0, 2)
            except Exception:
                pass

        # 3. Try psutil.cpu_freq()
        try:
            freq = psutil.cpu_freq()
            if freq and freq.current:
                return round(freq.current, 2)
        except Exception:
            pass

        return 0.0

    def read_core_frequency(self) -> float:
        """
        Reads VideoCore/GPU Core frequency in MHz via vcgencmd measure_clock core.
        """
        raw = self._exec_vcgencmd("measure_clock core")
        if raw:
            parsed = self.parse_clock_output(raw)
            if parsed is not None:
                return parsed
        return 0.0

    def read_core_voltage(self) -> float:
        """
        Reads SoC Core Voltage in Volts via vcgencmd measure_volts core.
        """
        raw = self._exec_vcgencmd("measure_volts core")
        if not raw:
            raw = self._exec_vcgencmd("measure_volts")
        if raw:
            parsed = self.parse_volts_output(raw)
            if parsed is not None:
                return parsed
        return 0.0

    def read_sdram_voltages(self) -> Dict[str, float]:
        """
        Reads SDRAM Controller (sdram_c), I/O (sdram_i), and PHY (sdram_p) voltages in Volts.
        """
        sdram_types = ["sdram_c", "sdram_i", "sdram_p"]
        results: Dict[str, float] = {}
        for mem_type in sdram_types:
            raw = self._exec_vcgencmd(f"measure_volts {mem_type}")
            parsed = self.parse_volts_output(raw) if raw else None
            results[f"{mem_type}_voltage_v"] = parsed if parsed is not None else 0.0
        return results

    def read_throttling_status(self) -> Dict[str, Any]:
        """
        Reads and decodes the throttling and under-voltage bitmask via vcgencmd get_throttled.
        """
        raw = self._exec_vcgencmd("get_throttled")
        return self.parse_throttled_output(raw or "")

    def read_cpu_metrics(self) -> Dict[str, Any]:
        """
        Reads CPU utilization percent and 1m/5m/15m system load averages.
        """
        cpu_percent = round(psutil.cpu_percent(interval=None), 2)
        cpu_count = psutil.cpu_count(logical=True) or 1

        # Load average (1, 5, 15 min)
        load_1m, load_5m, load_15m = 0.0, 0.0, 0.0
        if hasattr(os, "getloadavg"):
            try:
                l1, l5, l15 = os.getloadavg()
                load_1m, load_5m, load_15m = round(l1, 2), round(l5, 2), round(l15, 2)
            except Exception:
                pass
        elif hasattr(psutil, "getloadavg"):
            try:
                l1, l5, l15 = psutil.getloadavg()
                load_1m, load_5m, load_15m = round(l1, 2), round(l5, 2), round(l15, 2)
            except Exception:
                pass

        return {
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "load_1m": load_1m,
            "load_5m": load_5m,
            "load_15m": load_15m
        }

    def read_memory_metrics(self) -> Dict[str, Any]:
        """
        Reads physical RAM usage in MB and usage percentage via psutil.
        """
        mem = psutil.virtual_memory()
        total_mb = round(mem.total / (1024 * 1024), 2)
        used_mb = round(mem.used / (1024 * 1024), 2)
        free_mb = round(mem.available / (1024 * 1024), 2)
        percent = round(mem.percent, 2)

        return {
            "memory_total_mb": total_mb,
            "memory_used_mb": used_mb,
            "memory_free_mb": free_mb,
            "memory_percent": percent
        }

    def read_all_system_metrics(self) -> Dict[str, Any]:
        """
        Aggregates all Raspberry Pi 3B+ hardware telemetry into a clean dictionary.
        """
        cpu_temp = self.read_soc_temperature()
        cpu_freq = self.read_cpu_frequency()
        core_freq = self.read_core_frequency()
        core_volt = self.read_core_voltage()
        sdram_volts = self.read_sdram_voltages()
        throttled_info = self.read_throttling_status()
        cpu_info = self.read_cpu_metrics()
        mem_info = self.read_memory_metrics()

        return {
            # Primary telemetry metrics
            "cpu_temp_c": cpu_temp,
            "cpu_freq_mhz": cpu_freq,
            "core_freq_mhz": core_freq,
            "core_voltage_v": core_volt,
            "sdram_c_voltage_v": sdram_volts.get("sdram_c_voltage_v", 0.0),
            "sdram_i_voltage_v": sdram_volts.get("sdram_i_voltage_v", 0.0),
            "sdram_p_voltage_v": sdram_volts.get("sdram_p_voltage_v", 0.0),
            # Throttling & Undervoltage diagnostics
            "throttled_hex": throttled_info["throttled_hex"],
            "undervoltage_now": throttled_info["undervoltage_now"],
            "arm_freq_capped_now": throttled_info["arm_freq_capped_now"],
            "throttled_now": throttled_info["throttled_now"],
            "soft_temp_limit_now": throttled_info["soft_temp_limit_now"],
            "undervoltage_occurred": throttled_info["undervoltage_occurred"],
            "arm_freq_capped_occurred": throttled_info["arm_freq_capped_occurred"],
            "throttling_occurred": throttled_info["throttling_occurred"],
            "soft_temp_limit_occurred": throttled_info["soft_temp_limit_occurred"],
            # System load and capacity
            "cpu_percent": cpu_info["cpu_percent"],
            "cpu_count": cpu_info["cpu_count"],
            "load_1m": cpu_info["load_1m"],
            "load_5m": cpu_info["load_5m"],
            "load_15m": cpu_info["load_15m"],
            "memory_total_mb": mem_info["memory_total_mb"],
            "memory_used_mb": mem_info["memory_used_mb"],
            "memory_free_mb": mem_info["memory_free_mb"],
            "memory_percent": mem_info["memory_percent"],
            "vcgencmd_available": self.vcgencmd_available
        }


if __name__ == "__main__":
    print("=== Testing Raspberry Pi 3B+ Native System Telemetry ===")
    reader = RPiSystemReader()
    metrics = reader.read_all_system_metrics()

    print(f"vcgencmd available:     {metrics['vcgencmd_available']}")
    print(f"SoC / CPU Temperature:  {metrics['cpu_temp_c']} °C")
    print(f"CPU Frequency (ARM):    {metrics['cpu_freq_mhz']} MHz")
    print(f"Core Frequency:         {metrics['core_freq_mhz']} MHz")
    print(f"Core Voltage:           {metrics['core_voltage_v']} V")
    print(f"SDRAM-C Voltage:        {metrics['sdram_c_voltage_v']} V")
    print(f"SDRAM-I Voltage:        {metrics['sdram_i_voltage_v']} V")
    print(f"SDRAM-P Voltage:        {metrics['sdram_p_voltage_v']} V")
    print(f"Throttling Status:      {metrics['throttled_hex']} (Under-voltage now: {metrics['undervoltage_now']}, Throttled now: {metrics['throttled_now']})")
    print(f"CPU Utilization:        {metrics['cpu_percent']} % (Cores: {metrics['cpu_count']}, Load 1m: {metrics['load_1m']})")
    print(f"Memory Usage:           {metrics['memory_used_mb']} MB / {metrics['memory_total_mb']} MB ({metrics['memory_percent']} %)")
    print("=== RPiSystemReader test complete ===")
