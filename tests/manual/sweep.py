"""What the suites of tests/manual share: a window that cannot reach a real board, the states
it is put in, a watcher that answers its dialogs, every action and every context menu, and the
loop that triggers them with checks after each one.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QFile, QPoint, QPointF, Qt, QTimer, QUrl, qInstallMessageHandler
from PySide6.QtGui import QContextMenuEvent, QDesktopServices
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QDockWidget, QFileDialog, QInputDialog, QLineEdit, QMenu, QMessageBox, QToolBar,
)

from lvgl_mpy_studio.core.boards import builtin_profiles
from lvgl_mpy_studio.core.i18n import language
from lvgl_mpy_studio.core.model import Project
from lvgl_mpy_studio.core.validation import validate_project
from lvgl_mpy_studio.device.service import DeviceSession
from lvgl_mpy_studio.platform import IS_WINDOWS, runtime_path

pytestmark = pytest.mark.manual
ROOT = Path(__file__).parents[2]
REPORTS = ROOT / "build" / "manual"
QUESTION = vars(QMessageBox)["question"]       # the conftest answers questions itself; here the watcher does
SLOW = 10                                      # seconds: an action taking longer is reported
PROGRESS = bool(os.environ.get("LMS_PROGRESS"))        # a line per entry, with pytest -s
WINDOW_MANAGER = os.environ.get("LMS_WINDOW_MANAGER")  # set by tools/manual_on_x.sh when one runs
MOST_DIALOGS = 15                              # more dialogs than this in one action is a loop

# Not triggered, and why: actions of the window by their attribute, so that the language does not matter.
SKIPPED = {
    "exit_action": "closes the window: closing is tested in test_main_window and test_files_panel",
    "build_action": "builds in the background for minutes, without a dialog: tested in test_release",
    "single_file_action": "builds in the background for minutes, without a dialog: tested in test_release",
}
# Said by the offscreen platform, and by Qt Multimedia when the buzzer starts: not problems.
QT_NOISE = ("propagateSizeHints", "does not support raise()", "does not support grabbing", "Using Qt multimedia with FFmpeg")


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
        if window.sim_panel.running:
            raise AssertionError(f"{self.name}: the simulator did not stop with Run → Stop")
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
        view = self.window._active_designer() or next((view for _index, view in self.window.designers.values()), None)
        if view is None:
            return
        self.window.tabs.setCurrentWidget(view)       # the code may be in front after the last entry
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
    """A board connected: the virtual board of tests/virtual_board.py (real mpremote), or a fake where there is none."""

    name = "board"
    board = None

    def ready(self):
        return State.ready(self) and self.window.device.port == self.port

    def build(self):
        from tests.virtual_board import ROOT, VirtualBoard, available

        profile = next(profile for profile in builtin_profiles() if profile["id"].startswith("esp32_4848"))
        project = Project("board")
        project.set_display_size(480, 480)
        project.board = profile
        project.runTarget = {"kind": "board", "language": "micropython"}
        project.add_widget(project.pages[0], "button")
        project.add_widget(project.pages[0], "label")
        path = self.tmp_path / "states" / "board" / "project.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        project.save(path)
        self.open(path)
        window = self.window
        window.device.disconnect()
        if available():
            if self.board is None:
                files = {"/flash/display_driver.py": (ROOT / "runtime" / "program" / "display_driver.py").read_text(), "/flash/gt911.py": ""}
                Board.board = VirtualBoard(self.tmp_path / "virtual-board", files, size=(480, 480))
            window.device = window.hardware.virtual_session(self.board)
            self.port = self.board.port
        else:
            from tests.test_device import FakeRunner

            window.device = window.hardware.session(FakeRunner())
            self.port = "/dev/fake"
        window.device.connect(self.port, project.board)
        window.selected_port = self.port
        window._update_device_actions()
        wait(lambda: window._worker is None, 10)
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
    """The only board the sweep may reach: none, or the virtual board of the board state. Anything else is recorded."""

    def __init__(self, real_serial):
        self.attempts = []
        self.allowed = set()                   # the port of the virtual board, once there is one
        self._serial = real_serial

    def serial_class(self):
        """serial.Serial that opens only the virtual board: the port is checked when it is opened,
        since mpremote makes the object first and sets the port after."""
        guard = self

        class Guarded(self._serial):
            def open(self):
                if self.port not in guard.allowed:
                    guard.attempts.append(f"open {self.port}")
                    raise OSError("the sweep never opens a real port")
                return super().open()

        return Guarded

    def process(self, command, *arguments, **options):
        """mpremote, only towards the virtual board."""
        port = command[command.index("connect") + 1] if "connect" in command else None
        if port in self.allowed:
            return subprocess.Popen(command, *arguments, **options)
        return self.forbidden(" ".join(map(str, command[-4:])))

    def virtual_session(self, board):
        self.allowed.add(board.port)
        session = DeviceSession(process_factory=self.process, uart_factory=self.forbidden, interrupt=lambda port: None)
        # The ports the IDE offers: the virtual board only, so that no dialog can choose a real one.
        session.list_ports = lambda: [{"port": board.port, "id": "virtual", "usb": "0000:0000", "description": "Virtual board of the tests"}]
        return session

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


def run_action(window, watcher, qtbot, name, action, warnings, trigger=None):
    """Trigger one action and check what it left. Returns (problems, dialogs, seconds).
    trigger() does it another way than QAction.trigger(), such as pressing its shortcut."""
    trigger = trigger or action.trigger
    document = window.document
    stack = document.undo_stack
    before, index, valid = snapshot(window), stack.index(), validation(document.project)
    attempts = len(window.hardware.attempts)
    watcher.seen, watcher.problems = [], []
    warnings.clear()
    started = time.monotonic()
    with qtbot.capture_exceptions() as exceptions:
        trigger()
        if action.isCheckable():
            settle(window)
            trigger()                          # back as it was
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
    if WINDOW_MANAGER and not leftover and not wait(lambda: QApplication.activeWindow() is window, 2):
        # Only a window manager gives the focus: offscreen and a bare Xvfb have none to give.
        active = QApplication.activeWindow()
        problems.append(f"the window did not get the focus back: {type(active).__name__ if active else 'no window'} has it")
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



def make_files(tmp_path):
    """What the file dialogs choose when the answer is OK."""
    folder = tmp_path / "files"
    shutil.copytree(ROOT / "examples" / "weather", folder / "project", ignore=shutil.ignore_patterns("build", "visual"))
    (folder / "program").mkdir()
    (folder / "program" / "main.py").write_text("print('sweep')\n", encoding="utf-8")
    picture = next((path for path in sorted((ROOT / "examples").rglob("*.png")) if "visual" not in path.parts and path.stat().st_size < 200_000), None)
    if picture is not None:
        shutil.copyfile(picture, folder / "picture.png")
    return folder


# ---- The window of a sweep ----

class Sweep:
    """The window, the watcher and the guard, set up and taken down as a test needs them.

        with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
            sweep.run_entries(sweep.action_entries(), answer)
    """

    def __init__(self, qtbot, monkeypatch, tmp_path, state_class, watcher_class=None, language="en"):
        self.qtbot, self.monkeypatch, self.tmp_path = qtbot, monkeypatch, tmp_path
        self.state_class = state_class
        self.watcher_class = watcher_class or Watcher
        self.language = language
        self.results, self.failures = [], []

    def __enter__(self):
        if self.state_class.needs_runtime and not runtime_path().exists():
            pytest.skip("runtime not built")
        if self.state_class is Program and IS_WINDOWS:
            pytest.skip("programs without pages run only in the Linux simulator")
        from lvgl_mpy_studio.ui.main_window import MainWindow

        monkeypatch, tmp_path = self.monkeypatch, self.tmp_path
        QApplication.setAttribute(Qt.AA_DontUseNativeDialogs)
        monkeypatch.setattr(QMessageBox, "question", QUESTION)
        self.opened = []
        monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: self.opened.append(QUrl(url).toString()) or True))
        trash = tmp_path / "trash"             # Delete… of the Files panel: never the trash of the PC
        trash.mkdir(exist_ok=True)
        monkeypatch.setattr(QFile, "moveToTrash", staticmethod(lambda path: bool(shutil.move(path, trash / f"{len(list(trash.iterdir()))}-{Path(path).name}"))))
        self.warnings = []
        self._previous_handler = qInstallMessageHandler(lambda mode, context, text: self.warnings.append(text))
        self.watcher = self.watcher_class(make_files(tmp_path))
        self.menus = CaughtMenus()
        import serial

        self.hardware = NoRealBoard(serial.Serial)
        monkeypatch.setattr(serial, "Serial", self.hardware.serial_class())
        # The settings of the tests last the whole run: the port of a virtual board of an earlier
        # test would be tried again, as the port a person used last.
        from PySide6.QtCore import QSettings

        QSettings("CopperAndCode", "LVGL MPY Studio").remove("device/ports")
        window = self.window = MainWindow()
        self.qtbot.addWidget(window)
        window.hardware = self.hardware
        window.device = self.hardware.session()
        window.resize(1400, 900)
        window.show()
        if self.language != "en":
            window.change_language(self.language)
        self.state = self.state_class(window, tmp_path)
        try:
            self.state.make()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_exception):
        window = self.window
        self.watcher.answer = "cancel"
        if window.sim_panel.running:
            window.stop_simulation()
            wait(lambda: not window.sim_panel.running, 10)
        window.document.undo_stack.setClean()
        for tab in window.file_tabs:
            tab.editor.document().setModified(False)
        window.device.disconnect()
        window.change_language("en")
        if Board.board is not None:
            Board.board.close()
            Board.board = None
        self.watcher.stop()
        self.menus.stop()
        qInstallMessageHandler(self._previous_handler)
        return False

    # ---- what is triggered ----

    def action_entries(self):
        """(name, find) of every action of the window; find() gives the action as the window is now."""
        return [(name, lambda action=action: action) for name, action in actions(self.window)]

    def menu_entries(self):
        """(name, find) of every entry of every context menu of this state. find() opens the menu
        again (an entry can change what is under the pointer) and gives the entry, or None."""
        window, tmp_path, menus = self.window, self.tmp_path, self.menus
        found = []
        for menu_name, place, widget, _where in context_targets(window, tmp_path):
            if not self.state.ready():
                self.state.make()
            title = f"{menu_name} {place}".strip()
            if not widget.isEnabled():         # the canvas while the simulator runs: the project is locked
                self.results.append({"action": title, "result": "disabled"})
                continue
            menu = open_menu(window, tmp_path, menus, menu_name, place)
            if menu is None:
                self.results.append({"action": title, "result": "no menu"})
                self.failures.append(f"{title}: no menu opened")
                continue
            for entry, _action in menu_entries(menu):
                def find(menu_name=menu_name, place=place, entry=entry):
                    menu = open_menu(window, tmp_path, menus, menu_name, place)
                    return dict(menu_entries(menu)).get(entry) if menu is not None else None
                found.append((f"{title}/{entry}", find))
        return found

    def run_entries(self, entries, answer):
        """Trigger each entry with its checks; the state is made again when an entry changed it."""
        window = self.window
        skipped = {id(getattr(window, attribute)): why for attribute, why in SKIPPED.items()}
        for name, find in entries:
            if not self.state.ready():
                self.state.make()
            action = find()
            if action is None:
                self.results.append({"action": name, "result": "gone"})
                continue
            if id(action) in skipped:
                self.results.append({"action": name, "result": "skipped", "why": skipped[id(action)]})
                continue
            if not action.isEnabled():
                self.results.append({"action": name, "result": "disabled"})
                continue
            self.watcher.answer = answer
            problems, notes, dialogs, seconds = run_action(window, self.watcher, self.qtbot, name, action, self.warnings)
            if PROGRESS:
                print(f"{seconds:6.1f} s  {name}  {problems or ''}", flush=True)
            self.results.append({"action": name, "result": "problems" if problems else "ok", "dialogs": dialogs, "seconds": round(seconds, 2), "problems": problems, "notes": notes})
            if problems:
                self.failures.append(f"{name}: " + " | ".join(problems))
            if window.isHidden():
                window.show()                  # an action that closes the window would hide the rest
            if language() != self.language:    # View → Language: the rest goes on in the language asked
                window.change_language(self.language)

    def report(self, suite, name):
        """Write the report; print what changed since the last run; fail on the problems found."""
        changes = write_report(suite, name, self.results)
        if changes:
            print(f"\n{suite}, {name}: changed since the last run:\n  " + "\n  ".join(changes))
        assert not self.failures, f"{len(self.failures)} entries with problems in {name}:\n" + "\n".join(self.failures)


def write_report(suite, name, results):
    """Write the report and return what changed from the last one: new, gone, or other dialogs."""
    folder = REPORTS / suite
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
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


# ---- The context menus ----
#
# A context menu is opened as a right click opens it: a QContextMenuEvent sent to the widget.
# The menu is caught when shown (CaughtMenus); each of its entries is then triggered with the same checks as the actions of the window. The menu is
# opened again for each entry, since an entry can change what is under the pointer.

class CaughtMenus:
    """The menu a right click opens, caught as soon as it is shown, then hidden.

    Replacing QMenu.exec does not reach the IDE's calls (PySide keeps its own lookup of the
    methods of a Qt class), so the menu is caught on the screen instead: a timer looks for the
    popup while QMenu.exec waits, and hides it, which ends exec without choosing an entry. The
    entries stay: the menu belongs to its widget, and is not deleted when hidden."""

    def __init__(self):
        self.menus = []
        self._timer = QTimer()
        self._timer.timeout.connect(self._look)
        self._timer.start(10)

    def stop(self):
        self._timer.stop()

    def _look(self):
        popup = QApplication.activePopupWidget()
        if isinstance(popup, QMenu) and popup.isVisible():
            self.menus.append(popup)
            popup.hide()

    def open(self, widget, position):
        """The menu a right click at position (in widget's coordinates) opens, or None."""
        self.menus.clear()
        event = QContextMenuEvent(QContextMenuEvent.Mouse, position, widget.mapToGlobal(position))
        QApplication.sendEvent(widget, event)
        wait(lambda: bool(self.menus), 2)
        return self.menus[-1] if self.menus else None


def menu_entries(menu, path=""):
    """(name, action) of the entries of a menu, submenus walked."""
    found = []
    for action in menu.actions():
        if action.isSeparator() or not action.text():
            continue
        name = f"{path}/{action.text().replace('&', '')}" if path else action.text().replace("&", "")
        if action.menu() is not None:
            found += menu_entries(action.menu(), name)
        else:
            found.append((name, action))
    return found


def raise_dock(window, name):
    dock = window.findChild(QDockWidget, name)
    dock.show()
    dock.raise_()
    QApplication.processEvents()


# A target is (menu, place, widget, where): where() prepares the widget (scrolls to the item,
# selects some text) and returns the point of the click. It is called just before the click,
# since scrolling to one item moves the others.

def canvas_targets(window):
    view = window._active_designer()
    if view is None:
        return []
    scene = view.designer_scene
    targets = []
    if scene.widget_items:
        targets.append(("on a widget", lambda: view.mapFromScene(list(scene.widget_items.values())[-1].sceneBoundingRect().center())))
    width, height = window.document.project.display.width, window.document.project.display.height
    empty = next((QPointF(x, y) for x in range(2, width, 16) for y in range(2, height, 16) if scene.item_at(QPointF(x, y)) is None), None)
    if empty is not None:
        targets.append(("on the empty page", lambda: view.mapFromScene(empty)))
    return [("Canvas", place, view.viewport(), where) for place, where in targets]


def tree_items(tree):
    """Every item of a QTreeWidget, walked with child().

    Never with QTreeWidgetItemIterator: an iterator made from Python and a tree that changes
    afterwards crash PySide 6.12 in a later clear() or takeChildren() (seen on the board's files)."""
    pending = [tree.invisibleRootItem()]
    while pending:
        item = pending.pop(0)
        for index in range(item.childCount()):
            yield item.child(index)
            pending.append(item.child(index))


def tree_targets(tree, kinds):
    """One item of each kind of the project tree, and the empty space below the items."""
    def first(kind):
        return next((item for item in tree_items(tree) if isinstance(item.data(0, Qt.UserRole), tuple) and item.data(0, Qt.UserRole)[0] == kind), None)

    def on(kind):
        def where():
            tree.scrollToItem(first(kind))
            QApplication.processEvents()
            return tree.visualItemRect(first(kind)).center()
        return where

    targets = [(f"on a {kind}", on(kind)) for kind in kinds if first(kind) is not None]
    below = QPoint(4, tree.viewport().height() - 4)
    if tree.itemAt(below) is None:
        targets.append(("below the items", lambda: below))
    return [("Project tree", place, tree.viewport(), where) for place, where in targets]


PC_FILES = {"main.py": "print('menu')\n", "notes.txt": "notes\n", "sub/inner.py": "print('inner')\n"}


def pc_folder(tmp_path):
    """The folder of the Files panel, put back as it was: what an entry renamed or deleted is there again."""
    folder = (tmp_path / "pc").resolve()
    for name, text in PC_FILES.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text(text, encoding="utf-8")
    for path in folder.iterdir():
        if path.name not in ("main.py", "notes.txt", "sub"):
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    return folder


def files_targets(window, tmp_path):
    raise_dock(window, "filesDock")
    panel = window.files_panel
    folder = pc_folder(tmp_path)
    if panel.folder != folder:
        panel.set_folder(folder)

    # An index lives until the model changes, and the model reads folders in a thread: it is
    # asked again after every processEvents(), never kept.
    def index(name):
        return panel.proxy.mapFromSource(panel.model.index(str(folder / name)))

    def on(name):
        def where():
            if not wait(lambda: index(name).isValid(), 5):
                raise AssertionError(f"the Files panel does not show {name}")
            panel.tree.scrollTo(index(name))
            QApplication.processEvents()
            return panel.tree.visualRect(index(name)).center()
        return where

    targets = [(place, on(name)) for place, name in (("on a program", "main.py"), ("on a text file", "notes.txt"), ("on a folder", "sub"))]
    wait(lambda: all(index(name).isValid() for name in ("main.py", "notes.txt", "sub")), 5)
    below = QPoint(4, panel.tree.viewport().height() - 4)
    if not panel.tree.indexAt(below).isValid():
        targets.append(("below the files", lambda: below))
    return [("Files", place, panel.tree.viewport(), where) for place, where in targets]


BOARD_FILES = {"/flash/menu.py": b"print('menu')\n", "/flash/data/values.txt": b"1 2 3\n"}


def board_files_targets(window):
    """The board's files of the board state: a program, a text file, a folder and the empty space."""
    board = Board.board
    view = window.files_panel.board
    if board is None or not view.connected:
        return []
    for name, data in BOARD_FILES.items():
        target = board.flash / name.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            target.write_bytes(data)
    raise_dock(window, "filesDock")
    view.refresh()
    settle(window)

    def item(path):
        return next((item for item in tree_items(view.tree) if item.data(0, view.PATH) == path), None)

    for folder in ("/flash", "/flash/data"):
        if not wait(lambda: item(folder) is not None, 10):
            raise AssertionError(f"the board's files do not show {folder}")
        item(folder).setExpanded(True)
        settle(window)

    def on(path):
        def where():
            if not wait(lambda: item(path) is not None, 10):
                raise AssertionError(f"the board's files do not show {path}")
            view.tree.scrollToItem(item(path))
            QApplication.processEvents()
            return view.tree.visualItemRect(item(path)).center()
        return where

    targets = [(place, on(path)) for place, path in (("on a program", "/flash/menu.py"), ("on a text file", "/flash/data/values.txt"), ("on a folder", "/flash/data"))]
    below = QPoint(4, view.tree.viewport().height() - 4)
    if view.tree.itemAt(below) is None:
        targets.append(("below the files", lambda: below))
    return [("Board files", place, view.tree.viewport(), where) for place, where in targets]


def terminal_targets(window):
    """The terminals, with some text selected, so that Copy is there to choose."""
    def selected(terminal):
        def where():
            terminal.feed("menu sweep\r\n")
            terminal.select_all()
            return terminal.viewport().rect().center()
        return where

    raise_dock(window, "deviceConsoleDock")
    targets = [("Device Console", "", window.device_console.terminal.viewport(), selected(window.device_console.terminal))]
    if window.sim_panel.program:
        targets.append(("Simulator terminal", "", window.sim_panel.terminal.viewport(), selected(window.sim_panel.terminal)))
    return targets


def editor_targets(window):
    """The code editor with its first line selected: Cut, Copy and Delete are there to choose."""
    editor = window.code_panel.editor

    def where():
        window.tabs.setCurrentWidget(window.code_panel)
        cursor = editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        QApplication.clipboard().setText("menu = 1")
        return editor.viewport().rect().center()

    return [("Code editor", "", editor.viewport(), where)]


def context_targets(window, tmp_path):
    """(menu, place, widget, where) of every context menu the window has in this state."""
    found = []
    designer = next((view for _index, view in window.designers.values()), None)
    if designer is not None:
        window.tabs.setCurrentWidget(designer)
        QApplication.processEvents()
    found += canvas_targets(window)
    raise_dock(window, "projectDock")
    found += tree_targets(window.project_tree, ("page", "widget", "modules", "pymodule"))
    found += files_targets(window, tmp_path)
    found += board_files_targets(window)
    found += terminal_targets(window)
    found += editor_targets(window)
    return found


def open_menu(window, tmp_path, menus, menu_name, place):
    """The menu of (menu_name, place) as the window is now, or None."""
    for name, where_place, widget, where in context_targets(window, tmp_path):
        if (name, where_place) == (menu_name, place):
            return menus.open(widget, where())
    return None
