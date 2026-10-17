"""Perfil de layout derivado da tela física.

O display de campo é 1024×600 nativo, mas pode ser montado em pé
(área lógica 600×1024). Telas com mínimo horizontal maior que isso cortam,
porque a janela fullscreen não encolhe abaixo do mínimo dos layouts.

A decisão usa a geometria da tela e não o tamanho do widget: o widget nunca
fica estreito enquanto o próprio layout largo impõe o mínimo.
"""

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QGuiApplication

# Larguras lógicas abaixo deste valor usam layouts empilhados (retrato).
COMPACT_MAX_WIDTH = 760


class _LayoutProfile(QObject):
    changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._forced = None
        self._compact = None
        self._watched_app = None
        self._watched_screen = None

    def is_compact(self):
        if self._forced is not None:
            return self._forced
        screen = self._primary_screen()
        if screen is None:
            return False
        return screen.geometry().width() < COMPACT_MAX_WIDTH

    def force(self, compact):
        """Fixa o perfil (testes); ``None`` volta a seguir a tela."""
        self._forced = None if compact is None else bool(compact)
        self.refresh()

    def refresh(self):
        compact = self.is_compact()
        if compact != self._compact:
            self._compact = compact
            self.changed.emit(compact)

    def _primary_screen(self):
        app = QGuiApplication.instance()
        if app is None:
            return None
        if self._watched_app is not app:
            self._watched_app = app
            app.primaryScreenChanged.connect(lambda _screen: self.refresh())
        screen = app.primaryScreen()
        if screen is not None and screen is not self._watched_screen:
            self._watched_screen = screen
            screen.geometryChanged.connect(lambda _rect: self.refresh())
        return screen


layout_profile = _LayoutProfile()


def follow_layout_profile(callback):
    """Aplica o perfil atual e reaplica quando a tela muda de orientação.

    ``callback`` deve ser método de um QObject para a conexão ser desfeita
    automaticamente quando o widget for destruído.
    """
    layout_profile.changed.connect(callback)
    callback(layout_profile.is_compact())
