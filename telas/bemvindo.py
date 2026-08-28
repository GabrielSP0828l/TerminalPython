from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from datetime import datetime

from service.HoldToExitLabel import HoldToExitLabel
from styles.theme import Theme
from styles.tokens import Spacing


class TelaBemVindos(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setProperty("role", "page")
        self.setStyleSheet(Theme.welcome_stylesheet())

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout_principal.setAlignment(Qt.AlignCenter)
        layout_principal.setSizeConstraint(QVBoxLayout.SetNoConstraint)

        self.card = QFrame()
        self.card.setObjectName("centralCard")
        self.card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout_cartao = QVBoxLayout(self.card)
        layout_cartao.setAlignment(Qt.AlignCenter)
        layout_cartao.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        layout_cartao.setSpacing(Spacing.LG)

        self.logo = HoldToExitLabel(hold_time=2000)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.logo.hold_completed.connect(self.parent.abrir_configuracoes)

        logo_pixmap = QPixmap("css/ima.png")
        self.logo_pixmap_original = logo_pixmap
        self.atualizar_logo(logo_pixmap)

        titulo = QLabel("BEM VINDO")
        titulo.setObjectName("welcomeTitle")
        titulo.setAlignment(Qt.AlignCenter)

        subtitulo = QLabel("SEMPRE AQUI")
        subtitulo.setObjectName("welcomeSubtitle")
        subtitulo.setAlignment(Qt.AlignCenter)

        self.relogio = QLabel()
        self.relogio.setObjectName("welcomeClock")
        self.relogio.setAlignment(Qt.AlignCenter)

        self.botao_entrar = QPushButton("TOQUE PARA CONTINUAR")
        self.botao_entrar.setCursor(Qt.PointingHandCursor)
        self.botao_entrar.setProperty("variant", "primary")
        self.botao_entrar.setProperty("primaryAction", True)
        self.botao_entrar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.botao_entrar.clicked.connect(
            lambda: self.parent.setCurrentWidget(self.parent.terminal)
        )
        self.parent.compra_session.state_changed.connect(self._checkout_state_changed)

        layout_cartao.addStretch(1)
        layout_cartao.addWidget(self.logo, stretch=3)
        layout_cartao.addWidget(subtitulo)
        layout_cartao.addWidget(titulo)
        layout_cartao.addWidget(self.relogio)
        layout_cartao.addWidget(self.botao_entrar)
        layout_cartao.addStretch(1)

        layout_principal.addWidget(self.card)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.atualizarRelogio)
        self.clock_timer.start(1000)
        self.atualizarRelogio()

    def _checkout_state_changed(self, state):
        if state == "RECONCILIATION_PENDING":
            self.botao_entrar.setText("VERIFICANDO COMPRA ANTERIOR")
        else:
            self.botao_entrar.setText("TOQUE PARA CONTINUAR")

    def atualizarRelogio(self):
        self.relogio.setText(datetime.now().strftime("%H:%M:%S"))

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.logo_pixmap_original and not self.logo_pixmap_original.isNull():
            w = self.width()
            size = max(160, min(320, int(min(w * 0.45, self.height() * 0.32))))

            self.atualizar_logo(
                self.logo_pixmap_original.scaled(
                    size, size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

    def atualizar_logo(self, pixmap):
        self.logo.setPixmap(pixmap)

    def stop(self):
        self.clock_timer.stop()
