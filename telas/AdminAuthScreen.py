import hmac

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import TERMINAL_ADMIN_PASSWORD
from styles.theme import Theme
from styles.tokens import Spacing, TouchSize
from telas.teclado import VirtualKeyboard


class AdminAuthScreen(QWidget):
    """Barreira de autenticação anterior ao menu administrativo existente."""

    def __init__(self, parent, configured_password=None):
        super().__init__(parent)
        self.parent_app = parent
        self._return_widget = None
        self._configured_password = (
            TERMINAL_ADMIN_PASSWORD
            if configured_password is None
            else configured_password
        )

        self.setProperty("role", "page")
        self.setObjectName("adminAuthScreen")
        self.setStyleSheet(Theme.admin_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setSpacing(Spacing.LG)

        card = QFrame(self)
        card.setObjectName("adminAuthCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            Spacing.XXL, Spacing.XL, Spacing.XXL, Spacing.XL
        )
        card_layout.setSpacing(Spacing.MD)

        title = QLabel("ACESSO RESTRITO")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Digite a senha administrativa")
        subtitle.setProperty("role", "pageSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        self.password_input = QLineEdit()
        self.password_input.setProperty("role", "input")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Senha administrativa")
        self.password_input.setAlignment(Qt.AlignCenter)
        self.password_input.returnPressed.connect(self.validar)

        self.status_label = QLabel()
        self.status_label.setObjectName("adminAuthStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.status_label)

        self.keyboard = VirtualKeyboard(self)
        self.keyboard.set_target(self.password_input)

        self.enter_button = QPushButton("ENTRAR")
        self.enter_button.setProperty("variant", "primary")
        self.enter_button.setProperty("primaryAction", True)
        self.enter_button.setMinimumHeight(TouchSize.PRIMARY_BUTTON)
        self.enter_button.clicked.connect(self.validar)
        cancel_button = QPushButton("CANCELAR")
        cancel_button.setProperty("variant", "secondary")
        cancel_button.clicked.connect(self.cancelar)

        root.addWidget(card)
        root.addWidget(self.keyboard, 1)
        root.addWidget(self.enter_button)
        root.addWidget(cancel_button)

    def iniciar(self, return_widget):
        self._return_widget = return_widget
        self.password_input.clear()
        if self._configured_password:
            self._set_status("", None)
            self.enter_button.setEnabled(True)
        else:
            self._set_status(
                "Senha administrativa não configurada. Contate o responsável técnico.",
                "error",
            )
            self.enter_button.setEnabled(False)
        self.password_input.setFocus()

    def validar(self):
        if not self._configured_password:
            return
        entered_password = self.password_input.text()
        if hmac.compare_digest(entered_password, self._configured_password):
            self.password_input.clear()
            self._set_status("", None)
            self.parent_app.abrir_menu_admin_autenticado(self._return_widget)
            return

        self.password_input.clear()
        self._set_status("Senha incorreta", "error")
        self.password_input.setFocus()

    def cancelar(self):
        return_widget = self._return_widget
        self.password_input.clear()
        self._return_widget = None
        self._set_status("", None)
        self.parent_app.cancelar_autenticacao_admin(return_widget)

    def _set_status(self, text, state):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state or "")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
