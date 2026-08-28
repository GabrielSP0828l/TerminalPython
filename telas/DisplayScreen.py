from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from service.DisplayService import DisplayService, DisplayWorker
from styles.animated_svg import AnimatedSvgWidget
from styles.theme import Theme
from styles.tokens import Colors, Spacing


class DisplayScreen(QWidget):
    def __init__(self, parent_app, on_back, service=None, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app
        self.on_back = on_back
        self.service = service or DisplayService()
        self.worker = None
        self._operation_token = 0

        self.setProperty("role", "page")
        self.setObjectName("displayScreen")
        self.setStyleSheet(Theme.display_stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG)
        root.setSpacing(Spacing.LG)
        title = QLabel("ORIENTAÇÃO DA TELA")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Escolha como o display físico deve ser exibido.")
        subtitle.setProperty("role", "pageSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("displayStatusCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.LG)
        current_caption = QLabel("ORIENTAÇÃO ATUAL")
        current_caption.setProperty("role", "pageSubtitle")
        current_caption.setAlignment(Qt.AlignCenter)
        self.current_orientation = QLabel("Verificando...")
        self.current_orientation.setObjectName("displayCurrentOrientation")
        self.current_orientation.setAlignment(Qt.AlignCenter)
        self.output_details = QLabel()
        self.output_details.setProperty("role", "pageSubtitle")
        self.output_details.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(current_caption)
        card_layout.addWidget(self.current_orientation)
        card_layout.addWidget(self.output_details)

        self.spinner = AnimatedSvgWidget("tube-spinner.svg", Colors.INFO, self)
        self.spinner.setFixedSize(72, 72)
        self.spinner.hide()
        self.message = QLabel()
        self.message.setAlignment(Qt.AlignCenter)
        self.message.setWordWrap(True)
        choices = QHBoxLayout()
        self.horizontal_button = QPushButton("HORIZONTAL")
        self.horizontal_button.setProperty("variant", "primary")
        self.horizontal_button.clicked.connect(lambda: self.apply("horizontal"))
        self.vertical_button = QPushButton("VERTICAL")
        self.vertical_button.setProperty("variant", "primary")
        self.vertical_button.clicked.connect(lambda: self.apply("vertical"))
        choices.addWidget(self.horizontal_button)
        choices.addWidget(self.vertical_button)
        back = QPushButton("VOLTAR")
        back.setProperty("variant", "secondary")
        back.clicked.connect(self.leave)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(card)
        root.addWidget(self.spinner, 0, Qt.AlignHCenter)
        root.addWidget(self.message)
        root.addStretch(1)
        root.addLayout(choices)
        root.addWidget(back)

    def show_page(self):
        self.message.clear()
        self._set_actions_enabled(False)
        self.spinner.show()
        self._start_worker("current_status", {}, self._status_ready, self._operation_failed)

    def apply(self, orientation):
        if self._worker_running():
            return
        if self._purchase_active():
            self._set_message(
                "Não é possível alterar a orientação durante uma compra ou pagamento em andamento.",
                "warning",
            )
            return
        self._set_actions_enabled(False)
        self.spinner.show()
        self._set_message("Alterando orientação...", "loading")
        self._start_worker(
            "apply_orientation", {"orientation": orientation},
            self._apply_ready, self._operation_failed,
        )

    def _status_ready(self, status):
        self.spinner.hide()
        self.current_orientation.setText(
            "Horizontal" if status.orientation == "horizontal" else "Vertical"
        )
        self.output_details.setText(f"Saída: {status.output} • {status.backend}")
        self._set_actions_enabled(True)

    def _apply_ready(self, status):
        self._status_ready(status)
        self._set_message("Orientação alterada com sucesso.", "success")
        refresh = getattr(self.parent_app, "refresh_display_geometry", None)
        if refresh is not None:
            refresh()

    def _operation_failed(self, _code, message):
        self.spinner.hide()
        self._set_actions_enabled(True)
        self._set_message(message, "error")

    def _purchase_active(self):
        session = self.parent_app.compra_session
        cart = getattr(getattr(self.parent_app, "terminal", None), "carrinho", None)
        cart_active = bool(cart is not None and not cart.vazio())
        return bool(session.state != "IDLE" or cart_active)

    def _set_message(self, message, state):
        self.message.setText(message)
        self.message.setProperty("state", state)
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)

    def _set_actions_enabled(self, enabled):
        self.horizontal_button.setEnabled(enabled)
        self.vertical_button.setEnabled(enabled)

    def _start_worker(self, operation, parameters, success, failure):
        self._operation_token += 1
        token = self._operation_token
        self.worker = DisplayWorker(self.service, operation, parameters, self)
        self.worker.succeeded.connect(
            lambda result, expected=token: self._worker_success(expected, success, result)
        )
        self.worker.failed.connect(
            lambda code, message, expected=token:
            self._worker_failure(expected, failure, code, message)
        )
        self.worker.start()

    def _worker_success(self, token, callback, result):
        if token == self._operation_token:
            callback(result)

    def _worker_failure(self, token, callback, code, message):
        if token == self._operation_token:
            callback(code, message)

    def _worker_running(self):
        return self.worker is not None and self.worker.isRunning()

    def leave(self):
        self.stop_worker()
        self.on_back()

    def stop_worker(self, wait=False):
        self._operation_token += 1
        if self._worker_running():
            self.worker.requestInterruption()
            if wait:
                self.worker.wait(9000)
