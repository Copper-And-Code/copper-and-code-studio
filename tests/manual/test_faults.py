"""Things going wrong under the IDE: each one must be said, and lose nothing.

    pytest tests/manual/test_faults.py --manual

The disk full during a save, a read-only folder, the runtime killed or hanging, the project
changed outside while it is open, the board pulled out during an upload, a broken project
file. For each: no exception, a message that says what happened, the work of the person still
there (on disk and in the window), and the IDE able to go on.
"""
import errno
import os
import signal
import time

import pytest
from PySide6.QtWidgets import QApplication

from lvgl_mpy_studio.platform import IS_WINDOWS
from sweep import Board, Example, Simulating, Sweep, settle, wait

pytestmark = pytest.mark.manual


def change(window):
    """A change made in the window, to be saved."""
    def mutate(project):
        widget = project.pages[0].widgets[-1]
        widget.props["x"] = int(widget.props.get("x", 0)) + 7
    window.document.execute("Fault", mutate)
    assert window.document.modified


def through(sweep, operation):
    """Run operation as a person's choice would, and return (its result, the dialogs it opened, exceptions)."""
    sweep.watcher.seen = []
    with sweep.qtbot.capture_exceptions() as exceptions:
        result = operation()
        settle(sweep.window)
    return result, list(sweep.watcher.seen), [f"{kind.__name__}: {error}" for kind, error, _trace in exceptions]


def leftovers(folder):
    return sorted(path.name for path in folder.iterdir() if path.name.endswith(".tmp"))


# ---- The disk ----

def test_the_disk_full_during_a_save_keeps_the_file_and_the_changes(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        path = window.document.path
        before = path.read_bytes()
        change(window)

        def full(_descriptor):
            raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

        monkeypatch.setattr("lvgl_mpy_studio.core.model.os.fsync", full)
        saved, dialogs, exceptions = through(sweep, window.save_project)
        assert not exceptions
        assert saved is False
        assert any("Save Error" in dialog for dialog in dialogs), dialogs
        assert path.read_bytes() == before, "the file on disk changed"
        assert leftovers(path.parent) == [], "a temporary file was left"
        assert window.document.modified, "the changes are no longer marked as unsaved"
        assert "*" in window.windowTitle()
        monkeypatch.undo()                     # the disk has room again
        sweep.monkeypatch.setattr("lvgl_mpy_studio.core.model.os.fsync", os.fsync)
        assert window.save_project()
        assert not window.document.modified and path.read_bytes() != before


@pytest.mark.skipif(IS_WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="needs POSIX permissions and a user that is not root")
def test_a_read_only_folder_is_said_on_save_on_start_and_in_the_files_panel(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        path = window.document.path
        folder = path.parent
        before = path.read_bytes()
        change(window)
        folder.chmod(0o555)
        try:
            saved, dialogs, exceptions = through(sweep, window.save_project)
            assert not exceptions and saved is False
            assert any("Save Error" in dialog for dialog in dialogs), dialogs
            started, dialogs, exceptions = through(sweep, window.run_project)
            assert not exceptions and started is False and not window.sim_panel.running
            assert not window.document.read_only
            window.files_panel.set_folder(folder)
            created, dialogs, exceptions = through(sweep, lambda: window.files_panel.new_file(folder))
            assert not exceptions and created is None
            assert dialogs, "New File… in a read-only folder said nothing"
        finally:
            folder.chmod(0o755)
        assert path.read_bytes() == before and window.document.modified
        assert window.save_project()


@pytest.mark.skipif(IS_WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="needs POSIX permissions and a user that is not root")
def test_a_build_folder_that_cannot_be_written_stops_start_with_a_message(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        build = window._build_dir()
        build.mkdir(parents=True, exist_ok=True)
        build.chmod(0o555)
        try:
            started, _dialogs, exceptions = through(sweep, window.run_project)
        finally:
            build.chmod(0o755)
        assert not exceptions and started is False and not window.sim_panel.running
        assert "denied" in window.output.toPlainText().lower() or window.errors.topLevelItemCount(), window.output.toPlainText()[-400:]
        assert not window.document.read_only, "the project stayed read-only"
        assert window.run_project() and wait(lambda: window.sim_panel.running, 20)


# ---- The runtime ----

def runtime_pid(window):
    pid = window.sim_panel.process.processId()
    assert pid, "the simulator has no process"
    return pid


@pytest.mark.skipif(IS_WINDOWS, reason="signals of POSIX")
def test_the_runtime_killed_gives_back_the_project_and_starts_again(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Simulating) as sweep:
        window = sweep.window
        assert window.document.read_only
        before = window.document.project.to_dict()
        with qtbot.capture_exceptions() as exceptions:
            os.kill(runtime_pid(window), signal.SIGKILL)
            assert wait(lambda: not window.sim_panel.running, 10), "the IDE did not see the runtime die"
            settle(window)
        assert not exceptions
        assert not window.document.read_only, "the project stayed read-only"
        assert window.document.project.to_dict() == before
        assert window.sim_panel.status.text(), "nothing says the simulator ended"
        assert window.run_project() and wait(lambda: window.sim_panel.running, 20), "Start does not work again"


@pytest.mark.skipif(IS_WINDOWS, reason="signals of POSIX")
def test_a_hanging_runtime_is_stopped_by_stop(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Simulating) as sweep:
        window = sweep.window
        pid = runtime_pid(window)
        os.kill(pid, signal.SIGSTOP)           # it answers nothing any more
        try:
            started = time.monotonic()
            with qtbot.capture_exceptions() as exceptions:
                window.stop_action.trigger() if hasattr(window, "stop_action") else window.stop_simulation()
                stopped = wait(lambda: not window.sim_panel.running, 10)
            assert not exceptions
            assert stopped, "Stop did not end a runtime that does not answer"
            assert time.monotonic() - started < 5, "Stop took more than 5 seconds"
        finally:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        assert not window.document.read_only
        assert answers(window)


def answers(window):
    done = []
    from PySide6.QtCore import QTimer

    QTimer.singleShot(0, lambda: done.append(True))
    return wait(lambda: bool(done), 1)


# ---- The project file ----

def test_the_project_changed_outside_is_not_overwritten_without_a_choice(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        path = window.document.path
        change(window)
        outside = path.read_text(encoding="utf-8").replace('"name": "main"', '"name": "changed outside"', 1)
        assert "changed outside" in outside
        path.write_text(outside, encoding="utf-8")
        sweep.watcher.answer = "cancel"
        saved, dialogs, exceptions = through(sweep, window.save_project)
        assert not exceptions and saved is False
        assert any("changed by another program" in dialog for dialog in dialogs), dialogs
        assert path.read_text(encoding="utf-8") == outside, "the change made outside was lost"
        assert window.document.modified, "the changes made in the window were lost"


def test_a_broken_project_file_is_said_and_the_open_project_stays(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        before = window.document.path
        for name, text in (("truncated.json", '{"schemaVersion": 2, "pages": ['), ("wrong.json", '{"schemaVersion": 2, "pages": 7}'), ("empty.json", "")):
            broken = tmp_path / name
            broken.write_text(text, encoding="utf-8")
            opened, dialogs, exceptions = through(sweep, lambda: window.open_project(broken))
            assert not exceptions, f"{name}: {exceptions}"
            assert opened is False, f"{name} opened"
            assert dialogs or "error" in window.output.toPlainText().lower(), f"{name}: nothing said"
            assert window.document.path == before, f"{name}: the open project was closed"


# ---- The board ----

def test_the_board_pulled_out_during_an_upload_is_said_and_nothing_hangs(qtbot, tmp_path, monkeypatch):
    from tests.virtual_board import available

    if not available():
        pytest.skip("the virtual board needs the Linux runtime")
    with Sweep(qtbot, monkeypatch, tmp_path, Board) as sweep:
        window = sweep.window
        board = Board.board
        sweep.watcher.seen = []
        with qtbot.capture_exceptions() as exceptions:
            assert window.upload_board(), "the upload did not start"
            wait(lambda: board.received, 5)    # the copy has begun
            board.unplug()
            ended = wait(lambda: window._worker is None, 60)
            settle(window)
        assert not exceptions
        assert ended, "the upload did not end after the board was pulled out"
        said = list(sweep.watcher.seen) + [window.output.toPlainText()[-600:], window.device_console.terminal.selected_text() or ""]
        assert sweep.watcher.seen or "error" in window.output.toPlainText().lower(), said
        assert answers(window)
        assert not window.document.read_only
        QApplication.processEvents()
