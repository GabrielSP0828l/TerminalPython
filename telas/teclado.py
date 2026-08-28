from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from styles.theme import Theme
from styles.tokens import Spacing


class VirtualKeyboard(QWidget):
    """Teclado alfanumérico touchscreen reutilizável."""

    key_pressed = pyqtSignal(str)
    ALPHA_ROWS = (
        ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
        ("Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"),
        ("A", "S", "D", "F", "G", "H", "J", "K", "L", "⌫"),
        ("Z", "X", "C", "V", "B", "N", "M", "abc", "#+=", "ESPAÇO", "LIMPAR"),
    )
    SYMBOL_ROWS = (
        ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
        ("@", "#", "$", "%", "&", "*", "(", ")", "-", "_"),
        ("+", "=", "/", "\\", ":", ";", '"', "'", "?", "⌫"),
        (".", ",", "!", "~", "^", "`", "|", "ABC", "<", "ESPAÇO", ">"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_input = None
        self._uppercase = True
        self._symbol_mode = False
        self._key_buttons = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        for row in self.ALPHA_ROWS:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(Spacing.SM)
            for key in row:
                button = QPushButton(key)
                button.setProperty("key", True)
                if key in {"abc", "#+=", "ESPAÇO", "LIMPAR", "⌫"}:
                    button.setProperty("keyType", "special")
                button.clicked.connect(
                    lambda checked=False, target=button: self.process_key(target.text())
                )
                self._key_buttons.append(button)
                row_layout.addWidget(
                    button, 2 if key in {"abc", "ESPAÇO", "LIMPAR", "⌫"} else 1
                )
            layout.addLayout(row_layout)

    def set_target(self, input_field):
        self.target_input = input_field
        input_field.setFocus()

    def process_key(self, key):
        if self.target_input is None:
            return
        if key == "abc":
            self._toggle_case()
            return
        if key == "#+=":
            self._set_symbol_mode(True)
            return
        if key == "ABC":
            self._set_symbol_mode(False)
            return
        if key == "⌫":
            self.target_input.backspace()
        elif key == "LIMPAR":
            self.target_input.clear()
        elif key == "ESPAÇO":
            self.target_input.insert(" ")
        else:
            value = key
            if not self._symbol_mode and len(key) == 1 and key.isalpha():
                value = key if self._uppercase else key.lower()
            self.target_input.insert(value)
        self.key_pressed.emit(key)

    def _toggle_case(self):
        if self._symbol_mode:
            return
        self._uppercase = not self._uppercase
        self._apply_rows(self.ALPHA_ROWS)

    def _set_symbol_mode(self, enabled):
        self._symbol_mode = bool(enabled)
        self._apply_rows(self.SYMBOL_ROWS if enabled else self.ALPHA_ROWS)

    def _apply_rows(self, rows):
        values = [value for row in rows for value in row]
        for button, value in zip(self._key_buttons, values):
            if not self._symbol_mode and len(value) == 1 and value.isalpha():
                value = value.upper() if self._uppercase else value.lower()
            button.setText(value)


class TecladoScreen(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.target_input = None
        self.setProperty("role", "page")
        self.setStyleSheet(Theme.keyboard_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.MD)

        container = QFrame()
        container.setObjectName("inputContainer")
        inputs = QVBoxLayout(container)

        self.title = QLabel("AUTENTICAÇÃO")
        self.title.setProperty("role", "sectionTitle")
        self.title.setAlignment(Qt.AlignCenter)

        self.input_nome = QLineEdit()
        self.input_nome.setProperty("role", "input")
        self.input_nome.setPlaceholderText("NOME COMPLETO")
        self.input_nome.mousePressEvent = lambda event: self.set_target(self.input_nome)

        self.input_cpf = QLineEdit()
        self.input_cpf.setProperty("role", "input")
        self.input_cpf.setPlaceholderText("CPF")
        self.input_cpf.setAlignment(Qt.AlignCenter)
        self.input_cpf.mousePressEvent = lambda event: self.set_target(self.input_cpf)

        inputs.addWidget(self.title)
        inputs.addWidget(self.input_nome)
        inputs.addWidget(self.input_cpf)

        self.keyboard = VirtualKeyboard(self)
        self.keyboard.key_pressed.connect(self._after_key)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.MD)
        cancel = QPushButton("CANCELAR")
        cancel.setProperty("variant", "secondary")
        cancel.clicked.connect(lambda: self.parent.setCurrentWidget(self.parent.login))
        confirm = QPushButton("CONFIRMAR")
        confirm.setProperty("variant", "primary")
        confirm.setProperty("primaryAction", True)
        confirm.clicked.connect(self.finalizar)
        actions.addWidget(cancel, 1)
        actions.addWidget(confirm, 2)

        root.addWidget(container)
        root.addWidget(self.keyboard)
        root.addStretch(1)
        root.addLayout(actions)
        self.set_target(self.input_nome)

    def set_target(self, input_field):
        self.target_input = input_field
        self.keyboard.set_target(input_field)

    def processar_tecla(self, key):
        self.keyboard.process_key(key)

    def _after_key(self, key):
        if self.target_input == self.input_cpf:
            self.formatar_cpf()

    def formatar_cpf(self):
        numbers = "".join(filter(str.isdigit, self.input_cpf.text()))[:11]
        formatted = ""
        for index, character in enumerate(numbers):
            if index in (3, 6):
                formatted += "."
            elif index == 9:
                formatted += "-"
            formatted += character
        self.input_cpf.setText(formatted)

    def finalizar(self):
        nome = self.input_nome.text().strip()
        cpf = self.input_cpf.text().strip()
        if len(nome) < 3 or len(cpf) < 14:
            self.title.setText("PREENCHA TODOS OS CAMPOS")
            self.title.setProperty("state", "error")
            self.title.style().unpolish(self.title)
            self.title.style().polish(self.title)
            return
        self.parent.setCurrentWidget(self.parent.terminal)
