"""What is saved is what was in the window: save, open again in a new window, compare.

    pytest tests/manual/test_save_and_reopen.py --manual
    LMS_REOPEN_ROUNDS=20 pytest tests/manual/test_save_and_reopen.py --manual

- Each example, saved from the IDE and opened again, gives the same project; saved a second
  time, the file does not change by a byte.
- Round after round, the monkey of test_monkey.py works on a project for a while; then File →
  Save (or Save As, for a project without a file), and the file is opened in a second window.
  The project must be the same, and each page must look the same on the canvas of both windows.
"""
import json
import os
import random
import shutil

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from sweep import REPORTS, ROOT, SKIPPED, Example, Sweep, settle, wait
from test_monkey import step

pytestmark = pytest.mark.manual

ROUNDS = int(os.environ.get("LMS_REOPEN_ROUNDS", "6"))
EXAMPLES = sorted(path.parent.name for path in (ROOT / "examples").glob("*/project.json"))


def project_text(project):
    data = project.to_dict()
    return json.dumps(data, sort_keys=True, indent=1, default=str)


def canvas_pictures(window):
    """Each page as its canvas draws it, without selection and without the real preview."""
    pictures = {}
    for page_id, (_index, view) in window.designers.items():
        scene = view.designer_scene
        scene.clearSelection()
        rect = QRectF(0, 0, window.document.project.display.width, window.document.project.display.height)
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        pictures[page_id] = image
    return pictures


def without_preview(window):
    """Only the project on the canvas: no real rendering (it comes from a thread, when it comes)
    and no grid (a choice of the window, not of the project)."""
    for action in (window.preview_action, window.grid_action):
        if action.isChecked():
            action.trigger()
    QApplication.processEvents()


def reopened(qtbot, path):
    from lvgl_mpy_studio.ui.main_window import MainWindow

    other = MainWindow()
    qtbot.addWidget(other)
    other.resize(1400, 900)
    other.show()
    assert other.open_project(path), f"{path} does not open again"
    without_preview(other)
    settle(other)
    return other


def differences(window, other):
    found = []
    if project_text(window.document.project) != project_text(other.document.project):
        before, after = project_text(window.document.project).splitlines(), project_text(other.document.project).splitlines()
        changed = [f"{a!r} → {b!r}" for a, b in zip(before, after) if a != b][:3]
        found.append("the project opened again is not the one saved: " + "; ".join(changed or [f"{len(before)} lines → {len(after)}"]))
    mine, theirs = canvas_pictures(window), canvas_pictures(other)
    for page in window.document.project.pages:
        if page.id in mine and page.id in theirs and mine[page.id] != theirs[page.id]:
            folder = REPORTS / "reopen"
            folder.mkdir(parents=True, exist_ok=True)
            mine[page.id].save(str(folder / f"{page.name}-saved.png"))
            theirs[page.id].save(str(folder / f"{page.name}-opened.png"))
            found.append(f"the page {page.name} looks different on the canvas after opening it again (pictures in {folder})")
    return found


@pytest.mark.parametrize("example", EXAMPLES)
def test_an_example_saved_and_opened_again_is_the_same(qtbot, tmp_path, monkeypatch, example):
    folder = tmp_path / example
    shutil.copytree(ROOT / "examples" / example, folder, ignore=shutil.ignore_patterns("build", "visual", "*.mp4"))
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        window.document.undo_stack.setClean()
        assert window.open_project(folder / "project.json")
        without_preview(window)
        window.document.execute("Touch", lambda project: None)   # something to save
        assert window.save_project(), window.output.toPlainText()[-300:]
        first = (folder / "project.json").read_bytes()
        other = reopened(qtbot, folder / "project.json")
        problems = differences(window, other)
        other.document.execute("Touch", lambda project: None)
        assert other.save_project()
        if (folder / "project.json").read_bytes() != first:
            problems.append("saved a second time, the file changed")
        other.document.undo_stack.setClean()
        other.close()
    assert not problems, "\n".join(problems)


def test_what_the_monkey_did_is_saved(qtbot, tmp_path, monkeypatch):
    chance = random.Random(int(os.environ.get("LMS_MONKEY_SEED", "5")))
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        skipped = {id(getattr(window, attribute)) for attribute in SKIPPED}
        log = []
        for round_number in range(ROUNDS):
            sweep.watcher.answer = "cancel"
            for _ in range(60):
                step(chance, window, sweep.menus, skipped, log)
                settle(window, 20)
            if window.sim_panel.running:
                window.stop_simulation()
                wait(lambda: not window.sim_panel.running, 10)
            for dialog in [widget for widget in QApplication.topLevelWidgets() if widget.isVisible() and widget.isModal()]:
                dialog.close()
            path = window.document.path or tmp_path / f"round-{round_number}.json"
            if window.document.path is None:   # a new project: Save As is tried by the suite of every dialog
                window.document.save(path)
            else:
                window.document.execute("Touch", lambda project: None)
                saved = window.save_project()
                if not saved:                  # changed outside by the monkey's own Save As of another window: say so and go on
                    problems.append(f"round {round_number}: Save failed: {window.output.toPlainText()[-200:]}")
                    continue
            without_preview(window)
            other = reopened(qtbot, window.document.path)
            without_preview(other)
            found = differences(window, other)
            problems += [f"round {round_number}: {text}\n    last steps:\n      " + "\n      ".join(log[-8:]) for text in found]
            other.document.undo_stack.setClean()
            other.close()
        window.document.undo_stack.setClean()
        for tab in window.file_tabs:
            tab.editor.document().setModified(False)
    assert not problems, "\n".join(problems)
