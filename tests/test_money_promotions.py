import unittest
from decimal import Decimal

from app247_terminal.models.cart import Carrinho
from app247_terminal.models.item import Item
from app247_terminal.models.money import charged, format_brl, persisted
from app247_terminal.models.product import Produtos


class MoneyAndPromotionsTest(unittest.TestCase):
    def test_financial_precision_is_kept_until_final_charge(self):
        values = [Decimal("10.165750"), Decimal("7.347625"), Decimal("5.127500")]

        precise_total = sum(values, Decimal("0"))

        self.assertEqual(Decimal("22.640875"), precise_total)
        self.assertEqual(Decimal("22.64"), charged(precise_total))
        self.assertNotEqual(Decimal("22.65"), charged(precise_total))

    def test_product_preserves_backend_promotional_price(self):
        product = Produtos(
            id="p-1", codigo="789", nome="Refrigerante", quantidade=1,
            preco="10.165750", preco_original="10.990000",
            em_promocao=True, promocao_id="promo-1",
            promocao_nome="Semana do Refrigerante", categoria="BEBIDA",
        )

        self.assertEqual(Decimal("10.990000"), product.preco_original)
        self.assertEqual(Decimal("10.165750"), product.preco)
        self.assertEqual("R$ 10,17", format_brl(product.preco))

    def test_format_brl_uses_thousands_separator(self):
        self.assertEqual("R$ 0,00", format_brl(0))
        self.assertEqual("R$ 999,99", format_brl("999.99"))
        self.assertEqual("R$ 1.299,90", format_brl("1299.9"))
        self.assertEqual("R$ 123.456,78", format_brl("123456.78"))
        self.assertEqual("R$ 1.234.567,89", format_brl("1234567.891"))

    def test_cart_sends_exact_expected_price_without_local_recalculation(self):
        product = Produtos(
            id="p-1", codigo="789", nome="Refrigerante", quantidade=1,
            preco="10.165750", preco_original="10.990000",
            em_promocao=True, categoria="BEBIDA",
        )
        cart = Carrinho(terminal_id="terminal-test")
        cart.adicionar_item(Item(product))

        payload = cart.to_dict()

        self.assertEqual("10.165750", payload["items"][0]["expectedUnitPrice"])
        self.assertEqual(Decimal("10.165750"), persisted(cart.total()))

    def test_cart_total_matches_line_subtotal_for_weighted_item(self):
        product = Produtos(
            id="p-2", codigo="790", nome="Banana", quantidade=1,
            preco="8.000000", categoria="HORTIFRUTI",
        )
        item = Item(product, quantidade=1, received_weight="0.750")
        cart = Carrinho(terminal_id="terminal-test")
        cart.adicionar_item(item)

        self.assertEqual(item.subtotal(), cart.total())
        self.assertEqual(Decimal("6.000000"), persisted(cart.total()))


if __name__ == "__main__":
    unittest.main()
