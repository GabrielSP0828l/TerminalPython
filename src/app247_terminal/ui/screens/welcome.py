import logging

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from datetime import datetime

from app247_terminal.services.hold_to_exit_label import HoldToExitLabel
from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import Spacing
from app247_terminal.ui import texts
from app247_terminal.ui.brand import BrandLogo


logger = logging.getLogger(__name__)


class TelaBemVindos(QWidget):
    # O leitor digita o código inteiro em milissegundos; uma pausa maior separa leituras.
    SCAN_RESET_MS = 1000

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

        # O logotipo animado é só desenho: o toque longo continua no label.
        # Ele para sozinho quando esta tela sai de cena (hideEvent).
        self.brand_logo = BrandLogo(animated=True, parent=self.logo)
        logo_layout = QVBoxLayout(self.logo)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.addWidget(self.brand_logo)

        titulo = QLabel("BEM-VINDO")
        titulo.setObjectName("welcomeTitle")
        titulo.setAlignment(Qt.AlignCenter)

        subtitulo = QLabel("SEMPRE AQUI")
        subtitulo.setObjectName("welcomeSubtitle")
        subtitulo.setAlignment(Qt.AlignCenter)

        self.relogio = QLabel()
        self.relogio.setObjectName("welcomeClock")
        self.relogio.setAlignment(Qt.AlignCenter)

        self.botao_entrar = QPushButton("TOQUE PARA COMEÇAR")
        self.botao_entrar.setCursor(Qt.PointingHandCursor)
        self.botao_entrar.setProperty("variant", "primary")
        self.botao_entrar.setProperty("primaryAction", True)
        self.botao_entrar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Sem foco no botão: o leitor (teclado USB) digita sempre nesta tela.
        self.botao_entrar.setFocusPolicy(Qt.NoFocus)
        self.botao_entrar.clicked.connect(
            lambda: self.parent.setCurrentWidget(self.parent.terminal)
        )
        self.setFocusPolicy(Qt.StrongFocus)
        self._scan_buffer = ""
        self._scan_reset = QTimer(self)
        self._scan_reset.setSingleShot(True)
        self._scan_reset.setInterval(self.SCAN_RESET_MS)
        self._scan_reset.timeout.connect(self._descartar_leitura)
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

    def showEvent(self, event):
        super().showEvent(event)
        self._descartar_leitura()
        self.setFocus()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            code = self._scan_buffer.strip()
            self._descartar_leitura()
            if code:
                self.iniciar_compra_por_leitura(code)
            return
        text = event.text()
        if text and text.isprintable():
            self._scan_buffer += text
            self._scan_reset.start()
            return
        super().keyPressEvent(event)

    def _descartar_leitura(self):
        self._scan_reset.stop()
        self._scan_buffer = ""

    def iniciar_compra_por_leitura(self, code):
        """Cliente que já chega lendo o produto não precisa tocar em continuar."""
        terminal = getattr(self.parent, "terminal", None)
        if terminal is None:
            return
        self.parent.setCurrentWidget(terminal)
        if self.parent.stacked_widget.currentWidget() is not terminal:
            logger.info("[WELCOME] leitura descartada; compra indisponível")
            return
        terminal.codigo_barras.setText(code)
        terminal.readProduct()

    def _checkout_state_changed(self, state):
        if state == "RECONCILIATION_PENDING":
            self.botao_entrar.setText("VERIFICANDO COMPRA ANTERIOR")
        else:
            self.botao_entrar.setText("TOQUE PARA COMEÇAR")

    def atualizarRelogio(self):
        self.relogio.setText(datetime.now().strftime(texts.WELCOME_CLOCK_FORMAT))

    def resizeEvent(self, event):
        super().resizeEvent(event)

        size = max(160, min(320, int(min(self.width() * 0.45, self.height() * 0.32))))
        self.brand_logo.setMaximumHeight(size)

    def stop(self):
        self.clock_timer.stop()
