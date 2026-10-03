from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel


class HoldToExitLabel(QLabel):
    hold_completed = pyqtSignal()

    def __init__(self, parent=None, hold_time=2000):
        super().__init__(parent)
        self.hold_time = hold_time  # tempo em ms (2 segundos)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._emitir_acao)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.timer.start(self.hold_time)

    def mouseReleaseEvent(self, event):
        self.timer.stop()

    def _emitir_acao(self):
        self.hold_completed.emit()
