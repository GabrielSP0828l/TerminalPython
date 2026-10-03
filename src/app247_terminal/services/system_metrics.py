import os
import shutil
import subprocess
from pathlib import Path


class SystemMetricsCollector:
    THERMAL_PATH = Path("/sys/class/thermal/thermal_zone0/temp")
    PROC_STAT_PATH = Path("/proc/stat")
    PROC_MEMINFO_PATH = Path("/proc/meminfo")
    PROC_UPTIME_PATH = Path("/proc/uptime")

    def __init__(self, runner=None, disk_path="/", thermal_path=None):
        self._runner = runner or subprocess.run
        self.disk_path = disk_path
        self.thermal_path = Path(thermal_path or self.THERMAL_PATH)
        self._last_cpu = None

    @staticmethod
    def parse_throttled(raw):
        normalized = str(raw or "").strip().lower()
        if "=" in normalized:
            normalized = normalized.split("=", 1)[1].strip()
        try:
            value = int(normalized, 16)
        except (TypeError, ValueError):
            return None
        return {
            "undervoltageNow": bool(value & (1 << 0)),
            "frequencyCappedNow": bool(value & (1 << 1)),
            "throttledNow": bool(value & (1 << 2)),
            "softTemperatureLimitNow": bool(value & (1 << 3)),
            "undervoltageOccurred": bool(value & (1 << 16)),
            "frequencyCappedOccurred": bool(value & (1 << 17)),
            "throttledOccurred": bool(value & (1 << 18)),
            "softTemperatureLimitOccurred": bool(value & (1 << 19)),
            "throttledRaw": f"0x{value:x}",
        }

    def _cpu_usage(self):
        line = self.PROC_STAT_PATH.read_text(encoding="utf-8").splitlines()[0]
        values = [int(value) for value in line.split()[1:]]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values)
        current = (total, idle)
        previous, self._last_cpu = self._last_cpu, current
        if previous is None or total <= previous[0]:
            return None
        total_delta = total - previous[0]
        idle_delta = idle - previous[1]
        return round(max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta)), 2)

    def _temperature(self):
        try:
            return round(float(self.thermal_path.read_text(encoding="utf-8").strip()) / 1000.0, 2)
        except (OSError, ValueError):
            return None

    def _memory(self):
        values = {}
        for line in self.PROC_MEMINFO_PATH.read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0]) * 1024
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if not total or available is None:
            return None, None, None
        used = total - available
        return used, total, round(used * 100.0 / total, 2)

    def _energy(self):
        try:
            result = self._runner(
                ["vcgencmd", "get_throttled"], text=True, capture_output=True,
                timeout=2, check=False,
            )
            return self.parse_throttled(result.stdout) if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    def collect(self):
        metrics = {
            "uptimeSeconds": None, "cpuUsagePercent": None,
            "cpuTemperatureCelsius": self._temperature(), "memoryUsedBytes": None,
            "memoryTotalBytes": None, "memoryUsagePercent": None,
            "diskUsedBytes": None, "diskTotalBytes": None,
            "diskUsagePercent": None, "loadAverage1m": None,
            "undervoltageNow": None, "undervoltageOccurred": None,
            "throttledNow": None, "throttledOccurred": None,
            "frequencyCappedNow": None, "frequencyCappedOccurred": None,
            "softTemperatureLimitNow": None,
            "softTemperatureLimitOccurred": None, "throttledRaw": None,
        }
        try:
            metrics["cpuUsagePercent"] = self._cpu_usage()
        except (OSError, ValueError, IndexError, ZeroDivisionError):
            pass
        try:
            used, total, percent = self._memory()
            metrics.update(memoryUsedBytes=used, memoryTotalBytes=total, memoryUsagePercent=percent)
        except (OSError, ValueError):
            pass
        try:
            disk = shutil.disk_usage(self.disk_path)
            metrics.update(diskUsedBytes=disk.used, diskTotalBytes=disk.total,
                           diskUsagePercent=round(disk.used * 100.0 / disk.total, 2))
        except (OSError, ZeroDivisionError):
            pass
        try:
            metrics["uptimeSeconds"] = int(float(self.PROC_UPTIME_PATH.read_text(encoding="utf-8").split()[0]))
        except (OSError, ValueError, IndexError):
            pass
        try:
            metrics["loadAverage1m"] = round(os.getloadavg()[0], 2)
        except (OSError, AttributeError):
            pass
        energy = self._energy()
        if energy is not None:
            metrics.update(energy)
        return metrics
