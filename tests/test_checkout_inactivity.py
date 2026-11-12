import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from test_checkout_timeout import CheckoutHost, FakeClock

from app247_terminal.application import MainWindow
from app247_terminal.models import purchase_session
from app247_terminal.ui import texts
from app247_terminal.ui.inactivity import InactivityMonitor
from app247_terminal.ui.responsive import layout_profile
from app247_terminal.ui.screens.app_payment import AppPaymentScreen
from app247_terminal.ui.screens.confirmation import ConfirmacaoScreen
from app247_terminal.ui.screens.session_timer import SessionTimerLabel


IDLE = purchase_session.INACTIVITY_PROMPT_AFTER_SECONDS
COUNTDOWN = purchase_session.INACTIVITY_COUNTDOWN_SECONDS


class InactivityHost(CheckoutHost):
    """Host real do controlador com o teto de produção e o monitor de inatividade."""

    encerrar_compra_por_inatividade = MainWindow.encerrar_compra_por_inatividade

    def __init__(self, clock):
        super().__init__(clock)
        self.compra_session.duration_seconds = purchase_session.SESSION_LIMIT_SECONDS
        QVBoxLayout(self).addWidget(self.stacked_widget)
        self.inactivity_monitor = InactivityMonitor(
            self.stacked_widget, (self.terminal, self.confirmacao_compra), self,
            clock=clock,
        )
        self.inactivity_monitor.expired.connect(self.encerrar_compra_por_inatividade)

    def close_test_host(self):
        self.inactivity_monitor.stop()
        super().close_test_host()


class CheckoutInactivityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = FakeClock()
        self.host = InactivityHost(self.clock)
        self.host.resize(600, 1024)
        self.host.show()
        self.host.setCurrentWidget(self.host.terminal)
        self.monitor = self.host.inactivity_monitor

    def tearDown(self):
        self.host.close_test_host()
        self.host.close()
        layout_profile.force(None)

    def _scan_product(self):
        """Leitor USB: digita o código e envia Enter no campo do scanner."""
        field = self.host.terminal.codigo_barras
        field.setFocus()
        QTest.keyClicks(field, "789")
        QTest.keyClick(field, Qt.Key_Return)

    def _advance(self, seconds):
        self.clock.value += seconds
        self.monitor._tick()

    def _prompt(self, screen=None):
        return (screen or self.host.terminal).inactivity_prompt

    def test_prompt_appears_after_idle_time_with_countdown(self):
        self._scan_product()

        self._advance(IDLE - 1)
        self.assertTrue(self._prompt().isHidden())

        self._advance(1)
        self.assertFalse(self._prompt().isHidden())
        self.assertEqual(texts.INACTIVITY_TITLE, self._prompt().title.text())
        self.assertEqual(
            texts.INACTIVITY_COUNTDOWN.format(seconds=COUNTDOWN),
            self._prompt().countdown.text(),
        )
        self.assertEqual(texts.INACTIVITY_CONTINUE, self._prompt().continue_button.text())

    def test_touch_resets_countdown(self):
        self._scan_product()
        self._advance(IDLE + 5)
        self.assertFalse(self._prompt().isHidden())

        QTest.mouseClick(self._prompt(), Qt.LeftButton, pos=QPoint(5, 5))

        self.assertTrue(self._prompt().isHidden())
        self._advance(IDLE - 1)
        self.assertTrue(self._prompt().isHidden())
        self._advance(COUNTDOWN - 1)
        self.assertFalse(self._prompt().isHidden())
        self.assertEqual(0, self.host.reset_calls)
        self.assertFalse(self.host.terminal.carrinho.vazio())

    def test_continue_button_resets_countdown(self):
        self._scan_product()
        self._advance(IDLE + 10)

        self._prompt().continue_button.click()

        self.assertTrue(self._prompt().isHidden())
        self._advance(IDLE + COUNTDOWN - 1)
        self.assertIs(self.host.terminal, self.host.stacked_widget.currentWidget())
        self.assertEqual(0, self.host.reset_calls)

    def test_scanner_read_resets_countdown(self):
        self._scan_product()
        self._advance(IDLE + 15)
        self.assertFalse(self._prompt().isHidden())

        self._scan_product()

        self.assertTrue(self._prompt().isHidden())
        self.assertEqual(2, self.host.terminal.carrinho.quantidade_total_itens())
        self._advance(IDLE + COUNTDOWN - 1)
        self.assertEqual(0, self.host.reset_calls)

    def test_scanner_read_counts_even_without_key_events(self):
        self._scan_product()
        self._advance(IDLE + 15)

        self.host.terminal.codigo_barras.setText("789")
        self.host.terminal.readProduct()

        self.assertTrue(self._prompt().isHidden())
        self._advance(IDLE - 1)
        self.assertTrue(self._prompt().isHidden())

    def test_cancels_purchase_after_unanswered_prompt(self):
        self._scan_product()
        self._advance(IDLE)
        self.assertFalse(self._prompt().isHidden())

        self._advance(COUNTDOWN)

        self.assertEqual(1, self.host.reset_calls)
        self.assertIs(self.host.welcome, self.host.stacked_widget.currentWidget())
        self.assertTrue(self.host.terminal.carrinho.vazio())
        self.assertTrue(self._prompt().isHidden())
        self.assertEqual("IDLE", self.host.compra_session.state)
        self.host.pagamento.tratar_timeout_global.assert_not_called()

    def test_cancels_from_purchase_confirmation(self):
        self._scan_product()
        self.host.terminal.ir_para_pagamento()
        confirmation = self.host.confirmacao_compra
        self.assertIs(confirmation, self.host.stacked_widget.currentWidget())

        self._advance(IDLE)
        self.assertFalse(self._prompt(confirmation).isHidden())
        self._advance(COUNTDOWN)

        self.assertEqual(1, self.host.reset_calls)
        self.assertIs(self.host.welcome, self.host.stacked_widget.currentWidget())
        self.assertTrue(self.host.terminal.carrinho.vazio())

    def test_navigation_between_purchase_screens_restarts_count(self):
        self._scan_product()
        self._advance(IDLE - 10)
        self.host.terminal.ir_para_pagamento()

        self._advance(IDLE - 1)

        self.assertTrue(self._prompt(self.host.confirmacao_compra).isHidden())
        self.assertEqual(0, self.host.reset_calls)

    def test_empty_list_returns_to_welcome(self):
        self._advance(IDLE + COUNTDOWN)

        self.assertIs(self.host.welcome, self.host.stacked_widget.currentWidget())
        self.assertFalse(self.monitor.armed)

    def test_other_screens_are_not_monitored(self):
        self._scan_product()
        self.host.setCurrentWidget(self.host.welcome)

        self._advance(IDLE + COUNTDOWN + 5)

        self.assertFalse(self.monitor.armed)
        self.assertEqual(0, self.host.reset_calls)

    def test_never_cancels_with_payment_in_flight(self):
        self._scan_product()
        self.host.terminal.ir_para_pagamento()
        session = self.host.compra_session
        generation = session.generation
        session.payment_in_flight = True
        session.set_remote_ids(cart_id="cart-1", order_id="order-1")

        self._advance(IDLE)
        self._advance(COUNTDOWN)

        # Mesmo caminho do teto: o pagamento confere a cobrança antes de liberar.
        self.host.pagamento.tratar_timeout_global.assert_called_once_with(generation)
        self.assertEqual(0, self.host.reset_calls)
        self.assertFalse(self.host.terminal.carrinho.vazio())
        self.assertEqual("TIMEOUT_CHECK", session.state)
        self.assertTrue(session.payment_in_flight)
        self.assertEqual("order-1", session.order_id)

    def test_restored_payment_without_session_is_not_reset(self):
        session = self.host.compra_session
        session.payment_in_flight = True
        session.order_id = "order-1"

        self.host.encerrar_compra_por_inatividade()

        self.host.pagamento.mostrar_reconciliacao_pendente.assert_called_once_with(
            origin="INACTIVITY"
        )
        self.assertEqual(0, self.host.reset_calls)

    def test_inactivity_after_ceiling_expiry_is_ignored(self):
        self._scan_product()
        session = self.host.compra_session
        self.assertTrue(session.expire_for_inactivity())

        self.assertFalse(session.expire_for_inactivity())
        self.assertEqual(1, self.host.reset_calls)

    def _new_purchase(self, size, compact):
        layout_profile.force(compact)
        self.host.resize(*size)
        self.host.setCurrentWidget(self.host.welcome)
        self.host.reset_compra()
        self.host.setCurrentWidget(self.host.terminal)
        self._scan_product()

    def _assert_prompt_layout(self, screen, protected):
        session = self.host.compra_session
        # O aviso surge nos últimos 60 s do teto: relógio e aviso juntos.
        self.clock.value = session.started_at + session.duration_seconds - 50 - IDLE
        self.monitor.register_activity()
        self._advance(IDLE)
        session._tick()
        QApplication.processEvents()

        prompt = self._prompt(screen)
        self.assertFalse(prompt.isHidden())
        self.assertTrue(screen.session_timer.isVisible())
        timer = screen.session_timer
        # Relógio inteiro: "00:40  Sessão prestes a encerrar" sem corte.
        self.assertLessEqual(
            timer.fontMetrics().horizontalAdvance(timer.text()),
            timer.contentsRect().width(),
        )
        timer_rect = QRect(timer.mapTo(screen, QPoint(0, 0)), timer.size())
        self.assertTrue(screen.rect().contains(timer_rect))
        prompt_rect = prompt.geometry()
        for widget in (screen.session_timer, *protected):
            with self.subTest(widget=widget.text()):
                self.assertTrue(widget.isVisible())
                rect = QRect(widget.mapTo(screen, QPoint(0, 0)), widget.size())
                self.assertFalse(prompt_rect.intersects(rect))
        card = prompt.card.geometry()
        self.assertTrue(prompt.rect().contains(card))
        self.assertGreaterEqual(card.height(), prompt.card.minimumSizeHint().height())
        self.assertGreaterEqual(prompt.continue_button.height(), 72)
        for label in (prompt.title, prompt.countdown):
            with self.subTest(label=label.text()):
                # Texto inteiro visível: sem corte de palavra nem de linha.
                metrics = label.fontMetrics()
                needed = metrics.boundingRect(
                    QRect(0, 0, label.width(), 10000),
                    Qt.TextWordWrap if label.wordWrap() else 0, label.text(),
                )
                self.assertLessEqual(needed.width(), label.width())
                self.assertLessEqual(needed.height(), label.height())
        self.assertTrue(card.contains(prompt.continue_button.geometry().translated(
            card.topLeft()
        )))

    def test_prompt_never_covers_session_timer_or_actions(self):
        for compact, size in ((True, (600, 1024)), (False, (1024, 600))):
            with self.subTest(compact=compact, screen="lista"):
                self._new_purchase(size, compact)
                terminal = self.host.terminal
                self._assert_prompt_layout(
                    terminal, (terminal.btn_finalizar, terminal.btn_cancelar)
                )
            with self.subTest(compact=compact, screen="confirmação"):
                self._new_purchase(size, compact)
                self.host.terminal.ir_para_pagamento()
                confirmation = self.host.confirmacao_compra
                self._assert_prompt_layout(
                    confirmation, (confirmation.btn_confirmar, confirmation.btn_voltar)
                )


class PurchaseTimesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_times_come_from_single_place(self):
        self.assertEqual(45, ConfirmacaoScreen.POST_PURCHASE_TIMEOUT_SECONDS)
        self.assertEqual(
            purchase_session.POST_PURCHASE_TIMEOUT_SECONDS,
            ConfirmacaoScreen.POST_PURCHASE_TIMEOUT_SECONDS,
        )
        self.assertEqual(600, purchase_session.CompraSession.SESSION_LIMIT_SECONDS)
        self.assertEqual(
            purchase_session.SESSION_WARNING_SECONDS, SessionTimerLabel.WARNING_SECONDS
        )
        self.assertEqual(300, AppPaymentScreen.SCREEN_TIMEOUT_SECONDS)
        self.assertEqual((90, 20), (IDLE, COUNTDOWN))


class AppPaymentTimeoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = FakeClock()
        self.parent = QWidget()
        self.parent.compra_session = purchase_session.CompraSession(
            self.parent, clock=self.clock
        )
        self.parent.terminal = MagicMock()
        self.parent.terminal.carrinho.to_dict.return_value = {"items": []}
        self.parent.encerrar_compra_por_inatividade = MagicMock()
        self.parent.setCurrentWidget = MagicMock()
        self.parent.compra_session.start_if_needed()
        self.worker = patch("app247_terminal.ui.screens.app_payment.AppCheckoutWorker")
        self.worker.start()
        self.screen = AppPaymentScreen(self.parent, clock=self.clock)

    def tearDown(self):
        self.screen.screen_timer.stop()
        self.parent.compra_session.stop()
        self.worker.stop()

    def test_screen_limit_is_five_minutes(self):
        self.clock.value += 10
        self.screen.iniciar_pagamento("R$ 1,00")
        self.assertEqual("05:00", self.screen.timer_label.text())

        self.clock.value += 299
        self.screen._tick_screen_timeout()
        self.parent.encerrar_compra_por_inatividade.assert_not_called()

        self.clock.value += 1
        self.screen._tick_screen_timeout()
        self.parent.encerrar_compra_por_inatividade.assert_called_once_with()
        self.assertFalse(self.screen.screen_timer.isActive())

    def test_screen_limit_respects_purchase_ceiling(self):
        self.clock.value += 500
        self.screen.iniciar_pagamento("R$ 1,00")

        self.assertEqual("01:40", self.screen.timer_label.text())
        self.clock.value += 100
        self.screen._tick_screen_timeout()
        # No teto quem encerra é a própria sessão, uma única vez.
        self.parent.encerrar_compra_por_inatividade.assert_not_called()

    def test_leaving_screen_stops_limit(self):
        self.screen.iniciar_pagamento("R$ 1,00")
        self.screen.cancelar_pagamento()

        self.clock.value += 400
        self.screen._tick_screen_timeout()

        self.parent.encerrar_compra_por_inatividade.assert_not_called()


if __name__ == "__main__":
    unittest.main()
