import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app247_terminal import main
from app247_terminal.services.display_service import DisplayServiceError


class MainCliLifecycleTest(unittest.TestCase):
    def test_version_isolated_from_graphical_lifecycle(self):
        with patch("app247_terminal.main._run_gui") as run_gui:
            self.assertEqual(0, main.run(["--version"]))
        run_gui.assert_not_called()

    def test_check_isolated_from_graphical_lifecycle(self):
        with patch("app247_terminal.diagnostics.check_installation", return_value=0), patch(
            "app247_terminal.main._run_gui"
        ) as run_gui:
            self.assertEqual(0, main.run(["--check"]))
        run_gui.assert_not_called()

    def test_apply_display_isolated_and_returns_success_without_main_window(self):
        service = MagicMock()
        with patch("app247_terminal.services.display_service.DisplayService", return_value=service), patch(
            "app247_terminal.main._run_gui"
        ) as run_gui, patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISPLAY_ORIENTATION", None)
            self.assertEqual(0, main.run(["--apply-display"]))
        service.apply_saved.assert_called_once_with()
        run_gui.assert_not_called()

    def test_apply_display_returns_nonzero_on_orientation_failure(self):
        error = DisplayServiceError("TOOL_UNAVAILABLE", "Orientação indisponível")
        service = MagicMock()
        service.apply_saved.side_effect = error
        with patch("app247_terminal.services.display_service.DisplayService", return_value=service), patch(
            "app247_terminal.main._run_gui"
        ) as run_gui:
            self.assertEqual(1, main.run(["--apply-display"]))
        run_gui.assert_not_called()

    def test_intentional_shutdown_normalizes_exit_code_to_zero(self):
        self.assertEqual(0, main._gui_exit_code(5, shutdown_was_requested=True))
        self.assertEqual(5, main._gui_exit_code(5, shutdown_was_requested=False))


if __name__ == "__main__":
    unittest.main()
