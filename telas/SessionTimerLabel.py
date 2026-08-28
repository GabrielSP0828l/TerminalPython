from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel


class SessionTimerLabel(QLabel):
    """Representação visual do relógio único mantido por CompraSession."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setProperty("role", "sessionTimer")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(92)
        self.session.remaining_changed.connect(self.update_remaining)
        self.update_remaining(self.session.remaining_seconds())

    def update_remaining(self, seconds):
        seconds = max(0, int(seconds))
        minutes, remainder = divmod(seconds, 60)
        state = "critical" if seconds <= 30 else "warning" if seconds <= 60 else "normal"
        self.setProperty("state", state)
        if seconds <= 30:
            self.setText(f"{minutes:02}:{remainder:02}  Sessão prestes a encerrar")
        else:
            self.setText(f"{minutes:02}:{remainder:02}")
        self.style().unpolish(self)
        self.style().polish(self)
