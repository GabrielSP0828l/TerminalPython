import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

from app247_terminal.ui.styles.theme import Theme
from app247_terminal.ui.styles.tokens import Colors


class MessageBoxThemeTest(unittest.TestCase):
    """Texto branco do tema não pode cair sobre o fundo claro da paleta do sistema."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._parents = []

    def _render(self, stylesheet, default_is_cancel=False):
        parent = QWidget()
        self.addCleanup(parent.deleteLater)
        self._parents.append(parent)
        parent.setStyleSheet(stylesheet)
        dialog = QMessageBox(parent)
        dialog.setText("Aviso de teste com texto legível")
        dialog.setIcon(QMessageBox.Warning)
        cancel = dialog.addButton("CANCELAR", QMessageBox.RejectRole)
        confirm = dialog.addButton("RESETAR", QMessageBox.AcceptRole)
        dialog.setDefaultButton(cancel if default_is_cancel else confirm)
        dialog.show()
        self.app.processEvents()
        image = dialog.grab().toImage()
        dialog.hide()
        return image, dialog, cancel, confirm

    def test_every_screen_stylesheet_gives_dialog_a_dark_background(self):
        for name in (
            "component_stylesheet", "cart_stylesheet", "settings_stylesheet",
            "wifi_stylesheet", "display_stylesheet", "payment_stylesheet",
            "confirmation_stylesheet", "activation_stylesheet", "offline_stylesheet",
        ):
            with self.subTest(stylesheet=name):
                image, *_ = self._render(getattr(Theme, name)())
                self.assertEqual(
                    QColor(image.pixel(2, 2)).name().upper(), Colors.SURFACE_ELEVATED.upper()
                )

    def test_text_is_white_on_dark_background(self):
        image, dialog, *_ = self._render(Theme.settings_stylesheet())
        label = dialog.findChild(QWidget, "qt_msgbox_label")
        area = dialog.grab(label.geometry()).toImage()
        colors = {
            QColor(area.pixel(x, y)).name().upper()
            for x in range(area.width()) for y in range(area.height())
        }
        self.assertIn(Colors.TEXT_PRIMARY.upper(), colors)

    def test_buttons_are_distinct_and_readable(self):
        image, dialog, cancel, confirm = self._render(
            Theme.settings_stylesheet(), default_is_cancel=True
        )
        def pixel(button):
            point = button.mapTo(dialog, QPoint(button.width() // 2, 6))
            return QColor(image.pixel(point)).name().upper()

        self.assertEqual(pixel(cancel), Colors.PRIMARY.upper())
        self.assertEqual(pixel(confirm), Colors.SURFACE.upper())


if __name__ == "__main__":
    unittest.main()
