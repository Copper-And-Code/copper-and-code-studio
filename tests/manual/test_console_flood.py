"""Programs that print without pause: the window must keep answering, and stop them.

    pytest tests/manual/test_console_flood.py --manual

- A program without pages prints thousands of lines a second into the terminal of the
  simulator; Ctrl-C typed in the terminal stops it.
- An app with pages prints from an LVGL timer into the Output panel; Stop stops it.
- A file of the virtual board prints without pause into the Device Console; the Ctrl-C button
  stops it (Linux, where the virtual board runs).
For eight seconds each: the window answers within half a second at every look, the memory of
the process grows by less than 80 MB, and what the console keeps is bounded.
"""
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from copper_and_code_studio.platform import runtime_path
from sweep import Board, Empty, Sweep, settle, wait

pytestmark = pytest.mark.manual

SECONDS = 8
SLOWEST = 0.5                                  # seconds the window may take to answer
MEMORY = 80 * 1024 * 1024
FLOOD = 'i = 0\nwhile True:\n    print("line", i, "x" * 60)\n    i += 1\n'


def memory():
    statm = Path("/proc/self/statm")
    return int(statm.read_text().split()[1]) * 4096 if statm.exists() else 0


def watch(window, seconds):
    """The slowest answer of the window, looking every 50 ms for a while."""
    slowest, end = 0.0, time.monotonic() + seconds
    while time.monotonic() < end:
        done, asked = [], time.monotonic()
        QTimer.singleShot(0, lambda: done.append(time.monotonic()))
        while not done and time.monotonic() - asked < 5:
            QApplication.processEvents()
        slowest = max(slowest, (done[0] if done else time.monotonic()) - asked)
        wait(lambda: False, 0.05)
    return slowest


def check(slowest, grown, problems, what):
    if slowest > SLOWEST:
        problems.append(f"{what}: the window took {slowest:.2f} s to answer")
    if grown > MEMORY:
        problems.append(f"{what}: the memory grew by {grown // 1024 // 1024} MB")


def test_a_program_floods_its_terminal_and_ctrl_c_stops_it(qtbot, tmp_path, monkeypatch):
    if not runtime_path().exists():
        pytest.skip("runtime not built")
    program = tmp_path / "flood" / "flood.py"
    program.parent.mkdir()
    program.write_text(FLOOD, encoding="utf-8")
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        start = memory()
        assert window.run_program(program), window.output.toPlainText()[-300:]
        assert wait(lambda: window.sim_panel.running, 20)
        terminal = window.sim_panel.terminal
        slowest = watch(window, SECONDS)
        check(slowest, memory() - start, problems, "terminal")
        terminal.setFocus()
        QTest.keyClick(terminal, Qt.Key_C, Qt.ControlModifier)
        if not wait(lambda: "KeyboardInterrupt" in terminal.text() or not window.sim_panel.running, 5):
            problems.append("Ctrl-C did not stop the program")
        window.stop_simulation()
        if not wait(lambda: not window.sim_panel.running, 10):
            problems.append("Stop did not stop the simulator")
        if len(terminal.screen.history) > terminal.screen.history.maxlen:
            problems.append("the terminal keeps more lines than its limit")
    assert not problems, "\n".join(problems)


def test_an_app_floods_the_output_and_stop_stops_it(qtbot, tmp_path, monkeypatch):
    if not runtime_path().exists():
        pytest.skip("runtime not built")
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        def flood(project):
            project.add_widget(project.pages[0], "label")
            project.code.module = 'def _flood(timer):\n    for _ in range(40):\n        print("output", "y" * 70)\n\nlv.timer_create(_flood, 5, None)\n'
        window.document.execute("Flood", flood)
        start = memory()
        assert window.run_project(), window.output.toPlainText()[-300:]
        assert wait(lambda: window.sim_panel.running, 20)
        slowest = watch(window, SECONDS)
        check(slowest, memory() - start, problems, "Output")
        lines = window.output.document().blockCount()
        if lines > window.output.maximumBlockCount() + 1:
            problems.append(f"the Output keeps {lines} lines, more than its limit")
        if "output yyyy" not in window.output.toPlainText():
            problems.append("the Output shows nothing of what the app printed")
        stopping = time.monotonic()
        window.stop_simulation()
        if not wait(lambda: not window.sim_panel.running, 10):
            problems.append("Stop did not stop the app")
        elif time.monotonic() - stopping > 3:
            problems.append(f"Stop took {time.monotonic() - stopping:.1f} s")
        window.document.undo_stack.setClean()
    assert not problems, "\n".join(problems)


def test_a_board_floods_the_device_console_and_ctrl_c_stops_it(qtbot, tmp_path, monkeypatch):
    from tests.virtual_board import available

    if not available():
        pytest.skip("the virtual board needs the Linux runtime")
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Board) as sweep:
        window = sweep.window
        board = Board.board
        (board.flash / "flash" / "flood.py").write_text(FLOOD, encoding="utf-8")
        start = memory()
        assert window.run_file_on_board("/flash/flood.py")
        terminal = window.device_console.terminal
        if not wait(lambda: "line" in terminal.text(), 10):
            problems.append("the Device Console shows nothing of what the board printed")
        slowest = watch(window, SECONDS)
        check(slowest, memory() - start, problems, "Device Console")
        received = len(board.received)
        QTest.mouseClick(window.device_console.ctrl_c, Qt.LeftButton)
        settle(window, 5)
        if len(board.received) == received:
            problems.append("the Ctrl-C button sent nothing to the board")
        wait(lambda: False, 0.5)
        shown = terminal.text()
        wait(lambda: False, 1.0)
        if terminal.text() != shown:
            problems.append("after Ctrl-C the board goes on printing")
        if len(terminal.screen.history) > terminal.screen.history.maxlen:
            problems.append("the Device Console keeps more lines than its limit")
    assert not problems, "\n".join(problems)
