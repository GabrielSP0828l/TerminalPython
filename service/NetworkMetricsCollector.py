import time

import requests

from service.WifiService import WifiService, WifiServiceError


class NetworkMetricsCollector:
    def __init__(self, api_url, session=None, wifi_service=None, timeout=3):
        self.api_url = (api_url or "").rstrip("/")
        self.session = session or requests.Session()
        self.wifi_service = wifi_service or WifiService()
        self.timeout = timeout

    @staticmethod
    def signal_label(signal):
        if signal is None:
            return None
        if signal >= 75:
            return "EXCELENTE"
        if signal >= 55:
            return "BOM"
        if signal >= 35:
            return "MEDIO"
        return "FRACO"

    def collect(self):
        result = {
            "connected": None, "interfaceName": None, "ssid": None,
            "localIp": None, "wifiSignalPercent": None,
            "wifiSignalQuality": None, "backendReachable": False,
            "backendLatencyMs": None,
        }
        try:
            wifi = self.wifi_service.status()
            result.update(connected=wifi.connected, interfaceName=wifi.interface or None,
                          ssid=wifi.ssid or None, localIp=wifi.ip_address or None,
                          wifiSignalPercent=wifi.signal if wifi.connected else None,
                          wifiSignalQuality=self.signal_label(wifi.signal) if wifi.connected else None)
        except (WifiServiceError, OSError, ValueError):
            pass
        if not self.api_url:
            return result
        started = time.perf_counter()
        try:
            response = self.session.get(f"{self.api_url}/terminal/health", timeout=self.timeout)
            result["backendReachable"] = response.status_code == 200
            result["backendLatencyMs"] = max(0, round((time.perf_counter() - started) * 1000))
        except requests.RequestException:
            pass
        return result
