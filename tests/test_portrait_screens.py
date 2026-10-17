import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint

from PyQt5.QtWidgets import QApplication, QBoxLayout, QPushButton, QStackedWidget, QWidget

from app247_terminal.models.purchase_session import CompraSession
from app247_terminal.ui.screens.terminal_registration import CadastroTerminalScreen
from app247_terminal.ui.screens.admin_auth import AdminAuthScreen
from app247_terminal.ui.screens.settings import ConfiguracaoScreen
from app247_terminal.ui.screens.confirmation import ConfirmacaoScreen
from app247_terminal.ui.screens.app_payment import AppPaymentScreen
from app247_terminal.ui.screens.welcome import TelaBemVindos
from app247_terminal.ui.screens.login import LoginScreen
from app247_terminal.ui.screens.payment import PagamentoScreen
from app247_terminal.ui.screens.keyboard import TecladoScreen
from app247_terminal.ui.screens.terminal import TerminalScreen
from app247_terminal.ui.screens.purchase_confirmation import ConfirmacaoCompraScreen
from app247_terminal.ui.responsive import layout_profile

# Display de campo: 1024×600 nativo montado em pé (área lógica 600×1024).
PORTRAIT_SIZE = (600, 1024)
LANDSCAPE_SIZE = (1024, 600)


class ParentStub(QWidget):
    def __init__(self):
        super().__init__()
        self.compra_session = CompraSession(self)
        self.stacked_widget = QStackedWidget(self)
        self.terminal = SimpleNamespace(carrinho=MagicMock())
        self.login = QWidget()
        self.welcome = QWidget()
        self.confirmacao = ConfirmacaoScreen(self)
        self.current = None

    def abrir_configuracoes(self):
        pass

    def iniciar_operacao_terminal(self):
        pass

    def setCurrentWidget(self, widget):
        self.current = widget

    def reset_compra(self, outcome="cancelled"):
        self.compra_session.reset()


def make_cart_screen(parent):
    terminal_data = SimpleNamespace(uuidTerminal="terminal-1")
    with patch("app247_terminal.ui.screens.terminal.CatalogService"), \
         patch("app247_terminal.models.cart.Terminal.load", return_value=terminal_data), \
         patch("app247_terminal.services.payment_listener.Terminal.load", return_value=terminal_data), \
         patch("app247_terminal.services.payment_listener.PaymentListener.start"):
        return TerminalScreen(parent)


class PortraitScreensTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        layout_profile.force(True)

    def tearDown(self):
        layout_profile.force(None)

    def _show_fitting(self, screen, size):
        width, height = size
        minimum = screen.minimumSizeHint()
        # Mínimo acima da tela faz a janela fullscreen estourar e cortar.
        self.assertLessEqual(minimum.width(), width)
        self.assertLessEqual(minimum.height(), height)
        screen.resize(width, height)
        screen.show()
        self.app.processEvents()
        self.assertEqual(width, screen.width())
        self.assertEqual(height, screen.height())
        for button in screen.findChildren(QPushButton):
            if button.isVisible():
                self.assertGreaterEqual(button.height(), 44, button.text())
                right = button.mapTo(screen, QPoint(button.width(), 0)).x()
                self.assertLessEqual(right, width, button.text())
        screen.close()

    def _build_screens(self):
        parent = ParentStub()
        with patch("app247_terminal.ui.screens.terminal_registration.TerminalInfo.to_dict", return_value={
            "serialNumber": "serial", "macAddress": "00:00:00:00:00:00", "ipAddress": "0.0.0.0"
        }), patch("app247_terminal.ui.screens.terminal_registration.Terminal.is_activated", return_value=True):
            cadastro = CadastroTerminalScreen(parent)

        screens = [
            TelaBemVindos(parent),
            AdminAuthScreen(parent, configured_password="teste"),
            cadastro,
            ConfiguracaoScreen(parent),
            LoginScreen(parent),
            TecladoScreen(parent),
            PagamentoScreen(parent),
            parent.confirmacao,
            AppPaymentScreen(parent),
            make_cart_screen(parent),
            ConfirmacaoCompraScreen(parent),
        ]
        return screens

    def test_all_pages_fit_portrait(self):
        for screen in self._build_screens():
            with self.subTest(screen=type(screen).__name__):
                self._show_fitting(screen, PORTRAIT_SIZE)

    def test_all_pages_fit_landscape(self):
        layout_profile.force(False)
        for screen in self._build_screens():
            with self.subTest(screen=type(screen).__name__):
                self._show_fitting(screen, LANDSCAPE_SIZE)

    def test_layouts_follow_screen_orientation(self):
        parent = ParentStub()
        teclado = TecladoScreen(parent)
        cart = make_cart_screen(parent)
        confirmacao = parent.confirmacao
        wrap_keys = teclado.keyboard._wrap_buttons
        self.assertEqual(["ESPAÇO", "LIMPAR"], [key.text() for key in wrap_keys])

        layout_profile.force(False)
        self.assertGreaterEqual(teclado.keyboard._last_row_layout.indexOf(wrap_keys[0]), 0)
        self.assertEqual(QBoxLayout.LeftToRight, cart.footer_layout.direction())
        self.assertEqual(1, confirmacao.success_actions.getItemPosition(
            confirmacao.success_actions.indexOf(confirmacao.btn_cpf))[1])

        layout_profile.force(True)
        self.assertGreaterEqual(teclado.keyboard._wrap_row_layout.indexOf(wrap_keys[0]), 0)
        self.assertEqual(QBoxLayout.TopToBottom, cart.footer_layout.direction())
        self.assertEqual((3, 0), confirmacao.success_actions.getItemPosition(
            confirmacao.success_actions.indexOf(confirmacao.btn_cpf))[:2])

        teclado.keyboard._set_symbol_mode(True)
        self.assertEqual(">", wrap_keys[1].text())

    def test_admin_actions_side_by_side_only_in_landscape(self):
        admin = AdminAuthScreen(ParentStub(), configured_password="teste")
        self.assertEqual(QBoxLayout.TopToBottom, admin.actions_layout.direction())
        layout_profile.force(False)
        self.assertEqual(QBoxLayout.RightToLeft, admin.actions_layout.direction())
        self.assertTrue(admin.keyboard._key_buttons[0].property("dense"))

    def test_payment_error_has_large_title_and_retry_action(self):
        parent = ParentStub()
        screen = PagamentoScreen(parent)
        parent.compra_session.begin_payment()
        screen._safe_failure("Não foi possível concluir o pagamento.")
        self.assertEqual("PAGAMENTO NÃO CONCLUÍDO", screen.title.text())
        self.assertEqual("VOLTAR À COMPRA", screen.btn_voltar.text())
        self.assertFalse(screen.loading_spinner.isVisible())


if __name__ == "__main__":
    unittest.main()
