"""Checks of the looks that need no reference picture: text cut off, widgets covering each other
or sticking out, text with too little contrast. Used by tests/test_window_checks.py in the CI and
by the suites of tests/manual.
"""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QToolBar, QWidget

def cut_off(root):
    """The texts under root that do not fit their widget: labels, buttons, columns of lists."""
    from PySide6.QtWidgets import QAbstractButton, QLabel, QTreeView

    found = []
    for widget in root.findChildren(QWidget):
        # QWidget.width(widget): a widget may have a field called width.
        if not widget.isVisibleTo(root) or QWidget.width(widget) <= 0 or root.isVisible() and widget.visibleRegion().isEmpty():
            continue                           # not what is out of sight, such as a dock behind another
        if isinstance(widget, QLabel) and widget.text() and widget.pixmap().isNull():
            if widget.wordWrap():
                needed = widget.heightForWidth(QWidget.width(widget))
                if needed > QWidget.height(widget) + 1:
                    found.append(f"label “{plain(widget.text())}” needs {needed} px of height, has {QWidget.height(widget)}")
            elif widget.sizeHint().width() > QWidget.width(widget) + 1 and not widget.hasScaledContents():
                found.append(f"label “{plain(widget.text())}” needs {widget.sizeHint().width()} px, has {QWidget.width(widget)}")
        elif isinstance(widget, QAbstractButton) and widget.text() and not isinstance(widget.parentWidget(), QToolBar):
            if widget.sizeHint().width() > QWidget.width(widget) + 1:
                found.append(f"button “{plain(widget.text())}” needs {widget.sizeHint().width()} px, has {QWidget.width(widget)}")
        elif isinstance(widget, QTreeView) and not isinstance(widget.window(), QFileDialog) and widget.model() is not None and widget.model().rowCount():
            header = widget.header()
            if header.isHidden():
                continue
            for column in range(header.count()):
                if header.isSectionHidden(column) or column == header.count() - 1 and header.stretchLastSection():
                    continue
                needed = widget.sizeHintForColumn(column)
                if needed > header.sectionSize(column) + 1:
                    name = widget.model().headerData(column, Qt.Horizontal) or column
                    found.append(f"column “{name}” of a list cuts its text: needs {needed} px, has {header.sectionSize(column)}")
    return found


def plain(text):
    return re.sub(r"<[^>]+>", "", text).replace("&", "")[:60]


def overlapping(root):
    """Widgets placed by the same layout that cover each other, or stick out of their parent."""
    found = []
    for parent in [root] + root.findChildren(QWidget):
        layout = parent.layout()
        if layout is None or not parent.isVisibleTo(root) and parent is not root:
            continue
        children = [layout.itemAt(index).widget() for index in range(layout.count())]
        # Only what shows: a main window parks the docks tabbed behind others outside itself.
        children = [child for child in children if child is not None and child.isVisibleTo(root) and QWidget.width(child) > 0 and QWidget.height(child) > 0 and not child.visibleRegion().isEmpty()]
        inside = parent.rect()
        for index, child in enumerate(children):
            geometry = child.geometry()
            if not inside.contains(geometry):
                found.append(f"{name_of(child)} sticks out of {name_of(parent)}: {rect_text(geometry)} in {rect_text(inside)}")
            for other in children[index + 1:]:
                common = geometry.intersected(other.geometry())
                if common.width() > 1 and common.height() > 1:
                    found.append(f"{name_of(child)} and {name_of(other)} cover each other in {name_of(parent)}")
    return found


def rect_text(rect):
    return f"{rect.width()}×{rect.height()} at {rect.x()},{rect.y()}"


def name_of(widget):
    text = widget.text() if hasattr(widget, "text") and callable(widget.text) else ""
    text = text if isinstance(text, str) else ""
    return type(widget).__name__ + (f" “{plain(text)}”" if text else "") + (f" {widget.objectName()}" if widget.objectName() else "")


def luminance(color):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def low_contrast(root, least=3.0):
    """Enabled labels whose text has too little contrast on what is drawn behind it, measured on
    their picture: the background is the commonest colour, the text the farthest from it."""
    from collections import Counter

    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QLabel

    found = []
    for label in root.findChildren(QLabel):
        if not label.isVisibleTo(root) or not label.isEnabled() or not label.text().strip() or not label.pixmap().isNull():
            continue
        image = label.grab().toImage().convertToFormat(QImage.Format_RGB32)
        if image.width() < 2 or image.height() < 2:
            continue
        colors = Counter(image.pixel(x, y) for x in range(0, image.width(), 2) for y in range(0, image.height(), 2))
        if len(colors) < 2:
            continue
        background = QColor(colors.most_common(1)[0][0])
        text = max((QColor(pixel) for pixel in colors), key=lambda color: abs(luminance(color) - luminance(background)))
        ratio = contrast(background, text)
        if ratio < least:
            found.append(f"label “{plain(label.text())}”: contrast {ratio:.1f}, text {text.name()} on {background.name()}")
    return found


def visible_texts(root):
    """(where, text) of what root shows or tells: labels, buttons, menus, docks, tabs, column
    titles, placeholders and tooltips."""
    from PySide6.QtWidgets import QAbstractButton, QDockWidget, QLabel, QLineEdit, QMenu, QTabWidget, QTreeWidget

    found = set()

    def add(where, text):
        text = (text or "").replace("&", "").strip()
        if text:
            found.add((where, text))

    for widget in [root] + root.findChildren(QWidget):
        if isinstance(widget, (QAbstractButton, QLabel)):
            add(type(widget).__name__, widget.text())
        if isinstance(widget, QDockWidget):
            add("dock", widget.windowTitle())
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                add("tab", widget.tabText(index))
        if isinstance(widget, QTreeWidget):
            header = widget.headerItem()
            for index in range(header.columnCount()):
                add("column", header.text(index))
        if isinstance(widget, QLineEdit):
            add("placeholder", widget.placeholderText())
        add("tooltip", widget.toolTip())
        add("accessible name", widget.accessibleName())
    for menu in root.findChildren(QMenu):
        add("menu", menu.title())
        for action in menu.actions():
            add("menu entry", action.text())
            add("tooltip", action.toolTip())
    if root.isWindow():
        add("title", root.windowTitle())
    return found


def _catalog():
    import json
    from pathlib import Path

    return json.loads((Path(__file__).parents[1] / "lvgl_mpy_studio" / "translations" / "it.json").read_text(encoding="utf-8"))


def english_left(root):
    """Texts root shows in English that have an Italian translation: to call with Italian chosen."""
    catalog = _catalog()
    return sorted((where, text) for where, text in visible_texts(root) if catalog.get(text, text) != text)


def italian_left(root):
    """Texts root shows in Italian that come from an English one: to call with English chosen."""
    catalog = _catalog()
    english = {value: key for key, value in catalog.items() if value != key and value not in catalog}
    return sorted((where, text) for where, text in visible_texts(root) if text in english)


def nameless(root):
    """Buttons, fields and lists without a name for a screen reader: no text, tooltip or accessible name."""
    from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QAbstractSpinBox, QComboBox, QHeaderView, QLineEdit, QPlainTextEdit, QTabBar, QToolButton

    found = []
    for widget in root.findChildren(QWidget):
        if not widget.isVisibleTo(root) or not widget.isEnabled() or isinstance(widget.parentWidget(), QTabBar) or isinstance(widget, QHeaderView):
            continue                           # a header is part of its list, and its columns have their texts
        interactive = isinstance(widget, (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox, QAbstractItemView, QPlainTextEdit))
        if not interactive or widget.objectName().startswith("qt_"):
            continue
        text = widget.text() if isinstance(widget, QAbstractButton) else ""
        named = (text or "").replace("&", "").strip() or widget.toolTip().strip() or widget.accessibleName().strip()
        if isinstance(widget, QLineEdit):
            named = named or widget.placeholderText().strip()
        if isinstance(widget, QToolButton) and widget.defaultAction() is not None:
            named = named or widget.defaultAction().text().strip()
        if not named:
            found.append(f"{type(widget).__name__} in {type(widget.parentWidget()).__name__}" + (f" ({widget.objectName()})" if widget.objectName() else ""))
    return found
