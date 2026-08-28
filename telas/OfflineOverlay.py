from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from styles.theme import Theme
from styles.tokens import Spacing


class OfflineOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("offlineOverlay")
        self.setStyleSheet(Theme.offline_stylesheet())
        if parent is not None:
            self.resize(parent.size())

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setAlignment(Qt.AlignCenter)
        card = QFrame(self)
        card.setObjectName("offlineCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        layout.setSpacing(Spacing.LG)

        icon = QLabel("!")
        icon.setObjectName("offlineIcon")
        icon.setAlignment(Qt.AlignCenter)
        self.label = QLabel("SEM CONEXÃO COM O SERVIDOR")
        self.label.setProperty("role", "pageTitle")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.sub = QLabel("Tentando reconectar...")
        self.sub.setProperty("role", "pageSubtitle")
        self.sub.setAlignment(Qt.AlignCenter)
        self.sub.setWordWrap(True)

        layout.addWidget(icon)
        layout.addWidget(self.label)
        layout.addWidget(self.sub)
        root.addWidget(card)

    def showEvent(self, event):
        if self.parent():
            self.resize(self.parent().size())
        super().showEvent(event)
