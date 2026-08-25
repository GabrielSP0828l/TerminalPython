import json

from PyQt5.QtCore import QThread, pyqtSignal
from websocket import WebSocket

from config import WS_URL
from model.Terminal import Terminal


class PaymentListener(QThread):
    pagamento_aprovado_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        self.terminal_id = Terminal.load().uuidTerminal
        super().__init__(parent)

        self.is_running = True

    def run(self):

        while self.is_running:

            try:

                ws = WebSocket()

                ws.connect(
                    f"{WS_URL}/payment-socket/{self.terminal_id}"
                )

                print(
                    "WebSocket conectado"
                )

                while self.is_running:

                    message = ws.recv()

                    if not message:
                        continue

                    try:

                        data = json.loads(message)

                        self.pagamento_aprovado_signal.emit(
                            data
                        )

                    except json.JSONDecodeError:

                        print(
                            "Erro ao decodificar JSON"
                        )

            except Exception as e:

                print(
                    "Erro websocket:",
                    e
                )

                self.sleep(5)

    def stop(self):

        self.is_running = False

        self.quit()

        self.wait()
