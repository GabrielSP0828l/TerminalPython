import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QStackedWidget, QWidget, QPushButton

from app247_terminal.models.purchase_session import CompraSession
from app247_terminal.ui.screens.terminal import TerminalScreen


PRODUCT_ROW = (
    "product-1", "789", "Leite", 5.0, 10, "ALIMENTOS", "UNIDADE",
    "", "", None, None, "2026-01-01", "2026-01-01", 1,
)


class FakeDb:
    def buscar_por_codigo(self, barcode):
        return PRODUCT_ROW if barcode == "789" else None


class FakeParent(QWidget):
    def __init__(self):
        super().__init__()
        self.stacked_widget = QStackedWidget(self)
        self.compra_session = CompraSession(self)


class ScannerQuantityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_repeated_scan_increments_without_manual_quantity_buttons(self):
        parent = FakeParent()
        terminal_data = SimpleNamespace(uuidTerminal="terminal-1")
        with patch("app247_terminal.ui.screens.terminal.CatalogService", return_value=FakeDb()), \
             patch("app247_terminal.models.cart.Terminal.load", return_value=terminal_data), \
             patch("app247_terminal.services.payment_listener.Terminal.load", return_value=terminal_data), \
             patch("app247_terminal.services.payment_listener.PaymentListener.start"):
            screen = TerminalScreen(parent)
        parent.stacked_widget.addWidget(screen)

        screen.codigo_barras.setText("789")
        screen.readProduct()
        screen.codigo_barras.setText("789")
        screen.readProduct()

        self.assertEqual(2, screen.carrinho.buscar_item("789").quantidade)
        line_widget = screen.linhas["789"][0]
        self.assertEqual(["REMOVER"], [button.text() for button in line_widget.findChildren(QPushButton)])
        self.assertGreaterEqual(
            line_widget.findChild(QPushButton).minimumHeight(), 56
        )


if __name__ == "__main__":
    unittest.main()
