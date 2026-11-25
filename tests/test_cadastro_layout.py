import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QSizePolicy

from app247_terminal.ui import texts
from app247_terminal.ui.screens.terminal_registration import CadastroTerminalScreen


PAIRING = {"code": "ABC123", "qrPayload": "app247://pair?code=ABC123&serial=serial"}


class CadastroTerminalLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_screen(self, pairing=PAIRING):
        screen = self._create_unpaired_screen()
        if pairing is not None:
            screen._mostrar_pareamento(pairing)
        return screen

    def test_waiting_state_shows_loader_instead_of_empty_qr(self):
        screen = self._create_unpaired_screen()
        screen.resize(600, 1024)
        screen.show()
        self.app.processEvents()

        self.assertFalse(screen.qr_label.isVisible())
        self.assertTrue(screen.qr_loader.isVisible())
        self.assertTrue(screen.qr_loader.is_running)
        self.assertEqual(texts.ACTIVATION_WAITING, screen.status_label.text())
        self.assertNotIn("Gerando", screen.info_label.text())
        screen.close()

    def test_real_qr_replaces_loader_at_300px_in_portrait(self):
        screen = self._create_screen()
        screen.resize(600, 1024)
        screen.show()
        self.app.processEvents()

        self.assertTrue(screen.qr_label.isVisible())
        self.assertFalse(screen.qr_loader.isVisible())
        pixmap = screen.qr_label.pixmap()
        self.assertEqual((300, 300), (pixmap.width(), pixmap.height()))
        self.assertIn("ABC123", screen.info_label.text())
        self._assert_components_inside_screen(screen)
        screen.close()

    def _create_unpaired_screen(self):
        with patch(
            "app247_terminal.ui.screens.terminal_registration.TerminalInfo.to_dict",
            return_value={
                "serialNumber": "serial",
                "macAddress": "00:00:00:00:00:00",
                "ipAddress": "0.0.0.0",
            },
        ), patch(
            "app247_terminal.ui.screens.terminal_registration.Terminal.is_activated",
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
