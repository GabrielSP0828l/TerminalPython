from model.Money import decimal_value


class Item:

    def __init__(

        self,
        produto,
        quantidade=1,
        received_weight=None

    ):

        self.produto = produto

        self.quantidade = quantidade

        self.received_weight = received_weight

    def subtotal(self):

        if self.received_weight:

            return (
                self.produto.preco *
                decimal_value(self.received_weight)
            )

        return (
            self.produto.preco *
            self.quantidade
        )

    def __str__(self):

        return (
            f"{self.produto.nome} "
            f"x{self.quantidade} "
            f"= R$ {self.subtotal():.2f}"
        )
