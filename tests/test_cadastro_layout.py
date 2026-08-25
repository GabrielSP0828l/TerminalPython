import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QSizePolicy

from telas.CadastroTerminalScreen import CadastroTerminalScreen


class CadastroTerminalLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_screen(self):
        with patch(
            "telas.CadastroTerminalScreen.TerminalInfo.to_dict",
            return_value={
                "serialNumber": "serial",
                "macAddress": "00:00:00:00:00:00",
                "ipAddress": "0.0.0.0",
            },
        ), patch(
            "telas.CadastroTerminalScreen.Terminal.is_activated",
            return_value=True,
        ):
            return CadastroTerminalScreen(None)

    def _assert_components_inside_screen(self, screen):
        screen_rect = screen.rect()
        for widget in (
            screen.card,
            screen.title,
            screen.subtitle,
            screen.qr_label,
            screen.info_label,
            screen.status_label,
        ):
            top_left = widget.mapTo(screen, widget.rect().topLeft())
            bottom_right = widget.mapTo(screen, widget.rect().bottomRight())
            self.assertTrue(screen_rect.contains(top_left), widget.objectName())
            self.assertTrue(screen_rect.contains(bottom_right), widget.objectName())

    def test_expands_in_terminal_landscape_resolution(self):
        screen = self._create_screen()
        screen.resize(1024, 600)
        screen.show()
        self.app.processEvents()

        self.assertEqual("landscape", screen._layout_mode)
        self.assertEqual("activationScreen", screen.objectName())
        self.assertEqual(QSizePolicy.Expanding, screen.sizePolicy().horizontalPolicy())
        self.assertEqual(QSizePolicy.Expanding, screen.card.sizePolicy().horizontalPolicy())
        self._assert_components_inside_screen(screen)
        screen.close()

    def test_reflows_in_portrait_resolution(self):
        screen = self._create_screen()
        screen.resize(600, 1024)
        screen.show()
        self.app.processEvents()

        self.assertEqual("portrait", screen._layout_mode)
        self._assert_components_inside_screen(screen)
        screen.close()

    def test_reflows_when_resized_again(self):
        screen = self._create_screen()
        screen.resize(1024, 600)
        screen.show()
        self.app.processEvents()
        screen.resize(600, 1024)
        self.app.processEvents()

        self.assertEqual("portrait", screen._layout_mode)
        self._assert_components_inside_screen(screen)
        screen.close()

    def test_components_fit_in_smaller_development_window(self):
        screen = self._create_screen()
        screen.resize(800, 480)
        screen.show()
        self.app.processEvents()

        self.assertEqual("landscape", screen._layout_mode)
        self._assert_components_inside_screen(screen)
        screen.close()

    def test_can_be_shown_again_after_close(self):
        screen = self._create_screen()
        screen.resize(1024, 600)
        screen.show()
        self.app.processEvents()
        screen.close()
        screen.show()
        self.app.processEvents()

        self.assertTrue(screen.isVisible())
        self.assertEqual("landscape", screen._layout_mode)
        self._assert_components_inside_screen(screen)
        screen.close()


if __name__ == "__main__":
    unittest.main()
