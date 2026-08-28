import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QWidget

from model.CompraSession import CompraSession
from styles.svg_icons import icon_path, render_colored_svg
from styles.tokens import Colors
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

    def reset_compra(self):
        self.reset_calls += 1
        self.compra_session.reset()


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
            "cartId": "cart-a", "orderId": "order-a", "status": "WAITING_PAYMENT"
        })

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

    def test_waiting_is_attention_but_processing_is_loading(self):
        self.assertIs(self.screen.attention_page, self.screen.pages.currentWidget())
        self.parent.compra_session.set_remote_ids(order_id="order-a")
        self.screen._apply_status("order-a", "PROCESSING")
        self.assertIs(self.screen.loading_page, self.screen.pages.currentWidget())
        self.assertNotEqual(self.screen.error_page, self.screen.pages.currentWidget())

    def test_success_has_four_actions_and_no_automatic_reset(self):
        success = self.parent.confirmacao
        success.resize(768, 1360)
        success.mostrar_tela()
        success.show()
        self.app.processEvents()
        self.assertEqual("R$ 48,90", success.lbl_total.text())
        self.assertEqual([
            "FINALIZAR",
            "ADICIONAR CPF",
            "ENVIAR COMPROVANTE POR E-MAIL",
            "ENVIAR COMPROVANTE POR WHATSAPP",
        ], [
            success.btn_finalizar.text(), success.btn_cpf.text(),
            success.btn_email.text(), success.btn_whatsapp.text(),
        ])
        self.assertEqual(0, self.parent.reset_calls)
        for button in (
            success.btn_finalizar, success.btn_cpf, success.btn_email, success.btn_whatsapp
        ):
            self.assertGreaterEqual(button.height(), 60)

        success.btn_email.click()
        self.assertEqual(0, self.parent.reset_calls)
        self.assertIn("não está disponível", success.notice_message.text())
        success.pages.setCurrentWidget(success.success_page)
        success.btn_finalizar.click()
        self.assertEqual(1, self.parent.reset_calls)
        self.assertIs(self.parent.welcome, self.parent.current)

    def test_duplicate_approved_does_not_interrupt_success_subflow(self):
        self.screen._apply_status("order-a", "APPROVED")
        self.parent.confirmacao._show_unavailable("CPF")
        self.screen._apply_status("order-a", "APPROVED")
        self.assertIs(
            self.parent.confirmacao.notice_page,
            self.parent.confirmacao.pages.currentWidget(),
        )


if __name__ == "__main__":
    unittest.main()
