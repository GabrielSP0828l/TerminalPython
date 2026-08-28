import logging
from pathlib import Path

from PyQt5.QtCore import Qt, QRectF, QSize
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QLabel

from config import PROJECT_ROOT


logger = logging.getLogger(__name__)


def icon_path(filename):
    """Resolve um asset a partir da raiz, independente do diretório corrente."""
    return PROJECT_ROOT / "icon" / filename


def render_colored_svg(path, color, size):
    """Renderiza um SVG como máscara monocromática sem modificar o asset."""
    source = Path(path)
    target = size if isinstance(size, QSize) else QSize(*size)
    if not source.is_file() or target.width() <= 0 or target.height() <= 0:
        logger.error("Ícone SVG indisponível: %s", source)
        return QPixmap()

    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        logger.error("Não foi possível renderizar o SVG: %s", source)
        return QPixmap()

    image = QImage(target, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    source_size = renderer.defaultSize()
    if source_size.isEmpty():
        source_size = target
    scaled = source_size.scaled(target, Qt.KeepAspectRatio)
    bounds = QRectF(
        (target.width() - scaled.width()) / 2,
        (target.height() - scaled.height()) / 2,
        scaled.width(),
        scaled.height(),
    )
    painter = QPainter(image)
    renderer.render(painter, bounds)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(image.rect(), QColor(color))
    painter.end()
    return QPixmap.fromImage(image)


class ColoredSvgLabel(QLabel):
    """Label responsivo que mantém aspecto e recolore fill/stroke em runtime."""

    def __init__(self, filename, color, fallback="!", parent=None):
        super().__init__(parent)
        self._source = icon_path(filename)
        self._color = color
        self._fallback = fallback
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_pixmap()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self):
        target = QSize(max(1, self.width()), max(1, self.height()))
        pixmap = render_colored_svg(self._source, self._color, target)
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText(self._fallback)
            logger.error("Fallback textual aplicado ao ícone: %s", self._source)
        else:
            self.setText("")
            self.setPixmap(pixmap)
