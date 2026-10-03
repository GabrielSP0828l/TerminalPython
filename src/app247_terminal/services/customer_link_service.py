"""Fronteira de serviço para o estado local de identificação do cliente."""

from app247_terminal.repositories.customer_link_repository import CustomerLinkStore


class CustomerLinkStateService:
    def __init__(self, repository=None):
        self.repository = repository or CustomerLinkStore()

    def save(self, cart_id):
        self.repository.save(cart_id)

    def load(self):
        return self.repository.load()

    def clear(self):
        self.repository.clear()
