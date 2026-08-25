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

    def reset_compra(self):
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


if __name__ == "__main__":
    unittest.main()
