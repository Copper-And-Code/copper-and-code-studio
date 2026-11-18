"""The IDE without a mouse, and controls that a screen reader can name.

    pytest tests/manual/test_keyboard_only.py --manual

- Tab, from the canvas, reaches the toolbox, the project tree, the Properties panel and the code
  editor; Shift+Tab goes back; the focus is caught nowhere it cannot leave, except a terminal,
  where Tab belongs to the program, as in every terminal.
- Each menu of the menu bar opens with Alt and its underlined letter.
- Ctrl+Tab and Ctrl+Shift+Tab move between the tabs of pages, Code and Simulator.
- Every button, field and list of the window has a name: its text, its tooltip or its
  accessible name. A button with an icon and nothing else says nothing to a screen reader.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QPlainTextEdit,
)

from lvgl_mpy_studio.ui.terminal import TerminalView
from looks import nameless
from sweep import Example, Sweep, wait

pytestmark = pytest.mark.manual


def owner(widget, window):
    """The named place a focused widget belongs to."""
    places = {
        "canvas": window._active_designer(),
        "toolbox": window.toolbox_panel,
        "project tree": window.project_tree,
        "Properties": window.properties,
        "code editor": window.code_panel,
        "Files": window.files_panel,
        "Device Console": window.device_console,
        "Output": window.output,
        "Errors": window.errors,
        "Components": window.component_tray,
    }
    for name, place in places.items():
        if place is not None and (widget is place or place.isAncestorOf(widget)):
            return name
    return type(widget).__name__


@pytest.fixture
def ide(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        for dock in window.findChildren(QDockWidget):
            dock.show()
        window.activateWindow()
        QApplication.processEvents()
        yield sweep
        window.document.undo_stack.setClean()


def walk(window, start, key, modifiers=Qt.NoModifier, steps=80):
    start.setFocus(Qt.TabFocusReason)
    QApplication.processEvents()
    seen = []
    for _ in range(steps):
        focus = QApplication.focusWidget()
        if focus is None:
            break
        seen.append((owner(focus, window), focus))
        if isinstance(focus, TerminalView):
            break                              # Tab belongs to the program there
        QTest.keyClick(focus, key, modifiers)
        QApplication.processEvents()
    return seen


def test_tab_reaches_the_places_and_is_caught_nowhere(ide):
    window = ide.window
    view = window._active_designer()
    if QApplication.focusWidget() is None:
        view.setFocus()
        if QApplication.focusWidget() is None:
            pytest.skip("this platform gives no focus")
    forward = walk(window, view, Qt.Key_Tab)
    places = [name for name, _widget in forward]
    problems = []
    for wanted in ("toolbox", "project tree", "Properties"):
        if wanted not in places:
            problems.append(f"Tab from the canvas never reaches the {wanted}: {list(dict.fromkeys(places))}")
    last = forward[-1][1] if forward else None
    if forward and not isinstance(last, TerminalView):
        widgets = [widget for _name, widget in forward]
        if widgets.count(widgets[-1]) < 2 and len(set(map(id, widgets))) < 4:
            problems.append(f"Tab is caught in {places[-1]}")
        stuck = [name for (name, widget), (_next, after) in zip(forward, forward[1:]) if widget is after and not isinstance(widget, (QPlainTextEdit,))]
        if stuck:
            problems.append(f"Tab does not leave {stuck[0]}")
    window.tabs.setCurrentWidget(window.code_panel)
    QApplication.processEvents()
    editor_places = [name for name, _widget in walk(window, window.code_panel.object_combo, Qt.Key_Tab)]
    if "code editor" not in editor_places:
        problems.append("Tab does not reach the code editor")
    backward = [name for name, _widget in walk(window, window.project_tree, Qt.Key_Backtab)]
    if len(set(backward)) < 2:
        problems.append(f"Shift+Tab from the project tree does not move: {backward[:5]}")
    assert not problems, "\n".join(problems)


def test_every_menu_opens_with_alt_and_its_letter(ide):
    window = ide.window
    ide.menus.stop()                           # the menus must stay open here, to be seen open
    bar = window.menuBar()
    problems = []
    for action in bar.actions():
        text = action.text()
        index = text.find("&")
        if index < 0 or index + 1 >= len(text):
            problems.append(f"the menu {text!r} has no underlined letter")
            continue
        letter = text[index + 1]
        window._active_designer().setFocus()
        QApplication.processEvents()
        QTest.keyClick(window, Qt.Key(ord(letter.upper())), Qt.AltModifier)
        opened = wait(lambda: action.menu().isVisible(), 1)
        if not opened:
            problems.append(f"Alt+{letter} does not open {text.replace('&', '')}")
        for _ in range(2):                     # Escape closes the menu, then leaves the menu bar
            QTest.keyClick(QApplication.activePopupWidget() or bar, Qt.Key_Escape)
            QApplication.processEvents()
        wait(lambda: not action.menu().isVisible(), 1)
    assert not problems, "\n".join(problems)


def test_ctrl_tab_moves_between_the_tabs(ide):
    window = ide.window
    tabs = window.tabs
    tabs.setCurrentIndex(0)
    tabs.currentWidget().setFocus()
    seen = [tabs.currentIndex()]
    for _ in range(tabs.count()):
        QTest.keyClick(QApplication.focusWidget() or tabs, Qt.Key_Tab, Qt.ControlModifier)
        QApplication.processEvents()
        seen.append(tabs.currentIndex())
    assert len(set(seen)) == tabs.count(), f"Ctrl+Tab went through {seen} of {tabs.count()} tabs"
    QTest.keyClick(QApplication.focusWidget() or tabs, Qt.Key_Tab, Qt.ControlModifier | Qt.ShiftModifier)
    QApplication.processEvents()
    assert tabs.currentIndex() == seen[-2], "Ctrl+Shift+Tab does not go back"


def test_every_control_has_a_name(ide):
    window = ide.window
    missing = sorted(set(nameless(window)))
    assert not missing, f"{len(missing)} controls without a name:\n" + "\n".join(missing)
