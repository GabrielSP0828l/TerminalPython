"""Leitura feita na tela inicial abre a compra já com o item."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from test_checkout_timeout import CheckoutHost, FakeClock

from app247_terminal.ui.screens.welcome import TelaBemVindos


class WelcomeScanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = CheckoutHost(FakeClock())
        self.host.abrir_configuracoes = lambda: None
        self.welcome = TelaBemVindos(self.host)
        self.host.welcome = self.welcome
        self.host.stacked_widget.addWidget(self.welcome)
        self.host.setCurrentWidget(self.welcome)
        self.terminal = self.host.terminal

    def tearDown(self):
        self.welcome.stop()
        self.host.close_test_host()

    def _scan(self, code):
        QTest.keyClicks(self.welcome, code)
        QTest.keyClick(self.welcome, Qt.Key_Return)

    def test_scan_on_welcome_opens_purchase_with_the_product(self):
        self._scan("789")

        self.assertIs(self.terminal, self.host.stacked_widget.currentWidget())
        self.assertEqual(1, len(self.terminal.carrinho.items))
        self.assertTrue(self.host.compra_session.active)
        self.assertEqual("", self.terminal.codigo_barras.text())

    def test_pause_discards_partial_read(self):
        QTest.keyClicks(self.welcome, "12")
        self.welcome._scan_reset.timeout.emit()

        self._scan("789")

        self.assertEqual(1, len(self.terminal.carrinho.items))

    def test_enter_without_read_stays_on_welcome(self):
        QTest.keyClick(self.welcome, Qt.Key_Return)

        self.assertIs(self.welcome, self.host.stacked_widget.currentWidget())
        self.assertTrue(self.terminal.carrinho.vazio())

    def test_scan_during_pending_payment_does_not_start_purchase(self):
        session = self.host.compra_session
        session.start_if_needed()
        session.payment_in_flight = True

        self._scan("789")

        self.host.pagamento.mostrar_reconciliacao_pendente.assert_called()
        self.assertIsNot(self.terminal, self.host.stacked_widget.currentWidget())
        self.assertTrue(self.terminal.carrinho.vazio())

    def test_button_still_opens_purchase(self):
        self.welcome.botao_entrar.click()

        self.assertIs(self.terminal, self.host.stacked_widget.currentWidget())
        self.assertTrue(self.terminal.carrinho.vazio())


if __name__ == "__main__":
    unittest.main()
