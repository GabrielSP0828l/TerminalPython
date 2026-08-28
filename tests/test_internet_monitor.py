import unittest

import requests

from service.InternetMonitor import InternetMonitor


class InternetMonitorTest(unittest.TestCase):
    def test_checks_configured_backend_with_bounded_timeout(self):
        calls = []

        def request_get(url, **kwargs):
            calls.append((url, kwargs))
            return object()

        monitor = InternetMonitor(
            target_url="https://backend.example/api",
            request_get=request_get,
        )

        self.assertTrue(monitor.check_internet())
        self.assertEqual(
            [("https://backend.example/api", {"timeout": 3})],
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


if __name__ == "__main__":
    unittest.main()
