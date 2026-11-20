"""Every keyboard shortcut of the window, pressed with the focus where a person has it.

    pytest tests/manual/test_every_shortcut.py --manual

Each shortcut of each enabled action is pressed as keys, not triggered, with the focus in the
canvas, the project tree, the Files panel, the code editor, a field of the Properties panel
and the terminals. Where the focus is not a text, the shortcut must reach its action; in a
text field or a terminal the field may take it on purpose (Ctrl+C copies the text, or stops
the program), and that is written in the report, not counted as a problem. Anywhere, an
ambiguous shortcut shows as the Qt warning it causes. After each press the checks of every
action apply: no exception, no dialog left open, undo back to where it was.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QLineEdit

from copper_and_code_studio.ui.properties.panel import DESCRIPTOR_ROLE

from sweep import PROGRESS, SKIPPED, Board, Example, Program, Sweep, pc_folder, raise_dock, run_action

pytestmark = pytest.mark.manual

TEXT_PLACES = {"code editor", "Properties field", "Device Console", "Simulator terminal"}


def places(window, tmp_path):
    """(name, widget that gets the focus) where a person has the focus in this state."""
    found = []

    def canvas():                              # looked up each time: New and Open make other pages
        designer = next((view for _index, view in window.designers.values()), None)
        if designer is None or not designer.isEnabled():
            return None
        window.tabs.setCurrentWidget(designer)
        return designer

    found.append(("canvas", canvas))
    found.append(("project tree", lambda: (raise_dock(window, "projectDock"), window.project_tree)[1]))

    def files():
        raise_dock(window, "filesDock")
        folder = pc_folder(tmp_path)
        if window.files_panel.folder != folder:
            window.files_panel.set_folder(folder)
        return window.files_panel.tree

    found.append(("Files panel", files))
    found.append(("code editor", lambda: (window.tabs.setCurrentWidget(window.code_panel), window.code_panel.editor)[1]))

    def field():
        """The field of the property x of the selected widget, opened with a click as a person opens it."""
        raise_dock(window, "propertiesDock")
        panel = window.properties

        def item(parent):
            for row in range(parent.rowCount()):
                label, value = parent.child(row, 0), parent.child(row, 1)
                if value is not None and (value.data(DESCRIPTOR_ROLE) or {}).get("name") == "x":
                    return value
                found = item(label) if label is not None else None
                if found is not None:
                    return found
            return None

        def open_editor():
            return next((child for kind in (QAbstractSpinBox, QLineEdit) for child in panel.view.viewport().findChildren(kind) if child.isVisible()), None)

        if open_editor() is not None:          # still open from the last key
            return open_editor()
        # A click opens the field; on the cell that is already current a person double-clicks.
        for click in (QTest.mouseClick, QTest.mouseClick, QTest.mouseDClick):
            value = item(panel.model.invisibleRootItem())
            if value is None or not panel.view.isEnabled():
                return None
            panel.view.expandAll()
            panel.view.scrollTo(value.index())
            click(panel.view.viewport(), Qt.LeftButton, pos=panel.view.visualRect(value.index()).center())
            if open_editor() is not None:
                return open_editor()
        return None

    found.append(("Properties field", field))
    found.append(("Device Console", lambda: (raise_dock(window, "deviceConsoleDock"), window.device_console.terminal)[1]))
    if window.sim_panel.program:
        found.append(("Simulator terminal", lambda: (window.tabs.setCurrentWidget(window.sim_panel), window.sim_panel.terminal)[1]))
    return found


def focus(window, widget):
    """Give widget the focus; True if it has it (or the widget it hands it to)."""
    window.activateWindow()
    widget.setFocus(Qt.OtherFocusReason)
    QApplication.processEvents()
    focused = QApplication.focusWidget()
    return focused is not None and (focused is widget or widget.isAncestorOf(focused) or widget.focusProxy() is focused)


SHORTCUT_STATES = [Example, Program, Board]


@pytest.mark.parametrize("state_class", SHORTCUT_STATES, ids=[state.name for state in SHORTCUT_STATES])
def test_every_shortcut(qtbot, tmp_path, monkeypatch, state_class):
    with Sweep(qtbot, monkeypatch, tmp_path, state_class) as sweep:
        window = sweep.window
        skipped = {id(getattr(window, attribute)) for attribute in SKIPPED}
        keys = [(action, sequence) for action in window.findChildren(QAction) if id(action) not in skipped for sequence in action.shortcuts() if not sequence.isEmpty()]
        for place, find in places(window, tmp_path):
            for action, sequence in keys:
                key = sequence.toString(QKeySequence.NativeText)
                name = f"{place}/{key} {action.text().replace('&', '')}"
                if not sweep.state.ready():
                    sweep.state.make()
                widget = find()
                if widget is None:                 # the canvas while the simulator runs, a field with no widget selected
                    sweep.results.append({"action": name, "result": "not there"})
                    continue
                if not focus(window, widget):
                    sweep.results.append({"action": name, "result": "no focus"})
                    continue
                if not action.isEnabled():
                    sweep.results.append({"action": name, "result": "disabled"})
                    continue
                fired = []

                def seen(*_arguments, fired=fired):
                    fired.append(True)

                action.triggered.connect(seen)

                def press(widget=widget, sequence=sequence):
                    QTest.keySequence(QApplication.focusWidget() or widget, sequence)

                try:
                    problems, notes, dialogs, seconds = run_action(window, sweep.watcher, qtbot, name, action, sweep.warnings, trigger=press)
                finally:
                    action.triggered.disconnect(seen)   # only this one: the IDE's slots stay
                if not fired:
                    if place in TEXT_PLACES:
                        notes.append("taken by the field")
                    else:
                        problems.append(f"{key} did nothing with the focus in the {place}")
                if PROGRESS:
                    print(f"{seconds:6.1f} s  {name}  {problems or ''}", flush=True)
                result = "problems" if problems else ("taken" if not fired else "ok")
                sweep.results.append({"action": name, "result": result, "dialogs": dialogs, "seconds": round(seconds, 2), "problems": problems, "notes": notes})
                if problems:
                    sweep.failures.append(f"{name}: " + " | ".join(problems))
                if window.isHidden():
                    window.show()
    sweep.report("every-shortcut", state_class.name)
