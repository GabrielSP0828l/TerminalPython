import unittest
from types import SimpleNamespace

import requests

from app247_terminal.services.internet_monitor import InternetMonitor


def response(status_code=200):
    return SimpleNamespace(status_code=status_code)


class InternetMonitorTest(unittest.TestCase):
    def test_checks_light_health_endpoint_with_bounded_timeout(self):
        calls = []

        def request_get(url, **kwargs):
            calls.append((url, kwargs))
            return response()

        monitor = InternetMonitor(
            target_url="https://backend.example/api/",
            request_get=request_get,
        )

        self.assertTrue(monitor.check_internet())
        self.assertEqual(
            [("https://backend.example/api/terminal/health", {"timeout": 3})],
            calls,
        )

    def test_connection_failure_and_missing_backend_are_offline(self):
        def connection_failure(_url, **_kwargs):
            raise requests.ConnectionError("offline")

        self.assertFalse(
            InternetMonitor(
                target_url="https://backend.example/api",
                request_get=connection_failure,
            ).check_internet()
        )

        calls = []
        monitor = InternetMonitor(
            target_url="",
            request_get=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertFalse(monitor.check_internet())
        self.assertEqual([], calls)

    def test_tunnel_or_proxy_error_is_offline(self):
        for status in (403, 429, 502, 503):
            with self.subTest(status=status):
                monitor = InternetMonitor(
                    target_url="https://backend.example",
                    request_get=lambda *_args, **_kwargs: response(status),
                )
                self.assertFalse(monitor.check_internet())

    def test_connected_heartbeat_spends_no_http_request(self):
        calls = []
        monitor = InternetMonitor(
            target_url="https://backend.example",
            request_get=lambda *args, **kwargs: calls.append(args),
            channel_state_provider=lambda: "CONNECTED",
        )
        for _ in range(100):
            self.assertTrue(monitor.check_internet())
        self.assertEqual([], calls)

    def test_http_fallback_is_rate_limited_while_channel_is_down(self):
        now = [100.0]
        state = ["RECONNECTING"]
        calls = []

        def request_get(url, **_kwargs):
            calls.append(url)
            return response()

        monitor = InternetMonitor(
            target_url="https://backend.example",
            request_get=request_get,
            channel_state_provider=lambda: state[0],
            http_interval=30,
            clock=lambda: now[0],
        )

        for _ in range(10):
            self.assertTrue(monitor.check_internet())
            now[0] += 2.9
        self.assertEqual(1, len(calls))

        now[0] += 2
        self.assertTrue(monitor.check_internet())
        self.assertEqual(2, len(calls))

        state[0] = "CONNECTED"
        self.assertTrue(monitor.check_internet())
        state[0] = "RECONNECTING"
        self.assertTrue(monitor.check_internet())
        self.assertEqual(3, len(calls), "queda do canal testa HTTP sem esperar")


if __name__ == "__main__":
    unittest.main()
