"""The code editor as a person types in it.

    pytest tests/manual/test_typing_code.py --manual

With an example open, through the keyboard and the mouse:
- a double click on a widget opens its handler; typed lines are indented after a colon, Tab
  writes four spaces, and the handler holds what the editor shows; undo gives the old code;
- the suggestions come after "lv." and "ui." and with Ctrl+Space, the arrows move in them and
  Enter writes the one chosen;
- a syntax error is underlined and said under the editor while typing, and goes away when
  fixed; with the error, Start fills the Errors panel, and a double click on the error opens
  the handler at its line;
- every object and every event of the two lists opens its code without changing the project;
- while the simulator runs, keys change nothing, and Stop and Edit gives the code back;
- a few hundred random keys typed into a handler leave the editor and the project in agreement,
  the check of the syntax running, and undo all gives the code of the start.
"""
import json
import random

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from sweep import Example, Sweep, settle, wait

pytestmark = pytest.mark.manual


@pytest.fixture
def ide(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        window.document.undo_stack.setIndex(0)   # the example as shipped
        window.document.undo_stack.setClean()
        yield sweep
        window.document.undo_stack.setClean()


def snapshot(document):
    return json.dumps(document.project.to_dict(), sort_keys=True, default=str)


def open_by_double_click(window, widget_name):
    """Double-click the widget on the canvas, as a person opens its handler."""
    view = next(view for _index, view in window.designers.values() if any(item.name == widget_name for item in view.designer_scene.widget_items.values()))
    window.tabs.setCurrentWidget(view)
    item = next(item for item in view.designer_scene.widget_items.values() if item.name == widget_name)
    QTest.mouseDClick(view.viewport(), Qt.LeftButton, pos=view.mapFromScene(item.sceneBoundingRect().center()))
    QApplication.processEvents()


def a_button(window):
    return next(widget.name for widget in window.document.project.widgets if widget.type == "button")


def current_body(panel):
    kind, name = panel.current
    code = panel.document.project.code
    if kind == "module":
        return code.module
    if kind == "pymodule":
        module = panel.module()
        return module.source if module else ""
    handler = code.handlers.get(name)
    return handler.body if handler else ""


def type_lines(editor, lines):
    for line in lines:
        QTest.keyClicks(editor, line)
        QTest.keyClick(editor, Qt.Key_Return)


def test_typing_indents_and_is_kept_and_undone(ide):
    window = ide.window
    panel = window.code_panel
    start = snapshot(window.document)
    open_by_double_click(window, a_button(window))
    assert window.tabs.currentWidget() is panel and panel.current[0] == "handler", panel.current
    editor = panel.editor
    editor.setFocus()
    editor.moveCursor(editor.textCursor().MoveOperation.End)
    QTest.keyClick(editor, Qt.Key_Return)
    type_lines(editor, ["if True:", 'print("typed")'])
    QTest.keyClick(editor, Qt.Key_Backspace)
    QTest.keyClick(editor, Qt.Key_Backspace)
    QTest.keyClick(editor, Qt.Key_Backspace)
    QTest.keyClick(editor, Qt.Key_Backspace)
    QTest.keyClick(editor, Qt.Key_Tab)
    QTest.keyClicks(editor, "x = 1")
    QApplication.processEvents()
    text = editor.toPlainText()
    assert 'if True:\n    print("typed")\n    x = 1' in text, text
    assert current_body(panel) == text, "the handler does not hold what the editor shows"
    window.document.undo_stack.setIndex(0)
    QApplication.processEvents()
    assert snapshot(window.document) == start
    assert 'print("typed")' not in editor.toPlainText(), "the editor still shows the undone code"


def test_suggestions_come_move_and_are_written(ide):
    window = ide.window
    panel = window.code_panel
    open_by_double_click(window, a_button(window))
    editor = panel.editor
    editor.setFocus()
    editor.moveCursor(editor.textCursor().MoveOperation.End)
    QTest.keyClick(editor, Qt.Key_Return)
    problems = []
    for prefix in ("lv.", "ui."):
        QTest.keyClicks(editor, prefix)
        wait(lambda: editor.suggestions.isVisible(), 2)
        if not editor.suggestions.isVisible() or editor.suggestions.count() == 0:
            problems.append(f"no suggestions after {prefix!r}")
            QTest.keyClick(editor, Qt.Key_Return)
            continue
        QTest.keyClick(editor, Qt.Key_Down)
        chosen = editor.suggestions.currentItem().text()
        QTest.keyClick(editor, Qt.Key_Return)
        QApplication.processEvents()
        line = editor.textCursor().block().text()
        if not line.strip().startswith(prefix):
            problems.append(f"after choosing {chosen!r} the line is {line!r}")
        QTest.keyClick(editor, Qt.Key_Escape)
        editor.moveCursor(editor.textCursor().MoveOperation.EndOfBlock)
        QTest.keyClick(editor, Qt.Key_Return)
    # A word alone suggests the widgets: the first letters of one, Ctrl+Space, Enter.
    name = a_button(window)
    QTest.keyClicks(editor, name[:2])
    QTest.keyClick(editor, Qt.Key_Space, Qt.ControlModifier)
    wait(lambda: editor.suggestions.isVisible(), 2)
    if not editor.suggestions.isVisible():
        problems.append(f"Ctrl+Space shows no suggestions after {name[:2]!r}")
    else:
        names = [editor.suggestions.item(row).text() for row in range(editor.suggestions.count())]
        while editor.suggestions.currentItem().text() != name and editor.suggestions.currentRow() < len(names) - 1:
            QTest.keyClick(editor, Qt.Key_Down)
        QTest.keyClick(editor, Qt.Key_Return)
        QApplication.processEvents()
        line = editor.textCursor().block().text().strip()
        if not line.startswith(f"ui.{name}."):
            problems.append(f"choosing {name!r} wrote {line!r}")
    QTest.keyClick(editor, Qt.Key_Escape)
    if editor.suggestions.isVisible():
        problems.append("Escape does not hide the suggestions")
    assert not problems, "\n".join(problems)


def test_a_syntax_error_is_shown_found_by_start_and_opened(ide):
    window = ide.window
    panel = window.code_panel
    name = a_button(window)
    open_by_double_click(window, name)
    editor = panel.editor
    editor.setFocus()
    editor.moveCursor(editor.textCursor().MoveOperation.End)
    QTest.keyClick(editor, Qt.Key_Return)
    QTest.keyClicks(editor, "def (:")
    error_line = editor.textCursor().blockNumber() + 1
    assert wait(lambda: panel.error.isVisible(), 3), "the error is not said under the editor"
    assert editor.extraSelections(), "the line of the error is not underlined"
    assert not window.run_project(), "Start went on with a syntax error"
    settle(window)
    assert window.errors.topLevelItemCount(), "Start did not fill the Errors panel"
    item = window.errors.topLevelItem(0)
    editor.moveCursor(editor.textCursor().MoveOperation.Start)
    window.errors.itemActivated.emit(item, 0)  # what a double click does
    QApplication.processEvents()
    assert window.tabs.currentWidget() is panel
    assert editor.textCursor().blockNumber() + 1 == error_line, f"the error opened line {editor.textCursor().blockNumber() + 1}, not {error_line}"
    editor.moveCursor(editor.textCursor().MoveOperation.EndOfBlock)
    for _ in range(len("def (:")):
        QTest.keyClick(editor, Qt.Key_Backspace)
    assert wait(lambda: not panel.error.isVisible(), 3), "the error stays after the fix: " + panel.error.text()


def test_every_object_and_event_opens_without_changing_the_project(ide):
    window = ide.window
    panel = window.code_panel
    window.tabs.setCurrentWidget(panel)
    start = snapshot(window.document)
    problems = []
    for object_index in range(panel.object_combo.count()):
        panel.object_combo.setCurrentIndex(object_index)
        QApplication.processEvents()
        for event_index in range(panel.procedure_combo.count()):
            panel.procedure_combo.setCurrentIndex(event_index)
            QApplication.processEvents()
            if panel.editor.toPlainText() != current_body(panel):
                problems.append(f"{panel.object_combo.itemText(object_index)} / {panel.procedure_combo.itemText(event_index)}: the editor does not show the stored code")
    if snapshot(window.document) != start:
        problems.append("looking through the lists changed the project")
    if window.document.modified:
        problems.append("looking through the lists marked the project as changed")
    assert not problems, "\n".join(problems[:20])


def test_the_code_is_read_only_while_the_simulator_runs(ide):
    window = ide.window
    panel = window.code_panel
    from copper_and_code_studio.platform import runtime_path

    if not runtime_path().exists():
        pytest.skip("runtime not built")
    open_by_double_click(window, a_button(window))
    before = snapshot(window.document)
    assert window.run_project() and wait(lambda: window.sim_panel.running, 20)
    window.tabs.setCurrentWidget(panel)
    panel.editor.setFocus()
    QTest.keyClicks(panel.editor, "nothing")
    QApplication.processEvents()
    assert snapshot(window.document) == before, "keys changed the code while the simulator ran"
    assert panel.running_bar.isVisible()
    QTest.mouseClick(panel.stop_button, Qt.LeftButton)
    assert wait(lambda: not window.sim_panel.running, 10), "Stop and Edit did not stop the simulator"
    panel.editor.setFocus()
    QTest.keyClicks(panel.editor, "x")
    QApplication.processEvents()
    assert snapshot(window.document) != before, "after Stop and Edit the code still cannot be changed"


def type_text(widget, text):
    """A key that writes text: QTest.keyClicks asserts on anything that is not ASCII, an input
    method of the system sends such keys this way."""
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    for kind in (QEvent.KeyPress, QEvent.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, 0, Qt.NoModifier, text))


KEYS = list("abcxyz_019 ()[]{}:.,'\"#=+-*/\\\n\t") + ["é", "→", "😀"]


def test_random_typing_keeps_editor_and_project_in_agreement(ide):
    window = ide.window
    panel = window.code_panel
    start = snapshot(window.document)
    open_by_double_click(window, a_button(window))
    editor = panel.editor
    editor.setFocus()
    chance = random.Random(11)
    with ide.qtbot.capture_exceptions() as exceptions:
        for number in range(400):
            key = chance.choice(KEYS + ["<Backspace>", "<Left>", "<Up>", "<Home>", "<End>", "<Undo>"])
            if key == "<Backspace>":
                QTest.keyClick(editor, Qt.Key_Backspace)
            elif key == "<Left>":
                QTest.keyClick(editor, Qt.Key_Left)
            elif key == "<Up>":
                QTest.keyClick(editor, Qt.Key_Up)
            elif key == "<Home>":
                QTest.keyClick(editor, Qt.Key_Home)
            elif key == "<End>":
                QTest.keyClick(editor, Qt.Key_End)
            elif key == "<Undo>":
                QTest.keyClick(editor, Qt.Key_Z, Qt.ControlModifier)
            elif key == "\n":
                QTest.keyClick(editor, Qt.Key_Return)
            elif key == "\t":
                QTest.keyClick(editor, Qt.Key_Tab)
            elif not key.isascii():
                type_text(editor, key)
            else:
                QTest.keyClicks(editor, key)
            if editor.suggestions.isVisible() and chance.random() < 0.5:
                QTest.keyClick(editor, Qt.Key_Escape)
            if number % 50 == 49:
                QApplication.processEvents()
                assert current_body(panel) == editor.toPlainText(), f"after {number + 1} keys the handler and the editor differ"
        wait(lambda: False, 0.8)                # the check of the syntax runs
    assert not exceptions, [f"{kind.__name__}: {error}" for kind, error, _trace in exceptions]
    assert current_body(panel) == editor.toPlainText()
    window.document.undo_stack.setIndex(0)
    QApplication.processEvents()
    assert snapshot(window.document) == start, "undo all does not give the code of the start"
