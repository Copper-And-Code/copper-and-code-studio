"""Every action of the window, in five states, answered once with Cancel and once with OK.

    pytest tests/manual/test_every_action.py --manual

An action is what a menu entry or a toolbar button does. Each one is triggered as choosing it
does; every dialog it opens is answered by a watcher, as a person would answer it. After each
action: no exception, no Qt warning, no dialog left open, the window answers, the project is
as valid as before, and undo brings it back to where it was. A new action of the window is
tested without writing a test.

The report, with the dialogs each action opened and how long it took, is written to
build/manual/every-action/; the differences from the last run are printed, as a list of
things to look at by hand.
"""
import json
import shutil
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer, QUrl, qInstallMessageHandler
from PySide6.QtGui import QDesktopServices
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QLineEdit, QMessageBox, QToolBar

from lvgl_mpy_studio.core.boards import builtin_profiles
from lvgl_mpy_studio.core.model import Project
from lvgl_mpy_studio.core.validation import validate_project
from lvgl_mpy_studio.device.service import DeviceSession
from lvgl_mpy_studio.platform import IS_WINDOWS, runtime_path

pytestmark = pytest.mark.manual

ROOT = Path(__file__).parents[2]
REPORTS = ROOT / "build" / "manual" / "every-action"
QUESTION = vars(QMessageBox)["question"]       # the conftest answers questions itself; here the watcher does
SLOW = 10                                      # seconds: an action taking longer is reported
MOST_DIALOGS = 15                              # more dialogs than this in one action is a loop

# Not triggered, and why. Everything else is.
SKIPPED = {
    "File/Exit": "closes the window: closing is tested in test_main_window and test_files_panel",
    "Run/Build Executable…": "builds in the background for minutes, without a dialog: tested in test_release",
    "Run/Build Single-File Executable…": "builds in the background for minutes, without a dialog: tested in test_release",
}
QT_NOISE = ("propagateSizeHints",)             # the offscreen platform says it at each window


# ---- The actions ----

def actions(window):
    """(name, action) of every menu entry and toolbar button, in menu order; submenus are walked."""
    found, seen = [], set()

    def walk(menu, path):
        for action in menu.actions():
            if action.isSeparator():
                continue
            name = f"{path}/{action.text().replace('&', '')}"
            if action.menu() is not None:
                walk(action.menu(), name)
            elif id(action) not in seen and action.text():
                seen.add(id(action))
                found.append((name, action))

    for top in window.menuBar().actions():
        walk(top.menu(), top.text().replace("&", ""))
    for toolbar in window.findChildren(QToolBar):
        for action in toolbar.actions():
            if not action.isSeparator() and action.text() and id(action) not in seen and action.menu() is None:
                seen.add(id(action))
                found.append((f"Toolbar/{action.text().replace('&', '')}", action))
    return found


# ---- Answering the dialogs ----

class Watcher:
    """Answers each modal dialog as soon as it appears: with Cancel, or with OK and something sensible."""

    def __init__(self, files):
        self.files = files                     # a folder with a project, a program and a picture to open
        self.answer = "cancel"
        self.seen = []                         # (class, title) of the dialogs answered during an action
        self.problems = []
        self._answered = None
        self._patience = 0
        self._outputs = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._look)
        self._timer.start(20)

    def stop(self):
        self._timer.stop()

    def _look(self):
        dialog = QApplication.activeModalWidget()
        if dialog is None or not isinstance(dialog, QDialog):
            self._answered = None
            return
        if dialog is self._answered:           # answered at the last look: it is closing
            self._patience -= 1
            if self._patience <= 0:
                self.problems.append(f"the dialog {describe(dialog)} did not close when answered")
                dialog.reject()
            return
        self._answered, self._patience = dialog, 50
        self.seen.append(describe(dialog))
        if len(self.seen) > MOST_DIALOGS:
            self.problems.append(f"more than {MOST_DIALOGS} dialogs in a row: {', '.join(self.seen[-4:])}")
            dialog.reject()
            return
        (self._accept if self.answer == "ok" else self._cancel)(dialog)

    def _cancel(self, dialog):
        if isinstance(dialog, QMessageBox):
            for button in (QMessageBox.Cancel, QMessageBox.No, QMessageBox.Close, QMessageBox.Abort):
                if dialog.button(button) is not None:
                    dialog.button(button).click()
                    return
            # A message with OK only is information: OK is the only answer.
            (dialog.escapeButton() or dialog.defaultButton() or dialog.buttons()[0]).click()
            return
        dialog.reject()

    def _accept(self, dialog):
        if isinstance(dialog, QMessageBox):
            for button in (QMessageBox.Yes, QMessageBox.Ok, QMessageBox.Save, QMessageBox.Open, QMessageBox.Discard, QMessageBox.Apply, QMessageBox.Retry):
                if dialog.button(button) is not None:
                    dialog.button(button).click()
                    return
            accepting = [button for button in dialog.buttons() if dialog.buttonRole(button) in (QMessageBox.AcceptRole, QMessageBox.YesRole)]
            (accepting[0] if accepting else dialog.buttons()[0]).click()
            return
        if isinstance(dialog, QFileDialog):
            self._choose_file(dialog)
            return
        if isinstance(dialog, QInputDialog):
            if dialog.inputMode() == QInputDialog.TextInput and not dialog.textValue().strip():
                dialog.setTextValue("sweep")
            dialog.accept()
            return
        if isinstance(dialog, QPrintDialog):
            # Never a real printer: a PDF in the temporary folder.
            dialog.printer().setOutputFormat(QPrinter.PdfFormat)
            dialog.printer().setOutputFileName(str(self.output("print.pdf")))
            dialog.accept()
            return
        if isinstance(dialog, QPrintPreviewDialog):
            dialog.reject()
            return
        buttons = dialog.findChild(QDialogButtonBox)
        if buttons is not None:
            for kind in (QDialogButtonBox.Ok, QDialogButtonBox.Save, QDialogButtonBox.Open, QDialogButtonBox.Yes, QDialogButtonBox.Apply, QDialogButtonBox.Close):
                button = buttons.button(kind)
                if button is not None and button.isEnabled():
                    button.click()
                    return
        dialog.accept()

    def output(self, name):
        self._outputs += 1
        folder = self.files / "out" / str(self._outputs)
        folder.mkdir(parents=True, exist_ok=True)
        return folder / name

    def _choose_file(self, dialog):
        if dialog.fileMode() == QFileDialog.Directory:
            path = self.output("folder")
            path.mkdir()
        elif dialog.acceptMode() == QFileDialog.AcceptSave:
            chosen = dialog.selectedFiles()
            name = Path(chosen[0]).name if chosen and Path(chosen[0]).name else "sweep"
            if dialog.defaultSuffix() and "." not in name:
                name += "." + dialog.defaultSuffix()
            path = self.output(name)
        else:
            filters = " ".join(dialog.nameFilters()).lower()
            path = next((self.files / name for pattern, name in (("*.py", "program/main.py"), ("*.png", "picture.png"), ("*.json", "project/project.json")) if pattern in filters), self.files / "project" / "project.json")
        edit = dialog.findChild(QLineEdit, "fileNameEdit")
        if edit is None:
            dialog.selectFile(str(path))
            dialog.accept()
            return
        edit.setText(str(path))                # in one go: typed key by key the dialog follows each folder
        buttons = dialog.findChild(QDialogButtonBox)
        button = buttons.button(QDialogButtonBox.Save) or buttons.button(QDialogButtonBox.Open) if buttons else None
        button.click() if button is not None else dialog.accept()


def describe(dialog):
    text = dialog.text() if isinstance(dialog, QMessageBox) else ""
    title = dialog.windowTitle() or type(dialog).__name__
    return f"{type(dialog).__name__} “{title}”" + (f": {text.splitlines()[0][:80]}" if text else "")


# ---- The states ----

def example_copy(tmp_path, name):
    folder = tmp_path / "states" / name
    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(ROOT / "examples" / name, folder, ignore=shutil.ignore_patterns("build", "visual", "*.mp4"))
    return folder


class State:
    """What the window shows before each action. ready() is cheap; make() builds it again when an action changed it."""

    name = ""
    needs_runtime = False

    def __init__(self, window, tmp_path):
        self.window = window
        self.tmp_path = tmp_path
        self.path = None

    def ready(self):
        document = self.window.document
        return document.path == self.path and document.undo_stack.index() == self.base and not self.window.sim_panel.running

    def make(self):
        window = self.window
        if window.sim_panel.running:
            window.stop_simulation()
            wait(lambda: not window.sim_panel.running, 10)
        window.document.undo_stack.setClean()  # what an action left is not asked about
        self.build()
        self.base = window.document.undo_stack.index()

    def open(self, path):
        self.path = Path(path).resolve()
        assert self.window.open_project(self.path), f"{self.name}: {path} did not open"
        wait(lambda: True, 0.2)

    def change_once(self):
        """One change, so that Undo is there to be chosen."""
        def mutate(project):
            widget = project.pages[0].widgets[-1]
            widget.props["x"] = int(widget.props.get("x", 0)) + 1
        self.window.document.execute("Sweep", mutate)

    def select_two(self):
        """Two widgets selected on the canvas: Edit and Arrange act on a selection."""
        view = self.window._active_designer()
        if view is None:
            return
        items = list(view.designer_scene.widget_items.values())[:2]
        view.designer_scene.clearSelection()
        for item in items:
            item.setSelected(True)
        QApplication.processEvents()


class Empty(State):
    name = "empty"

    def build(self):
        path = self.tmp_path / "states" / "empty" / "project.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        Project("empty").save(path)
        self.open(path)


class Example(State):
    name = "example"

    def build(self):
        self.open(example_copy(self.tmp_path, "weather") / "project.json")
        self.change_once()
        self.select_two()


class Simulating(State):
    name = "simulating"
    needs_runtime = True

    def ready(self):
        document = self.window.document
        return document.path == self.path and document.undo_stack.index() == self.base and self.window.sim_panel.running and not self.window.sim_panel.program

    def build(self):
        self.open(example_copy(self.tmp_path, "weather") / "project.json")
        self.change_once()
        assert self.window.run_project(), "Start failed: " + self.window.output.toPlainText()[-500:]
        assert wait(lambda: self.window.sim_panel.running, 20), "the simulator did not start"


class Program(State):
    name = "program"
    needs_runtime = True

    def ready(self):
        return self.window.sim_panel.running and bool(self.window.sim_panel.program)

    def build(self):
        Empty.build(self)
        folder = example_copy(self.tmp_path, "shell")
        assert self.window.run_program(folder / "shell.py"), "Run Program failed: " + self.window.output.toPlainText()[-500:]
        assert wait(lambda: self.window.sim_panel.running, 20), "the program did not start"


class Board(State):
    name = "board"

    def ready(self):
        return State.ready(self) and self.window.device.port == "/dev/fake"

    def build(self):
        from tests.test_device import FakeRunner

        project = Project("board")
        project.set_display_size(240, 240)
        project.board = builtin_profiles()[0]
        project.runTarget = {"kind": "board", "language": "micropython"}
        project.add_widget(project.pages[0], "button")
        project.add_widget(project.pages[0], "label")
        path = self.tmp_path / "states" / "board" / "project.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        project.save(path)
        self.open(path)
        window = self.window
        window.device.disconnect()
        window.device = window.hardware.session(FakeRunner())
        window.device.connect("/dev/fake", project.board)
        window.selected_port = "/dev/fake"
        window._update_device_actions()
        self.change_once()
        self.select_two()


STATES = [Empty, Example, Simulating, Program, Board]


# ---- Running one action ----

def wait(condition, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QApplication.processEvents()
        if condition():
            return True
        time.sleep(0.005)
    return condition()


def settle(window, seconds=30):
    """Until the board and the background work are quiet and no dialog is open."""
    wait(lambda: window._worker is None and QApplication.activeModalWidget() is None, seconds)
    wait(lambda: False, 0.1)


def answers_within(window, seconds=1.0):
    done = []
    QTimer.singleShot(0, lambda: done.append(True))
    return wait(lambda: bool(done), seconds)


def snapshot(window):
    return json.dumps(window.document.project.to_dict(), sort_keys=True, default=str)


def validation(project):
    """None if the project is invalid (validate_project raises), else its warnings."""
    try:
        return set(map(str, validate_project(project)))
    except ValueError as exc:
        return {"INVALID: " + str(exc)}


class NoRealBoard:
    """The only board the sweep may reach: none, or the fake of the board state. Anything else is recorded."""

    def __init__(self):
        self.attempts = []

    def runner(self, command, timeout, *rest):
        if command[-1:] == ["devs"]:
            return ""                          # no board attached
        self.attempts.append(" ".join(map(str, command[-4:])))
        from lvgl_mpy_studio.device.common import DeviceError
        raise DeviceError("device.absent", "the sweep never reaches a real board")

    def forbidden(self, *arguments, **options):
        self.attempts.append(f"open {arguments[:1]}")
        raise OSError("the sweep never opens a real port")

    def session(self, runner=None):
        return DeviceSession(runner=runner or self.runner, process_factory=self.forbidden, uart_factory=self.forbidden, console_factory=self.console)

    def console(self, port):
        from tests.test_files_panel import QuietPort

        return QuietPort()


def run_action(window, watcher, qtbot, name, action, warnings):
    """Trigger one action and check what it left. Returns (problems, dialogs, seconds)."""
    document = window.document
    stack = document.undo_stack
    before, index, valid = snapshot(window), stack.index(), validation(document.project)
    attempts = len(window.hardware.attempts)
    watcher.seen, watcher.problems = [], []
    warnings.clear()
    started = time.monotonic()
    with qtbot.capture_exceptions() as exceptions:
        action.trigger()
        if action.isCheckable():
            settle(window)
            action.trigger()                   # back as it was
        settle(window)
    seconds = time.monotonic() - started
    problems = list(watcher.problems)
    problems += [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
    problems += [f"Qt warning: {text}" for text in warnings if not any(noise in text for noise in QT_NOISE)]
    leftover = [widget for widget in QApplication.topLevelWidgets() if isinstance(widget, QDialog) and widget.isVisible()]
    for dialog in leftover:
        problems.append(f"left open: {describe(dialog)}")
        dialog.close()
    if not answers_within(window):
        problems.append("the window does not answer")
    if seconds > SLOW:
        problems.append(f"slow: {seconds:.1f} s")
    problems += [f"tried to reach a real board: {attempt}" for attempt in window.hardware.attempts[attempts:]]
    notes = []
    if window.document is document:
        added = validation(document.project) - valid
        invalid = [problem for problem in added if problem.startswith("INVALID: ")]
        if invalid:
            problems.append("the project became invalid: " + invalid[0][9:300])
        notes += [f"new warning: {problem}" for problem in sorted(added) if not problem.startswith("INVALID: ")]
        if stack.count() < index:
            notes.append("the undo history was cleared")   # New, Open: another project, not a change to undo
        elif stack.index() != index:
            stack.setIndex(index)
            QApplication.processEvents()
            if snapshot(window) != before:
                problems.append("undo does not bring the project back")
    return problems, notes, list(watcher.seen), seconds


# ---- The test ----

@pytest.fixture
def files(tmp_path):
    """What the file dialogs choose when the answer is OK."""
    folder = tmp_path / "files"
    shutil.copytree(ROOT / "examples" / "weather", folder / "project", ignore=shutil.ignore_patterns("build", "visual"))
    (folder / "program").mkdir()
    (folder / "program" / "main.py").write_text("print('sweep')\n", encoding="utf-8")
    picture = next((path for path in sorted((ROOT / "examples").rglob("*.png")) if "visual" not in path.parts and path.stat().st_size < 200_000), None)
    if picture is not None:
        shutil.copyfile(picture, folder / "picture.png")
    return folder


@pytest.mark.parametrize("answer", ["cancel", "ok"])
@pytest.mark.parametrize("state_class", STATES, ids=[state.name for state in STATES])
def test_every_action(qtbot, tmp_path, monkeypatch, files, state_class, answer):
    if state_class.needs_runtime and not runtime_path().exists():
        pytest.skip("runtime not built")
    if state_class is Program and IS_WINDOWS:
        pytest.skip("programs without pages run only in the Linux simulator")
    from lvgl_mpy_studio.ui.main_window import MainWindow

    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs)
    monkeypatch.setattr(QMessageBox, "question", QUESTION)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(QUrl(url).toString()) or True))
    warnings = []
    previous_handler = qInstallMessageHandler(lambda mode, context, text: warnings.append(text))
    watcher = Watcher(files)
    import serial

    hardware = NoRealBoard()
    monkeypatch.setattr(serial, "Serial", hardware.forbidden)
    window = MainWindow()
    qtbot.addWidget(window)
    window.hardware = hardware
    window.device = hardware.session()
    window.resize(1400, 900)
    window.show()
    state = state_class(window, tmp_path)
    results, failures = [], []
    try:
        state.make()
        for name, action in actions(window):
            if name in SKIPPED:
                results.append({"action": name, "result": "skipped", "why": SKIPPED[name]})
                continue
            if not state.ready():
                state.make()
            if not action.isEnabled():
                results.append({"action": name, "result": "disabled"})
                continue
            watcher.answer = answer
            problems, notes, dialogs, seconds = run_action(window, watcher, qtbot, name, action, warnings)
            results.append({"action": name, "result": "problems" if problems else "ok", "dialogs": dialogs, "seconds": round(seconds, 2), "problems": problems, "notes": notes})
            if problems:
                failures.append(f"{name}: " + " | ".join(problems))
            if window.isHidden():
                window.show()                  # an action that closes the window would hide the rest
    finally:
        watcher.answer = "cancel"
        if window.sim_panel.running:
            window.stop_simulation()
            wait(lambda: not window.sim_panel.running, 10)
        window.document.undo_stack.setClean()
        for tab in window.file_tabs:
            tab.editor.document().setModified(False)
        window.device.disconnect()
        window.change_language("en")
        watcher.stop()
        qInstallMessageHandler(previous_handler)
    changes = write_report(f"{state.name}-{answer}", results)
    if changes:
        print(f"\n{state.name}, {answer}: changed since the last run:\n  " + "\n  ".join(changes))
    assert not failures, f"{len(failures)} actions with problems in the state {state.name}, answer {answer}:\n" + "\n".join(failures)


def write_report(name, results):
    """Write the report and return what changed from the last one: new, gone, or other dialogs."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{name}.json"
    previous = {}
    if path.is_file():
        try:
            previous = {entry["action"]: entry for entry in json.loads(path.read_text(encoding="utf-8"))}
        except (ValueError, KeyError):
            previous = {}
    path.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if not previous:
        return []
    changes = []
    current = {entry["action"]: entry for entry in results}
    for action, entry in current.items():
        old = previous.get(action)
        if old is None:
            changes.append(f"new: {action}")
        elif old["result"] != entry["result"]:
            changes.append(f"{action}: {old['result']} → {entry['result']}")
        elif old.get("dialogs") != entry.get("dialogs"):
            changes.append(f"{action}: dialogs {old.get('dialogs')} → {entry.get('dialogs')}")
    changes += [f"gone: {action}" for action in previous if action not in current]
    return changes
