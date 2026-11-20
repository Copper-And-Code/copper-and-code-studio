"""An AI agent changes the project through MCP while the window has it open and a person works.

    pytest tests/manual/test_mcp_and_window.py --manual

The window finds out about a change made outside when it saves: it never writes over it
without a choice. Each case mixes the two and checks that nothing is lost without that choice:
- the person saves after the agent added a widget: Cancel keeps both versions where they are,
  Reload shows the agent's widget, Save a Copy keeps the person's version in another file,
  Overwrite keeps the person's; after each, the window agrees with its project;
- the agent writes with the revision it read after the person saved: refused, nothing lost;
- the agent removes the widget the person has selected; after Reload the canvas and the
  Properties panel do not show it any more;
- Start after a change by the agent asks first, and Cancel runs nothing stale.
"""
import json

import pytest
from copper_and_code_studio import mcp_server
from helpers import call, payload
from sweep import Example, Sweep, settle, wait
from test_monkey import broken_rules

pytestmark = pytest.mark.manual


def answer_external_change(monkeypatch, choice):
    """The person's answer to "changed by another program": reload, copy, overwrite or None."""
    monkeypatch.setattr("copper_and_code_studio.ui.main_files.FilesMixin._ask_external_change", lambda self, deleted=False: choice)


def on_disk(path):
    return json.loads(path.read_text(encoding="utf-8"))


def widget_names(data):
    return {widget["name"] for page in data["pages"] for widget in page.get("widgets", [])}


def person_moves(window):
    def move(project):
        widget = project.pages[0].widgets[-1]
        widget.props["x"] = int(widget.props.get("x", 0)) + 11
    window.document.execute("Move", move)
    return window.document.project.pages[0].widgets[-1]


@pytest.fixture
def ide(qtbot, tmp_path, monkeypatch):
    mcp_server.set_enabled(True)
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        window.document.undo_stack.setIndex(0)
        assert window.save_project()                 # the file and the window agree to start with
        yield sweep
        window.document.undo_stack.setClean()


@pytest.mark.parametrize("choice", [None, "reload", "copy", "overwrite"])
def test_the_person_saves_after_the_agent_added_a_widget(ide, monkeypatch, choice):
    window = ide.window
    path = window.document.path
    added = payload(call("add_widget", project=str(path), type="label", name="from_the_agent", props={"x": 5, "y": 5}))
    assert added["name"] == "from_the_agent"
    moved = person_moves(window)
    moved_x = moved.props["x"]
    answer_external_change(monkeypatch, choice)
    copies_before = set(path.parent.glob("*.json"))
    if choice == "copy":
        ide.watcher.answer = "ok"                    # the Save As dialog: a name next to the file
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getSaveFileName", staticmethod(lambda *arguments, **options: (str(path.with_name("copy.json")), "")))
    with ide.qtbot.capture_exceptions() as exceptions:
        saved = window.save_project()
        settle(window)
    assert not exceptions, exceptions
    data = on_disk(path)
    problems = []
    if choice is None:
        if saved or "from_the_agent" not in widget_names(data):
            problems.append("Cancel wrote over the agent's change")
        if not window.document.modified:
            problems.append("Cancel lost the person's move")
    elif choice == "reload":
        if "from_the_agent" not in {widget.name for widget in window.document.project.widgets}:
            problems.append("Reload does not show the agent's widget")
    elif choice == "copy":
        if "from_the_agent" not in widget_names(data):
            problems.append("Save a Copy wrote over the agent's file")
        copy = path.with_name("copy.json")
        if not copy.exists() and len(set(path.parent.glob("*.json")) - copies_before) == 0:
            problems.append("Save a Copy saved nothing")
        elif copy.exists() and not any(widget.get("props", {}).get("x") == moved_x for page in on_disk(copy)["pages"] for widget in page.get("widgets", [])):
            problems.append("the copy does not have the person's move")
    elif choice == "overwrite":
        if "from_the_agent" in widget_names(data):
            problems.append("Overwrite kept the agent's widget")
    problems += broken_rules(window)
    assert not problems, "\n".join(problems)


def test_the_agent_writing_with_an_old_revision_is_refused(ide):
    window = ide.window
    path = window.document.path
    revision = payload(call("project_info", project=str(path)))["revision"]
    person_moves(window)
    assert window.save_project()
    result = call("add_widget", project=str(path), type="label", name="late", expected_revision=revision)
    assert result.get("isError") and "revision" in result["content"][0]["text"], result
    assert "late" not in widget_names(on_disk(path)), "the agent wrote over the person's save"


def test_the_agent_removes_the_selected_widget_and_reload_follows(ide, monkeypatch):
    window = ide.window
    path = window.document.path
    view = window._active_designer()
    target = view.designer_scene.widget_items[window.document.project.pages[0].widgets[-1].id]
    view.designer_scene.clearSelection()
    target.setSelected(True)
    name = target.name
    assert wait(lambda: window.properties.names == [name], 2)
    payload(call("remove_widget", project=str(path), name=name))
    window.document.execute("Touch", lambda project: None)
    answer_external_change(monkeypatch, "reload")
    window.save_project()
    settle(window)
    problems = broken_rules(window)
    if any(item.name == name for item in window._active_designer().designer_scene.widget_items.values()):
        problems.append("the canvas still shows the removed widget")
    if name in window.properties.names:
        problems.append("the Properties panel still shows the removed widget")
    assert not problems, "\n".join(problems)


def test_start_after_the_agent_changed_the_file_asks_first(ide, monkeypatch):
    window = ide.window
    path = window.document.path
    payload(call("add_widget", project=str(path), type="label", name="from_the_agent"))
    person_moves(window)
    answer_external_change(monkeypatch, None)
    assert not window.run_project(), "Start ran over a change it did not ask about"
    assert not window.sim_panel.running
    assert "from_the_agent" in widget_names(on_disk(path))
