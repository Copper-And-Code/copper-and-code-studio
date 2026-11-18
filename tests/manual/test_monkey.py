"""Random use of the whole window, without a plan: a monkey on the mouse and the keyboard.

    pytest tests/manual/test_monkey.py --manual
    LMS_MONKEY_STEPS=5000 LMS_MONKEY_SEED=7 pytest tests/manual/test_monkey.py --manual

Thousands of steps, each one an event a person could cause on any visible widget of the window:
a click, a double click, a right click, a drag, the wheel, a key. A menu that opens is caught,
and one of its entries chosen now and then; dialogs are answered at random, with Cancel or
with OK. After every step: no exception, no Qt warning, no dialog left open, the window
answers; every 50 steps the project must be valid. The suite of random use checks meanings;
this one only that nothing breaks, wherever the mouse lands.

The seed is printed; a failure prints the last steps, to replay with the same seed.
"""
import os
import random
import time

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMenuBar, QWidget

from sweep import QT_NOISE, REPORTS, SKIPPED, Board, Example, Program, Sweep, answers_within, settle, validation, wait

pytestmark = pytest.mark.manual

STEPS = int(os.environ.get("LMS_MONKEY_STEPS", "1500"))
SEED = int(os.environ.get("LMS_MONKEY_SEED", str(int(time.time()) % 100000)))
KEYS = [
    "a", "Z", "1", " ", "Return", "Escape", "Tab", "Backspace", "Delete", "Left", "Right", "Up", "Down",
    "Home", "End", "PgDown", "F2", "F5", "Shift+F5", "Ctrl+Z", "Ctrl+Y", "Ctrl+C", "Ctrl+V", "Ctrl+X",
    "Ctrl+A", "Ctrl+D", "Ctrl+S", "Ctrl+N", "Ctrl+O", "Ctrl+]", "Ctrl+[", "Ctrl++", "Ctrl+-", "Ctrl+0",
]
NEVER = {"Ctrl+Q", "Alt+F4"}                   # they close the window, and the test with it
MONKEY_STATES = [Example, Program, Board]


def targets(window):
    """Visible widgets of the window, and of the docks floated out of it."""
    return [widget for widget in window.findChildren(QWidget) if widget.isVisible() and widget.width() > 2 and widget.height() > 2 and widget.window() is window]


def step(chance, window, menus, skipped, log):
    widget = chance.choice(targets(window))
    point = QPoint(chance.randrange(widget.width()), chance.randrange(widget.height()))
    kind = chance.choices(["click", "double", "right", "drag", "wheel", "key", "menu"], weights=[30, 8, 8, 10, 6, 30, 8])[0]
    where = f"{type(widget).__name__}{'/' + widget.objectName() if widget.objectName() else ''} at {point.x()},{point.y()}"
    if kind == "click":
        log.append(f"click on {where}")
        QTest.mouseClick(widget, Qt.LeftButton, pos=point)
    elif kind == "double":
        log.append(f"double click on {where}")
        QTest.mouseDClick(widget, Qt.LeftButton, pos=point)
    elif kind == "right":
        log.append(f"right click on {where}")
        menu = menus.open(widget, point)
        if menu is not None:
            choose(chance, menu, skipped, log)
    elif kind == "drag":
        end = QPoint(chance.randrange(widget.width()), chance.randrange(widget.height()))
        log.append(f"drag on {where} to {end.x()},{end.y()}")
        QTest.mousePress(widget, Qt.LeftButton, pos=point)
        for fraction in (0.3, 0.6, 1.0):
            middle = point + (end - point) * fraction
            QTest.mouseMove(widget, middle)
        QTest.mouseRelease(widget, Qt.LeftButton, pos=end)
    elif kind == "wheel":
        log.append(f"wheel on {where}")
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QWheelEvent

        delta = chance.choice([120, -120])
        modifiers = chance.choice([Qt.NoModifier, Qt.ControlModifier])
        event = QWheelEvent(QPointF(point), QPointF(widget.mapToGlobal(point)), QPoint(), QPoint(0, delta), Qt.NoButton, modifiers, Qt.NoScrollPhase, False)
        QApplication.sendEvent(widget, event)
    elif kind == "key":
        key = chance.choice(KEYS)
        focus = QApplication.focusWidget() or widget
        log.append(f"key {key} on {type(focus).__name__}")
        QTest.keySequence(focus, QKeySequence(key))
    else:
        bar = window.menuBar()
        top = chance.choice([action for action in bar.actions() if action.menu() is not None])
        log.append(f"menu {top.text().replace('&', '')}")
        choose(chance, top.menu(), skipped, log)


def choose(chance, menu, skipped, log):
    """One entry of a menu, submenus included; never one that closes the window or builds for minutes."""
    entries = []

    def walk(menu):
        for action in menu.actions():
            if action.menu() is not None:
                walk(action.menu())
            elif not action.isSeparator() and action.isEnabled() and id(action) not in skipped and action.text():
                entries.append(action)

    walk(menu)
    if entries:
        action = chance.choice(entries)
        log.append(f"  → {action.text().replace('&', '')}")
        action.trigger()


class StepLog(list):
    """The steps, also written to build/manual/monkey-<state>.log as they are made: a crash of
    the process loses the test's output, not this file."""

    def __init__(self, name):
        super().__init__()
        REPORTS.mkdir(parents=True, exist_ok=True)
        self._file = open(REPORTS / f"monkey-{name}.log", "w", encoding="utf-8")

    def append(self, line):
        super().append(line)
        self._file.write(line + "\n")
        self._file.flush()


def broken_rules(window):
    """What must hold after any step, whatever came before."""
    from lvgl_mpy_studio.core.components import is_component

    found = []
    project, document = window.document.project, window.document
    invalid = [problem for problem in validation(project) if problem.startswith("INVALID")]
    if invalid:
        found.append("the project is invalid: " + invalid[0][9:300])
    names = [widget.name for widget in project.widgets]
    if len(names) != len(set(names)):
        found.append("two widgets with one name: " + ", ".join(sorted({name for name in names if names.count(name) > 1})))
    pages = {page.id: page for page in project.pages}
    designers = {page_id: view for page_id, (_index, view) in window.designers.items()}
    if set(designers) != set(pages):
        found.append(f"the tabs of the pages ({len(designers)}) are not the pages of the project ({len(pages)})")
    for page_id, view in designers.items():
        page = pages.get(page_id)
        if page is None:
            continue
        drawn = set(view.designer_scene.widget_items)
        wanted = {widget.id for widget in page.widgets if not is_component(widget.type)}
        if drawn != wanted:
            found.append(f"the canvas of {page.name} draws {len(drawn - wanted)} widgets more and {len(wanted - drawn)} less than its page")
    gone = [name for name in window.properties.names if project.find_widget(name) is None]
    if gone:
        found.append(f"the Properties panel shows widgets that are not in the project: {gone}")
    if ("*" in window.windowTitle()) != document.modified:
        found.append(f"the title {window.windowTitle()!r} does not say whether there is something to save ({document.modified})")
    return found


@pytest.mark.parametrize("state_class", MONKEY_STATES, ids=[state.name for state in MONKEY_STATES])
def test_the_monkey(qtbot, tmp_path, monkeypatch, state_class):
    seed = SEED + MONKEY_STATES.index(state_class)
    chance = random.Random(seed)
    print(f"\nmonkey: state {state_class.name}, seed {seed}, {STEPS} steps (LMS_MONKEY_SEED={SEED} to replay)")
    log, problems = StepLog(state_class.name), []
    with Sweep(qtbot, monkeypatch, tmp_path, state_class) as sweep:
        window = sweep.window
        skipped = {id(getattr(window, attribute)) for attribute in SKIPPED}
        for number in range(STEPS):
            sweep.watcher.answer = chance.choice(["cancel", "cancel", "ok"])
            sweep.watcher.seen, sweep.watcher.problems = [], []
            sweep.warnings.clear()
            with qtbot.capture_exceptions() as exceptions:
                step(chance, window, sweep.menus, skipped, log)
                settle(window, 20)
            found = list(sweep.watcher.problems)
            found += [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
            found += [f"Qt warning: {text}" for text in sweep.warnings if not any(noise in text for noise in QT_NOISE)]
            for dialog in [widget for widget in QApplication.topLevelWidgets() if isinstance(widget, QDialog) and widget.isVisible()]:
                found.append(f"left open: {dialog.windowTitle()}")
                dialog.close()
            popup = QApplication.activePopupWidget()
            if popup is not None and not isinstance(popup, (QMenu, QMenuBar)):
                popup.close()                  # a list of a combo box, a completer: a person clicks elsewhere
            if not answers_within(window):
                found.append("the window does not answer")
            found += broken_rules(window)
            if window.isHidden():
                window.show()
            if found:
                problems.append(f"step {number}: {' | '.join(found)}\n    last steps:\n      " + "\n      ".join(log[-12:]))
                if len(problems) >= 5:
                    break
            if window.sim_panel.running and chance.random() < 0.02:
                window.stop_simulation()       # now and then, so that the rest is not all read-only
                wait(lambda: not window.sim_panel.running, 10)
        window.document.undo_stack.setClean()
        for tab in window.file_tabs:
            tab.editor.document().setModified(False)
    assert not problems, f"seed {seed}:\n" + "\n".join(problems)
