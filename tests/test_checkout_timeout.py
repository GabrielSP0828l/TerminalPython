import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QStackedWidget, QWidget

from main import MainWindow
from model.CompraSession import CompraSession
from telas.ConfirmacaoCompraScreen import ConfirmacaoCompraScreen
from telas.terminal_screen import TerminalScreen


PRODUCT_ROW = (
    "product-1", "789", "Leite", 5.0, 10, "ALIMENTOS", "UNIDADE",
    "", "", None, None, "2026-01-01", "2026-01-01", 1,
)


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


class FakeDb:
    def buscar_por_codigo(self, barcode):
        return PRODUCT_ROW if barcode == "789" else None


class CheckoutHost(QWidget):
    """Host Qt mínimo que exercita os métodos reais do controlador principal."""

    def __init__(self, clock):
        super().__init__()
        self.compra_session = CompraSession(
            self, clock=clock, duration_seconds=2
        )
        self.reset_calls = 0
        self._expiring_checkout_generation = None
        self.stacked_widget = QStackedWidget(self)
        self.welcome = QWidget()
        self.configuracao = QWidget()
        self.pagamento = MagicMock()
        self.app_payment = None
        self.confirmacao_compra = None

        terminal_data = MagicMock(uuidTerminal="terminal-1")
        with patch("telas.terminal_screen.DatabaseProdutos", return_value=FakeDb()), \
             patch("model.Carrinho.Terminal.load", return_value=terminal_data), \
             patch("database.PaymentListener.Terminal.load", return_value=terminal_data), \
             patch("database.PaymentListener.PaymentListener.start"):
            self.terminal = TerminalScreen(self)
        self.confirmacao_compra = ConfirmacaoCompraScreen(self)

        for widget in (self.welcome, self.configuracao, self.terminal, self.confirmacao_compra):
            self.stacked_widget.addWidget(widget)
        self.compra_session.expired.connect(self._checkout_session_expired)

    _checkout_session_expired = MainWindow._checkout_session_expired
    complete_checkout_expiration = MainWindow.complete_checkout_expiration
    _set_checkout_interactions_enabled = MainWindow._set_checkout_interactions_enabled
    setCurrentWidget = MainWindow.setCurrentWidget

    def reset_compra(self, outcome="cancelled"):
        self.reset_calls += 1
        MainWindow.reset_compra(self, outcome)

    def close_test_host(self):
        self.terminal.timer_foco.stop()
        self.compra_session.stop()


class CheckoutTimeoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = FakeClock()
        self.host = CheckoutHost(self.clock)
        self.host.setCurrentWidget(self.host.terminal)

    def tearDown(self):
        self.host.close_test_host()

    def _scan_product(self):
        self.host.terminal.codigo_barras.setText("789")
        self.host.terminal.readProduct()

    def _expire(self):
        self.clock.value += 3
        self.host.compra_session._tick()

    def test_cart_timeout_resets_once_and_returns_to_welcome(self):
        expired = []
        remaining = []
        self.host.compra_session.expired.connect(expired.append)
        self.host.compra_session.remaining_changed.connect(remaining.append)
        self._scan_product()
        generation = self.host.compra_session.generation

        self._expire()
        self.host.compra_session._tick()

        self.assertEqual([generation], expired)
        self.assertEqual(1, self.host.reset_calls)
        self.assertIn(0, remaining)
        self.assertIs(self.host.welcome, self.host.stacked_widget.currentWidget())
        self.assertTrue(self.host.terminal.carrinho.vazio())
        self.assertFalse(self.host.terminal.codigo_barras.isEnabled())
        self.assertTrue(self.host.terminal.session_timer.text().startswith("00:02"))

    def test_confirmation_timeout_cancels_confirmation_and_resets(self):
        self._scan_product()
        self.host.terminal.ir_para_pagamento()
        self.assertIs(
            self.host.confirmacao_compra,
            self.host.stacked_widget.currentWidget(),
        )

        self._expire()

        self.assertIs(self.host.welcome, self.host.stacked_widget.currentWidget())
        self.assertTrue(self.host.terminal.carrinho.vazio())
        self.assertFalse(self.host.confirmacao_compra.btn_confirmar.isEnabled())

    def test_scanner_is_blocked_after_timeout_and_new_session_is_clean(self):
        self._scan_product()
        expired_generation = self.host.compra_session.generation
        self._expire()

        self.host.terminal.codigo_barras.setText("789")
        self.host.terminal.readProduct()
        self.assertTrue(self.host.terminal.carrinho.vazio())

        self.host.setCurrentWidget(self.host.terminal)
        self._scan_product()

        self.assertFalse(self.host.terminal.carrinho.vazio())
        self.assertNotEqual(expired_generation, self.host.compra_session.generation)
        self.assertEqual(2, self.host.compra_session.remaining_seconds())
        self.assertTrue(self.host.compra_session.active)


if __name__ == "__main__":
    unittest.main()
