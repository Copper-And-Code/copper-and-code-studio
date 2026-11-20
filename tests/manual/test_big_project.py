"""A large project in the window: what a person does must stay quick.

    pytest tests/manual/test_big_project.py --manual

A project of 30 pages and about 2000 widgets (every visual type, some inside panels, a handler
for every button) is opened in the window. Then, timed: opening it, showing each page, Select
All on a page, moving the selection with an arrow key, a property typed in the panel, undo and
redo of a move, saving, and Start until the simulator shows its screen. Each must stay within
its limit, and within half again of the last run on this PC, kept in
build/manual/big-project.json.
"""
import json
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from copper_and_code_studio.core.components import is_component
from copper_and_code_studio.core.model import Project, widget_definitions
from copper_and_code_studio.platform import runtime_path
from sweep import REPORTS, Empty, Sweep, settle, wait

pytestmark = pytest.mark.manual

PAGES, PER_PAGE = 30, 66
LIMITS = {                                     # seconds
    "open": 8.0, "show a page": 1.0, "select all": 1.5, "move with an arrow": 1.5, "type a property": 1.5,
    "undo": 1.5, "redo": 1.5, "save": 3.0, "start": 30.0,
}
SLIP = 1.5                                     # against the last run on this PC


def big_project():
    project = Project("big")
    project.set_display_size(1024, 600)
    types = [widget_type for widget_type in sorted(widget_definitions()) if not is_component(widget_type)]
    for number in range(PAGES):
        page = project.pages[0] if number == 0 else project.new_page(f"page{number + 1}")
        if number:
            project.pages.append(page)
        panel = project.add_widget(page, "panel", {"x": 700, "y": 20, "width": 300, "height": 500})
        for index in range(PER_PAGE - 1):
            widget_type = types[index % len(types)]
            widget = project.add_widget(page, widget_type, {"x": (index % 8) * 85, "y": (index // 8) * 70})
            if index % 6 == 0:
                widget.parentId = panel.id
                widget.props.update(x=(index % 3) * 90, y=(index // 18) * 60)
            if widget_type == "button":
                project.ensure_handler(widget.name)[1].body = 'print("pressed")'
    return project


def timed(action, done=lambda: True, seconds=60):
    started = time.monotonic()
    action()
    wait(done, seconds)
    QApplication.processEvents()
    return time.monotonic() - started


def test_a_large_project_stays_quick(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "big" / "project.json"
    path.parent.mkdir()
    project = big_project()
    project.save(path)
    count = len(project.widgets)
    times = {}
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        window.document.undo_stack.setClean()
        if window.preview_action.isChecked():
            window.preview_action.trigger()   # the real rendering of each page is timed by test_looks, not here
        times["open"] = timed(lambda: window.open_project(path))
        views = [view for _index, view in sorted(window.designers.values(), key=lambda pair: pair[0])]
        slowest = 0.0
        for view in views:
            slowest = max(slowest, timed(lambda view=view: window.tabs.setCurrentWidget(view)))
        times["show a page"] = slowest
        view = views[0]
        window.tabs.setCurrentWidget(view)
        view.setFocus()
        times["select all"] = timed(lambda: window.select_all_action.trigger(), lambda: len(view.designer_scene.selected_names()) >= PER_PAGE - 1)
        times["move with an arrow"] = timed(lambda: QTest.keyClick(view, Qt.Key_Right))
        times["undo"] = timed(lambda: window.undo_action.trigger())
        times["redo"] = timed(lambda: window.redo_action.trigger())
        view.designer_scene.clearSelection()
        first = window.document.project.pages[0].widgets[1]
        view.designer_scene.widget_items[first.id].setSelected(True)
        wait(lambda: window.properties.names == [first.name], 3)
        def type_x():
            from test_every_property import open_field, type_into

            editor = open_field(window.properties, "x")
            type_into(editor, "333")
        times["type a property"] = timed(type_x, lambda: window.document.project.find_widget(first.name).props.get("x") == 333)
        times["save"] = timed(lambda: window.save_project())
        if runtime_path().exists():
            times["start"] = timed(lambda: window.run_project(), lambda: window.sim_panel.running and window.sim_panel.first_frame_ms is not None, 60)
            window.stop_simulation()
            wait(lambda: not window.sim_panel.running, 10)
        settle(window)
        window.document.undo_stack.setClean()
    report = REPORTS / "big-project.json"
    previous = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(times, indent=1) + "\n", encoding="utf-8")
    print(f"\n{count} widgets on {PAGES} pages:\n  " + "\n  ".join(f"{name}: {seconds:.2f} s" + (f" (last {previous[name]:.2f})" if name in previous else "") for name, seconds in times.items()))
    problems = [f"{name}: {seconds:.2f} s, over the limit of {LIMITS[name]} s" for name, seconds in times.items() if seconds > LIMITS[name]]
    problems += [f"{name}: {seconds:.2f} s, {seconds / previous[name]:.1f} times the last run" for name, seconds in times.items() if name in previous and previous[name] > 0.2 and seconds > previous[name] * SLIP]
    assert not problems, "\n".join(problems)
