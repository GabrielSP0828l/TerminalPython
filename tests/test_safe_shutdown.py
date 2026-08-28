import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt

from main import MainWindow


class SafeShutdownTest(unittest.TestCase):
    def test_escape_is_consumed_in_kiosk_mode(self):
        event = MagicMock()
        event.key.return_value = Qt.Key_Escape
        MainWindow.keyPressEvent(SimpleNamespace(), event)
        event.accept.assert_called_once()

    def test_unauthorized_close_event_is_ignored(self):
        event = MagicMock()
        window = SimpleNamespace(_shutdown_authorized=False)
        MainWindow.closeEvent(window, event)
        event.ignore.assert_called_once()
        event.accept.assert_not_called()

    def test_shutdown_stops_services_once_without_resetting_purchase(self):
        activation_worker = MagicMock()
        activation_worker.isRunning.return_value = True
        window = SimpleNamespace(
            _services_stopped=False,
            compra_session=MagicMock(),
            welcome=MagicMock(),
            cadastro_terminal=SimpleNamespace(
                activation_timer=MagicMock(), activation_worker=activation_worker
            ),
            confirmacao=MagicMock(),
            configuracao=MagicMock(),
            pagamento=MagicMock(),
            app_payment=MagicMock(),
            terminal=SimpleNamespace(timer_foco=MagicMock(), listener=MagicMock()),
            sync_service=MagicMock(),
            socket=MagicMock(),
            internet_monitor=MagicMock(),
        )

        MainWindow._parar_servicos(window)
        MainWindow._parar_servicos(window)

        window.compra_session.stop.assert_called_once()
        window.compra_session.reset.assert_not_called()
        window.terminal.listener.stop.assert_called_once()
        window.sync_service.stop.assert_called_once()
        window.socket.stop.assert_called_once()
        window.pagamento.parar_workers.assert_called_once()
        window.configuracao.stop_workers.assert_called_once_with(wait=True)
        window.app_payment.parar_espera.assert_called_once()
        window.internet_monitor.stop.assert_called_once()
        activation_worker.requestInterruption.assert_called_once()

    def test_authorized_shutdown_quits_application(self):
        app = MagicMock()
        window = SimpleNamespace(
            _shutdown_started=False,
            _shutdown_authorized=False,
            _parar_servicos=MagicMock(),
        )
        with patch("main.QApplication.instance", return_value=app):
            MainWindow.encerrar_terminal(window)
        self.assertTrue(window._shutdown_authorized)
        window._parar_servicos.assert_called_once()
        app.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
