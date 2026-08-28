import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QStackedWidget, QWidget

from model.CompraSession import CompraSession
from model.Item import Item
from model.Produtos import Produtos
from telas.ConfirmacaoCompraScreen import ConfirmacaoCompraScreen
from telas.OfflineOverlay import OfflineOverlay
from telas.pagamento import PagamentoScreen
from telas.terminal_screen import TerminalScreen


PRODUCT_ROW = (
    "product-1", "789", "Produto com um nome bastante longo para validar quebra de linha",
    123456.78, 10, "ALIMENTOS", "UNIDADE", "", "", None, None,
    "2026-01-01", "2026-01-01", 1,
)


class ParentStub(QWidget):
    def __init__(self):
        super().__init__()
        self.stacked_widget = QStackedWidget(self)
        self.compra_session = CompraSession(self)
        self.pagamento = MagicMock()
        self.welcome = QWidget()
        self.sync_service = None
        self.confirmacao_compra = None

    def setCurrentWidget(self, widget):
        self.stacked_widget.setCurrentWidget(widget)

    def reset_compra(self, outcome="cancelled"):
        self.compra_session.reset()


class PortraitPurchaseFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = ParentStub()
        terminal_data = SimpleNamespace(uuidTerminal="terminal-1")
        with patch("telas.terminal_screen.DatabaseProdutos"), \
             patch("model.Carrinho.Terminal.load", return_value=terminal_data), \
             patch("database.PaymentListener.Terminal.load", return_value=terminal_data), \
             patch("database.PaymentListener.PaymentListener.start"):
            self.terminal = TerminalScreen(self.parent)
        self.parent.terminal = self.terminal
        self.parent.confirmacao_compra = ConfirmacaoCompraScreen(self.parent)
        self.parent.stacked_widget.addWidget(self.terminal)
        self.parent.stacked_widget.addWidget(self.parent.confirmacao_compra)

    def _add_item(self, quantity=3):
        product = Produtos.from_tuple(PRODUCT_ROW)
        item = Item(product, quantidade=quantity)
        self.terminal.carrinho.adicionar_item(item)
        self.terminal.linhas[product.codigo] = (QWidget(), QWidget(), 1)
        self.terminal.atualizar_interface()

    def test_cart_is_portrait_friendly_and_has_only_finalize_as_payment_action(self):
        self.parent.resize(768, 1360)
        self.parent.stacked_widget.resize(768, 1360)
        self.parent.stacked_widget.setCurrentWidget(self.terminal)
        self.parent.show()
        self.app.processEvents()
        self.assertEqual("FINALIZAR", self.terminal.btn_finalizar.text())
        button_texts = [button.text() for button in self.terminal.findChildren(type(self.terminal.btn_finalizar))]
        self.assertNotIn("PAGAR NO APP", button_texts)
        self.assertGreaterEqual(self.terminal.btn_finalizar.minimumHeight(), 72)
        self.assertGreater(self.terminal.scroll.height(), 300)

    def test_real_hardware_uses_three_column_grid_and_legible_confirmation(self):
        self.parent.resize(1024, 600)
        self.parent.stacked_widget.resize(1024, 600)
        self.parent.stacked_widget.setCurrentWidget(self.terminal)
        self.parent.show()

        rows = []
        for index, (name, price) in enumerate((
            (PRODUCT_ROW[2], PRODUCT_ROW[3]),
            ("Leite Integral 1L", 7.99),
            ("Arroz Tipo 1 1kg", 8.90),
            ("Café Torrado 500g", 18.90),
        )):
            row = list(PRODUCT_ROW)
            row[0], row[1], row[2], row[3] = (
                f"product-{index + 1}", str(789 + index), name, price
            )
            rows.append((str(789 + index), tuple(row)))

        for barcode, row in rows:
            self.terminal.db.buscar_por_codigo.return_value = row
            self.terminal.codigo_barras.setText(barcode)
            self.terminal.readProduct()
        self.app.processEvents()

        cards = [entry[0] for entry in self.terminal.linhas.values()]
        columns = [
            self.terminal.productsLayout.getItemPosition(
                self.terminal.productsLayout.indexOf(card)
            )[1]
            for card in cards
        ]
        positions = [
            self.terminal.productsLayout.getItemPosition(
                self.terminal.productsLayout.indexOf(card)
            )[:2]
            for card in cards
        ]
        self.assertEqual(3, self.terminal._grid_columns)
        self.assertEqual([0, 1, 2, 0], columns)
        self.assertEqual([(0, 0), (0, 1), (0, 2), (1, 0)], positions)
        self.assertTrue(all(250 <= card.width() <= 292 for card in cards))
        self.assertTrue(all(card.height() == 224 for card in cards))
        self.assertGreaterEqual(
            cards[3].y(), cards[0].y() + cards[0].height() + 12
        )
        self.assertEqual(Qt.ScrollBarAlwaysOff, self.terminal.scroll.horizontalScrollBarPolicy())
        self.assertFalse(self.terminal.scroll.horizontalScrollBar().isVisible())
        self.assertTrue(all("Código" not in card.findChild(QLabel).text() for card in cards))
        self.assertLessEqual(len(cards[0].name.text().splitlines()), 2)
        self.assertGreaterEqual(cards[0].name.font().pixelSize(), 26)
        self.assertGreaterEqual(cards[0].price.font().pixelSize(), 34)
        self.assertGreaterEqual(cards[0].quantity.font().pixelSize(), 22)
        self.assertGreaterEqual(self.terminal.totalBox.font().pixelSize(), 40)
        self.assertEqual(26, self.terminal.btn_finalizar.font().pixelSize())
        self.assertGreaterEqual(self.terminal.btn_finalizar.height(), 72)

        self.parent.confirmacao_compra.mostrar_resumo()
        self.parent.stacked_widget.setCurrentWidget(self.parent.confirmacao_compra)
        self.app.processEvents()
        total_card = self.parent.confirmacao_compra.findChild(
            QFrame, "confirmationTotalCard"
        )
        self.assertEqual(
            "#ffffff", total_card.palette().color(QPalette.Window).name().lower()
        )
        confirmation_names = [
            label for label in self.parent.confirmacao_compra.findChildren(QLabel)
            if label.property("role") == "confirmationProductName"
        ]
        confirmation_quantities = [
            label for label in self.parent.confirmacao_compra.findChildren(QLabel)
            if label.property("role") == "confirmationProductQuantity"
        ]
        self.assertEqual(26, confirmation_names[0].font().pixelSize())
        self.assertEqual(24, confirmation_quantities[0].font().pixelSize())
        self.assertGreaterEqual(self.parent.confirmacao_compra.total.font().pixelSize(), 40)
        self.assertGreaterEqual(self.parent.confirmacao_compra.btn_voltar.font().pixelSize(), 24)
        self.assertGreaterEqual(self.parent.confirmacao_compra.btn_confirmar.height(), 72)

    def test_finalize_opens_summary_without_starting_payment(self):
        self._add_item()
        self.terminal.ir_para_pagamento()
        self.assertIs(self.parent.confirmacao_compra, self.parent.stacked_widget.currentWidget())
        self.assertEqual("3 itens", self.parent.confirmacao_compra.item_count.text())
        self.assertEqual("R$ 370370,34", self.parent.confirmacao_compra.total.text())
        self.parent.pagamento.iniciar_pagamento.assert_not_called()

    def test_back_preserves_same_cart_and_confirmation_starts_existing_point_flow(self):
        self._add_item()
        cart = self.terminal.carrinho
        self.parent.confirmacao_compra.mostrar_resumo()
        self.parent.confirmacao_compra.voltar()
        self.assertIs(cart, self.terminal.carrinho)
        self.parent.confirmacao_compra.confirmar()
        self.parent.pagamento.iniciar_pagamento.assert_called_once()
        self.assertFalse(self.parent.confirmacao_compra.btn_confirmar.isEnabled())

    def test_offline_overlay_fits_portrait_parent(self):
        host = QWidget()
        host.resize(768, 1360)
        overlay = OfflineOverlay(host)
        overlay.show()
        self.app.processEvents()
        self.assertEqual(host.size(), overlay.size())


if __name__ == "__main__":
    unittest.main()
