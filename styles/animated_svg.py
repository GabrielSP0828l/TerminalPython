import logging

from PyQt5.QtCore import QByteArray
from PyQt5.QtSvg import QSvgWidget

from styles.svg_icons import icon_path


logger = logging.getLogger(__name__)


class AnimatedSvgWidget(QSvgWidget):
    """Carrega o SVG original, preservando sua animação SMIL em QSvgWidget."""

    def __init__(self, filename, color=None, parent=None):
        super().__init__(parent)
        self.source = icon_path(filename)
        self._load(color)

    def _load(self, color):
        try:
            data = self.source.read_bytes()
        except OSError:
            logger.exception("Não foi possível ler o SVG animado: %s", self.source)
            return
        if color:
            replacement = color.encode("ascii")
            data = data.replace(b"#490FFF", replacement).replace(b"#490fff", replacement)
        self.load(QByteArray(data))
        if not self.renderer().isValid():
            logger.error("SVG animado inválido: %s", self.source)
        elif not self.renderer().animated():
            logger.warning("SVG carregado sem animação reconhecida: %s", self.source)

    @property
    def is_animated(self):
        return self.renderer().isValid() and self.renderer().animated()
