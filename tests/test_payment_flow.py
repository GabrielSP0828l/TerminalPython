import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from app247_terminal.models.purchase_session import CompraSession
from app247_terminal.ui.screens.payment import PagamentoScreen


class ConfirmationStub(QWidget):
    def __init__(self):
        super().__init__()
        self.shown = False
        self.recovered_amount = None

    def mostrar_tela(self, recovered_amount=None):
        self.shown = True
        self.recovered_amount = recovered_amount


class ParentStub(QWidget):
    def __init__(self):
        super().__init__()
        self.compra_session = CompraSession(self)
        self.confirmacao = ConfirmationStub()
        self.terminal = QWidget()
        self.welcome = QWidget()
        self.current = None
        self.reset_calls = 0

    def setCurrentWidget(self, widget):
        self.current = widget

    def reset_compra(self, outcome="cancelled"):
        self.reset_calls += 1
        self.compra_session.reset()


class PaymentFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = ParentStub()
        self.screen = PagamentoScreen(self.parent)
        self.attempt = self.parent.compra_session.begin_payment()
        self.screen.current_attempt = self.attempt
        self.screen._point_started(self.attempt, {
            "cartId": "cart-a", "orderId": "order-a",
            "terminalId": "terminal-a", "status": "WAITING_PAYMENT"
        })

    def tearDown(self):
        self.screen.parar_workers()

    def test_approved_event_is_correlated_and_opens_existing_success_screen(self):
        terminal = SimpleNamespace(terminalId="terminal-a")
        with patch("app247_terminal.ui.screens.payment.Terminal.load", return_value=terminal):
            self.screen.processar_evento({
                "terminalId": "terminal-a", "orderId": "order-old", "status": "APPROVED"
            })
            self.assertFalse(self.parent.confirmacao.shown)
            self.screen.processar_evento({
                "terminalId": "terminal-a", "orderId": "order-a", "status": "APPROVED"
            })
        self.assertTrue(self.parent.confirmacao.shown)
        self.assertIs(self.parent.confirmacao, self.parent.current)

    def test_rejected_returns_to_cart_without_reset(self):
        self.screen._apply_status("order-a", "REJECTED")
        self.assertEqual("CART_READY", self.parent.compra_session.state)
        self.assertEqual(0, self.parent.reset_calls)
        self.screen._voltar_lista()
        self.assertIs(self.parent.terminal, self.parent.current)

    def test_processing_keeps_waiting(self):
        self.screen._apply_status("order-a", "WAITING_PAYMENT")
        self.assertTrue(self.parent.compra_session.payment_in_flight)
        self.assertIs(self.screen.attention_page, self.screen.pages.currentWidget())
        self.assertEqual("FINALIZE NA MAQUININHA", self.screen.attention_page.title.text())

    def test_global_timeout_without_remote_payment_returns_to_welcome(self):
        self.parent.compra_session.reset()
        self.parent.compra_session.start_if_needed()
        generation = self.parent.compra_session.generation
        self.screen.tratar_timeout_global(generation)
        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)

    def test_global_timeout_with_remote_payment_starts_bounded_reconciliation(self):
        generation = self.parent.compra_session.generation
        with patch.object(self.screen, "_cancel_payment") as cancel:
            self.screen.tratar_timeout_global(generation)
        cancel.assert_called_once()
        self.assertTrue(self.screen.timeout_pending)
        self.assertTrue(self.screen.final_recovery_timer.isActive())
        self.assertIs(self.screen.attention_page, self.screen.pages.currentWidget())

    def test_timeout_while_point_request_has_no_ids_waits_for_safe_result(self):
        self.parent.compra_session.reset()
        attempt = self.parent.compra_session.begin_payment()
        self.screen.current_attempt = attempt
        self.screen.point_worker = SimpleNamespace(
            isRunning=lambda: True,
            requestInterruption=lambda: None,
            wait=lambda _milliseconds: True,
        )

        self.screen.tratar_timeout_global(self.parent.compra_session.generation)

        self.assertTrue(self.screen.timeout_pending)
        self.assertEqual(0, self.parent.reset_calls)
        self.assertIs(self.screen.loading_page, self.screen.pages.currentWidget())

    def test_definitive_failure_after_global_timeout_resets_instead_of_retrying(self):
        self.screen.timeout_pending = True
        self.screen._apply_status("order-a", "REJECTED")

        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)

    def test_old_order_event_cannot_replace_current_payment_id(self):
        self.parent.compra_session.set_remote_ids(payment_id="payment-current")
        self.screen._apply_status("order-old", "APPROVED", "payment-old")

        self.assertEqual("payment-current", self.parent.compra_session.payment_id)
        self.assertFalse(self.parent.confirmacao.shown)

    def test_reconnect_checks_backend_and_approved_opens_success(self):
        with patch.object(self.screen, "reconciliar_estado") as reconcile:
            self.screen.verificar_apos_reconexao()
        reconcile.assert_called_once()
        self.assertIs(self.screen.attention_page, self.screen.pages.currentWidget())

        self.screen._status_received("order-a", {
            "orderId": "order-a", "paymentId": "attempt-a",
            "paymentAttemptId": "attempt-a", "transactionId": "payment-a",
            "status": "APPROVED", "reconciled": True,
        })

        self.assertTrue(self.parent.confirmacao.shown)
        self.assertIs(self.parent.confirmacao, self.parent.current)
        self.assertEqual("payment-a", self.parent.compra_session.payment_id)
        self.assertEqual("attempt-a", self.parent.compra_session.payment_attempt_id)

    def test_reconnect_pending_keeps_payment_in_flight(self):
        self.screen._status_received("order-a", {
            "orderId": "order-a", "status": "WAITING_PAYMENT", "reconciled": True,
        })

        self.assertTrue(self.parent.compra_session.payment_in_flight)
        self.assertNotEqual("CART_READY", self.parent.compra_session.state)

    def test_reconnect_rejected_shows_error_state(self):
        self.screen._status_received("order-a", {
            "orderId": "order-a", "status": "REJECTED", "reconciled": True,
        })

        self.assertEqual("CART_READY", self.parent.compra_session.state)
        self.assertEqual("Pagamento recusado", self.screen.error_reason.text())
        self.assertIs(self.screen.error_page, self.screen.pages.currentWidget())

    def test_reconciliation_degraded_keeps_visible_recovery_and_slow_polling(self):
        self.screen.reconciliation_failures = self.screen.MAX_RECONCILIATION_FAILURES
        self.screen.timeout_pending = False
        self.screen._status_failed("order-a", "offline")

        self.assertEqual("RECONCILIATION_PENDING", self.parent.compra_session.state)
        self.assertTrue(self.screen.poll_timer.isActive())
        self.assertEqual(
            self.screen.DEGRADED_POLL_INTERVAL_MS,
            self.screen.poll_timer.interval(),
        )
        self.assertIs(self.screen, self.parent.current)
        self.assertEqual(
            "PAGAMENTO AINDA NÃO CONCLUÍDO",
            self.screen.attention_page.title.text(),
        )
        self.assertEqual("CANCELAR COMPRA", self.screen.cancel_payment_button.text())

    def test_cancelamento_confirmado_so_entao_volta_para_home(self):
        self.assertTrue(self.parent.compra_session.mark_cancelling())

        self.screen._cancel_received("order-a", {
            "orderId": "order-a", "status": "CANCELLED",
            "cancellationRequested": True,
        })

        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)

    def test_cancelamento_inconclusivo_mantem_bloqueio_e_tela_laranja(self):
        self.assertTrue(self.parent.compra_session.mark_cancelling())
        with patch.object(self.screen, "reconciliar_estado") as reconcile:
            self.screen._cancel_failed("timeout", "order-a")

        self.assertTrue(self.parent.compra_session.payment_in_flight)
        self.assertTrue(self.parent.compra_session.cancellation_requested)
        self.assertIs(self.screen.attention_page, self.screen.pages.currentWidget())
        self.assertFalse(self.screen.cancel_payment_button.isEnabled())
        reconcile.assert_called_once()

    def test_pending_without_order_reconcilia_no_backend_antes_de_reenviar_cart(self):
        self.parent.compra_session.order_id = None
        self.parent.compra_session.mark_reconciliation_pending()
        with patch.object(self.screen, "_discover_active_payment") as discover:
            self.screen.reconciliar_estado()
        discover.assert_called_once_with("TERMINAL_RECOVERY")

    def test_startup_adopts_backend_attempt_and_rejects_stale_discovery_callback(self):
        self.parent.compra_session.reset()
        self.screen.current_attempt = None
        self.screen._active_recovery_received(None, "STARTUP", {
            "orderId": "order-restored",
            "paymentAttemptId": "attempt-restored",
            "status": "WAITING_PAYMENT",
            "mercadoPagoStatus": "CREATED",
        })

        self.assertTrue(self.parent.compra_session.payment_in_flight)
        self.assertEqual("order-restored", self.parent.compra_session.order_id)
        self.assertEqual("attempt-restored", self.parent.compra_session.payment_attempt_id)

        current_token = self.parent.compra_session.attempt_id
        self.screen._active_recovery_received("stale-token", "STARTUP", None)
        self.assertEqual(current_token, self.parent.compra_session.attempt_id)
        self.assertTrue(self.parent.compra_session.payment_in_flight)

    def test_recovered_approval_passes_backend_amount_to_success_screen(self):
        self.screen._status_received("order-a", {
            "orderId": "order-a", "status": "APPROVED", "amount": "48.90"
        })

        self.assertTrue(self.parent.confirmacao.shown)
        self.assertEqual("48.90", self.parent.confirmacao.recovered_amount)


if __name__ == "__main__":
    unittest.main()
