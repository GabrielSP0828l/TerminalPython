from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel

from app247_terminal.models.purchase_session import (
    SESSION_CRITICAL_SECONDS,
    SESSION_WARNING_SECONDS,
)
from app247_terminal.ui import texts
from app247_terminal.ui.responsive import follow_layout_profile


class SessionTimerLabel(QLabel):
    """Aviso do fim da sessão, lido do relógio único mantido por CompraSession.

    Fica oculto durante a compra e só aparece nos últimos ``WARNING_SECONDS``,
    quando o cliente precisa saber que a sessão vai encerrar.
    """

    WARNING_SECONDS = SESSION_WARNING_SECONDS
    CRITICAL_SECONDS = SESSION_CRITICAL_SECONDS

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setProperty("role", "sessionTimer")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(92)
        self.session.remaining_changed.connect(self.update_remaining)
        self.update_remaining(self.session.remaining_seconds())

    def follow_orientation(self, inline_layout, stacked_layout, stacked_index):
        """Deitado fica em ``inline_layout``; em pé, em linha própria.

        Em pé o cabeçalho deixa ~100 px ao relógio e o aviso precisa de ~370:
        a linha própria em ``stacked_layout`` (posição ``stacked_index``) usa a
        largura toda e só ocupa altura quando o aviso está visível.
        """
        self._inline_layout = inline_layout
        self._stacked_layout = stacked_layout
        self._stacked_index = stacked_index
        follow_layout_profile(self._apply_compact)

    def _apply_compact(self, compact):
        target = self._stacked_layout if compact else self._inline_layout
        source = self._inline_layout if compact else self._stacked_layout
        if target.indexOf(self) >= 0:
            return
        source.removeWidget(self)
        if compact:
            target.insertWidget(self._stacked_index, self)
        else:
            target.addWidget(self)
        # Trocar de layout pode reexibir o widget; a regra dos 60 s decide.
        self.update_remaining(self.session.remaining_seconds())

    def update_remaining(self, seconds):
        seconds = max(0, int(seconds))
        minutes, remainder = divmod(seconds, 60)
        warning = seconds <= self.WARNING_SECONDS
        state = (
            "critical" if seconds <= self.CRITICAL_SECONDS
            else "warning" if warning else "normal"
        )
        self.setProperty("state", state)
        if warning:
            self.setText(f"{minutes:02}:{remainder:02}  {texts.SESSION_ENDING}")
        else:
            self.setText(f"{minutes:02}:{remainder:02}")
        self.setVisible(warning)
        self.style().unpolish(self)
        self.style().polish(self)
