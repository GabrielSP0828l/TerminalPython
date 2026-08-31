import os

from telas.OfflineOverlay import OfflineOverlay

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

import sys
import logging

from PyQt5.QtCore import Qt, QTimer

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget, QSizePolicy, QMessageBox
)

from model.Terminal import Terminal
from model.CompraSession import CompraSession
from service.SyncService import SyncService
from service.TerminalSocket import TerminalSocket
from service.FactoryResetService import FactoryResetService
from service.InternetMonitor import InternetMonitor
from service.TelemetryService import TelemetryService

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
        self.internet_monitor = None
        self.telemetry_service = None
        self._network_settings_active = False
        self.compra_session = CompraSession(self)
        self._expiring_checkout_generation = None
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

        if Terminal.is_activated():
            self.iniciar_operacao_terminal()
            self.stacked_widget.setCurrentWidget(self.welcome)

        else:
            self.stacked_widget.setCurrentWidget(self.cadastro_terminal)

    def handle_internet(self, online):
        if online:
            if self.is_offline:
                self.is_offline = False
                self.offline_overlay.hide()
            return

        # OFFLINE
        if self._network_settings_active:
            self.is_offline = True
            self.offline_overlay.hide()
            return
        if not self.is_offline:
            self.is_offline = True
            self.offline_overlay.resize(self.size())
            self.offline_overlay.show()
            self.offline_overlay.raise_()
            self.offline_overlay.activateWindow()

    def set_network_settings_active(self, active):
        self._network_settings_active = bool(active)
        if active:
            self.offline_overlay.hide()
        elif self.is_offline:
            self.offline_overlay.resize(self.size())
            self.offline_overlay.show()
            self.offline_overlay.raise_()


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

        self.compra_session.expired.connect(self._checkout_session_expired)

    def _checkout_session_expired(self, generation):
        """Processa uma única expiração e delega só a reconciliação financeira."""
        session = self.compra_session
        if not generation or generation != session.generation:
            return
        if self._expiring_checkout_generation == generation:
            return

        self._expiring_checkout_generation = generation
        logging.getLogger(__name__).warning(
            "[CHECKOUT-SESSION] expiring session generation=%s", generation
        )
        self._set_checkout_interactions_enabled(False)

        if session.payment_in_flight or session.order_id or session.cart_id:
            self.pagamento.tratar_timeout_global(generation)
            return
        self.complete_checkout_expiration(generation)

    def complete_checkout_expiration(self, generation):
        """Conclui no controlador o reset de uma sessão expirada sem pendência."""
        if not generation or generation != self.compra_session.generation:
            return
        logging.getLogger(__name__).warning(
            "[CHECKOUT-SESSION] resetting purchase generation=%s", generation
        )
        self.reset_compra(outcome="cancelled")
        logging.getLogger(__name__).warning(
            "[CHECKOUT-SESSION] returning to welcome screen"
        )
        self.setCurrentWidget(self.welcome)
        self._expiring_checkout_generation = None

    def _set_checkout_interactions_enabled(self, enabled):
        if self.terminal is not None:
            self.terminal.set_checkout_interactions_enabled(enabled)
        if self.confirmacao_compra is not None:
            self.confirmacao_compra.set_checkout_interactions_enabled(enabled)

    def iniciar_operacao_terminal(self):
        if self._operacao_iniciada:
            return

        self.sync_service = SyncService()
        self.inicializar_terminal()
        self.sync_thread = self.sync_service.iniciar_sync_em_thread()
        self.socket = TerminalSocket()
        self.socket.start()
        self.internet_monitor = InternetMonitor(interval=3)
        self.internet_monitor.status_changed.connect(self.handle_internet)
        self.internet_monitor.start()
        self.telemetry_service = TelemetryService(
            sync_service=self.sync_service,
            purchase_session=self.compra_session,
            websocket_state_provider=lambda: (
                self.terminal.listener.connection_state
                if self.terminal is not None else "DISCONNECTED"
            ),
            screen_provider=lambda: QApplication.primaryScreen(),
        )
        self.telemetry_service.start()
        self._operacao_iniciada = True

    def closeEvent(self, event):
        if not self._shutdown_authorized:
            event.ignore()
            return
        self._parar_servicos()
        event.accept()

    def abrir_configuracoes(self):
        if self.is_offline:
            self.set_network_settings_active(True)
        return_widget = self.stacked_widget.currentWidget()
        self.admin_auth.iniciar(return_widget)
        self.stacked_widget.setCurrentWidget(self.admin_auth)

    def abrir_menu_admin_autenticado(self, return_widget):
        self.configuracao.entrar(return_widget)
        self.stacked_widget.setCurrentWidget(self.configuracao)

    def cancelar_autenticacao_admin(self, return_widget):
        self.set_network_settings_active(False)
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
        configuracao = getattr(self, "configuracao", None)
        if configuracao is not None:
            configuracao.stop_workers(wait=True)
        if self.pagamento is not None:
            self.pagamento.parar_workers()
        if self.app_payment is not None:
            self.app_payment.parar_espera()
        telemetry_service = getattr(self, "telemetry_service", None)
        if telemetry_service is not None:
            telemetry_service.stop()
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

    def reset_compra(self, outcome="cancelled"):
        if self.pagamento is not None:
            self.pagamento.parar_espera()
        if self.app_payment is not None:
            self.app_payment.parar_espera()
        if self.terminal is not None:
            self.terminal.set_checkout_interactions_enabled(False)
            self.terminal.liberar_tela()
        if outcome == "finalized":
            self.compra_session.finish()
        else:
            self.compra_session.cancel()
        self._expiring_checkout_generation = None

    # -----------------------------
    # HELPERS
    # -----------------------------
    def setCurrentWidget(self, widget):
        if (
            widget is self.terminal
            and self.compra_session.started_at is not None
            and not self.compra_session.active
        ):
            if (
                self.compra_session.payment_in_flight
                or self.compra_session.order_id
                or self.compra_session.cart_id
            ):
                self.pagamento.mostrar_reconciliacao_pendente()
            else:
                self.stacked_widget.setCurrentWidget(self.welcome)
            return
        if widget is self.terminal:
            self._set_checkout_interactions_enabled(True)
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

    def refresh_display_geometry(self):
        QTimer.singleShot(250, self._refresh_display_geometry)

    def _refresh_display_geometry(self):
        self.showFullScreen()
        self.central_widget.updateGeometry()
        self.stacked_widget.updateGeometry()
        current = self.stacked_widget.currentWidget()
        if current is not None:
            current.updateGeometry()
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
    #screen = app.primaryScreen()
    #print("Screen size:", screen.size(), flush=True)
    #print("Available geometry:", screen.availableGeometry(), flush=True)
    window = MainWindow()

    # cursor oculto (modo terminal)
    #app.setOverrideCursor(Qt.BlankCursor)
    window.setFixedSize(1024, 600)
    #window.showFullScreen()
    screen = app.primaryScreen().availableGeometry()

    width = min(1024, screen.width())
    height = min(600, screen.height())

    window.setFixedSize(width, height)
    window.show()
    sys.exit(app.exec_())
