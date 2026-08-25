import os

from service.InternetMonitor import InternetMonitor
from telas.OfflineOverlay import OfflineOverlay

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget, QSizePolicy, QMessageBox
)

from model.Terminal import Terminal
from service.SyncService import SyncService
from service.TerminalSocket import TerminalSocket

from telas.CadastroTerminalScreen import CadastroTerminalScreen
from telas.ConfirmacaoScreen import ConfirmacaoScreen
from telas.app_payment_screen import AppPaymentScreen
from telas.bemvindo import TelaBemVindos
from telas.login_screen import LoginScreen
from telas.pagamento import PagamentoScreen
from telas.pix import PixScreen
from telas.teclado import TecladoScreen
from telas.terminal_screen import TerminalScreen


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.no_internet_popup = None
        self.is_offline = False

        self.setWindowTitle("Terminal Inteligente")

        # -----------------------------
        # CENTRAL WIDGET
        # -----------------------------
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        # -----------------------------
        # STACKED RESPONSIVO
        # -----------------------------
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        # -----------------------------
        # LAYOUT CORRETO (FULL SCREEN)
        # -----------------------------
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stacked_widget)

        # -----------------------------
        # TELAS
        # -----------------------------
        self.welcome = TelaBemVindos(self)
        # self.login = LoginScreen(self)
        self.cadastro_terminal = CadastroTerminalScreen(self)
        self.offline_overlay = OfflineOverlay(self)
        self.offline_overlay.hide()


        self.stacked_widget.addWidget(self.welcome)
        # self.stacked_widget.addWidget(self.login)
        self.stacked_widget.addWidget(self.cadastro_terminal)

        # -----------------------------
        # OUTRAS TELAS (lazy init)
        # -----------------------------
        self.terminal = None
        self.pagamento = None
        self.teclado = None
        self.app_payment = None
        self.pix = None
        self.confirmacao = None

        # self.internet_monitor = InternetMonitor(interval=3)
        # self.internet_monitor.status_changed.connect(self.handle_internet)
        # self.internet_monitor.start()

        if Terminal.is_activated():
            sync = SyncService()
            sync.iniciar_sync_em_thread()

            print("Aplicação continua executando...")

            self.inicializar_terminal()

            self.socket = TerminalSocket()
            self.socket.start()

            self.stacked_widget.setCurrentWidget(self.welcome)

        else:
            self.stacked_widget.setCurrentWidget(self.cadastro_terminal)

    def handle_internet(self, online):
        print("NET:", online)

        if online:
            if self.is_offline:
                self.is_offline = False
                self.offline_overlay.hide()
            return

        # OFFLINE
        if not self.is_offline:
            self.is_offline = True
            self.offline_overlay.resize(self.size())
            self.offline_overlay.show()
            self.offline_overlay.raise_()
            self.offline_overlay.activateWindow()

    # INICIALIZA TELAS PESADAS
    # -----------------------------
    def inicializar_terminal(self):

        if self.terminal is not None:
            return

        self.terminal = TerminalScreen(self)
        self.pagamento = PagamentoScreen(self)
        self.teclado = TecladoScreen(self)
        self.app_payment = AppPaymentScreen(self)
        self.pix = PixScreen(self)
        self.confirmacao = ConfirmacaoScreen(self)

        self.stacked_widget.addWidget(self.confirmacao)
        self.stacked_widget.addWidget(self.app_payment)
        self.stacked_widget.addWidget(self.teclado)
        self.stacked_widget.addWidget(self.terminal)
        self.stacked_widget.addWidget(self.pagamento)
        self.stacked_widget.addWidget(self.pix)

    # -----------------------------
    # HELPERS
    # -----------------------------
    def setCurrentWidget(self, widget):
        self.stacked_widget.setCurrentWidget(widget)

    def currentWidget(self):
        return self.stacked_widget.currentWidget()

    def show_no_internet_popup(self):
        if self.no_internet_popup is not None:
            return  # já está aberto

        self.no_internet_popup = QMessageBox(self)
        self.no_internet_popup.setWindowTitle("Sem Internet")
        self.no_internet_popup.setText(
            "Conexão perdida.\nO sistema está aguardando internet voltar."
        )
        self.no_internet_popup.setIcon(QMessageBox.Critical)
        self.no_internet_popup.setStandardButtons(QMessageBox.NoButton)

        self.no_internet_popup.open()

    def close_no_internet_popup(self):
        if self.no_internet_popup is not None:
            self.no_internet_popup.close()
            self.no_internet_popup = None

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "offline_overlay"):
            self.offline_overlay.resize(self.size())
# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    print("Screen size:", screen.size(), flush=True)
    print("Available geometry:", screen.availableGeometry(), flush=True)
    window = MainWindow()

    # cursor oculto (modo terminal)
    #app.setOverrideCursor(Qt.BlankCursor)

    #    window.setFixedSize(1024, 600)

    window.showFullScreen()
    #  window.show()
    # window.resize(800, 480)

    window.show()

    sys.exit(app.exec_())
