import os
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QObject, QSize, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QProgressBar, QWidget

from model.CompraSession import CompraSession
from styles.svg_icons import icon_path, render_colored_svg
from styles.animated_svg import AnimatedSvgWidget
from styles.tokens import Colors, FontSize
from telas.ConfirmacaoScreen import ConfirmacaoScreen
from telas.pagamento import PagamentoScreen


class CartStub:
    def total_formatado(self):
        return "R$ 48.90"


class ParentStub(QWidget):
    def __init__(self):
        super().__init__()
        self.compra_session = CompraSession(self)
        self.terminal = SimpleNamespace(carrinho=CartStub())
        self.welcome = QWidget()
        self.current = None
        self.reset_calls = 0
        self.confirmacao = ConfirmacaoScreen(self)

    def setCurrentWidget(self, widget):
        self.current = widget

    def reset_compra(self, outcome="cancelled"):
        self.reset_calls += 1
        self.compra_session.reset()


class FakeReceiptWorker(QObject):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str, str)
    finished = pyqtSignal()
    starts = 0

    def __init__(self, *args, **kwargs):
        super().__init__(kwargs.get("parent"))

    def start(self):
        type(self).starts += 1


class PaymentStateScreensTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = ParentStub()
        self.screen = PagamentoScreen(self.parent)
        attempt = self.parent.compra_session.begin_payment()
        self.screen.current_attempt = attempt
        self.screen._point_started(attempt, {
            "cartId": "cart-a", "orderId": "order-a", "status": "WAITING_PAYMENT",
            "mercadoPagoStatus": "AT_TERMINAL",
        })

    def tearDown(self):
        self.screen.parar_workers()
        self.parent.confirmacao.stop()

    def test_assets_are_root_relative_and_recolored_without_changing_svg(self):
        original = icon_path("alert.svg").read_bytes()
        current = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.chdir(directory)
                pixmap = render_colored_svg(
                    icon_path("alert.svg"), Colors.PAYMENT_STATE_FOREGROUND, QSize(160, 160)
                )
        finally:
            os.chdir(current)
        self.assertFalse(pixmap.isNull())
        image = pixmap.toImage()
        opaque_colors = {
            QColor(image.pixel(x, y)).name().lower()
            for x in range(image.width()) for y in range(image.height())
            if QColor.fromRgba(image.pixel(x, y)).alpha() == 255
        }
        self.assertEqual({"#ffffff"}, opaque_colors)
        self.assertEqual(original, icon_path("alert.svg").read_bytes())

    def test_definitive_failures_use_fullscreen_error_and_human_reason(self):
        expected = {
            "REJECTED": "Pagamento recusado",
            "CANCELLED": "Pagamento cancelado",
            "FAILED": "Não foi possível concluir o pagamento",
            "EXPIRED": "O tempo para pagamento terminou",
        }
        for status, message in expected.items():
            with self.subTest(status=status):
                self.parent.compra_session.set_remote_ids(order_id="order-a")
                self.parent.compra_session.payment_in_flight = True
                self.screen._apply_status("order-a", status)
                self.assertIs(self.screen.error_page, self.screen.pages.currentWidget())
                self.assertEqual(message, self.screen.error_reason.text())
                self.assertEqual("TENTAR NOVAMENTE", self.screen.error_retry.text())

    def test_waiting_and_processing_remain_on_point_instruction_screen(self):
        self.assertIs(self.screen.attention_page, self.screen.pages.currentWidget())
        self.assertTrue(self.screen.attention_recheck_timer.isActive())
        self.parent.compra_session.set_remote_ids(order_id="order-a")
        self.screen._apply_status("order-a", "PROCESSING")
        self.assertIs(self.screen.attention_page, self.screen.pages.currentWidget())
        self.assertFalse(self.screen.operation_timer.isActive())
        self.assertNotEqual(self.screen.error_page, self.screen.pages.currentWidget())

    def test_orange_screen_explains_method_change_and_total_cancellation(self):
        self.assertIn("botão verde", self.screen.attention_page.message.text())
        self.assertIn("cancelar Débito", self.screen.attention_support.text())
        self.assertEqual("CANCELAR COMPRA", self.screen.cancel_payment_button.text())
        self.assertGreaterEqual(self.screen.cancel_payment_button.height(), 60)

    def test_tube_spinner_is_animated_and_replaces_qt_progress_bar(self):
        spinner = AnimatedSvgWidget("tube-spinner.svg", Colors.INFO)
        spinner.resize(128, 128)
        spinner.show()
        self.app.processEvents()
        first = spinner.grab().toImage()
        QTest.qWait(250)
        self.app.processEvents()
        second = spinner.grab().toImage()
        self.assertTrue(spinner.is_animated)
        self.assertNotEqual(first, second)
        self.assertEqual([], self.screen.findChildren(QProgressBar))
        self.assertEqual("tube-spinner.svg", self.screen.loading_spinner.source.name)
        self.assertEqual(QSize(128, 128), self.screen.loading_spinner.size())
        self.assertEqual(FontSize.LOADING_MESSAGE, self.screen.loading.font().pixelSize())

    def test_success_has_four_actions_and_no_automatic_reset(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.resize(768, 1360)
        success.show()
        self.app.processEvents()
        self.assertEqual("R$ 48,90", success.lbl_total.text())
        self.assertEqual([
            "ADICIONAR CPF",
            "ENVIAR POR E-MAIL",
            "ENVIAR POR WHATSAPP",
            "FINALIZAR",
        ], [
            success.btn_cpf.text(), success.btn_email.text(),
            success.btn_whatsapp.text(), success.btn_finalizar.text(),
        ])
        self.assertEqual(0, self.parent.reset_calls)
        for button in (
            success.btn_finalizar, success.btn_cpf, success.btn_email, success.btn_whatsapp
        ):
            self.assertGreaterEqual(button.height(), 60)

        self.assertFalse(success.btn_cpf.isEnabled())
        self.assertTrue(success.btn_email.isEnabled())
        self.assertTrue(success.btn_whatsapp.isEnabled())
        success.btn_finalizar.click()
        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)

    def test_recovered_success_uses_backend_amount_when_visual_cart_was_lost(self):
        self.parent.terminal.carrinho = CartStub()
        self.parent.terminal.carrinho.total_formatado = lambda: "R$ 0.00"

        self.screen.recovered_amount = "48.90"
        self.screen._apply_status("order-a", "APPROVED")

        self.assertEqual("R$ 48,90", self.parent.confirmacao.lbl_total.text())

    def test_duplicate_approved_does_not_interrupt_success_subflow(self):
        self.screen._apply_status("order-a", "APPROVED")
        self.parent.confirmacao._show_notice("TESTE", "Subfluxo aberto")
        self.screen._apply_status("order-a", "APPROVED")
        self.assertIs(
            self.parent.confirmacao.notice_page,
            self.parent.confirmacao.pages.currentWidget(),
        )

    def test_failure_returns_to_cart_and_success_times_out_to_welcome(self):
        self.screen._apply_status("order-a", "REJECTED")
        self.assertTrue(self.screen.failure_return_timer.isActive())
        self.screen._voltar_lista()
        self.assertIs(self.parent.terminal, self.parent.current)

        attempt = self.parent.compra_session.begin_payment()
        self.screen.current_attempt = attempt
        self.parent.compra_session.set_remote_ids(order_id="order-b")
        self.parent.compra_session.mark_waiting()
        self.screen._apply_status("order-b", "APPROVED")
        success = self.parent.confirmacao
        success._post_deadline = time.monotonic() - 1
        success._tick_post_timeout()
        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)

    def test_pending_never_enables_post_purchase_actions(self):
        success = self.parent.confirmacao
        success.mostrar_tela()
        self.assertFalse(success.btn_whatsapp.isEnabled())
        self.assertFalse(success.btn_email.isEnabled())
        self.assertFalse(success.btn_finalizar.isEnabled())
        self.assertFalse(success.post_timeout_timer.isActive())

    def test_paid_and_processed_use_the_same_approved_entry(self):
        for status in ("PAID", "PROCESSED"):
            with self.subTest(status=status):
                parent = ParentStub()
                screen = PagamentoScreen(parent)
                attempt = parent.compra_session.begin_payment()
                screen.current_attempt = attempt
                screen._point_started(attempt, {
                    "cartId": f"cart-{status}",
                    "orderId": f"order-{status}",
                    "status": "WAITING_PAYMENT",
                })
                screen._apply_status(f"order-{status}", status)
                self.assertIs(parent.confirmacao, parent.current)
                self.assertTrue(parent.confirmacao.btn_whatsapp.isEnabled())
                self.assertFalse(parent.compra_session._timer.isActive())
                self.assertTrue(parent.confirmacao.post_timeout_timer.isActive())
                screen.parar_workers()
                parent.confirmacao.stop()

    def test_whatsapp_uses_numeric_keyboard_and_pauses_timeout(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.btn_whatsapp.click()

        self.assertIs(success.input_page, success.pages.currentWidget())
        self.assertIs(
            success.numeric_keyboard, success.keyboard_pages.currentWidget()
        )
        self.assertFalse(success.post_timeout_timer.isActive())
        for digit in "75999999999":
            success.numeric_keyboard.process_key(digit)
        self.assertEqual("(75) 99999-9999", success.destination_input.text())

    def test_post_purchase_layout_and_touch_targets_fit_1024x600(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.resize(1024, 600)
        success.show()
        self.app.processEvents()
        for button in (
            success.btn_finalizar, success.btn_cpf,
            success.btn_whatsapp, success.btn_email,
        ):
            self.assertGreaterEqual(button.height(), 60, button.text())
            self.assertLessEqual(button.geometry().bottom(), success.height())

        success.btn_email.click()
        self.app.processEvents()
        for button in success.email_keyboard.findChildren(
                __import__("PyQt5.QtWidgets", fromlist=["QPushButton"]).QPushButton):
            self.assertGreaterEqual(button.height(), 48, button.text())
            self.assertLessEqual(
                button.mapTo(success, button.rect().bottomRight()).y(),
                success.height(), button.text(),
            )

    def test_email_uses_touch_keyboard_and_validation_stays_inline(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.btn_email.click()
        self.assertIs(success.email_keyboard, success.keyboard_pages.currentWidget())
        success.destination_input.setText("invalido")
        success._send_receipt()
        self.assertIn("e-mail válido", success.input_error.text())
        self.assertIs(success.input_page, success.pages.currentWidget())

    def test_cancel_input_returns_to_approved_without_losing_order(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.btn_email.click()
        success._cancel_receipt_input()

        self.assertIs(success.success_page, success.pages.currentWidget())
        self.assertEqual("order-a", success.post_purchase_order_id)
        self.assertEqual("order-a", self.parent.compra_session.order_id)
        self.assertTrue(success.post_timeout_timer.isActive())

    def test_receipt_success_keeps_approved_screen_available_after_feedback(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.receipt_channel = "WHATSAPP"
        success.receipt_send_in_progress = True
        success._receipt_succeeded({
            "status": "ENVIADO", "pedido": "order-a", "tipoEnvio": "WHATSAPP"
        })

        self.assertEqual("SUCCESS", self.parent.compra_session.state)
        self.assertEqual("order-a", self.parent.compra_session.order_id)
        self.assertIs(success.notice_page, success.pages.currentWidget())
        success.btn_notice_back.click()
        self.assertIs(success.success_page, success.pages.currentWidget())
        self.assertTrue(success.btn_email.isEnabled())
        self.assertTrue(success.btn_whatsapp.isEnabled())

    def test_repeated_clicks_start_only_one_receipt_worker_and_pause_timeout(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.btn_whatsapp.click()
        success.destination_input.setText("(75) 99999-9999")
        FakeReceiptWorker.starts = 0
        with patch("telas.ConfirmacaoScreen.Terminal.load", return_value=SimpleNamespace(
            terminalId="terminal-1"
        )), patch("telas.ConfirmacaoScreen.ReceiptSendWorker", FakeReceiptWorker):
            for _ in range(10):
                success._send_receipt()

        self.assertEqual(1, FakeReceiptWorker.starts)
        self.assertTrue(success.receipt_send_in_progress)
        success._post_deadline = time.monotonic() - 1
        success._tick_post_timeout()
        self.assertEqual(0, self.parent.reset_calls)

    def test_receipt_failure_keeps_approved_state_and_other_actions_available(self):
        self.screen._apply_status("order-a", "APPROVED")
        success = self.parent.confirmacao
        success.receipt_channel = "EMAIL"
        success.receipt_send_in_progress = True
        success._receipt_failed("Não foi possível enviar o comprovante.", "receipt")

        self.assertEqual("SUCCESS", self.parent.compra_session.state)
        self.assertEqual("order-a", self.parent.compra_session.order_id)
        self.assertTrue(success.btn_whatsapp.isEnabled())
        self.assertTrue(success.btn_email.isEnabled())
        self.assertIs(success.notice_page, success.pages.currentWidget())


if __name__ == "__main__":
    unittest.main()
