"""Kit de identidade do 24/7 Terminal: logotipo, loader e microanimações.

Tudo aqui é pintado com QPainter sobre pixmaps em cache; nenhum efeito gráfico
(blur, sombra, QGraphicsOpacityEffect) é usado, por causa do Raspberry Pi.
Animações contínuas só rodam enquanto o widget está visível e nenhuma delas
captura toque ou foco: o leitor de código de barras nunca é interrompido.

``APP247_ANIMATIONS=0`` desliga todo o movimento sem alterar o layout.
"""

import logging
import math
import os

from PyQt5.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
)
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QStackedWidget, QWidget

from app247_terminal.ui.styles.tokens import Colors, Motion, Radius
from app247_terminal.utils.resources import image_path


logger = logging.getLogger(__name__)

LOGO_FILE = "logo.png"
# Área do PNG 1024×1024 que contém o desenho; o resto é margem transparente.
_LOGO_CONTENT = QRect(196, 206, 654, 530)
_LOGO_PULSE_GROWTH = 0.05
_logo_cache = None


def _logo_pixmap():
    """Decodifica o PNG uma única vez; todas as instâncias dividem o recorte."""
    global _logo_cache
    if _logo_cache is None:
        try:
            _logo_cache = QPixmap(str(image_path(LOGO_FILE))).copy(_LOGO_CONTENT)
        except FileNotFoundError:
            logger.error("Logotipo ausente: %s", LOGO_FILE)
            _logo_cache = QPixmap()
    return _logo_cache


def animations_enabled():
    return os.environ.get("APP247_ANIMATIONS", "1") != "0"


def _loop(target, name, duration, parent):
    animation = QPropertyAnimation(target, name, parent)
    animation.setDuration(duration)
    animation.setLoopCount(-1)
    return animation


class BrandLogo(QWidget):
    """Logotipo oficial (PNG); com ``animated`` ele respira num pulso suave."""

    def __init__(self, animated=False, parent=None):
        super().__init__(parent)
        self._animated = bool(animated) and animations_enabled()
        self._pulse = 0.0
        self._scaled = QPixmap()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._beat = _loop(self, b"pulse", Motion.LOGO_PULSE, self)
        self._beat.setKeyValueAt(0.0, 0.0)
        self._beat.setKeyValueAt(0.5, 1.0)
        self._beat.setKeyValueAt(1.0, 0.0)
        self._beat.setEasingCurve(QEasingCurve.InOutSine)

    def sizeHint(self):
        return QSize(200, 160)

    def minimumSizeHint(self):
        return QSize(50, 40)

    @property
    def is_running(self):
        return self._beat.state() == QAbstractAnimation.Running

    def _get_pulse(self):
        return self._pulse

    def _set_pulse(self, value):
        # 16 degraus por meia batida: ~13 repinturas por segundo.
        value = round(value * 16) / 16
        if value != self._pulse:
            self._pulse = value
            self.update()

    pulse = pyqtProperty(float, _get_pulse, _set_pulse)

    def showEvent(self, event):
        super().showEvent(event)
        if self._animated:
            self._beat.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._beat.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scaled = QPixmap()

    def paintEvent(self, _event):
        source = _logo_pixmap()
        if source.isNull():
            return
        if self._scaled.isNull():
            # Reserva a folga do pulso para o desenho nunca ser cortado.
            room = self.size() / (1.0 + _LOGO_PULSE_GROWTH)
            self._scaled = source.scaled(
                room, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        painter = QPainter(self)
        painter.translate(self.width() / 2, self.height() / 2)
        if self._pulse:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            factor = 1.0 + _LOGO_PULSE_GROWTH * self._pulse
            painter.scale(factor, factor)
        painter.drawPixmap(
            QPoint(-self._scaled.width() // 2, -self._scaled.height() // 2),
            self._scaled,
        )
        painter.end()


class BrandLoader(QWidget):
    """Indicador de espera: dois arcos, azul e laranja, em ciclo contínuo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._turn = _loop(self, b"angle", Motion.LOADER_TURN, self)
        self._turn.setStartValue(0.0)
        self._turn.setEndValue(360.0)

    def sizeHint(self):
        return QSize(96, 96)

    @property
    def is_running(self):
        return self._turn.state() == QAbstractAnimation.Running

    def _get_angle(self):
        return self._angle

    def _set_angle(self, value):
        value = round(value / 9) * 9
        if value != self._angle:
            self._angle = value
            self.update()

    angle = pyqtProperty(float, _get_angle, _set_angle)

    def showEvent(self, event):
        super().showEvent(event)
        if animations_enabled():
            self._turn.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._turn.stop()

    def paintEvent(self, _event):
        side = min(self.width(), self.height())
        width = max(3.0, side * 0.1)
        rect = QRectF(
            (self.width() - side) / 2 + width,
            (self.height() - side) / 2 + width,
            side - 2 * width,
            side - 2 * width,
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        start = -self._angle
        for offset, color in ((0, Colors.BRAND_BLUE), (180, Colors.BRAND_ORANGE)):
            painter.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(rect, int((start + offset) * 16), 130 * 16)
        painter.end()


class AnimatedCheck(QWidget):
    """Confirmação desenhada em traço: círculo e depois o check."""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._progress = 1.0
        self._draw = QPropertyAnimation(self, b"progress", self)
        self._draw.setDuration(Motion.SLOW + Motion.BASE)
        self._draw.setStartValue(0.0)
        self._draw.setEndValue(1.0)
        self._draw.setEasingCurve(QEasingCurve.OutCubic)

    def _get_progress(self):
        return self._progress

    def _set_progress(self, value):
        self._progress = value
        self.update()

    progress = pyqtProperty(float, _get_progress, _set_progress)

    def play(self):
        if animations_enabled():
            self._draw.stop()
            self._draw.start()
        else:
            self._set_progress(1.0)

    def paintEvent(self, _event):
        side = min(self.width(), self.height())
        width = max(4.0, side * 0.08)
        left = (self.width() - side) / 2
        top = (self.height() - side) / 2
        rect = QRectF(left + width, top + width, side - 2 * width, side - 2 * width)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(
            QPen(self._color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        ring = min(1.0, self._progress / 0.6)
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * ring))
        mark = max(0.0, (self._progress - 0.5) / 0.5)
        if mark > 0:
            points = (
                (left + side * 0.30, top + side * 0.52),
                (left + side * 0.45, top + side * 0.66),
                (left + side * 0.71, top + side * 0.38),
            )
            first = math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1])
            second = math.hypot(points[2][0] - points[1][0], points[2][1] - points[1][1])
            drawn = mark * (first + second)
            path = QPainterPath()
            path.moveTo(*points[0])
            ratio = min(1.0, drawn / first)
            path.lineTo(
                points[0][0] + (points[1][0] - points[0][0]) * ratio,
                points[0][1] + (points[1][1] - points[0][1]) * ratio,
            )
            if drawn > first:
                ratio = (drawn - first) / second
                path.lineTo(
                    points[1][0] + (points[2][0] - points[1][0]) * ratio,
                    points[1][1] + (points[2][1] - points[1][1]) * ratio,
                )
            painter.drawPath(path)
        painter.end()


class _Fading(QWidget):
    """Camada que some sozinha; nunca recebe toque nem foco."""

    def __init__(self, parent, duration):
        super().__init__(parent)
        self._opacity = 1.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._fade = QPropertyAnimation(self, b"opacity", self)
        self._fade.setDuration(duration)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(self._finished)

    def _get_opacity(self):
        return self._opacity

    def _set_opacity(self, value):
        self._opacity = value
        self.update()

    opacity = pyqtProperty(float, _get_opacity, _set_opacity)

    def _finished(self):
        self.hide()

    def play(self):
        self._fade.stop()
        self._set_opacity(1.0)
        self.show()
        self.raise_()
        self._fade.start()


class _Flash(_Fading):
    def __init__(self, parent, color, duration):
        super().__init__(parent, duration)
        self._color = QColor(color)
        self.setGeometry(parent.rect())

    def _finished(self):
        self.hide()
        self.deleteLater()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self._opacity)
        painter.setPen(QPen(self._color, 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(2, 2, -2, -2), Radius.CARD, Radius.CARD
        )
        painter.end()


def flash(widget, color=Colors.BRAND_ORANGE, duration=Motion.SLOW):
    """Contorno na cor da marca que some em ``duration`` ms sobre ``widget``."""
    if not animations_enabled() or not widget.isVisible():
        return
    _Flash(widget, color, duration).play()


def shake(widget, distance=10, duration=Motion.BASE):
    """Balanço horizontal curto; termina exatamente na posição do layout."""
    if not animations_enabled() or not widget.isVisible():
        return
    running = widget.findChild(QPropertyAnimation, "brandShake")
    if running is not None:
        return
    origin = widget.pos()
    animation = QPropertyAnimation(widget, b"pos", widget)
    animation.setObjectName("brandShake")
    animation.setDuration(duration)
    animation.setKeyValueAt(0.0, origin)
    for step, direction in ((0.2, -1), (0.4, 1), (0.6, -0.6), (0.8, 0.6)):
        animation.setKeyValueAt(step, origin + QPoint(int(distance * direction), 0))
    animation.setKeyValueAt(1.0, origin)
    animation.finished.connect(animation.deleteLater)
    animation.start()


class _Snapshot(_Fading):
    def __init__(self, parent):
        super().__init__(parent, Motion.BASE)
        self.pixmap = QPixmap()
        self.hide()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        painter.drawPixmap(0, 0, self.pixmap)
        painter.end()


class FadeStackedWidget(QStackedWidget):
    """QStackedWidget cuja troca de página é imediata, com fade só visual.

    A página nova assume índice, foco e toque na mesma chamada; por cima dela
    uma captura da página anterior desaparece em ``Motion.BASE`` ms.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot = _Snapshot(self)

    def setCurrentIndex(self, index):
        self._capture(index)
        super().setCurrentIndex(index)

    def setCurrentWidget(self, widget):
        self._capture(self.indexOf(widget))
        super().setCurrentWidget(widget)

    def _capture(self, index):
        if (
            index < 0
            or index == self.currentIndex()
            or not animations_enabled()
            or not self.isVisible()
        ):
            return
        self._snapshot.pixmap = self.grab()
        self._snapshot.setGeometry(self.rect())
        self._snapshot.play()
