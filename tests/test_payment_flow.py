import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from model.CompraSession import CompraSession
from telas.pagamento import PagamentoScreen


class ConfirmationStub(QWidget):
    def __init__(self):
        super().__init__()
        self.shown = False

    def mostrar_tela(self):
        self.shown = True


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

    def test_approved_event_is_correlated_and_opens_existing_success_screen(self):
        terminal = SimpleNamespace(terminalId="terminal-a")
        with patch("telas.pagamento.Terminal.load", return_value=terminal):
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
        self.assertIn("Aguardando", self.screen.loading.text())

    def test_global_timeout_without_remote_payment_returns_to_welcome(self):
        self.parent.compra_session.reset()
        self.parent.compra_session.start_if_needed()
        generation = self.parent.compra_session.generation
        self.screen.tratar_timeout_global(generation)
        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)

    def test_global_timeout_with_remote_payment_starts_bounded_reconciliation(self):
        generation = self.parent.compra_session.generation
        self.screen.tratar_timeout_global(generation)
        self.assertTrue(self.screen.timeout_pending)
        self.assertTrue(self.screen.final_recovery_timer.isActive())
        self.assertIs(self.screen.loading_page, self.screen.pages.currentWidget())

    def test_reconnect_checks_backend_and_approved_opens_success(self):
        with patch.object(self.screen, "reconciliar_estado") as reconcile:
            self.screen.verificar_apos_reconexao()
        reconcile.assert_called_once()
        self.assertEqual("VERIFICANDO PAGAMENTO", self.screen.title.text())

        self.screen._status_received("order-a", {
            "orderId": "order-a", "paymentId": "payment-a",
            "status": "APPROVED", "reconciled": True,
        })

        self.assertTrue(self.parent.confirmacao.shown)
        self.assertIs(self.parent.confirmacao, self.parent.current)
        self.assertEqual("payment-a", self.parent.compra_session.payment_id)

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


if __name__ == "__main__":
    unittest.main()
