from model.Item import Item
from model.Terminal import Terminal
from decimal import Decimal
from model.Money import format_brl


class Carrinho:

    def __init__(self):
        terminal = Terminal.load()

        self.terminal_id = terminal.uuidTerminal

        self.items = []

    def adicionar_item(self, item: Item):

        for i in self.items:

            if i.produto.id == item.produto.id:
                i.quantidade += item.quantidade

                return

        self.items.append(item)

    # remover item pelo código
    def remover_item(self, codigo_produto):

        self.items = [
            item for item in self.items
            if item.produto.codigo != codigo_produto and item.produto.id != codigo_produto
        ]

    # limpar carrinho
    def limpar(self):

        self.items.clear()

    # quantidade total de itens
    def quantidade_total_itens(self):

        return sum(item.quantidade for item in self.items)

    # total do carrinho
    def total(self):

        return sum((
            item.produto.preco * item.quantidade
            for item in self.items
        ), Decimal("0"))

    # busca item
    def buscar_item(self, codigo_produto):

        for item in self.items:

            if item.produto.codigo == codigo_produto or item.produto.id == codigo_produto:
                return item

        return None

    # verifica se carrinho está vazio
    def vazio(self):

        return len(self.items) == 0

    # listar itens
    def listar_itens(self):

        return self.items

    # remover uma unidade
    def remover_quantidade_item(self, codigo_produto, quantidade=1):

        for item in self.items:

            if item.produto.codigo == codigo_produto:

                item.quantidade -= quantidade

                if item.quantidade <= 0:
                    self.remover_item(codigo_produto)

                return

    # total formatado
    def total_formatado(self):

        return format_brl(self.total())

    def to_dict(self):

        return {

            "terminalId": self.terminal_id,

            "items": [

                {
                    "productId": item.produto.id,

                    "quantity": str(item.quantidade),

                    "receivedWeight": (
                        str(item.received_weight) if item.received_weight is not None else None
                    ),

                    "expectedUnitPrice": str(item.produto.preco),

                    "codigoBarras": item.produto.codigo
                }

                for item in self.items

            ]

        }

    def __str__(self):

        texto = "\n=== CARRINHO ===\n"

        for item in self.items:
            subtotal = item.produto.preco * item.quantidade

            texto += (
                f"{item.produto.nome} "
                f"x{item.quantidade} "
                f"- R$ {subtotal:.2f}\n"
            )

        texto += f"\nTOTAL: {self.total_formatado()}"

        return texto
