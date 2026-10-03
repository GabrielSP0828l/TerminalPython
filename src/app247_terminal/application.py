import os

from app247_terminal.ui.screens.offline_overlay import OfflineOverlay

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

import logging

from PyQt5.QtCore import Qt, QTimer

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget, QSizePolicy, QMessageBox, QLabel
)

from app247_terminal.models.terminal import Terminal
from app247_terminal.models.purchase_session import CompraSession
from app247_terminal.repositories.active_payment_repository import ActivePaymentStore
from app247_terminal.services.sync_service import SyncService
from app247_terminal.services.terminal_socket import TerminalSocket
from app247_terminal.services.factory_reset import (
    FactoryResetService,
    ResetBlockedActivePayment,
    ResetBlockedCriticalState,
)
from app247_terminal.services.terminal_lifecycle import (
    TerminalLifecycleApi,
    TerminalLifecycleCheckThread,
    TerminalResetPolicy,
)
from app247_terminal.services.internet_monitor import InternetMonitor
from app247_terminal.services.telemetry_service import TelemetryService
from app247_terminal.services.purchase_api import ActivePaymentRecoveryWorker
from app247_terminal.services.terminal_auth import TerminalCredentialStore
from app247_terminal.services.backend_client import terminal_access_state
from app247_terminal.config.settings import IS_PRODUCTION

from app247_terminal.ui.screens.terminal_registration import CadastroTerminalScreen
from app247_terminal.ui.screens.admin_auth import AdminAuthScreen
from app247_terminal.ui.screens.confirmation import ConfirmacaoScreen
from app247_terminal.ui.screens.purchase_confirmation import ConfirmacaoCompraScreen
from app247_terminal.ui.screens.settings import ConfiguracaoScreen
from app247_terminal.ui.screens.app_payment import AppPaymentScreen
from app247_terminal.ui.screens.welcome import TelaBemVindos
from app247_terminal.ui.screens.payment import PagamentoScreen
from app247_terminal.ui.screens.keyboard import TecladoScreen
from app247_terminal.ui.screens.terminal import TerminalScreen


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.factory_reset_service = FactoryResetService()
        self._startup_recovery_error = None
        try:
            self.factory_reset_service.apply_pending()
        except ResetBlockedActivePayment:
            logging.getLogger(__name__).warning(
                "[TERMINAL-RESET] RESET_BLOCKED_ACTIVE_PAYMENT no startup"
            )
        except ResetBlockedCriticalState:
            self._startup_recovery_error = "SQLITE_INTEGRITY_FAILED"
            logging.getLogger(__name__).exception(
                "[LOCAL-STATE] reset bloqueado: estado critico nao verificavel"
            )
        self.lifecycle_api = TerminalLifecycleApi(
            reset_service=self.factory_reset_service
        )
        self._lifecycle_worker = None
        self._factory_reset_pending = None
        self.no_internet_popup = None
        self.is_offline = False
        self._operacao_iniciada = False
        self.sync_thread = None
        self.sync_service = None
        self.socket = None
        self.internet_monitor = None
        self.telemetry_service = None
        self._network_settings_active = False
        try:
            self.active_payment_store = ActivePaymentStore()
        except Exception:
            self.active_payment_store = None
            self._startup_recovery_error = "SQLITE_INTEGRITY_FAILED"
            logging.getLogger(__name__).exception(
                "[LOCAL-STATE] SQLite indisponivel; operacao comercial bloqueada"
            )
        self.compra_session = CompraSession(
            self,
            payment_store=self.active_payment_store,
            terminal_id_provider=self._current_terminal_id,
        )
        self.compra_session.state_changed.connect(
            self._retry_pending_factory_reset
        )
        self._expiring_checkout_generation = None
        self._shutdown_authorized = False
        self._shutdown_started = False
        self._services_stopped = False
        self.identity_recovery_worker = None
        self.identity_recovery_timer = QTimer(self)
        self.identity_recovery_timer.setSingleShot(True)
        self.identity_recovery_timer.timeout.connect(
            self._start_identity_recovery
        )
        self.device_auth_guard_timer = QTimer(self)
        self.device_auth_guard_timer.setInterval(1000)
        self.device_auth_guard_timer.timeout.connect(self._guard_device_auth)
        self.device_auth_guard_timer.start()

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
        self.local_recovery_screen = self._build_local_recovery_screen()
        self.identity_recovery_screen = self._build_identity_recovery_screen()


        self.stacked_widget.addWidget(self.welcome)
        # self.stacked_widget.addWidget(self.login)
        self.stacked_widget.addWidget(self.cadastro_terminal)
        self.stacked_widget.addWidget(self.configuracao)
        self.stacked_widget.addWidget(self.admin_auth)
        self.stacked_widget.addWidget(self.local_recovery_screen)
        self.stacked_widget.addWidget(self.identity_recovery_screen)

        # -----------------------------
        # OUTRAS TELAS (lazy init)
        # -----------------------------
        self.terminal = None
        self.pagamento = None
        self.teclado = None
        self.app_payment = None
        self.confirmacao = None
        self.confirmacao_compra = None

        pending_payment = (
            self.active_payment_store.load()
            if self.active_payment_store is not None else None
        )
        if self._startup_recovery_error:
            self.stacked_widget.setCurrentWidget(self.local_recovery_screen)
        elif pending_payment and not TerminalCredentialStore().load():
            self.compra_session.restore_pending_payment()
            self.identity_recovery_status.setText(
                "Pagamento preservado. A credencial do equipamento precisa ser "
                "reprovisionada pelo administrador antes da reconciliacao."
            )
            self.stacked_widget.setCurrentWidget(self.identity_recovery_screen)
        elif Terminal.is_activated() and TerminalCredentialStore().load():
            self.iniciar_operacao_terminal()
            self.stacked_widget.setCurrentWidget(self.welcome)

        elif pending_payment:
            self.compra_session.restore_pending_payment()
            self.stacked_widget.setCurrentWidget(self.identity_recovery_screen)
            QTimer.singleShot(0, self._start_identity_recovery)
        else:
            if Terminal.is_activated() and not TerminalCredentialStore().load():
                self.cadastro_terminal.activation_timer.start(
                    self.cadastro_terminal.POLL_INTERVAL_MS
                )
                QTimer.singleShot(0, self.cadastro_terminal.verificar_ativacao)
            self.stacked_widget.setCurrentWidget(self.cadastro_terminal)

    def _guard_device_auth(self):
        state = terminal_access_state.get()
        if state not in {"AUTH_REQUIRED", "FORBIDDEN"}:
            return
        self._set_checkout_interactions_enabled(False)
        if TerminalResetPolicy.has_unresolved_payment(self.compra_session):
            self.identity_recovery_status.setText(
                "Pagamento preservado. Operacao bloqueada ate o administrador "
                "restaurar a autorizacao deste equipamento."
            )
            self.stacked_widget.setCurrentWidget(self.identity_recovery_screen)
            return
        message = (
            "Credencial revogada ou invalida. Solicite reprovisionamento."
            if state == "AUTH_REQUIRED"
            else "Terminal sem permissao operacional. Contate o administrador."
        )
        self.cadastro_terminal._atualizar_status(message, True)
        if not self.cadastro_terminal.activation_timer.isActive():
            self.cadastro_terminal.activation_timer.start(
                self.cadastro_terminal.POLL_INTERVAL_MS
            )
        self.stacked_widget.setCurrentWidget(self.cadastro_terminal)

    def _build_local_recovery_screen(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 80, 80, 80)
        message = QMessageBox(
            QMessageBox.Critical, "Recuperacao necessaria", "", parent=page
        )
        message.setText(
            "O armazenamento local nao passou na verificacao de integridade.\n\n"
            "Uma nova compra foi bloqueada para preservar possivel estado de "
            "pagamento. Contate o administrador; o banco nao foi apagado."
        )
        message.setStandardButtons(QMessageBox.NoButton)
        layout.addWidget(message)
        return page

    def _build_identity_recovery_screen(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 80, 80, 80)
        title = QLabel("RECUPERANDO PAGAMENTO", page)
        title.setAlignment(Qt.AlignCenter)
        self.identity_recovery_status = QLabel(
            "A identidade local precisa ser restaurada. Estamos consultando o "
            "backend antes de permitir outra ativacao ou compra.", page
        )
        self.identity_recovery_status.setAlignment(Qt.AlignCenter)
        self.identity_recovery_status.setWordWrap(True)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(self.identity_recovery_status)
        layout.addStretch(1)
        return page

    def _start_identity_recovery(self):
        if self._shutdown_started or self.active_payment_store is None:
            return
        if (self.identity_recovery_worker is not None
                and self.identity_recovery_worker.isRunning()):
            return
        terminal_id = self.current_terminal_id()
        if not terminal_id:
            self.identity_recovery_status.setText(
                "O checkpoint nao possui identidade suficiente. Nova compra "
                "permanece bloqueada; contate o administrador."
            )
            return
        worker = ActivePaymentRecoveryWorker(terminal_id, parent=self)
        self.identity_recovery_worker = worker
        worker.succeeded.connect(self._identity_recovery_received)
        worker.failed.connect(self._identity_recovery_failed)
        worker.finished.connect(
            lambda expected=worker: self._identity_recovery_finished(expected)
        )
        worker.start()

    def _identity_recovery_received(self, data):
        session = self.compra_session
        if isinstance(data, dict) and data.get("orderId"):
            session.adopt_backend_payment(data)
            outcome = session.apply_status(
                data.get("orderId"), data.get("status"),
                data.get("paymentAttemptId") or data.get("paymentId"),
            )
            if outcome in {"APPROVED", "FAILED"}:
                self._complete_identity_recovery(outcome)
                return
            self.identity_recovery_status.setText(
                "O pagamento remoto ainda esta ativo ou incerto. Outra compra "
                "permanece bloqueada; nova verificacao sera feita automaticamente."
            )
            self.identity_recovery_timer.start(30000)
            return
        session.clear_unresolved_after_authoritative_absence()
        self._complete_identity_recovery("ABSENT")

    def _identity_recovery_failed(self, message):
        logging.getLogger(__name__).warning(
            "[PAYMENT-RECOVERY] identidade local ausente; consulta falhou: %s",
            message,
        )
        self.compra_session.mark_reconciliation_pending()
        self.identity_recovery_status.setText(
            "Nao foi possivel confirmar o pagamento. O Terminal continua "
            "bloqueado e tentara novamente."
        )
        self.identity_recovery_timer.start(30000)

    def _identity_recovery_finished(self, worker):
        if self.identity_recovery_worker is worker:
            self.identity_recovery_worker = None
        worker.deleteLater()

    def _complete_identity_recovery(self, outcome):
        logging.getLogger(__name__).warning(
            "[PAYMENT-RECOVERY] concluida sem identidade local outcome=%s", outcome
        )
        self.identity_recovery_timer.stop()
        self.cadastro_terminal.activation_timer.start(
            self.cadastro_terminal.POLL_INTERVAL_MS
        )
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

        terminal_config = Terminal.load()
        self.compra_session.restore_pending_payment(
            terminal_config.terminalId if terminal_config is not None else None
        )

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
        QTimer.singleShot(0, self.pagamento.recuperar_apos_startup)

    @staticmethod
    def _current_terminal_id():
        terminal = Terminal.load()
        return terminal.terminalId if terminal is not None else None

    def current_terminal_id(self):
        terminal_id = self._current_terminal_id()
        if terminal_id or self.active_payment_store is None:
            return terminal_id
        snapshot = self.active_payment_store.load()
        return snapshot.get("terminal_id") if snapshot else None

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
        if not TerminalCredentialStore().load():
            terminal_access_state.set("AUTH_REQUIRED")
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

        self.terminal.listener.factory_reset_required.connect(
            self._on_factory_reset_hint, Qt.QueuedConnection
        )
        self.terminal.listener.lifecycle_check_requested.connect(
            self._check_terminal_lifecycle, Qt.QueuedConnection
        )
        self.lifecycle_timer = QTimer(self)
        self.lifecycle_timer.setInterval(60000)
        self.lifecycle_timer.timeout.connect(
            lambda: self._check_terminal_lifecycle("PERIODIC_BOOTSTRAP")
        )
        self.lifecycle_timer.start()
        QTimer.singleShot(
            0, lambda: self._check_terminal_lifecycle("APPLICATION_STARTUP")
        )

    def _on_factory_reset_hint(self, payload):
        logging.getLogger(__name__).warning(
            "[TERMINAL-RESET] aviso WebSocket recebido; confirmando via HTTP"
        )
        self._check_terminal_lifecycle("WEBSOCKET_RESET_HINT")

    def _check_terminal_lifecycle(self, origin="BOOTSTRAP"):
        terminal = Terminal.load()
        if terminal is None or self._shutdown_started:
            return
        if self._lifecycle_worker is not None and self._lifecycle_worker.isRunning():
            return
        worker = TerminalLifecycleCheckThread(
            terminal.terminalId, api=self.lifecycle_api, parent=self
        )
        self._lifecycle_worker = worker
        worker.result_ready.connect(
            lambda response, source=origin: self._handle_lifecycle_response(
                response, source
            )
        )
        worker.finished.connect(self._lifecycle_check_finished)
        worker.start()

    def _lifecycle_check_finished(self):
        worker = self._lifecycle_worker
        self._lifecycle_worker = None
        if worker is not None:
            worker.deleteLater()

    def _handle_lifecycle_response(self, response, origin):
        if not isinstance(response, dict):
            # Timeout, 5xx, offline ou JSON inválido: nunca resetar.
            return
        state = response.get("state")
        if state != "RESET_REQUIRED":
            return
        logging.getLogger(__name__).warning(
            "[TERMINAL-RESET] estado autoritativo recebido origin=%s reason=%s",
            origin, response.get("reason"),
        )
        if TerminalResetPolicy.has_unresolved_payment(self.compra_session):
            self._factory_reset_pending = response
            logging.getLogger(__name__).warning(
                "[TERMINAL-RESET] adiado para reconciliar pagamento em andamento"
            )
            if self.terminal is not None:
                self.terminal.verificar_pagamento_apos_reconexao()
            return
        self._execute_factory_reset(response)

    def _retry_pending_factory_reset(self, _state):
        if self._factory_reset_pending is None:
            return
        if TerminalResetPolicy.has_unresolved_payment(self.compra_session):
            return
        response, self._factory_reset_pending = self._factory_reset_pending, None
        self._execute_factory_reset(response)

    def _execute_factory_reset(self, response):
        terminal = Terminal.load()
        if terminal is None or self._shutdown_started:
            return
        self.lifecycle_api.notify_started(terminal.terminalId)
        try:
            self.factory_reset_service.request_reset(
                terminal_id=terminal.terminalId,
                reason=response.get("reason") or "RESET_REQUIRED",
                remote=True,
            )
        except OSError:
            logging.getLogger(__name__).exception(
                "[TERMINAL-RESET] não foi possível persistir o marcador"
            )
            return
        self.encerrar_terminal()

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

    def abrir_wifi_pre_ativacao(self):
        if Terminal.is_activated() or self._startup_recovery_error:
            return
        self.configuracao.entrar_pre_ativacao(self.cadastro_terminal)
        self.stacked_widget.setCurrentWidget(self.configuracao)

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
        lifecycle_timer = getattr(self, "lifecycle_timer", None)
        if lifecycle_timer is not None:
            lifecycle_timer.stop()
        identity_timer = getattr(self, "identity_recovery_timer", None)
        if identity_timer is not None:
            identity_timer.stop()
        identity_worker = getattr(self, "identity_recovery_worker", None)
        if identity_worker is not None and identity_worker.isRunning():
            identity_worker.requestInterruption()
            identity_worker.wait(25000)
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
            and self.compra_session.payment_in_flight
        ):
            self.pagamento.mostrar_reconciliacao_pendente(origin="HOME_GUARD")
            return
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
        if IS_PRODUCTION:
            self.showFullScreen()
        else:
            self.showNormal()
            self.setFixedSize(1024, 600)
        self.central_widget.updateGeometry()
        self.stacked_widget.updateGeometry()
        current = self.stacked_widget.currentWidget()
        if current is not None:
            current.updateGeometry()


def present_main_window(window, production=IS_PRODUCTION):
    """Aplica explicitamente o contrato de janela para dev ou kiosk."""
    if production:
        window.showFullScreen()
    else:
        window.setFixedSize(1024, 600)
        window.show()
