"""Bloqueio de 401/403 confirmado se desfaz sozinho, sem perder pagamento."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app247_terminal.application import MainWindow
from app247_terminal.services.backend_client import terminal_access_state


def host(**session):
    state = {"payment_in_flight": False, "order_id": None}
    state.update(session)
    return SimpleNamespace(
        _restore_device_access=lambda: MainWindow._restore_device_access(window),
        _last_access_probe=None,
        _startup_recovery_error=None,
        ACCESS_PROBE_INTERVAL_SECONDS=30,
        _check_terminal_lifecycle=MagicMock(),
        cadastro_terminal=SimpleNamespace(activation_timer=MagicMock()),
        terminal=object(),
        pagamento=MagicMock(),
        compra_session=SimpleNamespace(**state),
        reset_compra=MagicMock(),
        setCurrentWidget=MagicMock(),
        iniciar_operacao_terminal=MagicMock(),
        welcome=object(),
    )


window = None


class DeviceAccessRecoveryTest(unittest.TestCase):
    def setUp(self):
        terminal_access_state.set("AUTH_REQUIRED")

    def tearDown(self):
        terminal_access_state.set("OPERATIONAL")

    def build(self, **session):
        global window
        window = host(**session)
        return window

    def test_active_bootstrap_releases_terminal_to_welcome(self):
        app = self.build()
        MainWindow._handle_lifecycle_response(app, {"state": "ACTIVE"}, "ACCESS_RECOVERY")
        self.assertEqual("OPERATIONAL", terminal_access_state.get())
        app.cadastro_terminal.activation_timer.stop.assert_called_once()
        app.reset_compra.assert_called_once_with(outcome="cancelled")
        app.setCurrentWidget.assert_called_once_with(app.welcome)

    def test_active_payment_goes_to_reconciliation_not_to_reset(self):
        app = self.build(order_id="order-1")
        MainWindow._handle_lifecycle_response(app, {"state": "ACTIVE"}, "ACCESS_RECOVERY")
        self.assertEqual("OPERATIONAL", terminal_access_state.get())
        app.pagamento.mostrar_reconciliacao_pendente.assert_called_once_with(
            origin="ACCESS_RECOVERY"
        )
        app.reset_compra.assert_not_called()

    def test_failed_or_disabled_bootstrap_keeps_terminal_blocked(self):
        for response in (None, {"state": "DISABLED"}, {"state": "UNACTIVATED"}):
            with self.subTest(response=response):
                app = self.build()
                MainWindow._handle_lifecycle_response(app, response, "ACCESS_RECOVERY")
                self.assertEqual("AUTH_REQUIRED", terminal_access_state.get())
                app.setCurrentWidget.assert_not_called()

    def test_operational_terminal_ignores_periodic_bootstrap(self):
        terminal_access_state.set("OPERATIONAL")
        app = self.build()
        MainWindow._handle_lifecycle_response(app, {"state": "ACTIVE"}, "PERIODIC_BOOTSTRAP")
        app.reset_compra.assert_not_called()
        app.setCurrentWidget.assert_not_called()

    def test_probe_is_rate_limited(self):
        app = self.build()
        with patch("app247_terminal.application.time.monotonic") as clock:
            clock.return_value = 100.0
            MainWindow._probe_device_access(app)
            clock.return_value = 129.0
            MainWindow._probe_device_access(app)
            self.assertEqual(1, app._check_terminal_lifecycle.call_count)
            clock.return_value = 130.0
            MainWindow._probe_device_access(app)
            self.assertEqual(2, app._check_terminal_lifecycle.call_count)

    def test_probe_is_skipped_during_local_state_recovery(self):
        app = self.build()
        app._startup_recovery_error = "SQLITE_INTEGRITY_FAILED"
        MainWindow._probe_device_access(app)
        app._check_terminal_lifecycle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
