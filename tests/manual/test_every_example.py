"""Every example started in the simulator and touched, as a person tries it.

    pytest tests/manual/test_every_example.py --manual

Each example is opened in the window and started with Run → Start; then, on the page it
starts from, the middle of each widget is touched in turn on the simulated screen, with a
little time between touches, and a few seconds more are left to its timers. Nothing may
reach the Errors panel or the Output as a Python error, the simulator must still run at the
end, and Stop must stop it. Games and pages change under the touches: that is the point.
"""
import os
import shutil

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from copper_and_code_studio.core.model import is_component
from copper_and_code_studio.platform import runtime_path
from sweep import QT_NOISE, ROOT, Empty, Sweep, wait

pytestmark = pytest.mark.manual

EXAMPLES = sorted(path.parent.name for path in (ROOT / "examples").glob("*/project.json"))
ERRORS = ("Traceback", "Error:", "Exception")


def tap(window, x, y):
    screen = window.sim_panel.screen
    target = screen._target()
    point = QPoint(int(target.x() + (x + 0.5) * target.width() / screen.image.width()), int(target.y() + (y + 0.5) * target.height() / screen.image.height()))
    QTest.mousePress(screen, Qt.LeftButton, pos=point)
    wait(lambda: False, 0.12)
    QTest.mouseRelease(screen, Qt.LeftButton, pos=point)
    wait(lambda: False, 0.25)


@pytest.mark.parametrize("example", EXAMPLES)
def test_every_example_runs_and_answers_touches(qtbot, tmp_path, monkeypatch, example):
    if not runtime_path().exists():
        pytest.skip("runtime not built")
    folder = tmp_path / example
    shutil.copytree(ROOT / "examples" / example, folder, ignore=shutil.ignore_patterns("build", "visual", "*.mp4"))
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        assert window.open_project(folder / "project.json")
        project = window.document.project
        page = project.pages[project.initial_page_index()]
        widgets = [widget for widget in page.widgets if not is_component(widget.type)] if hasattr(page, "widgets") else []
        sweep.warnings.clear()
        with qtbot.capture_exceptions() as exceptions:
            assert window.run_project(), "Start failed: " + window.output.toPlainText()[-500:]
            assert wait(lambda: window.sim_panel.running and window.sim_panel.screen.image is not None and not window.sim_panel.screen.image.isNull(), 20), "the simulator did not show its screen"
            wait(lambda: False, 1.0)
            for widget in widgets:
                x, y = project.screen_position(widget)
                width, height = (widget.props.get(key, 0) for key in ("width", "height"))
                if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
                    continue
                tap(window, min(max(int(x + width / 2), 0), project.display.width - 1), min(max(int(y + height / 2), 0), project.display.height - 1))
                if not window.sim_panel.running:
                    break
            wait(lambda: False, 3.0)           # the timers of the app
            still_running = window.sim_panel.running
            window.stop_simulation()
            stopped = wait(lambda: not window.sim_panel.running, 10)
        output = window.output.toPlainText()
        if os.environ.get("LMS_SHOW_OUTPUT"):
            print("\n----- OUTPUT -----\n" + output[-3000:])
        problems += [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
        problems += [f"Qt warning: {text}" for text in sweep.warnings if not any(noise in text for noise in QT_NOISE)]
        if window.errors.topLevelItemCount():
            problems.append("the Errors panel: " + "; ".join(window.errors.topLevelItem(index).text(2) for index in range(window.errors.topLevelItemCount())))
        problems += [f"the Output has: {line}" for line in output.splitlines() if any(mark in line for mark in ERRORS)]
        if not still_running:
            problems.append("the simulator stopped by itself under the touches")
        if not stopped:
            problems.append("Stop did not stop the simulator")
        window.document.undo_stack.setClean()
    print(f"\n{example}: {len(widgets)} widgets touched")
    assert not problems, f"{example}:\n" + "\n".join(problems[:20])
