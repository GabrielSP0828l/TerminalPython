import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLabel, QWidget

from app247_terminal.ui.brand import BrandLoader, BrandLogo, FadeStackedWidget, flash
from app247_terminal.ui.styles.tokens import Motion


class BrandKitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_logo_renders_and_only_animates_while_visible(self):
        logo = BrandLogo(animated=True)
        logo.resize(200, 200)
        self.assertFalse(logo.is_running)
        logo.show()
        self.app.processEvents()
        self.assertTrue(logo.is_running)
        image = logo.grab().toImage()
        self.assertGreater(image.pixelColor(100, 100).alpha(), 0)
        logo.hide()
        self.assertFalse(logo.is_running)

    def test_static_logo_never_starts_a_timer(self):
        logo = BrandLogo()
        logo.show()
        self.app.processEvents()
        self.assertFalse(logo.is_running)

    def test_loader_stops_when_hidden(self):
        loader = BrandLoader()
        loader.show()
        self.app.processEvents()
        self.assertTrue(loader.is_running)
        loader.hide()
        self.assertFalse(loader.is_running)

    def test_page_switch_is_synchronous_and_overlay_ignores_touch(self):
        stack = FadeStackedWidget()
        first, second = QLabel("a"), QLabel("b")
        stack.addWidget(first)
        stack.addWidget(second)
        stack.resize(300, 300)
        stack.show()
        self.app.processEvents()
        stack.setCurrentWidget(second)
        self.assertIs(second, stack.currentWidget())
        self.assertEqual(2, stack.count())
        self.assertIs(second, stack.childAt(150, 150))
        QTest.qWait(Motion.BASE + 150)
        self.assertFalse(stack._snapshot.isVisible())

    def test_flash_removes_itself(self):
        card = QWidget()
        card.resize(200, 100)
        card.show()
        self.app.processEvents()
        flash(card, duration=50)
        self.assertEqual(1, len(card.findChildren(QWidget)))
        QTest.qWait(200)
        self.app.processEvents()
        self.assertEqual([], card.findChildren(QWidget))


if __name__ == "__main__":
    unittest.main()
