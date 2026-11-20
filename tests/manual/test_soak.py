"""A long session in one window: what the IDE holds must not grow.

    pytest tests/manual/test_soak.py --manual
    LMS_SOAK_ROUNDS=100 pytest tests/manual/test_soak.py --manual     # longer

In one MainWindow, round after round: projects opened and closed, undo and redo of a whole
history, the simulator started and stopped, a property typed again and again. After a few
rounds to warm up, the next ones must leave the same number of Qt objects in the window, no
more top-level windows, no child processes left (or left as zombies), no temporary folders of
the IDE, and the memory of the process within a margin. Linux only: the memory and the
processes are read from /proc.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QApplication

from sweep import ROOT, Example, Sweep, settle, wait

pytestmark = [pytest.mark.manual, pytest.mark.skipif(not Path("/proc/self/statm").exists(), reason="reads /proc: Linux only")]

ROUNDS = int(os.environ.get("LMS_SOAK_ROUNDS", "30"))
WARM_UP = 5
MEMORY_MARGIN = 40 * 1024 * 1024               # bytes the process may grow after warming up
OBJECTS_MARGIN = 20                            # Qt objects: a few come and go with the timers


def memory():
    pages = int(Path("/proc/self/statm").read_text().split()[1])
    return pages * os.sysconf("SC_PAGE_SIZE")


def children():
    """(pid, state) of the child processes of this one; state Z is a zombie."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            continue
        if int(fields[1]) == os.getpid():
            found.append((int(entry.name), fields[0]))
    return found


def temporary_folders():
    return sorted(path.name for path in Path(tempfile.gettempdir()).glob("copper-and-code-studio-*") if "selftest" not in path.name)


def measure(window):
    # deleteLater acts when the event loop gets control back; processEvents() does not give it.
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    return {
        "memory": memory(),
        "objects": len(window.findChildren(QObject)),
        "windows": len([widget for widget in QApplication.topLevelWidgets() if widget.isVisible()]),
        "children": children(),
        "temporary": temporary_folders(),
    }


def one_round(window, projects, round_number):
    # Projects opened and closed: the other example, then back.
    for path in projects:
        window.document.undo_stack.setClean()  # nothing to save: Open must not ask
        assert window.open_project(path), f"{path} did not open"
        settle(window, 10)
    # A whole history undone and redone.
    def move(project):
        widget = project.pages[0].widgets[-1]
        widget.props["x"] = int(widget.props.get("x", 0)) + 1
    for _ in range(10):
        window.document.execute("Soak", move)
    stack = window.document.undo_stack
    for _ in range(3):
        stack.setIndex(0)
        stack.setIndex(stack.count())
    QApplication.processEvents()
    # The simulator started and stopped.
    assert window.run_project(), "Start failed: " + window.output.toPlainText()[-300:]
    assert wait(lambda: window.sim_panel.running, 20), "the simulator did not start"
    wait(lambda: False, 0.3)
    window.stop_simulation()
    assert wait(lambda: not window.sim_panel.running, 10), "the simulator did not stop"
    settle(window)
    stack.setIndex(0)
    window.document.undo_stack.setClean()


def test_a_long_session_does_not_grow(qtbot, tmp_path, monkeypatch):
    from copper_and_code_studio.platform import runtime_path

    if not runtime_path().exists():
        pytest.skip("runtime not built")
    folders = []
    for name in ("weather", "snake"):
        folder = tmp_path / "soak" / name
        shutil.copytree(ROOT / "examples" / name, folder, ignore=shutil.ignore_patterns("build", "visual", "*.mp4"))
        folders.append(folder / "project.json")
    rows = []
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        with qtbot.capture_exceptions() as exceptions:
            for number in range(ROUNDS):
                one_round(window, folders, number)
                rows.append(measure(window))
        base, last = rows[WARM_UP - 1], rows[-1]
    (ROOT / "build" / "manual").mkdir(parents=True, exist_ok=True)
    (ROOT / "build" / "manual" / "soak.json").write_text(json.dumps([{key: row[key] for key in ("memory", "objects", "windows")} for row in rows], indent=1) + "\n", encoding="utf-8")
    problems = [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
    grown = last["memory"] - base["memory"]
    if grown > MEMORY_MARGIN:
        problems.append(f"the memory grew by {grown // 1024 // 1024} MB in {ROUNDS - WARM_UP} rounds after warming up")
    if last["objects"] > base["objects"] + OBJECTS_MARGIN:
        problems.append(f"Qt objects of the window: {base['objects']} after warming up, {last['objects']} at the end")
    if last["windows"] > base["windows"]:
        problems.append(f"visible top-level windows: {base['windows']} → {last['windows']}")
    zombies = [pid for pid, state in last["children"] if state == "Z"]
    if zombies:
        problems.append(f"zombie processes left: {zombies}")
    if len(last["children"]) > len(base["children"]):
        problems.append(f"child processes: {base['children']} → {last['children']}")
    added = sorted(set(last["temporary"]) - set(base["temporary"]))
    if added:
        problems.append(f"temporary folders left: {added}")
    print(f"\nsoak: {ROUNDS} rounds, memory {base['memory'] // 1024 // 1024} → {last['memory'] // 1024 // 1024} MB, Qt objects {base['objects']} → {last['objects']}")
    assert not problems, "\n".join(problems)
