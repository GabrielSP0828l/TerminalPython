import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from model.CompraSession import CompraSession
from service.DisplayService import DisplayService, DisplayServiceError, DisplayStatus
from telas.DisplayScreen import DisplayScreen


def result(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class DisplayRunner:
    WLR_OUTPUT = (
        'HDMI-A-2 "Display 7"\n'
        "  Enabled: yes\n"
        "  Modes:\n"
        "  Transform: normal\n"
        'HDMI-A-1 "Inactive"\n'
        "  Enabled: no\n"
    )

    def __init__(self):
        self.calls = []
        self.timeout_apply = False
        self.xrandr_output = (
            "VGA-1 connected primary 1024x600+0+0 "
            "(normal left inverted right x axis y axis)\n"
        )

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command == ["/usr/bin/wlr-randr"]:
            return result(self.WLR_OUTPUT)
        if "--transform" in command:
            if self.timeout_apply:
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return result()
        if command == ["/usr/bin/xrandr", "--query"]:
            return result(self.xrandr_output)
        if "--rotate" in command:
            return result()
        raise AssertionError(f"Comando inesperado: {command}")


class DisplayServiceTest(unittest.TestCase):
    def test_startup_script_has_no_hardcoded_output_and_reuses_saved_service(self):
        script = (Path(__file__).resolve().parents[1] / "start.sh").read_text(encoding="utf-8")
        self.assertNotIn("HDMI-A-2", script)
        self.assertIn("service.DisplayService --apply-saved", script)

    def test_wayland_detects_active_output_applies_and_persists(self):
        runner = DisplayRunner()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "display_orientation"
            service = DisplayService(
                config_path=path,
                runner=runner,
                which=lambda name: f"/usr/bin/{name}" if name == "wlr-randr" else None,
                environ={"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
            )
            status = service.apply_orientation("vertical")

            self.assertEqual("HDMI-A-2", status.output)
            self.assertEqual("vertical", status.orientation)
            self.assertEqual("vertical", path.read_text(encoding="utf-8").strip())
            apply_command = next(call[0] for call in runner.calls if "--transform" in call[0])
            self.assertEqual([
                "/usr/bin/wlr-randr", "--output", "HDMI-A-2", "--transform", "90"
            ], apply_command)

    def test_saved_orientation_is_reapplied_without_rewriting(self):
        runner = DisplayRunner()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "display_orientation"
            path.write_text("horizontal\n", encoding="utf-8")
            service = DisplayService(
                config_path=path,
                runner=runner,
                which=lambda name: f"/usr/bin/{name}" if name == "wlr-randr" else None,
                environ={"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
            )
            status = service.apply_saved()
            self.assertEqual("horizontal", status.orientation)
            self.assertEqual("horizontal\n", path.read_text(encoding="utf-8"))

    def test_xrandr_is_used_only_for_x11(self):
        runner = DisplayRunner()
        service = DisplayService(
            runner=runner,
            which=lambda name: "/usr/bin/xrandr" if name == "xrandr" else None,
            environ={"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"},
        )
        status = service.apply_orientation("vertical", persist=False)
        self.assertEqual("xrandr", status.backend)
        self.assertIn(
            ["/usr/bin/xrandr", "--output", "VGA-1", "--rotate", "right"],
            [call[0] for call in runner.calls],
        )

    def test_xrandr_uses_active_output_and_reads_existing_rotation(self):
        runner = DisplayRunner()
        runner.xrandr_output = (
            "DP-1 connected (normal left inverted right x axis y axis)\n"
            "HDMI-1 connected primary 600x1024+0+0 left "
            "(normal left inverted right x axis y axis)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            service = DisplayService(
                config_path=Path(directory) / "orientation",
                runner=runner,
                which=lambda name: f"/usr/bin/{name}" if name == "xrandr" else None,
                environ={"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"},
            )
            status = service.current_status()

        self.assertEqual("HDMI-1", status.output)
        self.assertEqual("vertical", status.orientation)
        self.assertEqual("left", status.transform)

    def test_wayland_without_wlr_randr_fails_safely_even_if_xrandr_exists(self):
        service = DisplayService(
            which=lambda name: "/usr/bin/xrandr" if name == "xrandr" else None,
            environ={"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
        )
        with self.assertRaises(DisplayServiceError) as unavailable:
            service.current_status()
        self.assertEqual("TOOL_UNAVAILABLE", unavailable.exception.code)

    def test_display_command_has_timeout(self):
        runner = DisplayRunner()
        runner.timeout_apply = True
        service = DisplayService(
            runner=runner,
            which=lambda name: f"/usr/bin/{name}" if name == "wlr-randr" else None,
            environ={"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"},
        )
        with self.assertRaises(DisplayServiceError) as timeout:
            service.apply_orientation("vertical", persist=False)
        self.assertEqual("TIMEOUT", timeout.exception.code)
        apply_options = next(call[1] for call in runner.calls if "--transform" in call[0])
        self.assertEqual(8, apply_options["timeout"])


class FakeDisplayService:
    def __init__(self):
        self.applied = []

    def current_status(self):
        return DisplayStatus("wlr-randr", "HDMI-A-2", "horizontal", "normal")

    def apply_orientation(self, orientation):
        self.applied.append(orientation)
        return DisplayStatus(
            "wlr-randr", "HDMI-A-2", orientation,
            "90" if orientation == "vertical" else "normal",
        )


class DisplayParent(QWidget):
    def __init__(self, cart_active=False):
        super().__init__()
        self.compra_session = CompraSession(self)
        self.terminal = SimpleNamespace(
            carrinho=SimpleNamespace(vazio=lambda: not cart_active)
        )
        self.refresh_calls = 0

    def refresh_display_geometry(self):
        self.refresh_calls += 1


class DisplayScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _wait(self, screen):
        if screen.worker is not None:
            screen.worker.wait(1000)
        self.app.processEvents()

    def test_horizontal_to_vertical_updates_ui_and_requests_geometry_refresh(self):
        parent = DisplayParent()
        service = FakeDisplayService()
        screen = DisplayScreen(parent, lambda: None, service=service)
        screen.show_page()
        self._wait(screen)
        screen.apply("vertical")
        self._wait(screen)
        self.assertEqual(["vertical"], service.applied)
        self.assertEqual("Vertical", screen.current_orientation.text())
        self.assertEqual(1, parent.refresh_calls)

    def test_active_purchase_blocks_rotation(self):
        parent = DisplayParent(cart_active=True)
        service = FakeDisplayService()
        screen = DisplayScreen(parent, lambda: None, service=service)
        screen.apply("vertical")
        self.assertEqual([], service.applied)
        self.assertIn("compra ou pagamento", screen.message.text())


if __name__ == "__main__":
    unittest.main()
