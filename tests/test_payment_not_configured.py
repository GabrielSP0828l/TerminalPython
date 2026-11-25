"""Terminal sem maquininha não pode ficar preso em "Confirmando pagamento".

O backend responde 409 MERCADO_PAGO_NOT_CONFIGURED antes de criar cobrança.
Essa recusa é definitiva: tratá-la como ambígua levava a tela ao loop de
reconciliação e, persistida em active_payment, voltava a cada reinício.
"""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from test_checkout_timeout import CheckoutHost, FakeClock
from test_payment_flow import ParentStub
from test_purchase_api import FakeResponse, FakeSession

from app247_terminal.application import MainWindow
from app247_terminal.models.purchase_session import CompraSession
from app247_terminal.repositories.active_payment_repository import ActivePaymentStore
from app247_terminal.services.purchase_api import PurchaseApi, PurchaseApiError
from app247_terminal.ui import texts
from app247_terminal.ui.screens.payment import PagamentoScreen

NOT_CONFIGURED = {
    "code": "MERCADO_PAGO_NOT_CONFIGURED",
    "message": "Mercado Pago não está configurado para este Terminal.",
}


class NotConfiguredClassificationTest(unittest.TestCase):
    def test_backend_refusal_is_definitive_not_ambiguous(self):
        http = FakeSession([
            FakeResponse({"carrinhoId": "cart-1"}),
            FakeResponse(NOT_CONFIGURED, status_code=409),
        ])
        with patch(
            "app247_terminal.services.terminal_auth.TerminalCredentialStore.load",
            return_value="tdc_test_payment",
        ), self.assertRaises(PurchaseApiError) as raised:
            PurchaseApi("http://backend", http, terminal_id="t-1").start_point(
                {"items": []}
            )

        self.assertEqual("payment_not_configured", raised.exception.stage)
        self.assertFalse(raised.exception.ambiguous)
        self.assertEqual("cart-1", raised.exception.context["requestedCartId"])


class NotConfiguredPaymentScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = ParentStub()
        self.parent.marcar_pagamento_indisponivel = MagicMock()
        self.screen = PagamentoScreen(self.parent)
        session = self.parent.compra_session
        session.reset()
        session.start_if_needed()
        payload = {"terminalId": "terminal-a", "items": [{"productId": "p1"}]}
        with patch("app247_terminal.ui.screens.payment.PointCheckoutWorker"):
            self.assertTrue(self.screen.iniciar_pagamento(payload, "R$ 1,00"))
        self.screen.point_worker = None
        self.attempt = self.screen.current_attempt
        self.screen._cart_created(self.attempt, {"cartId": "cart-1"})

    def tearDown(self):
        self.screen.parar_workers()
        self.parent.compra_session.reset()

    def test_refusal_shows_unavailable_and_releases_payment(self):
        # Mesmo marcado como ambíguo, o estágio definitivo não entra na reconciliação.
        self.screen._point_failed(
            self.attempt, "Pagamento indisponível neste Terminal.",
            "payment_not_configured", True, {"requestedCartId": "cart-1"},
        )

        session = self.parent.compra_session
        self.assertFalse(session.payment_in_flight)
        self.assertFalse(self.screen.poll_timer.isActive())
        self.assertIn(texts.PAYMENT_UNAVAILABLE, self.screen.loading.text())
        self.assertNotEqual(texts.PAYMENT_CONFIRMING_TITLE, self.screen.title.text())
        self.assertTrue(self.screen.btn_voltar.isEnabled())
        self.assertEqual("cart-1", session.cart_id)
        self.parent.marcar_pagamento_indisponivel.assert_called_once_with(
            "PAYMENT_START_REFUSED"
        )

    def test_other_ambiguous_failure_still_reconciles(self):
        with patch.object(self.screen, "_retomar_inicio_point"):
            self.screen._point_failed(
                self.attempt, "Falha de rede", "payment", True,
                {"requestedCartId": "cart-1"},
            )

        self.assertTrue(self.parent.compra_session.payment_in_flight)
        self.assertTrue(self.screen.poll_timer.isActive())
        self.parent.marcar_pagamento_indisponivel.assert_not_called()


class NotConfiguredResumeTest(unittest.TestCase):
    """Cenário do campo: a tentativa presa é retomada pelo POST do mesmo carrinho."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ActivePaymentStore(Path(self.tmp.name) / "terminal.db")
        self.parent = ParentStub()
        self.parent.compra_session = CompraSession(
            self.parent, payment_store=self.store,
            terminal_id_provider=lambda: "terminal-a",
        )
        self.parent.marcar_pagamento_indisponivel = MagicMock()
        self.screen = PagamentoScreen(self.parent)

    def tearDown(self):
        self.screen.parar_workers()
        self.parent.compra_session.reset()
        self.tmp.cleanup()

    def _start(self, restored):
        session = self.parent.compra_session
        session.reset()
        if not restored:
            session.start_if_needed()
        with patch("app247_terminal.ui.screens.payment.PointCheckoutWorker"):
            self.screen.iniciar_pagamento({"items": []}, "R$ 1,00")
        self.screen.point_worker = None
        attempt = self.screen.current_attempt
        self.screen._cart_created(attempt, {"cartId": "cart-1"})
        if restored:
            # Depois do reinício a sessão não tem itens nem início local.
            session.started_at = None
        self.screen.poll_timer.start(self.screen.POLL_INTERVAL_MS)
        self.assertTrue(self.store.has_unresolved_payment())
        return attempt

    def _refuse(self, attempt):
        self.screen._resume_failed(
            attempt, "cart-1", "Pagamento indisponível neste Terminal.",
            {**NOT_CONFIGURED, "requestedCartId": "cart-1",
             "stage": "payment_not_configured"},
        )

    def test_resume_refusal_stops_reconciliation_loop(self):
        attempt = self._start(restored=False)
        self._refuse(attempt)

        self.assertFalse(self.parent.compra_session.payment_in_flight)
        self.assertFalse(self.screen.poll_timer.isActive())
        self.assertIn(texts.PAYMENT_UNAVAILABLE, self.screen.loading.text())
        self.assertEqual(0, self.parent.reset_calls)
        self.parent.marcar_pagamento_indisponivel.assert_called_once_with(
            "PAYMENT_RESUME_REFUSED"
        )

    def test_attempt_restored_after_reboot_returns_to_welcome(self):
        attempt = self._start(restored=True)
        self._refuse(attempt)

        self.assertFalse(self.parent.compra_session.payment_in_flight)
        self.assertFalse(self.screen.poll_timer.isActive())
        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)
        # Sem isso o próximo reinício voltaria para a mesma tela presa.
        self.assertFalse(self.store.has_unresolved_payment())

    def test_resume_worker_reports_stage_to_screen(self):
        from app247_terminal.services.purchase_api import PointResumeWorker

        api = MagicMock()
        api.resume_point.side_effect = PurchaseApiError(
            "Pagamento indisponível neste Terminal.", "payment_not_configured",
            False, dict(NOT_CONFIGURED),
        )
        worker = PointResumeWorker("cart-1", "t-1", api_factory=lambda: api)
        received = []
        worker.failed.connect(lambda message, context: received.append(context))
        worker.run()

        self.assertEqual("payment_not_configured", received[0]["stage"])
        self.assertEqual("MERCADO_PAGO_NOT_CONFIGURED", received[0]["code"])


class FakeSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        for slot in self.slots:
            slot(*args)


class FakeWorker:
    """Worker que responde na hora, no lugar da QThread com HTTP."""

    outcome = None

    def __init__(self, *args, **kwargs):
        self.succeeded = FakeSignal()
        self.failed = FakeSignal()
        self.finished = FakeSignal()

    def isRunning(self):
        return False

    def start(self):
        signal, args = type(self).outcome
        getattr(self, signal).emit(*args)


class NoActivePayment(FakeWorker):
    outcome = ("succeeded", (None,))


class ResumeRefused(FakeWorker):
    outcome = ("failed", (
        "Pagamento indisponível neste Terminal.",
        {**NOT_CONFIGURED, "requestedCartId": "cart-1",
         "stage": "payment_not_configured"},
    ))


class StuckTerminalAfterUpgradeTest(unittest.TestCase):
    """Cadeia completa do campo: tentativa salva → startup → descoberta → retomada."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ActivePaymentStore(Path(self.tmp.name) / "terminal.db")
        old = CompraSession(
            payment_store=self.store, terminal_id_provider=lambda: "terminal-a"
        )
        old.start_if_needed()
        old.begin_payment()
        old.persist_cart_checkpoint(old.attempt_id, "cart-1")
        self.assertTrue(self.store.has_unresolved_payment())

        self.parent = ParentStub()
        self.parent.stacked_widget = MagicMock()
        self.parent.marcar_pagamento_indisponivel = MagicMock()
        self.parent.compra_session = CompraSession(
            self.parent, payment_store=self.store,
            terminal_id_provider=lambda: "terminal-a",
        )
        self.screen = PagamentoScreen(self.parent)

    def tearDown(self):
        # Os fakes já responderam; não há QThread para parar.
        self.screen.active_recovery_worker = None
        self.screen.resume_worker = None
        self.screen.parar_workers()
        self.tmp.cleanup()

    def test_upgraded_terminal_releases_stuck_attempt_by_itself(self):
        session = self.parent.compra_session
        self.assertTrue(session.restore_pending_payment("terminal-a"))
        self.assertEqual("cart-1", session.cart_id)

        terminal = SimpleNamespace(terminalId="terminal-a", uuidTerminal="terminal-a")
        with patch("app247_terminal.ui.screens.payment.ActivePaymentRecoveryWorker",
                   NoActivePayment), \
             patch("app247_terminal.ui.screens.payment.PointResumeWorker",
                   ResumeRefused), \
             patch("app247_terminal.ui.screens.payment.Terminal.load",
                   return_value=terminal), \
             patch.object(self.screen, "_track_worker"):
            self.screen.current_attempt = session.attempt_id
            self.screen.mostrar_reconciliacao_pendente(origin="APPLICATION_STARTUP")

        self.assertFalse(session.payment_in_flight)
        self.assertFalse(self.screen.poll_timer.isActive())
        self.assertFalse(self.store.has_unresolved_payment())
        self.assertIs(self.parent.welcome, self.parent.current)
        self.parent.marcar_pagamento_indisponivel.assert_called_once_with(
            "PAYMENT_RESUME_REFUSED"
        )


class NotConfiguredCheckoutGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = CheckoutHost(FakeClock())
        self.host._check_terminal_lifecycle = MagicMock()
        self.host.setCurrentWidget(self.host.terminal)
        self.terminal = self.host.terminal
        self.terminal.codigo_barras.setText("789")
        self.terminal.readProduct()
        self.host.setCurrentWidget(self.host.confirmacao_compra)

    def tearDown(self):
        self.host.close_test_host()

    def test_unconfigured_terminal_never_creates_cart_or_charge(self):
        self.host.payment_configured = False
        with patch.object(self.terminal, "mostrar_aviso") as warning:
            self.assertFalse(self.terminal.iniciar_pagamento_confirmado())

        self.host.pagamento.iniciar_pagamento.assert_not_called()
        warning.assert_called_once_with(
            texts.PAYMENT_UNAVAILABLE_TITLE, texts.PAYMENT_UNAVAILABLE
        )
        self.host._check_terminal_lifecycle.assert_called_once_with("CHECKOUT_BLOCKED")

    def test_unknown_state_keeps_selling_and_backend_decides(self):
        self.host.payment_configured = None
        with patch.object(self.terminal, "mostrar_aviso"):
            self.terminal.iniciar_pagamento_confirmado()

        self.host.pagamento.iniciar_pagamento.assert_called_once()


class LifecyclePaymentStateTest(unittest.TestCase):
    def _window(self):
        return SimpleNamespace(
            payment_configured=None, _restore_device_access=MagicMock(),
            _check_terminal_lifecycle=MagicMock(),
        )

    def test_bootstrap_state_drives_payment_availability(self):
        window = self._window()
        MainWindow._handle_lifecycle_response(
            window, {"state": "PAYMENT_NOT_CONFIGURED"}, "APPLICATION_STARTUP"
        )
        self.assertIs(False, window.payment_configured)
        window._restore_device_access.assert_called_once()

        MainWindow._handle_lifecycle_response(
            window, {"state": "ACTIVE"}, "PERIODIC_BOOTSTRAP"
        )
        self.assertIs(True, window.payment_configured)

    def test_invalid_response_keeps_previous_state(self):
        window = self._window()
        window.payment_configured = False
        MainWindow._handle_lifecycle_response(window, None, "PERIODIC_BOOTSTRAP")
        self.assertIs(False, window.payment_configured)

    def test_refusal_marks_unavailable_and_rechecks_backend(self):
        window = self._window()
        window.payment_configured = True
        MainWindow.marcar_pagamento_indisponivel(window, "PAYMENT_START_REFUSED")
        self.assertIs(False, window.payment_configured)
        window._check_terminal_lifecycle.assert_called_once_with("PAYMENT_START_REFUSED")


if __name__ == "__main__":
    unittest.main()
