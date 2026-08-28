import os
import subprocess
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLineEdit, QStackedWidget, QWidget

from model.CompraSession import CompraSession
from service.WifiService import (
    WifiNetwork,
    WifiService,
    WifiServiceError,
    WifiSnapshot,
    WifiStatus,
)
from telas.WifiScreen import WifiScreen
from telas.teclado import VirtualKeyboard


def result(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class NmcliRunner:
    def __init__(self):
        self.calls = []
        self.fail_connect = None
        self.timeout_scan = False
        self.connected_ssid = "Minha:Rede"

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        joined = " ".join(command)
        if "radio wifi" in joined:
            return result("enabled\n")
        if "device status" in joined:
            return result("wlan0:wifi:connected\nenp2s0:ethernet:connected\n")
        if "connection show" in joined:
            return result("Minha\\:Rede:802-11-wireless\nCASA:802-11-wireless\n")
        if "device wifi list" in joined:
            if self.timeout_scan:
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            connected = self.connected_ssid.replace("\\", "\\\\").replace(":", "\\:")
            security = "--" if self.connected_ssid == "Visitantes" else "WPA2"
            return result(
                f"*:{connected}:82:{security}\n"
                ":CASA:61:WPA2\n"
                ":CASA:30:WPA2\n"
                ":Visitantes:45:--\n"
            )
        if "IP4.ADDRESS" in joined:
            return result("192.168.1.25/24\n")
        if "device wifi connect" in joined or "connection up" in joined:
            if self.fail_connect is not None:
                return self.fail_connect
            if "device wifi connect" in joined:
                self.connected_ssid = command[command.index("connect") + 1]
            else:
                self.connected_ssid = command[command.index("id") + 1]
            return result("Device successfully activated\n")
        if "device disconnect" in joined or "radio wifi on" in joined:
            return result()
        raise AssertionError(f"Comando inesperado: {command}")


class WifiServiceTest(unittest.TestCase):
    def setUp(self):
        self.runner = NmcliRunner()
        self.service = WifiService(runner=self.runner, nmcli_path="/usr/bin/nmcli")

    def test_scan_deduplicates_sorts_and_exposes_human_signal(self):
        snapshot = self.service.snapshot()

        self.assertTrue(snapshot.status.connected)
        self.assertEqual("Minha:Rede", snapshot.status.ssid)
        self.assertEqual("192.168.1.25", snapshot.status.ip_address)
        self.assertEqual(["Minha:Rede", "CASA", "Visitantes"], [
            network.ssid for network in snapshot.networks
        ])
        self.assertEqual("Excelente", snapshot.networks[0].signal_label)
        self.assertTrue(snapshot.networks[0].known)
        self.assertFalse(snapshot.networks[-1].protected)

    def test_special_characters_use_argv_and_password_only_on_stdin(self):
        network = WifiNetwork("Rede com espaços - _ @#!", 70, "WPA2")
        password = "s e-n_h@#!"
        self.service.connect(network, password)

        connect_command, options = next(
            call for call in self.runner.calls if "device wifi connect" in " ".join(call[0])
        )
        self.assertIn(network.ssid, connect_command)
        self.assertNotIn(password, connect_command)
        self.assertEqual(f"{password}\n", options["input"])
        self.assertNotIn("shell", options)
        self.assertLessEqual(options["timeout"], 20)

    def test_open_network_does_not_request_password(self):
        network = WifiNetwork("Visitantes", 45, "--")
        self.service.connect(network)
        _command, options = next(
            call for call in self.runner.calls if "device wifi connect" in " ".join(call[0])
        )
        self.assertIsNone(options["input"])

    def test_saved_network_reuses_profile_without_password(self):
        network = WifiNetwork("CASA", 61, "WPA2", profile_name="CASA")
        self.service.connect(network)
        command, options = next(
            call for call in self.runner.calls if "connection up" in " ".join(call[0])
        )
        self.assertIn("CASA", command)
        self.assertIsNone(options["input"])

    def test_timeout_and_authentication_errors_are_human_readable(self):
        self.runner.timeout_scan = True
        with self.assertRaises(WifiServiceError) as timeout:
            self.service.snapshot()
        self.assertEqual("TIMEOUT", timeout.exception.code)
        self.assertNotIn("nmcli", timeout.exception.user_message.lower())

        self.runner.timeout_scan = False
        self.runner.fail_connect = result(
            stderr="Error: 802-11-wireless-security.key-mgmt activation failed",
            returncode=10,
        )
        with self.assertRaises(WifiServiceError) as auth:
            self.service.connect(WifiNetwork("CASA", 60, "WPA2"), "errada")
        self.assertEqual("AUTH_FAILED", auth.exception.code)
        self.assertIn("Verifique a senha", auth.exception.user_message)
        self.assertNotIn("802-11", auth.exception.user_message)

    def test_missing_nmcli_is_safe(self):
        service = WifiService(which=lambda _name: None)
        with self.assertRaises(WifiServiceError) as unavailable:
            service.snapshot()
        self.assertEqual("SERVICE_UNAVAILABLE", unavailable.exception.code)


class FakeWifiService:
    def __init__(self):
        self.calls = []
        self.connect_error = None

    def snapshot(self):
        self.calls.append(("snapshot",))
        return WifiSnapshot(
            WifiStatus(True, True, "wlan0", "MinhaRede", 80, "192.168.1.25"),
            (
                WifiNetwork("MinhaRede", 80, "WPA2", True, "MinhaRede"),
                WifiNetwork("CASA_2G", 60, "WPA2"),
                WifiNetwork("Visitantes", 42, "--"),
            ),
        )

    def connect(self, network, password=None):
        self.calls.append(("connect", network.ssid, password))
        if self.connect_error:
            raise self.connect_error
        return WifiStatus(True, True, "wlan0", network.ssid, network.signal, "10.0.0.2")

    def disconnect(self):
        self.calls.append(("disconnect",))
        return WifiStatus(True, False, "wlan0")

    def enable_wifi(self):
        self.calls.append(("enable",))
        return self.snapshot()


class SlowWifiService(FakeWifiService):
    def snapshot(self):
        time.sleep(0.2)
        return super().snapshot()


class WifiParent(QWidget):
    def __init__(self):
        super().__init__()
        self.compra_session = CompraSession(self)
        self.terminal = SimpleNamespace(carrinho=SimpleNamespace(vazio=lambda: True))


class WifiScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = WifiParent()
        self.service = FakeWifiService()
        self.back_calls = 0
        self.screen = WifiScreen(
            self.parent, lambda: setattr(self, "back_calls", self.back_calls + 1),
            service=self.service,
        )
        self.screen.resize(1024, 600)

    def tearDown(self):
        self.screen.stop_worker()
        if self.screen.worker is not None:
            self.screen.worker.wait(1000)

    def _wait_worker(self):
        if self.screen.worker is not None:
            self.screen.worker.wait(1000)
        self.app.processEvents()

    def test_scan_runs_off_ui_thread_and_renders_touch_networks(self):
        slow = SlowWifiService()
        screen = WifiScreen(self.parent, lambda: None, service=slow)
        started = time.monotonic()
        screen.show_page()
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.1)
        self.assertTrue(screen.worker.isRunning())
        screen.worker.wait(1000)
        self.app.processEvents()
        buttons = [
            button for button in screen.findChildren(__import__("PyQt5.QtWidgets", fromlist=["QPushButton"]).QPushButton)
            if button.property("wifiNetwork")
        ]
        self.assertEqual(3, len(buttons))
        self.assertTrue(all(button.minimumHeight() >= 76 for button in buttons))
        screen.stop_worker()

    def test_protected_network_uses_masked_password_and_symbol_keyboard(self):
        self.screen.show_page()
        self._wait_worker()
        network = WifiNetwork("CASA_2G", 60, "WPA2")
        self.screen.select_network(network)
        self.assertIs(self.screen.password_page, self.screen.pages.currentWidget())
        self.assertEqual(QLineEdit.Password, self.screen.password_input.echoMode())

        self.screen.keyboard.process_key("#+=")
        for key in ("@", "#", "!", "-", "_"):
            self.screen.keyboard.process_key(key)
        self.assertEqual("@#!-_", self.screen.password_input.text())

    def test_open_network_connects_without_password_and_shows_success(self):
        network = WifiNetwork("Visitantes", 42, "--")
        with patch.object(self.screen, "_confirm_network_change", return_value=True):
            self.screen.select_network(network)
        self._wait_worker()
        self.assertIn(("connect", "Visitantes", None), self.service.calls)
        self.assertEqual("CONECTADO COM SUCESSO", self.screen.feedback_title.text())

    def test_wrong_password_is_sanitized_and_can_retry(self):
        self.service.connect_error = WifiServiceError(
            "AUTH_FAILED",
            "Não foi possível conectar. Verifique a senha da rede e tente novamente.",
            "raw linux error",
        )
        self.screen._selected_network = WifiNetwork("CASA_2G", 60, "WPA2")
        self.screen.password_input.setText("segredo")
        with patch.object(self.screen, "_confirm_network_change", return_value=True):
            self.screen.connect_with_password()
        self.assertEqual("", self.screen.password_input.text())
        self._wait_worker()
        self.assertIn("Verifique a senha", self.screen.feedback_message.text())
        self.screen.retry()
        self.assertIs(self.screen.password_page, self.screen.pages.currentWidget())
        self.assertEqual("", self.screen.password_input.text())

    def test_payment_warning_does_not_reset_payment(self):
        self.parent.compra_session.begin_payment()
        attempt = self.parent.compra_session.attempt_id
        network = WifiNetwork("Visitantes", 42, "--")
        with patch.object(self.screen, "_confirm_action", return_value=False) as confirm:
            self.screen.select_network(network)
        self.assertIn("pagamento em andamento", confirm.call_args.args[1])
        self.assertEqual(attempt, self.parent.compra_session.attempt_id)


class VirtualKeyboardSymbolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_symbol_mode_returns_to_alpha_without_exposing_input(self):
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        keyboard = VirtualKeyboard()
        keyboard.set_target(field)
        keyboard.process_key("#+=")
        keyboard.process_key("@")
        keyboard.process_key("#")
        keyboard.process_key("ABC")
        keyboard.process_key("A")
        self.assertEqual("@#A", field.text())
        self.assertEqual(QLineEdit.Password, field.echoMode())


if __name__ == "__main__":
    unittest.main()
