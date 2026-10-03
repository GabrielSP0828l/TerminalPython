import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QStackedWidget, QWidget

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


class PortraitScreensTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _show_portrait(self, screen):
        screen.resize(768, 1360)
        screen.show()
        self.app.processEvents()
        self.assertEqual(768, screen.width())
        self.assertEqual(1360, screen.height())
        for button in screen.findChildren(__import__("PyQt5.QtWidgets", fromlist=["QPushButton"]).QPushButton):
            if button.isVisible():
                self.assertGreaterEqual(button.height(), 56, button.text())
        screen.close()

    def test_all_pages_smoke_in_portrait(self):
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
        ]
        for screen in screens:
            with self.subTest(screen=type(screen).__name__):
                self._show_portrait(screen)

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
