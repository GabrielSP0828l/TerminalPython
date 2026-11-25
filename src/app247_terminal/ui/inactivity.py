"""Inatividade nas telas da compra: aviso "Ainda está aí?" e encerramento.

O monitor só mede tempo e mostra o aviso; quem decide o que encerrar é o
controlador principal, pelo mesmo caminho do teto de 10 minutos. Assim uma
cobrança em andamento nunca é cancelada aqui.
"""

import logging
import time

from PyQt5.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app247_terminal.models.purchase_session import (
    INACTIVITY_COUNTDOWN_SECONDS,
    INACTIVITY_PROMPT_AFTER_SECONDS,
)
from app247_terminal.ui import texts
from app247_terminal.ui.responsive import follow_layout_profile
from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import Spacing, TouchSize


logger = logging.getLogger(__name__)


class InactivityPrompt(QWidget):
    """Aviso sobre a área de conteúdo da tela.

    Cobre só o ``anchor`` (lista de produtos ou resumo): o cabeçalho com o
    relógio da sessão e os botões do rodapé continuam visíveis e livres. O véu
    escuro absorve o toque sobre o conteúdo, que vale só como presença.
    """

    # Em pé o texto quebra em linhas; deitado fica numa linha ao lado do botão.
    MAX_CARD_WIDTH_COMPACT = 560
    MAX_CARD_WIDTH_WIDE = 880

    continue_requested = pyqtSignal()

    def __init__(self, anchor, parent):
        super().__init__(parent)
        self.anchor = anchor
        self.setObjectName("inactivityPrompt")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(Theme.inactivity_prompt_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setAlignment(Qt.AlignCenter)

        self.card = QFrame(self)
        self.card.setObjectName("inactivityCard")
        # Cartão do tamanho do conteúdo: não estica para ocupar a lista inteira.
        self.card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.card_layout = QBoxLayout(QBoxLayout.TopToBottom, self.card)
        self.card_layout.setContentsMargins(
            Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL
        )
        self.card_layout.setSpacing(Spacing.LG)

        messages = QVBoxLayout()
        messages.setSpacing(Spacing.SM)
        self.title = QLabel(texts.INACTIVITY_TITLE, self.card)
        self.title.setObjectName("inactivityTitle")
        self.title.setWordWrap(True)
        self.countdown = QLabel(self.card)
        self.countdown.setObjectName("inactivityCountdown")
        self.countdown.setWordWrap(True)
        messages.addWidget(self.title)
        messages.addWidget(self.countdown)

        self.continue_button = QPushButton(texts.INACTIVITY_CONTINUE, self.card)
        self.continue_button.setProperty("variant", "primary")
        self.continue_button.setProperty("primaryAction", True)
        self.continue_button.setMinimumHeight(TouchSize.PRIMARY_BUTTON)
        self.continue_button.clicked.connect(self.continue_requested)

        self.card_layout.addLayout(messages, 1)
        self.card_layout.addWidget(self.continue_button, 0, Qt.AlignVCenter)
        root.addWidget(self.card, 0, Qt.AlignCenter)
        follow_layout_profile(self._apply_compact)

        anchor.installEventFilter(self)
        self.hide()

    def _apply_compact(self, compact):
        """Em pé empilha; deitado (só ~250 px de lista) põe o botão ao lado."""
        self.card_layout.setDirection(
            QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        )
        alignment = Qt.AlignCenter if compact else Qt.AlignLeft | Qt.AlignVCenter
        for label in (self.title, self.countdown):
            label.setAlignment(alignment)
            label.setWordWrap(compact)
        self.card.setMaximumWidth(
            self.MAX_CARD_WIDTH_COMPACT if compact else self.MAX_CARD_WIDTH_WIDE
        )
        self.continue_button.setMinimumWidth(0 if compact else 220)

    def show_countdown(self, seconds):
        self.countdown.setText(
            texts.INACTIVITY_COUNTDOWN.format(seconds=max(0, int(seconds)))
        )
        if self.isHidden():
            self._place()
            self.show()
        self.raise_()

    def _place(self):
        parent = self.parentWidget()
        if parent is None:
            return
        top_left = self.anchor.mapTo(parent, QPoint(0, 0))
        self.setGeometry(QRect(top_left, self.anchor.size()))

    def eventFilter(self, watched, event):
        if watched is self.anchor and event.type() in (QEvent.Resize, QEvent.Move):
            if not self.isHidden():
                self._place()
        return False


class InactivityMonitor(QObject):
    """Conta o tempo sem toque e sem leitura nas telas observadas.

    Depois de ``idle_seconds`` mostra o aviso da tela atual; se ninguém
    responder em ``countdown_seconds`` emite ``expired`` uma única vez.
    """

    ACTIVITY_EVENTS = (
        QEvent.MouseButtonPress,
        QEvent.TouchBegin,
        QEvent.KeyPress,
    )

    expired = pyqtSignal()

    def __init__(self, stacked_widget, screens, parent=None, clock=None,
                 idle_seconds=INACTIVITY_PROMPT_AFTER_SECONDS,
                 countdown_seconds=INACTIVITY_COUNTDOWN_SECONDS):
        super().__init__(parent)
        self._clock = clock or time.monotonic
        self.idle_seconds = idle_seconds
        self.countdown_seconds = countdown_seconds
        self.stacked_widget = stacked_widget
        self.screens = tuple(screens)
        self._screen = None
        self._last_activity = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        for screen in self.screens:
            screen.inactivity_prompt.continue_requested.connect(
                self.register_activity
            )
        stacked_widget.currentChanged.connect(self._screen_changed)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._screen_changed(stacked_widget.currentIndex())

    @property
    def armed(self):
        return self._screen is not None

    @property
    def prompt_visible(self):
        return self._screen is not None and not self._screen.inactivity_prompt.isHidden()

    def register_activity(self):
        """Toque, leitura do leitor ou CONTINUAR: recomeça a contagem."""
        if self._screen is None:
            return
        self._last_activity = self._clock()
        self._hide_prompt()

    def stop(self):
        self._disarm()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def eventFilter(self, watched, event):
        if self._screen is not None and event.type() in self.ACTIVITY_EVENTS:
            self.register_activity()
        return False

    def _screen_changed(self, index):
        widget = self.stacked_widget.widget(index)
        if widget is self._screen:
            return
        self._disarm()
        if widget in self.screens:
            self._screen = widget
            self._last_activity = self._clock()
            self._timer.start()

    def _disarm(self):
        self._hide_prompt()
        self._timer.stop()
        self._screen = None
        self._last_activity = None

    def _hide_prompt(self):
        if self._screen is not None:
            self._screen.inactivity_prompt.hide()

    def _tick(self):
        if self._screen is None or self._last_activity is None:
            return
        idle = self._clock() - self._last_activity
        if idle < self.idle_seconds:
            self._hide_prompt()
            return
        remaining = int(self.idle_seconds + self.countdown_seconds - idle + 0.999)
        if remaining > 0:
            self._screen.inactivity_prompt.show_countdown(remaining)
            return
        logger.warning(
            "[CHECKOUT-INACTIVITY] sem resposta ao aviso screen=%s",
            self._screen.objectName(),
        )
        self._disarm()
        self.expired.emit()
