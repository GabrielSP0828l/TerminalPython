import unittest
from decimal import Decimal

from model.Carrinho import Carrinho
from model.Item import Item
from model.Money import charged, format_brl, persisted
from model.Produtos import Produtos


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

    def test_cart_sends_exact_expected_price_without_local_recalculation(self):
        product = Produtos(
            id="p-1", codigo="789", nome="Refrigerante", quantidade=1,
            preco="10.165750", preco_original="10.990000",
            em_promocao=True, categoria="BEBIDA",
        )
        cart = Carrinho()
        cart.adicionar_item(Item(product))

        payload = cart.to_dict()

        self.assertEqual("10.165750", payload["items"][0]["expectedUnitPrice"])
        self.assertEqual(Decimal("10.165750"), persisted(cart.total()))


if __name__ == "__main__":
    unittest.main()
