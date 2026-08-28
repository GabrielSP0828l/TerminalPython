import logging

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from config import API_URL


logger = logging.getLogger(__name__)


class InternetMonitor(QThread):
    status_changed = pyqtSignal(bool)

    def __init__(self, interval=3, target_url=API_URL, request_get=requests.get):
        super().__init__()
        self.interval = interval
        self.target_url = str(target_url or "").strip()
        self.request_get = request_get
        self.status = None

    def check_internet(self):
        if not self.target_url:
            return False
        try:
            self.request_get(self.target_url, timeout=3)
            return True
        except requests.RequestException:
            return False

    def run(self):
        while not self.isInterruptionRequested():
            new_status = self.check_internet()

            if new_status != self.status:
                self.status = new_status
                logger.info("[NETWORK] backend=%s", "online" if new_status else "offline")
                self.status_changed.emit(self.status)
            self.msleep(max(250, int(self.interval * 1000)))

    def stop(self):
        self.requestInterruption()
        self.wait(3500)
