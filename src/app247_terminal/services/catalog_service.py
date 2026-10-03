"""Caso de uso de leitura do catálogo usado pela interface de venda."""

from app247_terminal.repositories.product_repository import DatabaseProdutos


class CatalogService:
    def __init__(self, repository=None):
        self.repository = repository or DatabaseProdutos()

    def find_by_barcode(self, barcode):
        return self.repository.buscar_por_codigo(barcode)

    # Compatibilidade temporária com a interface interna da tela e seus testes.
    def buscar_por_codigo(self, barcode):
        return self.find_by_barcode(barcode)
