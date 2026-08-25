import json
import threading
import time

import websocket

from config import WS_URL
from model.Terminal import Terminal


class TerminalSocket:

    def __init__(self):

        self.terminal = Terminal.load()

        self.ws = None

    def start(self):

        threading.Thread(
            target=self._heartbeat,
            daemon=True
        ).start()

    def _heartbeat(self):

        while True:

            try:

                self.ws = websocket.WebSocket()

                self.ws.connect(
                    f"{WS_URL}/terminal-socket"
                )

                print(
                    "Conectado ao websocket:status"
                )

                while True:

                    payload = {
                        "terminalId": self.terminal.terminalId,
                        "status": "ONLINE"
                    }

                    self.ws.send(
                        json.dumps(payload)
                    )

                    time.sleep(10)

            except Exception as e:

                print(
                    "Erro websocket:",
                    e
                )

                time.sleep(5)