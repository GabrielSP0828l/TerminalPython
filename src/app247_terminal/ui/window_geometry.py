"""Registro do tamanho da janela principal (diagnóstico da tela cortada, BUG-066).

Cada mudança de tamanho, de estado (tela cheia) ou da tela vai para o log com a
página atual. No kiosk, se a janela continuar diferente da tela depois que o
compositor assentar, um warning registra a largura mínima e a página mais larga.
"""
import logging

from PyQt5.QtCore import QEvent, QObject, QTimer
from PyQt5.QtWidgets import QApplication

logger = logging.getLogger(__name__)

_ORIGINS = {
    QEvent.Show: "SHOW",
    QEvent.Resize: "RESIZE",
    QEvent.WindowStateChange: "STATE",
}


class WindowGeometryLogger(QObject):
    # Abrir em tela cheia passa por um tamanho intermediário por ~150 ms; só
    # o que persiste além disto é anomalia.
    SETTLE_MS = 2000

    def __init__(self, window, kiosk):
        super().__init__(window)
        self.window = window
        self.kiosk = bool(kiosk)
        self._last = None
        self._screen = None
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(self.SETTLE_MS)
        self._settle.timeout.connect(self.check_settled)
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        origin = _ORIGINS.get(event.type())
        if watched is self.window and origin is not None:
            self._watch_screen()
            self.record(origin)
        return False

    def screen_size(self):
        handle = self.window.windowHandle()
        screen = handle.screen() if handle is not None else None
        screen = screen or QApplication.primaryScreen()
        if screen is None:
            return None
        geometry = screen.geometry()
        return geometry.width(), geometry.height()

    def _watch_screen(self):
        handle = self.window.windowHandle()
        screen = handle.screen() if handle is not None else None
        if screen is None or screen is self._screen:
            return
        self._screen = screen
        screen.geometryChanged.connect(lambda _rect: self.record("SCREEN"))

    def _snapshot(self):
        return (
            self.window.width(), self.window.height(),
            self.screen_size(), self.window.isFullScreen(),
        )

    def _current_page(self):
        stack = getattr(self.window, "stacked_widget", None)
        current = stack.currentWidget() if stack is not None else None
        return type(current).__name__ if current is not None else "-"

    @staticmethod
    def _size_text(size):
        return f"{size[0]}x{size[1]}" if size else "?"

    def record(self, origin):
        snapshot = self._snapshot()
        if snapshot == self._last:
            return
        self._last = snapshot
        width, height, screen, fullscreen = snapshot
        logger.info(
            "[WINDOW] origem=%s janela=%dx%d tela=%s fullscreen=%s pagina=%s",
            origin, width, height, self._size_text(screen), fullscreen,
            self._current_page(),
        )
        self._settle.start()

    def _widest_page(self):
        stack = getattr(self.window, "stacked_widget", None)
        if stack is None or stack.count() == 0:
            return "-", 0
        def min_width(page):
            return max(page.minimumSizeHint().width(), page.minimumWidth())

        pages = [stack.widget(i) for i in range(stack.count())]
        widest = max(pages, key=min_width)
        return type(widest).__name__, min_width(widest)

    def check_settled(self):
        width, height, screen, fullscreen = self._snapshot()
        if not self.kiosk or screen is None or (width, height) == screen:
            return False
        page, page_width = self._widest_page()
        logger.warning(
            "[WINDOW] janela não ocupa a tela janela=%dx%d tela=%s fullscreen=%s "
            "largura_minima=%d pagina_mais_larga=%s(%d) pagina=%s",
            width, height, self._size_text(screen), fullscreen,
            self.window.minimumSizeHint().width(), page, page_width,
            self._current_page(),
        )
        return True
