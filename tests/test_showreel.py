"""tools/showreel: the storyboards without Qt, then a short replay of an example in the real IDE."""
import json
import shutil
from pathlib import Path

import pytest

from lvgl_mpy_studio.platform import runtime_path
from tools.showreel import storyboard

ROOT = Path(__file__).parents[1]
EXAMPLES = sorted(path.parent for path in (ROOT / "examples").glob("*/project.json"))
needs_runtime = pytest.mark.skipif(not runtime_path().exists(), reason="runtime not built")


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.name)
def test_every_example_has_a_storyboard_that_loads(example):
    board = storyboard.load(example)
    assert board["step"][0]["do"] == "title" and board["step"][-1]["do"] == "end"
    assert storyboard.check(storyboard.tomllib.loads(storyboard.to_toml(board))) == board


def test_the_default_storyboard_types_a_handler_of_a_widget_on_the_first_page():
    project = json.loads((ROOT / "examples/weather/project.json").read_text(encoding="utf-8"))
    board = storyboard.default(project)
    code = next(step for step in board["step"] if step["do"] == "code")
    assert project["code"]["handlers"][code["handler"]]["widget"] in {widget["name"] for widget in project["pages"][0]["widgets"]}
    add = next(step for step in board["step"] if step["do"] == "add")
    assert "clock" not in add["widgets"]        # a timer has no place on the canvas to drop it


@pytest.mark.parametrize("data, message", [
    ({"step": [{"do": "jump"}]}, "do = 'jump'"),
    ({"step": [{"do": "tap", "widgte": "ok"}]}, "no field widgte"),
    ({"step": [{"do": "start", "anchor": "sidebar"}]}, "anchor = 'sidebar'"),
    ({"video": {"colour": 1}, "step": [{"do": "end"}]}, "no field 'colour'"),
    ({"step": []}, "no [[step]]"),
])
def test_mistakes_in_a_storyboard_are_named(data, message):
    with pytest.raises(storyboard.StoryboardError, match=message.replace("[", r"\[")):
        storyboard.check(data)


def test_only_keeps_one_phase():
    board = storyboard.load(ROOT / "examples/snake")
    design = [step["do"] for step in storyboard.only(board, "design")["step"]]
    run = [step["do"] for step in storyboard.only(board, "run")["step"]]
    assert "start" not in design and design[-1] == "end"
    assert run[:3] == ["create", "fill", "start"] and "code" not in run


@needs_runtime
def test_a_replay_rebuilds_the_example_and_runs_it(tmp_path):
    from tools.showreel.ide import Ide
    from tools.showreel.player import Player
    from tools.showreel.timeline import Timeline

    board = storyboard.check({"video": {"window": [1200, 800], "title": "Weather"}, "step": [
        {"do": "title", "seconds": 0.2},
        {"do": "create", "balloon": "A new project", "anchor": "toolbar.resolution", "hold": 0.1},
        {"do": "add", "widgets": ["background"], "seconds_each": 0.1},
        {"do": "fill", "page": "main", "per_frame": 10, "hold": 0},
        {"do": "set", "widget": "city", "prop": "text", "value": "Rome", "hold": 0},
        {"do": "code", "handler": "refresh_clicked", "chars_per_frame": 20, "anchor": "code.editor", "hold": 0},
        {"do": "start", "hold": 0.3},
        {"do": "tap", "widget": "refresh", "hold": 0.3},
        {"do": "end", "seconds": 0.2},
    ]})
    ide = Ide(tuple(board["video"]["window"]))
    timeline = Timeline(tmp_path / "frames", 25)
    player = Player(ide, timeline, board, ROOT / "examples/weather", tmp_path / "work", log=lambda text: None)
    try:
        player.play()
    finally:
        ide.close()
        timeline.finish()
    assert player.notes == ["before Start, completed without frames: settings"]
    assert {"title", "create", "start", "end"} <= set(timeline.marks)
    from PySide6.QtGui import QImage
    assert QImage(str(timeline.path(timeline.count - 1))).size().toTuple() == (1200, 800)
    original = json.loads((ROOT / "examples/weather/project.json").read_text(encoding="utf-8"))
    rebuilt = json.loads((tmp_path / "work/project.json").read_text(encoding="utf-8"))
    assert rebuilt["code"] == original["code"]          # the typed handler is the example's, to the character
    city = next(widget for widget in rebuilt["pages"][0]["widgets"] if widget["name"] == "city")
    assert city["props"]["text"] == "Rome"

    if shutil.which("ffmpeg"):
        from tools.showreel import encode
        assert encode.gif(timeline, tmp_path / "cut.gif", timeline.marks["start"], 10, 10, 320).stat().st_size > 0
