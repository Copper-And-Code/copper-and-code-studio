"""Cheap checks of the main window, in English and in Italian: no shortcut used twice, no menu
with two entries on the same underlined letter, no text cut off at a common laptop size."""
import pytest
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu

from looks import cut_off, overlapping


@pytest.fixture(params=["en", "it"])
def window(qtbot, request):
    from lvgl_mpy_studio.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.change_language(request.param)
    yield window
    window.change_language("en")


def test_no_shortcut_is_used_twice(window):
    used = {}
    for action in window.findChildren(QAction):
        for sequence in action.shortcuts():
            key = sequence.toString(QKeySequence.PortableText)
            if key:
                used.setdefault(key, set()).add(action.text().replace("&", ""))
    assert {key: names for key, names in used.items() if len(names) > 1} == {}


def test_no_menu_underlines_the_same_letter_twice(window):
    def letter(text):
        index = text.replace("&&", "").find("&")
        return text.replace("&&", "")[index + 1].lower() if index >= 0 and index + 1 < len(text.replace("&&", "")) else None

    clashes = []
    menus = [window.menuBar()] + window.findChildren(QMenu)
    for menu in menus:
        seen = {}
        for action in menu.actions():
            key = letter(action.text()) if not action.isSeparator() and action.isVisible() else None
            if key:
                if key in seen:
                    clashes.append(f"{menu.title() or 'menu bar'}: “{seen[key]}” and “{action.text()}” on {key}")
                seen[key] = action.text()
    assert clashes == []


def test_no_text_is_cut_off_at_1280_by_800(window):
    window.resize(1280, 800)
    window.show()
    for _ in range(5):
        QApplication.processEvents()
    assert cut_off(window) == []
    assert overlapping(window) == []


def visible_texts(window):
    """(where, text) of what the window shows or tells: labels, buttons, menus, docks, tabs,
    column titles, placeholders and tooltips."""
    from PySide6.QtWidgets import QAbstractButton, QDockWidget, QLabel, QLineEdit, QTabWidget, QTreeWidget, QWidget

    found = set()

    def add(where, text):
        text = (text or "").replace("&", "").strip()
        if text:
            found.add((where, text))

    for widget in window.findChildren(QWidget):
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
    for menu in window.findChildren(QMenu):
        add("menu", menu.title())
        for action in menu.actions():
            add("menu entry", action.text())
            add("tooltip", action.toolTip())
    return found


def test_nothing_stays_in_english_after_switching_to_italian(qtbot):
    import json
    from pathlib import Path

    from lvgl_mpy_studio.ui.main_window import MainWindow

    catalog = json.loads((Path(__file__).parents[1] / "lvgl_mpy_studio" / "translations" / "it.json").read_text(encoding="utf-8"))
    window = MainWindow()
    qtbot.addWidget(window)
    window.change_language("it")
    try:
        english = sorted((where, text) for where, text in visible_texts(window) if catalog.get(text, text) != text)
    finally:
        window.change_language("en")
    assert english == []


def test_a_text_the_ide_changed_is_kept_when_the_language_changes(qtbot, tmp_path):
    from lvgl_mpy_studio.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()
    window.files_panel.set_folder(tmp_path / "first")
    window.change_language("it")
    window.files_panel.set_folder(tmp_path / "second")
    window.change_language("en")
    assert window.files_panel.folder_label.text() == "second"
    assert window.files_panel.folder_label.toolTip() == str((tmp_path / "second").resolve())
