import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QAbstractAnimation, QObject, pyqtSignal
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QApplication, QWidget

from app247_terminal.models.item import Item
from app247_terminal.models.product import Produtos
from app247_terminal.ui import texts
from app247_terminal.ui.screens.session_timer import SessionTimerLabel
from app247_terminal.ui.screens.terminal import ProductCard
from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import FontSize, Motion


LONG_NAMES = (
    "Biscoito Recheado Chocolate com Avelã 140g",
    "Refrigerante Guaraná Antarctica Zero Açúcar Garrafa 2L",
    "Sabão em Pó Concentrado Lavanda e Flor de Algodão 1,6kg",
    "Pão de Queijo Tradicional Congelado 400g",
    "Água",
)


class FakeSession(QObject):
    remaining_changed = pyqtSignal(int)

    def remaining_seconds(self):
        return 600


class ClientScreenTextsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_session_timer_only_appears_in_the_last_minute(self):
        session = FakeSession()
        host = QWidget()
        label = SessionTimerLabel(session, host)
        host.show()
        self.app.processEvents()
        self.assertFalse(label.isVisible())
        session.remaining_changed.emit(61)
        self.assertFalse(label.isVisible())
        session.remaining_changed.emit(60)
        self.assertTrue(label.isVisible())
        self.assertEqual(f"01:00  {texts.SESSION_ENDING}", label.text())
        self.assertEqual("warning", label.property("state"))
        session.remaining_changed.emit(30)
        self.assertEqual("critical", label.property("state"))
        session.remaining_changed.emit(600)
        self.assertFalse(label.isVisible())

    def test_long_product_names_use_at_most_three_lines_inside_the_card(self):
        host = QWidget()
        host.setStyleSheet(Theme.cart_stylesheet())
        for width in (250, 276, 292):
            for name in LONG_NAMES:
                with self.subTest(width=width, name=name):
                    product = Produtos.from_tuple((
                        "p", "1", name, 9.9, 10, "ALIMENTOS", "UNIDADE", "", "",
                        None, None, "2026-01-01", "2026-01-01", 1,
                    ))
                    card = ProductCard(Item(product, quantidade=1), lambda: None, host)
                    card.set_card_width(width)
                    card.show()
                    self.app.processEvents()
                    lines = card.name.text().split("\n")
                    self.assertLessEqual(len(lines), ProductCard.MAX_NAME_LINES)
                    self.assertFalse(card.name.wordWrap())
                    metrics = QFontMetrics(card.name.font())
                    for line in lines:
                        self.assertLessEqual(
                            metrics.horizontalAdvance(line), card.name.width()
                        )
                    self.assertLessEqual(
                        len(lines) * metrics.lineSpacing(), card.name.height()
                    )
                    self.assertEqual(name, card.name.toolTip())
                    card.deleteLater()


if __name__ == "__main__":
    unittest.main()


def _promo_card(host, original, price, promo_name, quantity=1, name="Biscoito Recheado"):
    product = Produtos.from_tuple((
        "p", "1", name, original, price, 1, "promo", promo_name, 10,
        "ALIMENTOS", "UNIDADE", "", "", None, None, "2026-01-01", "2026-01-01", 1,
    ))
    card = ProductCard(Item(product, quantidade=quantity), lambda: None, host)
    card.set_card_width(271)
    card.show()
    QApplication.processEvents()
    return card


class ProductCardLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = QWidget()
        self.host.setStyleSheet(Theme.cart_stylesheet())

    def test_discount_percent_is_rounded_down(self):
        self.assertEqual(50, ProductCard.discount_percent(8.98, 4.49))
        # 33,67% vira 33%: o selo nunca anuncia mais que o desconto real.
        self.assertEqual(33, ProductCard.discount_percent(3.00, 1.99))
        self.assertEqual(49, ProductCard.discount_percent(10.00, 5.04))
        self.assertIsNone(ProductCard.discount_percent(18.90, 18.90))
        self.assertIsNone(ProductCard.discount_percent(0, 5))
        self.assertIsNone(ProductCard.discount_percent(100, 99.9))

    def test_promotion_shows_percent_badge_and_prices_without_prefix(self):
        card = _promo_card(self.host, 8.98, 4.49, "Leve 2 Pague 1", quantity=2)
        self.assertEqual(
            texts.CART_DISCOUNT_BADGE.format(percent=50),
            card.promotion_badge.text(),
        )
        self.assertEqual("R$ 17,96", card.original_price.text())
        self.assertEqual("R$ 8,98", card.price.text())
        self.assertTrue(card.price.property("promotion"))
        self.assertNotIn("De ", card.original_price.text())
        self.assertNotIn("Por ", card.price.text())

    def test_badge_falls_back_to_short_promotion_name_without_overlap(self):
        card = _promo_card(
            self.host, 18.90, 18.90, "Semana do Café Especial do Mercado",
            name="Café Torrado e Moído 500g",
        )
        self.assertTrue(card.promotion_badge.text().endswith("…"))
        badge = card.promotion_badge.geometry()
        self.assertLessEqual(badge.right(), card.width() - ProductCard.PADDING)
        metrics = QFontMetrics(card.name.font())
        first_line = card.name.text().split("\n")[0]
        name_left = card.name.geometry().left()
        self.assertLess(
            name_left + metrics.horizontalAdvance(first_line), badge.left()
        )

    def test_remove_button_keeps_56px_touch_area(self):
        card = _promo_card(self.host, 8.98, 4.49, None)
        remove = card.remove_button
        self.assertEqual((56, 56), (remove.width(), remove.height()))
        self.assertFalse(remove.icon().isNull())
        quantity_center = card.quantity.geometry().center().y()
        self.assertLessEqual(abs(quantity_center - remove.geometry().center().y()), 2)

    def test_unit_price_only_when_quantity_above_one(self):
        single = _promo_card(self.host, 8.98, 4.49, None)
        self.assertTrue(single.unit_price.isHidden())
        triple = _promo_card(self.host, 8.98, 4.49, None, quantity=3)
        self.assertFalse(triple.unit_price.isHidden())
        self.assertEqual(
            texts.CART_UNIT_PRICE.format(quantity=3, price="R$ 4,49"),
            triple.unit_price.text(),
        )

    def test_scan_highlight_fades_out(self):
        card = _promo_card(self.host, 8.98, 4.49, None)
        card.highlight()
        self.assertEqual(QAbstractAnimation.Running, card._highlight_fade.state())
        self.assertEqual(Motion.CARD_HIGHLIGHT, card._highlight_fade.duration())
        card._highlight_fade.setCurrentTime(Motion.CARD_HIGHLIGHT)
        self.assertEqual(0.0, card._highlight)

    def test_price_font_shrinks_only_when_it_does_not_fit(self):
        for value, shrinks in ((4.49, False), (1299.90, False), (12999.90, True), (123456.78, True)):
            with self.subTest(value=value):
                card = _promo_card(self.host, value, value, None)
                size = card.price.font().pixelSize()
                if shrinks:
                    self.assertLess(size, FontSize.PRODUCT_PRICE)
                    self.assertGreaterEqual(size, FontSize.PRODUCT_PRICE_MIN)
                else:
                    self.assertEqual(FontSize.PRODUCT_PRICE, size)
                self.assertLessEqual(
                    card.price.fontMetrics().horizontalAdvance(card.price.text()),
                    card._content_width(),
                )
