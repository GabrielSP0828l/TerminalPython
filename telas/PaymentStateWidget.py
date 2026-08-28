from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from styles.svg_icons import ColoredSvgLabel
from styles.tokens import Colors, Spacing


class PaymentStateWidget(QWidget):
    """Composição fullscreen reutilizável para estados semânticos da compra."""

    def __init__(
        self,
        kind,
        icon_name,
        title,
        message="",
        fallback="!",
        parent=None,
    ):
        super().__init__(parent)
        self.setProperty("paymentState", kind)
        # Subclasses de QWidget precisam declarar explicitamente que o fundo
        # definido por QSS deve ser pintado em toda a área.
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.layout_root = QVBoxLayout(self)
        self.layout_root.setContentsMargins(
            Spacing.XXXL, Spacing.XXXL, Spacing.XXXL, Spacing.XXXL
        )
        self.layout_root.setSpacing(Spacing.XL)
        self.layout_root.addStretch(1)

        self.icon = ColoredSvgLabel(
            icon_name, Colors.PAYMENT_STATE_FOREGROUND, fallback, self
        )
        self.icon.setObjectName("paymentStateIcon")
        self.icon.setMinimumSize(160, 160)
        self.icon.setMaximumSize(200, 200)
        self.layout_root.addWidget(self.icon, 0, Qt.AlignHCenter)

        self.title = QLabel(title)
        self.title.setObjectName("paymentStateTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        self.layout_root.addWidget(self.title)

        self.message = QLabel(message)
        self.message.setObjectName("paymentStateMessage")
        self.message.setAlignment(Qt.AlignCenter)
        self.message.setWordWrap(True)
        self.layout_root.addWidget(self.message)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(Spacing.MD)
        self.layout_root.addLayout(self.content_layout)
        self.layout_root.addStretch(2)

        self.action_layout = QVBoxLayout()
        self.action_layout.setSpacing(Spacing.MD)
        self.layout_root.addLayout(self.action_layout)

    def set_message(self, message):
        self.message.setText(message)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.height() > self.width():
            self.icon.setMinimumSize(160, 160)
            self.icon.setMaximumSize(200, 200)
        else:
            self.icon.setMinimumSize(100, 100)
            self.icon.setMaximumSize(140, 140)
