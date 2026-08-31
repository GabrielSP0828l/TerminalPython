import subprocess
import tempfile
import unittest
from pathlib import Path

import requests

from model.Terminal import Terminal
from service.ApplicationMetricsCollector import ApplicationMetricsCollector
from service.DisplayMetricsCollector import DisplayMetricsCollector
from service.NetworkMetricsCollector import NetworkMetricsCollector
from service.SystemMetricsCollector import SystemMetricsCollector
from service.TelemetryService import TelemetryService
from service.WifiService import WifiStatus


class StaticCollector:
    def __init__(self, value=None, error=None):
        self.value = value or {}
        self.error = error

    def collect(self):
        if self.error:
            raise self.error
        return dict(self.value)


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, posts=None, get_response=None):
        self.posts = list(posts or [])
        self.get_response = get_response or FakeResponse()
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        value = self.posts.pop(0) if self.posts else FakeResponse()
        if isinstance(value, Exception):
            raise value
        return value

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        if isinstance(self.get_response, Exception):
            raise self.get_response
        return self.get_response


class FakeWifi:
    def __init__(self, status):
        self._status = status

    def status(self):
        return self._status


class TelemetryCollectorsTest(unittest.TestCase):
    def test_get_throttled_zero_reports_all_flags_false(self):
        parsed = SystemMetricsCollector.parse_throttled("throttled=0x0")
        self.assertEqual("0x0", parsed["throttledRaw"])
        self.assertFalse(parsed["undervoltageNow"])
        self.assertFalse(parsed["throttledOccurred"])

    def test_get_throttled_decodes_current_and_historical_flags(self):
        parsed = SystemMetricsCollector.parse_throttled("throttled=0x50005")
        self.assertTrue(parsed["undervoltageNow"])
        self.assertTrue(parsed["throttledNow"])
        self.assertTrue(parsed["undervoltageOccurred"])
        self.assertTrue(parsed["throttledOccurred"])
        self.assertFalse(parsed["frequencyCappedNow"])
        self.assertFalse(parsed["softTemperatureLimitOccurred"])

    def test_missing_vcgencmd_returns_unavailable_instead_of_fake_zero(self):
        def missing(*args, **kwargs):
            raise FileNotFoundError("vcgencmd")

        collector = SystemMetricsCollector(runner=missing)
        self.assertIsNone(collector._energy())

    def test_temperature_cpu_ram_disk_and_uptime_are_collected_without_psutil(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stat = root / "stat"
            memory = root / "meminfo"
            uptime = root / "uptime"
            thermal = root / "temp"
            stat.write_text("cpu  100 0 100 800 0 0 0 0\n", encoding="utf-8")
            memory.write_text("MemTotal: 1000 kB\nMemAvailable: 400 kB\n", encoding="utf-8")
            uptime.write_text("123.4 0\n", encoding="utf-8")
            thermal.write_text("61400\n", encoding="utf-8")
            collector = SystemMetricsCollector(
                runner=lambda *a, **k: subprocess.CompletedProcess(a, 0, "throttled=0x0", ""),
                disk_path=root, thermal_path=thermal,
            )
            collector.PROC_STAT_PATH = stat
            collector.PROC_MEMINFO_PATH = memory
            collector.PROC_UPTIME_PATH = uptime
            first = collector.collect()
            stat.write_text("cpu  120 0 120 860 0 0 0 0\n", encoding="utf-8")
            second = collector.collect()

            self.assertIsNone(first["cpuUsagePercent"])
            self.assertEqual(40.0, second["cpuUsagePercent"])
            self.assertEqual(61.4, second["cpuTemperatureCelsius"])
            self.assertEqual(1024000, second["memoryTotalBytes"])
            self.assertEqual(60.0, second["memoryUsagePercent"])
            self.assertEqual(123, second["uptimeSeconds"])
            self.assertIsNotNone(second["diskUsagePercent"])

    def test_network_uses_real_api_latency_and_human_signal_label(self):
        session = FakeSession()
        collector = NetworkMetricsCollector(
            "http://backend", session=session,
            wifi_service=FakeWifi(WifiStatus(True, True, "wlan0", "MinhaRede", 82, "192.168.1.4")),
        )
        result = collector.collect()
        self.assertTrue(result["backendReachable"])
        self.assertEqual("EXCELENTE", result["wifiSignalQuality"])
        self.assertEqual("MinhaRede", result["ssid"])
        self.assertGreaterEqual(result["backendLatencyMs"], 0)
        self.assertEqual("http://backend/terminal/health", session.calls[0][0])

    def test_network_timeout_is_non_fatal(self):
        collector = NetworkMetricsCollector(
            "http://backend", session=FakeSession(get_response=requests.Timeout()),
            wifi_service=FakeWifi(WifiStatus(True, False, "wlan0")), timeout=1,
        )
        result = collector.collect()
        self.assertFalse(result["backendReachable"])
        self.assertIsNone(result["backendLatencyMs"])

    def test_application_uses_actual_sync_purchase_and_payment_state(self):
        sync = type("Sync", (), {
            "last_sync_started_at": "2026-08-30T10:00:00Z",
            "last_sync_completed_at": "2026-08-30T10:00:02Z",
            "last_successful_sync_at": "2026-08-30T10:00:02Z",
            "last_sync_error": None,
        })()
        purchase = type("Purchase", (), {
            "started_at": 1, "state": "WAITING_PAYMENT", "payment_in_flight": True,
        })()
        times = iter([100.0, 145.5])
        collector = ApplicationMetricsCollector(
            sync, purchase, lambda: "RECONNECTING", version="1.2.3", clock=lambda: next(times))
        result = collector.collect()
        self.assertEqual(45, result["uptimeSeconds"])
        self.assertEqual("RECONNECTING", result["websocketStatus"])
        self.assertTrue(result["purchaseActive"])
        self.assertTrue(result["paymentInProgress"])

    def test_display_reports_resolution_and_orientation(self):
        size = type("Size", (), {"width": lambda self: 1024, "height": lambda self: 600})()
        screen = type("Screen", (), {"size": lambda self: size})()
        result = DisplayMetricsCollector(lambda: screen).collect()
        self.assertEqual({"width": 1024, "height": 600, "orientation": "HORIZONTAL"}, result)


class TelemetryServiceTest(unittest.TestCase):
    def make_service(self, root, session, system=None):
        terminal_path = root / "terminal.json"
        Terminal.from_dict({
            "terminalId": "terminal-a", "ativo": True, "activated": True,
        }).save(terminal_path)
        return TelemetryService(
            sync_service=None, purchase_session=None,
            websocket_state_provider=lambda: "CONNECTED", screen_provider=lambda: None,
            api_url="http://backend", terminal_path=terminal_path,
            interval_seconds=60, timeout_seconds=2, session=session,
            system_collector=system or StaticCollector({"cpuUsagePercent": 10}),
            network_collector=StaticCollector({"backendReachable": True}),
            application_collector=StaticCollector({"version": "1.0.0"}),
            display_collector=StaticCollector({"width": 1024}),
        )

    def test_payload_and_timeout_are_sent_to_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession()
            service = self.make_service(Path(directory), session)
            self.assertTrue(service.collect_and_send())
            url, payload, timeout = session.calls[0]
            self.assertEqual("http://backend/terminal/telemetry", url)
            self.assertEqual("terminal-a", payload["terminalUuid"])
            self.assertEqual(2, timeout)
            self.assertIn("system", payload)

    def test_offline_sample_is_discarded_and_next_cycle_can_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession([requests.ConnectionError("offline"), FakeResponse()])
            service = self.make_service(Path(directory), session)
            self.assertFalse(service.collect_and_send())
            self.assertTrue(service.collect_and_send())
            self.assertEqual(2, len(session.calls))

    def test_collection_error_never_escapes_to_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession()
            service = self.make_service(
                Path(directory), session, system=StaticCollector(error=RuntimeError("sensor")))
            self.assertFalse(service.collect_and_send())
            self.assertEqual([], session.calls)


if __name__ == "__main__":
    unittest.main()
