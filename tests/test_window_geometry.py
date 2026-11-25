"""BUG-066: o tamanho da janela fica registrado para diagnosticar tela cortada."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QStackedWidget, QVBoxLayout, QWidget

from app247_terminal.ui.window_geometry import WindowGeometryLogger

LOGGER = "app247_terminal.ui.window_geometry"


class Page(QWidget):
    def __init__(self, width):
        super().__init__()
        self.setMinimumWidth(width)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.stacked_widget = QStackedWidget(self)
        QVBoxLayout(self).addWidget(self.stacked_widget)
        self.stacked_widget.addWidget(Page(300))
        self.stacked_widget.addWidget(Page(450))


class WindowGeometryLoggerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def build(self, kiosk=True, screen=(600, 1024)):
        window = Window()
        geometry = WindowGeometryLogger(window, kiosk=kiosk)
        geometry.screen_size = lambda: screen
        self.addCleanup(window.deleteLater)
        return window, geometry

    def test_each_change_is_logged_once_with_screen_and_page(self):
        window, geometry = self.build()
        window.resize(600, 1024)
        with self.assertLogs(LOGGER, "INFO") as logs:
            geometry.record("RESIZE")
            geometry.record("RESIZE")
        self.assertEqual(1, len(logs.output))
        self.assertIn("janela=600x1024 tela=600x1024", logs.output[0])
        self.assertIn("pagina=Page", logs.output[0])

    def test_resize_event_is_recorded(self):
        window, _geometry = self.build()
        window.show()
        with self.assertLogs(LOGGER, "INFO") as logs:
            window.resize(658, 1024)
        self.assertIn("origem=RESIZE janela=658x1024", "\n".join(logs.output))

    def test_kiosk_window_smaller_than_screen_warns_with_widest_page(self):
        window, geometry = self.build()
        window.resize(658, 868)
        with self.assertLogs(LOGGER, "WARNING") as logs:
            self.assertTrue(geometry.check_settled())
        self.assertIn("janela=658x868 tela=600x1024", logs.output[0])
        self.assertIn("pagina_mais_larga=Page(450)", logs.output[0])

    def test_matching_window_or_dev_mode_does_not_warn(self):
        window, geometry = self.build()
        window.resize(600, 1024)
        self.assertFalse(geometry.check_settled())

        dev_window, dev = self.build(kiosk=False)
        dev_window.resize(1024, 600)
        self.assertFalse(dev.check_settled())


if __name__ == "__main__":
    unittest.main()
