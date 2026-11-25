"""O cliente vinculado pertence a uma única compra e nunca passa para a seguinte."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from test_checkout_timeout import CheckoutHost, FakeClock

from app247_terminal.application import MainWindow
from app247_terminal.ui.screens.payment import PagamentoScreen as PaymentScreen


from app247_terminal.ui import texts

PROMPT = texts.CART_CUSTOMER_PROMPT


class CustomerUnlinkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = FakeClock()
        self.host = CheckoutHost(self.clock)
        self.host.setCurrentWidget(self.host.terminal)
        self.terminal = self.host.terminal
        self.session = self.host.compra_session

    def tearDown(self):
        self.host.close_test_host()

    def _scan_product(self):
        self.terminal.codigo_barras.setText("789")
        self.terminal.readProduct()

    def _link(self, name="Maria", cart_id="cart-1"):
        self.session.start_if_needed()
        self.terminal.customer_link_generation = self.session.generation
        self.terminal._customer_linked({"cartId": cart_id, "displayName": name})

    def _assert_unlinked(self):
        self.assertIsNone(self.terminal.customer_display_name)
        self.assertIsNone(self.session.cart_id)
        self.assertEqual(PROMPT, self.terminal.customer_status.text())

    def _fail_charge(self, payload):
        self.session.cart_id = "cart-1"
        self.session.lock_cart_after_failure(payload)

    def _start_charge(self):
        self.host.setCurrentWidget(self.host.confirmacao_compra)
        self.host.pagamento = MagicMock()
        self.terminal.iniciar_pagamento_confirmado()
        return self.host.pagamento.iniciar_pagamento

    def test_retry_with_same_items_keeps_the_customer(self):
        self._scan_product()
        self._link()
        self._fail_charge(self.terminal.carrinho.to_dict())

        with patch.object(self.terminal, "mostrar_aviso") as warning:
            charge = self._start_charge()

        warning.assert_not_called()
        charge.assert_called_once()
        self.assertEqual("Maria", self.terminal.customer_display_name)

    def test_retry_with_changed_items_warns_and_unlinks(self):
        self._scan_product()
        self._link()
        self._fail_charge({"terminalId": "terminal-1", "items": []})

        with patch.object(self.terminal, "mostrar_aviso") as warning:
            charge = self._start_charge()

        warning.assert_called_once()
        self.assertEqual("Cliente desvinculado", warning.call_args.args[0])
        charge.assert_called_once()
        self.assertIsNone(self.terminal.customer_display_name)

    def test_link_is_shown_during_the_purchase(self):
        self._link()
        self.assertEqual("Maria", self.terminal.customer_display_name)
        self.assertEqual("cart-1", self.session.cart_id)
        self.assertIn("Maria", self.terminal.customer_status.text())

    def test_finalized_purchase_unlinks(self):
        self._link()
        self.host.reset_compra(outcome="finalized")
        self._assert_unlinked()

    def test_cancelled_purchase_unlinks(self):
        self._link()
        self.host.reset_compra(outcome="cancelled")
        self._assert_unlinked()

    def test_expired_session_unlinks(self):
        self._link()
        self.host.complete_checkout_expiration(self.session.generation)
        self._assert_unlinked()

    def test_removing_last_item_unlinks(self):
        self._scan_product()
        self._link()
        codigo = next(iter(self.terminal.linhas))
        with patch.object(self.terminal, "mostrar_aviso") as warning:
            self.terminal.remover_produto(codigo, MagicMock())
        self._assert_unlinked()
        warning.assert_called_once()
        self.assertEqual("Cliente desvinculado", warning.call_args.args[0])
        self.assertIn("novo QR", warning.call_args.args[1])

    def test_removing_last_item_warns_while_link_is_in_progress(self):
        self._scan_product()
        self.terminal.customer_link_worker = MagicMock()
        codigo = next(iter(self.terminal.linhas))
        with patch.object(self.terminal, "mostrar_aviso") as warning:
            self.terminal.remover_produto(codigo, MagicMock())
        self.terminal.customer_link_worker = None
        warning.assert_called_once()

    def test_removing_last_item_without_customer_shows_no_warning(self):
        self._scan_product()
        codigo = next(iter(self.terminal.linhas))
        with patch.object(self.terminal, "mostrar_aviso") as warning:
            self.terminal.remover_produto(codigo, MagicMock())
        warning.assert_not_called()

    def test_removing_one_of_two_items_keeps_customer_without_warning(self):
        self._scan_product()
        self._link()
        with patch.object(self.terminal.carrinho, "vazio", return_value=False), \
                patch.object(self.terminal, "mostrar_aviso") as warning:
            codigo = next(iter(self.terminal.linhas))
            self.terminal.remover_produto(codigo, MagicMock())
        warning.assert_not_called()
        self.assertEqual("Maria", self.terminal.customer_display_name)

    def test_rejected_payment_keeps_customer_for_retry(self):
        self._link()
        self.session.prepare_retry()
        self.assertEqual("Maria", self.terminal.customer_display_name)
        self.assertEqual("cart-1", self.session.cart_id)

    def test_link_response_after_cancel_is_discarded(self):
        self._link("Anterior")
        self.host.reset_compra(outcome="cancelled")
        self.session.start_if_needed()
        self.terminal._customer_linked({"cartId": "cart-old", "displayName": "Anterior"})
        self.assertIsNone(self.terminal.customer_display_name)
        self.assertIsNone(self.session.cart_id)

    def test_link_response_from_previous_generation_is_discarded(self):
        self.session.start_if_needed()
        self.terminal.customer_link_generation = self.session.generation
        self.host.reset_compra(outcome="cancelled")
        self.session.start_if_needed()
        self.terminal._customer_linked({"cartId": "cart-old", "displayName": "Anterior"})
        self._assert_unlinked()

    def test_link_failure_after_cancel_shows_no_warning(self):
        self.session.start_if_needed()
        self.terminal.customer_link_generation = self.session.generation
        self.host.reset_compra(outcome="cancelled")
        with patch.object(self.terminal, "mostrar_aviso") as warning:
            self.terminal._customer_link_failed("CUSTOMER_LINK_FAILED", "x")
        warning.assert_not_called()

    def test_link_response_during_payment_does_not_replace_cart(self):
        self.session.start_if_needed()
        self.terminal.customer_link_generation = self.session.generation
        self.session.set_remote_ids(cart_id="cart-payment")
        self.session.payment_in_flight = True
        self.terminal._customer_linked({"cartId": "cart-other", "displayName": "Anterior"})
        self.assertEqual("cart-payment", self.session.cart_id)
        self.assertIsNone(self.terminal.customer_display_name)
        self.session.payment_in_flight = False

    def test_startup_discards_persisted_link(self):
        self.terminal.customer_link_store.repository.save("cart-antigo")
        other = CheckoutHost(FakeClock())
        try:
            self.assertIsNone(other.terminal.customer_link_store.load())
            self.assertIsNone(other.terminal.customer_display_name)
            self.assertIsNone(other.compra_session.cart_id)
        finally:
            other.close_test_host()

    def test_retry_screen_without_session_ends_recovered_purchase(self):
        parent = MagicMock()
        parent.compra_session.payment_in_flight = False
        parent.compra_session.started_at = None
        screen = SimpleNamespace(parent=parent, failure_return_timer=MagicMock())
        PaymentScreen._voltar_lista(screen)
        parent.reset_compra.assert_called_once_with(outcome="cancelled")
        parent.setCurrentWidget.assert_called_once_with(parent.welcome)

    def test_retry_screen_with_session_returns_to_list(self):
        parent = MagicMock()
        parent.compra_session.payment_in_flight = False
        parent.compra_session.started_at = 1.0
        screen = SimpleNamespace(parent=parent, failure_return_timer=MagicMock())
        PaymentScreen._voltar_lista(screen)
        parent.reset_compra.assert_not_called()
        parent.setCurrentWidget.assert_called_once_with(parent.terminal)

    def test_identity_recovery_clears_session(self):
        window = MagicMock()
        MainWindow._complete_identity_recovery(window, "FAILED")
        window.compra_session.reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
