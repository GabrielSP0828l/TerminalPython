from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QSizePolicy
)
from styles.theme import Theme


class ConfirmacaoScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self._countdown = 5

        self.setObjectName("confirmationScreen")
        self.setStyleSheet(Theme.confirmation_stylesheet())

        # Layout raiz centralizado
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)
        root.setContentsMargins(40, 40, 40, 40)

        # Card
        card = QFrame()
        card.setObjectName("confirmationCard")
        card.setMaximumWidth(700)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(48, 48, 48, 40)
        card_layout.setSpacing(0)
        card_layout.setAlignment(Qt.AlignCenter)

        # Ícone
        self.lbl_icon = QLabel("✓")
        self.lbl_icon.setObjectName("confirmationIcon")
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_icon)

        card_layout.addSpacing(20)

        # Título
        self.lbl_sucesso = QLabel("PAGAMENTO APROVADO")
        self.lbl_sucesso.setObjectName("confirmationTitle")
        self.lbl_sucesso.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_sucesso)

        card_layout.addSpacing(24)

        # Divisória
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.HLine)
        card_layout.addWidget(divider)

        card_layout.addSpacing(24)

        # Subtext
        self.lbl_subtext = QLabel("Compra concluída com sucesso.")
        self.lbl_subtext.setObjectName("confirmationSubtitle")
        self.lbl_subtext.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_subtext)

        card_layout.addSpacing(28)

        # Barra de progresso
        self.progress = QProgressBar()
        self.progress.setRange(0, 5)
        self.progress.setValue(5)
        self.progress.setTextVisible(False)
        card_layout.addWidget(self.progress)

        card_layout.addSpacing(8)

        # Contador
        self.lbl_timer = QLabel("Liberando o terminal em 5s...")
        self.lbl_timer.setObjectName("confirmationTimer")
        self.lbl_timer.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_timer)

        card_layout.addSpacing(28)

        # Botão
        self.btn_voltar = QPushButton("AVANÇAR AGORA  ↵")
        self.btn_voltar.setProperty("variant", "primary")
        self.btn_voltar.setMinimumHeight(52)
        self.btn_voltar.clicked.connect(self.finalizar_e_voltar)
        card_layout.addWidget(self.btn_voltar)

        root.addWidget(card)

        # Timers
        self.timer_auto_fechar = QTimer(self)
        self.timer_auto_fechar.setSingleShot(True)
        self.timer_auto_fechar.timeout.connect(self.finalizar_e_voltar)

        self.timer_countdown = QTimer(self)
        self.timer_countdown.timeout.connect(self._tick)

    def mostrar_tela(self):
        self._countdown = 5
        self.progress.setValue(5)
        self.lbl_timer.setText("Liberando o terminal em 5s...")
        self.btn_voltar.setFocus()
        self.timer_auto_fechar.start(5000)
        self.timer_countdown.start(1000)

    def _tick(self):
        self._countdown -= 1
        self.progress.setValue(self._countdown)
        if self._countdown > 0:
            self.lbl_timer.setText(f"Liberando o terminal em {self._countdown}s...")
        else:
            self.timer_countdown.stop()

    def finalizar_e_voltar(self):
        self.timer_auto_fechar.stop()
        self.timer_countdown.stop()
        if self.parent_app:
            self.parent_app.reset_compra()
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.finalizar_e_voltar()
        else:
            super().keyPressEvent(event)
