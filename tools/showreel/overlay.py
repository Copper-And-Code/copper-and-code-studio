"""What the showreel draws over the grabbed window: balloons, highlight, cursor, cards, caption.

Everything is painted with QPainter on a copy of the grabbed QImage; nothing is added to the
IDE's widgets. Coordinates are those of the window.
"""
import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen, QPolygonF

# One light palette, readable on the light IDE and on the dark apps.
INK = QColor("#1d2330")
PAPER = QColor("#ffffff")
ACCENT = QColor("#f2a900")            # outline of the balloon and of the highlight
SHADOW = QColor(0, 0, 0, 70)
CARD_TEXT = QColor("#ffffff")
CARD_SOFT = QColor("#c9d1e0")
CAPTION = "Scripted replay, sped up"
URL = "github.com/Copper-And-Code/copper-and-code-studio"

FADE_FRAMES = 6
BALLOON_FONT = 20                     # pixels
BALLOON_WIDTH = 460                   # at most, before wrapping
BALLOON_PADDING = 16
BALLOON_RADIUS = 14
TAIL = 26                             # distance between the balloon and its anchor
MARGIN = 16


def _font(pixels, bold=False):
    font = QFont()
    font.setPixelSize(pixels)
    font.setBold(bold)
    return font


def ease(t):
    """Ease-in-out on [0, 1]."""
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


class Balloon:
    def __init__(self, text, anchor=None):
        self.text = text
        self.anchor = anchor            # name, resolved to a rect by the player
        self.rect = None                # anchor rect in window coordinates, or None
        self.alpha = 0.0
        self.target = 1.0
        self.frames = 0                 # frames shown at full or partial opacity

    @property
    def gone(self):
        return self.target == 0 and self.alpha <= 0


class Cursor:
    def __init__(self):
        self.pos = None                 # QPointF, None while hidden
        self.pressed = False
        self.ghost = None               # (QIcon or None, text) carried while dragging


class Overlay:
    def __init__(self, size):
        self.width, self.height = size
        self.balloons = []              # the current one last; older ones fading out
        self.cursor = Cursor()
        self.caption = True

    # ---- State ----

    @property
    def balloon(self):
        return self.balloons[-1] if self.balloons and self.balloons[-1].target else None

    def show_balloon(self, text, anchor=None):
        current = self.balloon
        if current is not None and current.text == text and current.anchor == anchor:
            return current
        self.hide_balloon()
        self.balloons.append(Balloon(text, anchor))
        return self.balloons[-1]

    def hide_balloon(self):
        for balloon in self.balloons:
            balloon.target = 0.0

    @property
    def animating(self):
        return any(balloon.alpha != balloon.target for balloon in self.balloons if balloon.rect is not None or balloon.anchor is None)

    def advance(self, frames):
        """Count repeated frames as time on screen for the balloons that are fully shown."""
        for balloon in self.balloons:
            if balloon.alpha > 0 and balloon.alpha == balloon.target:
                balloon.frames += frames

    def tick(self):
        step = 1.0 / FADE_FRAMES
        for balloon in self.balloons:
            if balloon.anchor is not None and balloon.rect is None and balloon.target:
                continue                # waiting for its anchor to appear
            if balloon.alpha < balloon.target:
                balloon.alpha = min(balloon.target, balloon.alpha + step)
            elif balloon.alpha > balloon.target:
                balloon.alpha = max(balloon.target, balloon.alpha - step)
            if balloon.alpha > 0:
                balloon.frames += 1
        self.balloons = [balloon for balloon in self.balloons if not balloon.gone]

    # ---- Drawing ----

    def draw(self, image):
        frame = image.convertToFormat(QImage.Format_RGB32)
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        for balloon in self.balloons:
            if balloon.alpha > 0:
                if balloon.rect is not None:
                    self._highlight(painter, balloon.rect, balloon.alpha)
                self._balloon(painter, balloon)
        if self.caption:
            self._caption(painter)
        if self.cursor.pos is not None:
            self._cursor(painter)
        painter.end()
        return frame

    def _highlight(self, painter, rect, alpha):
        color = QColor(ACCENT)
        color.setAlphaF(alpha)
        painter.setPen(QPen(color, 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(rect).adjusted(-3, -3, 3, 3), 8, 8)

    def _layout(self, text, width):
        metrics = QFontMetrics(_font(BALLOON_FONT))
        bounds = metrics.boundingRect(QRect(0, 0, width - 2 * BALLOON_PADDING, 1000), Qt.TextWordWrap, text)
        return bounds.width() + 2 * BALLOON_PADDING, bounds.height() + 2 * BALLOON_PADDING

    def place(self, text, anchor):
        """The balloon rect and the point its tail touches, beside the anchor where there is most room."""
        if anchor is None:
            w, h = self._layout(text, BALLOON_WIDTH)
            return QRectF((self.width - w) / 2, 120, w, h), None
        a = QRectF(anchor)
        room = {
            "right": self.width - a.right() - TAIL - MARGIN,
            "left": a.left() - TAIL - MARGIN,
            "below": self.height - a.bottom() - TAIL - MARGIN,
            "above": a.top() - TAIL - MARGIN,
        }
        # A side where the text fits on one or two wide lines first, then any side with room.
        for side, least in [(side, least) for least in (360, 220) for side in sorted(room, key=room.get, reverse=True)]:
            horizontal = side in ("right", "left")
            width = min(BALLOON_WIDTH, room[side]) if horizontal else BALLOON_WIDTH
            if width < least:
                continue
            w, h = self._layout(text, int(width))
            if not horizontal and h > room[side]:
                continue
            if side == "right":
                x, y = a.right() + TAIL, a.center().y() - h / 2
            elif side == "left":
                x, y = a.left() - TAIL - w, a.center().y() - h / 2
            elif side == "below":
                x, y = a.center().x() - w / 2, a.bottom() + TAIL
            else:
                x, y = a.center().x() - w / 2, a.top() - TAIL - h
            x = min(max(MARGIN, x), self.width - MARGIN - w)
            y = min(max(MARGIN, y), self.height - MARGIN - h)
            box = QRectF(x, y, w, h)
            tip = {
                "right": QPointF(a.right(), min(max(a.top() + 8, box.center().y()), a.bottom() - 8)),
                "left": QPointF(a.left(), min(max(a.top() + 8, box.center().y()), a.bottom() - 8)),
                "below": QPointF(min(max(a.left() + 8, box.center().x()), a.right() - 8), a.bottom()),
                "above": QPointF(min(max(a.left() + 8, box.center().x()), a.right() - 8), a.top()),
            }[side]
            return box, tip
        # No room around it (a large anchor): inside, near its top, pointing down at it.
        w, h = self._layout(text, BALLOON_WIDTH)
        box = QRectF(a.center().x() - w / 2, a.top() + 24, w, h)
        return box, QPointF(a.center().x(), box.bottom() + TAIL)

    def _balloon(self, painter, balloon):
        box, tip = self.place(balloon.text, balloon.rect)
        path = QPainterPath()
        path.addRoundedRect(box, BALLOON_RADIUS, BALLOON_RADIUS)
        if tip is not None:
            center = box.center()
            angle = math.atan2(tip.y() - center.y(), tip.x() - center.x())
            base = _edge_point(box, tip)
            spread = 13
            normal = QPointF(-math.sin(angle) * spread, math.cos(angle) * spread)
            tail = QPainterPath()
            tail.addPolygon(QPolygonF([base + normal, tip, base - normal, base + normal]))
            path = path.united(tail)
        painter.save()
        painter.setOpacity(balloon.alpha)
        painter.translate(3, 5)
        painter.fillPath(path, SHADOW)
        painter.translate(-3, -5)
        painter.setPen(QPen(ACCENT, 2.5))
        painter.setBrush(PAPER)
        painter.drawPath(path)
        painter.setPen(INK)
        painter.setFont(_font(BALLOON_FONT))
        painter.drawText(box.adjusted(BALLOON_PADDING, BALLOON_PADDING, -BALLOON_PADDING, -BALLOON_PADDING), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter, balloon.text)
        painter.restore()

    def _caption(self, painter):
        painter.save()
        painter.setFont(_font(13))
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(CAPTION) + 20
        box = QRectF(self.width - w - 12, self.height - 26 - 12, w, 26)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(29, 35, 48, 190))
        painter.drawRoundedRect(box, 13, 13)
        painter.setPen(PAPER)
        painter.drawText(box, Qt.AlignCenter, CAPTION)
        painter.restore()

    def _cursor(self, painter):
        cursor = self.cursor
        painter.save()
        painter.translate(cursor.pos)
        if cursor.ghost is not None:
            icon, text = cursor.ghost
            painter.setOpacity(0.85)
            painter.setFont(_font(15))
            w = painter.fontMetrics().horizontalAdvance(text) + 40
            box = QRectF(14, 14, w, 28)
            painter.setPen(QPen(ACCENT, 1.5))
            painter.setBrush(PAPER)
            painter.drawRoundedRect(box, 6, 6)
            if icon is not None:
                icon.paint(painter, QRect(20, 19, 18, 18))
            painter.setPen(INK)
            painter.drawText(box.adjusted(30, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, text)
            painter.setOpacity(1.0)
        scale = 1.25 if not cursor.pressed else 1.05
        if cursor.pressed:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(242, 169, 0, 110))
            painter.drawEllipse(QPointF(0, 0), 16, 16)
        painter.scale(scale, scale)
        arrow = QPolygonF([QPointF(x, y) for x, y in ((0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12), (13, 12))])
        painter.setPen(QPen(QColor("#000000"), 1.3))
        painter.setBrush(QColor("#ffffff"))
        painter.drawPolygon(arrow)
        painter.restore()

    # ---- Cards ----

    def card(self, background, title, subtitle="", lines=()):
        """A title or end card: the background blurred and darkened, the text in the middle."""
        small = background.scaled(max(1, self.width // 16), max(1, self.height // 16), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        frame = small.scaled(self.width, self.height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.fillRect(frame.rect(), QColor(14, 18, 28, 200))
        y = self.height / 2 - 70 - 18 * len(lines)
        painter.setPen(CARD_TEXT)
        painter.setFont(_font(48, bold=True))
        painter.drawText(QRectF(0, y, self.width, 70), Qt.AlignCenter, title)
        y += 80
        if subtitle:
            painter.setPen(CARD_SOFT)
            painter.setFont(_font(26))
            painter.drawText(QRectF(0, y, self.width, 40), Qt.AlignCenter, subtitle)
            y += 70
        painter.setFont(_font(22))
        for line in lines:
            painter.setPen(CARD_SOFT if line != URL else ACCENT)
            painter.drawText(QRectF(0, y, self.width, 36), Qt.AlignCenter, line)
            y += 40
        painter.end()
        return frame


def blend(first, second, amount):
    """second over first with opacity amount, for cross-fades."""
    frame = first.convertToFormat(QImage.Format_RGB32)
    painter = QPainter(frame)
    painter.setOpacity(amount)
    painter.drawImage(0, 0, second)
    painter.end()
    return frame


def _edge_point(box, toward):
    """Where the line from the centre of box to toward leaves box, pulled inside a little."""
    center = box.center()
    dx, dy = toward.x() - center.x(), toward.y() - center.y()
    if dx == 0 and dy == 0:
        return center
    scale = min(abs((box.width() / 2 - BALLOON_RADIUS) / dx) if dx else math.inf,
                abs((box.height() / 2 - 6) / dy) if dy else math.inf)
    return QPointF(center.x() + dx * scale, center.y() + dy * scale)
