from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar
)


class ConfirmacaoScreen(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self._countdown = 20

        self.setStyleSheet("""
            QWidget {
                background-color: #0d1117;
            }

            /* card central */
            QFrame#card {
                background-color: #161b22;
                border: 1px solid #21262d;
                border-radius: 24px;
            }

            /* ícone check */
            QLabel#lbl_icon {
                color: #00d084;
                font-size: 96px;
            }

            /* título */
            QLabel#lbl_sucesso {
                color: #f0f6fc;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 2px;
            }

            /* linha divisória */
            QFrame#divider {
                background-color: #21262d;
                max-height: 1px;
                border: none;
            }

            /* subtext */
            QLabel#lbl_sub {
                color: #8b949e;
                font-size: 15px;
            }

            /* contador regressivo */
            QLabel#lbl_timer {
                color: #58a6ff;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 1px;
            }

            /* barra de progresso */
            QProgressBar {
                background-color: #21262d;
                border: none;
                border-radius: 3px;
                max-height: 6px;
            }
            QProgressBar::chunk {
                background-color: #00d084;
                border-radius: 3px;
            }

            /* botão principal */
            QPushButton#btn_voltar {
                background-color: #00d084;
                color: #0d1117;
                font-size: 15px;
                font-weight: bold;
                border-radius: 10px;
                padding: 14px 32px;
                border: none;
                letter-spacing: 1px;
            }
            QPushButton#btn_voltar:hover {
                background-color: #00e693;
            }
            QPushButton#btn_voltar:pressed {
                background-color: #00b871;
            }
        """)

        # Layout raiz centralizado
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)
        root.setContentsMargins(40, 40, 40, 40)

        # Card
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(560)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(48, 48, 48, 40)
        card_layout.setSpacing(0)
        card_layout.setAlignment(Qt.AlignCenter)

        # Ícone
        self.lbl_icon = QLabel("✓")
        self.lbl_icon.setObjectName("lbl_icon")
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_icon)

        card_layout.addSpacing(20)

        # Título
        self.lbl_sucesso = QLabel("PAGAMENTO APROVADO")
        self.lbl_sucesso.setObjectName("lbl_sucesso")
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
        self.lbl_subtext = QLabel("Imprimindo cupom fiscal...")
        self.lbl_subtext.setObjectName("lbl_sub")
        self.lbl_subtext.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_subtext)

        card_layout.addSpacing(28)

        # Barra de progresso
        self.progress = QProgressBar()
        self.progress.setRange(0, 20)
        self.progress.setValue(20)
        self.progress.setTextVisible(False)
        card_layout.addWidget(self.progress)

        card_layout.addSpacing(8)

        # Contador
        self.lbl_timer = QLabel("Avançando em 20s...")
        self.lbl_timer.setObjectName("lbl_timer")
        self.lbl_timer.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_timer)

        card_layout.addSpacing(28)

        # Botão
        self.btn_voltar = QPushButton("AVANÇAR AGORA  ↵")
        self.btn_voltar.setObjectName("btn_voltar")
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
        self._countdown = 20
        self.progress.setValue(20)
        self.lbl_timer.setText("Avançando em 20s...")
        self.btn_voltar.setFocus()
        self.timer_auto_fechar.start(20000)
        self.timer_countdown.start(1000)

    def _tick(self):
        self._countdown -= 1
        self.progress.setValue(self._countdown)
        if self._countdown > 0:
            self.lbl_timer.setText(f"Avançando em {self._countdown}s...")
        else:
            self.timer_countdown.stop()

    def finalizar_e_voltar(self):
        self.timer_auto_fechar.stop()
        self.timer_countdown.stop()
        if self.parent_app:
            self.parent_app.terminal.liberar_tela()
            self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.finalizar_e_voltar()
        else:
            super().keyPressEvent(event)