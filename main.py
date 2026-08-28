import os

from telas.OfflineOverlay import OfflineOverlay

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

import sys
import logging

from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget, QSizePolicy, QMessageBox
)

from model.Terminal import Terminal
from model.CompraSession import CompraSession
from service.SyncService import SyncService
from service.TerminalSocket import TerminalSocket
from service.FactoryResetService import FactoryResetService

from telas.CadastroTerminalScreen import CadastroTerminalScreen
from telas.AdminAuthScreen import AdminAuthScreen
from telas.ConfirmacaoScreen import ConfirmacaoScreen
from telas.ConfirmacaoCompraScreen import ConfirmacaoCompraScreen
from telas.ConfiguracaoScreen import ConfiguracaoScreen
from telas.app_payment_screen import AppPaymentScreen
from telas.bemvindo import TelaBemVindos
from telas.pagamento import PagamentoScreen
from telas.teclado import TecladoScreen
from telas.terminal_screen import TerminalScreen


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        FactoryResetService().apply_pending()
        self.no_internet_popup = None
        self.is_offline = False
        self._operacao_iniciada = False
        self.sync_thread = None
        self.sync_service = None
        self.socket = None
        self.compra_session = CompraSession(self)
        self._shutdown_authorized = False
        self._shutdown_started = False
        self._services_stopped = False

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
        self.configuracao = ConfiguracaoScreen(self)
        self.admin_auth = AdminAuthScreen(self)
        self.offline_overlay = OfflineOverlay(self)
        self.offline_overlay.hide()


        self.stacked_widget.addWidget(self.welcome)
        # self.stacked_widget.addWidget(self.login)
        self.stacked_widget.addWidget(self.cadastro_terminal)
        self.stacked_widget.addWidget(self.configuracao)
        self.stacked_widget.addWidget(self.admin_auth)

        # -----------------------------
        # OUTRAS TELAS (lazy init)
        # -----------------------------
        self.terminal = None
        self.pagamento = None
        self.teclado = None
        self.app_payment = None
        self.confirmacao = None
        self.confirmacao_compra = None

        # self.internet_monitor = InternetMonitor(interval=3)
        # self.internet_monitor.status_changed.connect(self.handle_internet)
        # self.internet_monitor.start()

        if Terminal.is_activated():
            self.iniciar_operacao_terminal()
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


    def inicializar_terminal(self):

        if self.terminal is not None:
            return

        self.terminal = TerminalScreen(self)
        self.pagamento = PagamentoScreen(self)
        self.teclado = TecladoScreen(self)
        self.app_payment = AppPaymentScreen(self)
        self.confirmacao = ConfirmacaoScreen(self)
        self.confirmacao_compra = ConfirmacaoCompraScreen(self)

        self.stacked_widget.addWidget(self.confirmacao)
        self.stacked_widget.addWidget(self.confirmacao_compra)
        self.stacked_widget.addWidget(self.app_payment)
        self.stacked_widget.addWidget(self.teclado)
        self.stacked_widget.addWidget(self.terminal)
        self.stacked_widget.addWidget(self.pagamento)

        self.compra_session.expired.connect(self.pagamento.tratar_timeout_global)

    def iniciar_operacao_terminal(self):
        if self._operacao_iniciada:
            return

        self.sync_service = SyncService()
        self.inicializar_terminal()
        self.sync_thread = self.sync_service.iniciar_sync_em_thread()
        self.socket = TerminalSocket()
        self.socket.start()
        self._operacao_iniciada = True

    def closeEvent(self, event):
        if not self._shutdown_authorized:
            event.ignore()
            return
        self._parar_servicos()
        event.accept()

    def abrir_configuracoes(self):
        return_widget = self.stacked_widget.currentWidget()
        self.admin_auth.iniciar(return_widget)
        self.stacked_widget.setCurrentWidget(self.admin_auth)

    def abrir_menu_admin_autenticado(self, return_widget):
        self.configuracao.entrar(return_widget)
        self.stacked_widget.setCurrentWidget(self.configuracao)

    def cancelar_autenticacao_admin(self, return_widget):
        self.stacked_widget.setCurrentWidget(return_widget or self.welcome)

    def encerrar_menu_admin(self, return_widget):
        self.stacked_widget.setCurrentWidget(return_widget or self.welcome)

    def encerrar_terminal(self):
        if self._shutdown_started:
            return
        self._shutdown_started = True
        self._shutdown_authorized = True
        self._parar_servicos()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _parar_servicos(self):
        if self._services_stopped:
            return
        self._services_stopped = True
        self.compra_session.stop()
        self.welcome.stop()
        self.cadastro_terminal.activation_timer.stop()
        if self.cadastro_terminal.activation_worker.isRunning():
            self.cadastro_terminal.activation_worker.requestInterruption()
            self.cadastro_terminal.activation_worker.wait(500)
        if self.confirmacao is not None:
            self.confirmacao.stop()
        if self.pagamento is not None:
            self.pagamento.parar_workers()
        if self.app_payment is not None:
            self.app_payment.parar_espera()
        if self.terminal is not None:
            self.terminal.timer_foco.stop()
            self.terminal.listener.stop()
        if self.sync_service is not None:
            self.sync_service.stop()
        if self.socket is not None:
            self.socket.stop()
        internet_monitor = getattr(self, "internet_monitor", None)
        if internet_monitor is not None:
            internet_monitor.stop()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def reset_compra(self):
        if self.pagamento is not None:
            self.pagamento.parar_espera()
        if self.app_payment is not None:
            self.app_payment.parar_espera()
        if self.terminal is not None:
            self.terminal.liberar_tela()
        self.compra_session.reset()

    # -----------------------------
    # HELPERS
    # -----------------------------
    def setCurrentWidget(self, widget):
        if (
            self.stacked_widget.currentWidget() is self.configuracao
            and widget is not self.configuracao
        ):
            self.configuracao.encerrar_sessao()
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    from config import API_URL, DATABASE_PATH
    logging.getLogger(__name__).info("[API] Backend: %s", API_URL or "não configurado")
    logging.getLogger(__name__).info("[SYNC] SQLite path: %s", DATABASE_PATH.resolve())
    activated_terminal = Terminal.load()
    if activated_terminal is not None:
        logging.getLogger(__name__).info(
            "[TERMINAL] UUID carregado: %s", activated_terminal.terminalId
        )
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    print("Screen size:", screen.size(), flush=True)
    print("Available geometry:", screen.availableGeometry(), flush=True)
    window = MainWindow()

    # cursor oculto (modo terminal)
    #app.setOverrideCursor(Qt.BlankCursor)

    window.setFixedSize(1024, 600)

    window.showFullScreen()

    sys.exit(app.exec_())
