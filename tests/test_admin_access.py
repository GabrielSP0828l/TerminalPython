import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QStackedWidget, QWidget

from model.CompraSession import CompraSession
from telas.AdminAuthScreen import AdminAuthScreen
from telas.ConfiguracaoScreen import ConfiguracaoScreen


class CartStub:
    def __init__(self, active=False):
        self.active = active

    def vazio(self):
        return not self.active


class AdminParentStub(QWidget):
    def __init__(self, password="Senha9"):
        super().__init__()
        self.stacked_widget = QStackedWidget(self)
        self.welcome = QWidget()
        self.terminal = SimpleNamespace(carrinho=CartStub())
        self.compra_session = CompraSession(self)
        self.shutdown_calls = 0
        self.configuracao = ConfiguracaoScreen(self)
        self.admin_auth = AdminAuthScreen(self, configured_password=password)
        self.stacked_widget.addWidget(self.welcome)
        self.stacked_widget.addWidget(self.configuracao)
        self.stacked_widget.addWidget(self.admin_auth)
        self.stacked_widget.setCurrentWidget(self.welcome)

    def abrir_configuracoes(self):
        previous = self.stacked_widget.currentWidget()
        self.admin_auth.iniciar(previous)
        self.stacked_widget.setCurrentWidget(self.admin_auth)

    def abrir_menu_admin_autenticado(self, return_widget):
        self.configuracao.entrar(return_widget)
        self.stacked_widget.setCurrentWidget(self.configuracao)

    def cancelar_autenticacao_admin(self, return_widget):
        self.stacked_widget.setCurrentWidget(return_widget or self.welcome)

    def encerrar_menu_admin(self, return_widget):
        self.stacked_widget.setCurrentWidget(return_widget or self.welcome)

    def encerrar_terminal(self):
        self.shutdown_calls += 1


class AdminAccessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_password_is_hidden_and_correct_password_opens_existing_menu(self):
        parent = AdminParentStub()
        parent.abrir_configuracoes()
        self.assertIs(parent.admin_auth, parent.stacked_widget.currentWidget())
        self.assertEqual(QLineEdit.Password, parent.admin_auth.password_input.echoMode())

        parent.admin_auth.password_input.setText("Senha9")
        parent.admin_auth.validar()

        self.assertIs(parent.configuracao, parent.stacked_widget.currentWidget())
        self.assertTrue(parent.configuracao._authenticated)
        self.assertEqual("", parent.admin_auth.password_input.text())

    def test_wrong_password_never_opens_menu_and_allows_retry(self):
        parent = AdminParentStub()
        parent.abrir_configuracoes()
        parent.admin_auth.password_input.setText("errada")
        parent.admin_auth.validar()

        self.assertIs(parent.admin_auth, parent.stacked_widget.currentWidget())
        self.assertFalse(parent.configuracao._authenticated)
        self.assertEqual("Senha incorreta", parent.admin_auth.status_label.text())
        self.assertEqual("", parent.admin_auth.password_input.text())

    def test_touch_keyboard_can_enter_lowercase_admin_password(self):
        parent = AdminParentStub(password="senha9")
        parent.abrir_configuracoes()
        keyboard = parent.admin_auth.keyboard
        keyboard.process_key("abc")
        for key in ("S", "E", "N", "H", "A", "9"):
            keyboard.process_key(key)
        parent.admin_auth.validar()
        self.assertIs(parent.configuracao, parent.stacked_widget.currentWidget())

    def test_cancel_returns_to_exact_previous_screen_without_touching_purchase(self):
        parent = AdminParentStub()
        previous = QWidget()
        parent.stacked_widget.addWidget(previous)
        parent.stacked_widget.setCurrentWidget(previous)
        cart = parent.terminal.carrinho
        state = parent.compra_session.state

        parent.abrir_configuracoes()
        parent.admin_auth.cancelar()

        self.assertIs(previous, parent.stacked_widget.currentWidget())
        self.assertIs(cart, parent.terminal.carrinho)
        self.assertEqual(state, parent.compra_session.state)

    def test_leaving_menu_locks_it_and_next_access_requests_password_again(self):
        parent = AdminParentStub()
        parent.abrir_configuracoes()
        parent.admin_auth.password_input.setText("Senha9")
        parent.admin_auth.validar()
        parent.configuracao.voltar()

        self.assertFalse(parent.configuracao._authenticated)
        self.assertIs(parent.welcome, parent.stacked_widget.currentWidget())

        parent.abrir_configuracoes()
        self.assertIs(parent.admin_auth, parent.stacked_widget.currentWidget())
        self.assertFalse(parent.configuracao._authenticated)

    def test_missing_configuration_keeps_menu_blocked(self):
        parent = AdminParentStub(password="")
        parent.abrir_configuracoes()
        self.assertFalse(parent.admin_auth.enter_button.isEnabled())
        parent.admin_auth.password_input.setText("qualquer")
        parent.admin_auth.validar()
        self.assertIs(parent.admin_auth, parent.stacked_widget.currentWidget())

    def test_reset_is_guarded_by_menu_authentication(self):
        parent = AdminParentStub()
        parent.configuracao.reset_service = MagicMock()
        parent.configuracao.confirmar_reset()
        parent.configuracao.reset_service.request_reset.assert_not_called()

        parent.configuracao.entrar(parent.welcome)
        with patch.object(parent.configuracao, "_confirm_action", return_value=True), \
             patch("telas.ConfiguracaoScreen.QMessageBox.information"):
            parent.configuracao.confirmar_reset()
        parent.configuracao.reset_service.request_reset.assert_called_once()
        self.assertEqual(1, parent.shutdown_calls)

    def test_close_terminal_requires_only_confirmation_after_menu_auth(self):
        parent = AdminParentStub()
        parent.configuracao.entrar(parent.welcome)
        with patch.object(parent.configuracao, "_confirm_action", return_value=True) as confirm:
            parent.configuracao.confirmar_encerramento()
        self.assertEqual(1, parent.shutdown_calls)
        self.assertIn("Encerrar Terminal", confirm.call_args.args[1])

    def test_payment_warning_does_not_cancel_or_reset_session(self):
        parent = AdminParentStub()
        parent.compra_session.begin_payment()
        attempt = parent.compra_session.attempt_id
        parent.configuracao.entrar(parent.welcome)
        with patch.object(parent.configuracao, "_confirm_action", return_value=False) as confirm:
            parent.configuracao.confirmar_encerramento()
        self.assertIn("pagamento em andamento", confirm.call_args.args[1])
        self.assertEqual(attempt, parent.compra_session.attempt_id)
        self.assertTrue(parent.compra_session.payment_in_flight)
        self.assertEqual(0, parent.shutdown_calls)

    def test_existing_admin_menu_contains_wifi_and_orientation_touch_actions(self):
        parent = AdminParentStub()
        screen = parent.configuracao
        screen.resize(1024, 600)
        screen.entrar(parent.welcome)
        screen.show()
        self.app.processEvents()

        self.assertEqual("CONFIGURAR WI-FI", screen.wifi_button.text())
        self.assertEqual("ORIENTAÇÃO DA TELA", screen.display_button.text())
        for button in (
            screen.wifi_button, screen.display_button, screen.reset_button,
            screen.close_terminal_button, screen.back_button,
        ):
            self.assertGreaterEqual(button.height(), 60)
            self.assertLessEqual(button.geometry().bottom(), 600)

    def test_returning_from_admin_subpage_does_not_request_password_again(self):
        parent = AdminParentStub()
        screen = parent.configuracao
        screen.entrar(parent.welcome)
        with patch.object(screen.wifi_screen, "show_page"):
            screen.abrir_wifi()
        self.assertIs(screen.wifi_screen, screen.pages.currentWidget())

        screen.show_menu()

        self.assertTrue(screen._authenticated)
        self.assertIs(screen.menu_page, screen.pages.currentWidget())


if __name__ == "__main__":
    unittest.main()
