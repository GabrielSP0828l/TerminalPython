import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from service.FactoryResetService import FactoryResetService


logger = logging.getLogger(__name__)


class ConfiguracaoScreen(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.reset_service = FactoryResetService()
        self._carregar_estilo()
        self._montar_interface()

    def _carregar_estilo(self):
        try:
            with open("css/configuracao_screen.css", "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        except OSError as error:
            logger.warning("Não foi possível carregar o estilo de configurações: %s", error)

    def _montar_interface(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 48, 48, 48)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("settingsCard")
        card.setMaximumWidth(680)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(48, 44, 48, 44)
        layout.setSpacing(18)

        title = QLabel("CONFIGURAÇÕES DO TERMINAL")
        title.setObjectName("settingsTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Área local de manutenção. As configurações do backend e do Mercado Pago não são alteradas aqui."
        )
        subtitle.setObjectName("settingsSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        self.reset_button = QPushButton("RESTAURAR PADRÕES DE FÁBRICA")
        self.reset_button.setObjectName("factoryResetButton")
        self.reset_button.setMinimumHeight(64)
        self.reset_button.clicked.connect(self.confirmar_reset)

        back_button = QPushButton("VOLTAR")
        back_button.setObjectName("backButton")
        back_button.setMinimumHeight(54)
        back_button.clicked.connect(self.voltar)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        layout.addWidget(self.reset_button)
        layout.addWidget(back_button)
        root.addWidget(card)

    def voltar(self):
        self.parent_app.setCurrentWidget(self.parent_app.welcome)

    def confirmar_reset(self):
        resposta = QMessageBox.warning(
            self,
            "Restaurar padrões",
            "Esta operação removerá a ativação e o cache local deste equipamento.\n\n"
            "O cadastro no backend, as credenciais Mercado Pago e o arquivo .env serão preservados.\n\n"
            "O aplicativo será encerrado e voltará à tela de ativação na próxima inicialização. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if resposta != QMessageBox.Yes:
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
        QApplication.quit()
