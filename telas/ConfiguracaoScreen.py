import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from service.FactoryResetService import FactoryResetService
from styles.theme import Theme
from styles.tokens import Spacing
from telas.DisplayScreen import DisplayScreen
from telas.WifiScreen import WifiScreen


logger = logging.getLogger(__name__)


class ConfiguracaoScreen(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.reset_service = FactoryResetService()
        self._authenticated = False
        self._return_widget = None
        self._carregar_estilo()
        self._montar_interface()

    def _carregar_estilo(self):
        self.setProperty("role", "page")
        self.setStyleSheet(Theme.settings_stylesheet())

    def _montar_interface(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.pages = QStackedWidget(self)
        self.menu_page = QWidget(self)
        menu_root = QVBoxLayout(self.menu_page)
        menu_root.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        menu_root.setAlignment(Qt.AlignCenter)

        self.wifi_screen = WifiScreen(self.parent_app, self.show_menu, parent=self)
        self.display_screen = DisplayScreen(self.parent_app, self.show_menu, parent=self)
        self.pages.addWidget(self.menu_page)
        self.pages.addWidget(self.wifi_screen)
        self.pages.addWidget(self.display_screen)
        root.addWidget(self.pages)

        card = QFrame(self.menu_page)
        card.setObjectName("settingsCard")
        card.setMaximumWidth(760)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.SM)

        title = QLabel("CONFIGURAÇÕES DO TERMINAL")
        title.setProperty("role", "pageTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Área local de manutenção. As configurações do backend e do Mercado Pago não são alteradas aqui."
        )
        subtitle.setProperty("role", "pageSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        self.wifi_button = QPushButton("CONFIGURAR WI-FI")
        self.wifi_button.setProperty("variant", "primary")
        self.wifi_button.clicked.connect(self.abrir_wifi)

        self.display_button = QPushButton("ORIENTAÇÃO DA TELA")
        self.display_button.setProperty("variant", "primary")
        self.display_button.clicked.connect(self.abrir_display)

        self.reset_button = QPushButton("RESTAURAR PADRÕES DE FÁBRICA")
        self.reset_button.setProperty("variant", "danger")
        self.reset_button.setProperty("primaryAction", True)
        self.reset_button.clicked.connect(self.confirmar_reset)

        self.close_terminal_button = QPushButton("FECHAR TERMINAL")
        self.close_terminal_button.setProperty("variant", "danger")
        self.close_terminal_button.clicked.connect(self.confirmar_encerramento)

        self.back_button = QPushButton("VOLTAR")
        self.back_button.setProperty("variant", "secondary")
        self.back_button.clicked.connect(self.voltar)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(Spacing.SM)
        layout.addWidget(self.wifi_button)
        layout.addWidget(self.display_button)
        layout.addWidget(self.reset_button)
        layout.addWidget(self.close_terminal_button)
        layout.addWidget(self.back_button)
        menu_root.addWidget(card)

    def entrar(self, return_widget):
        self._authenticated = True
        self._return_widget = return_widget
        self.show_menu()

    def encerrar_sessao(self):
        self.stop_workers()
        set_network_settings = getattr(
            self.parent_app, "set_network_settings_active", None
        )
        if set_network_settings is not None:
            set_network_settings(False)
        self._authenticated = False
        self._return_widget = None

    def show_menu(self):
        self.pages.setCurrentWidget(self.menu_page)

    def abrir_wifi(self):
        if not self._authenticated:
            return
        set_network_settings = getattr(
            self.parent_app, "set_network_settings_active", None
        )
        if set_network_settings is not None:
            set_network_settings(True)
        self.pages.setCurrentWidget(self.wifi_screen)
        self.wifi_screen.show_page()

    def abrir_display(self):
        if not self._authenticated:
            return
        self.pages.setCurrentWidget(self.display_screen)
        self.display_screen.show_page()

    def stop_workers(self, wait=False):
        self.wifi_screen.stop_worker(wait=wait)
        self.display_screen.stop_worker(wait=wait)

    def voltar(self):
        return_widget = self._return_widget
        self.encerrar_sessao()
        self.parent_app.encerrar_menu_admin(return_widget)

    def confirmar_reset(self):
        if not self._authenticated:
            return
        confirmed = self._confirm_action(
            "Restaurar padrões",
            "Esta operação removerá a ativação e o cache local deste equipamento.\n\n"
            "O cadastro no backend, as credenciais Mercado Pago e o arquivo .env serão preservados.\n\n"
            "O aplicativo será encerrado e voltará à tela de ativação na próxima inicialização. Deseja continuar?",
            "RESETAR",
        )

        if not confirmed:
            return

        try:
            self.reset_service.request_reset()
        except OSError as error:
            logger.exception("Não foi possível agendar o reset local")
            QMessageBox.critical(
                self,
                "Erro ao restaurar",
                "Não foi possível preparar a restauração. Nenhum dado foi removido."
            )
            return

        QMessageBox.information(
            self,
            "Restauração preparada",
            "O aplicativo será encerrado. Abra-o novamente para concluir a restauração."
        )
        self.parent_app.encerrar_terminal()

    def confirmar_encerramento(self):
        if not self._authenticated:
            return

        session = self.parent_app.compra_session
        payment_active = session.payment_in_flight or session.state in {
            "STARTING_PAYMENT", "WAITING_PAYMENT", "PROCESSING", "TIMEOUT_CHECK"
        }
        cart = getattr(getattr(self.parent_app, "terminal", None), "carrinho", None)
        cart_active = bool(cart is not None and not cart.vazio())
        purchase_active = session.state != "IDLE" or cart_active

        if payment_active:
            message = (
                "Existe um pagamento em andamento.\n\n"
                "A cobrança não será cancelada automaticamente e poderá continuar "
                "no backend ou na maquininha.\n\n"
                "Deseja realmente encerrar o Terminal?"
            )
        elif purchase_active:
            message = (
                "Existe uma compra em andamento.\n\n"
                "Deseja realmente encerrar o Terminal?"
            )
        else:
            message = (
                "Encerrar Terminal?\n\n"
                "O aplicativo será fechado e o terminal ficará indisponível até "
                "ser iniciado novamente."
            )

        if self._confirm_action("Fechar Terminal", message, "ENCERRAR"):
            self.parent_app.encerrar_terminal()

    def _confirm_action(self, title, message, confirm_text):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setStyleSheet(Theme.component_stylesheet())
        cancel_button = dialog.addButton("CANCELAR", QMessageBox.RejectRole)
        confirm_button = dialog.addButton(confirm_text, QMessageBox.AcceptRole)
        dialog.setDefaultButton(cancel_button)
        dialog.exec_()
        return dialog.clickedButton() is confirm_button
