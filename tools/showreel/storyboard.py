"""The storyboard: <example>/showreel.toml, or a default one made from project.json.

It is plain data, read without Qt: a [video] table and a list of [[step]] tables.
"""
import json
import tomllib
from pathlib import Path

VIDEO = {
    "title": "",
    "subtitle": "Built and run in LVGL MPY Studio",
    "window": [1600, 1000],
    "fps": 25,
    "gif": {"from": "start", "seconds": 10},
    "poster": "start",
}
GIF = {"from", "seconds", "fps", "width"}
ANCHORS = {"toolbox", "project", "properties", "events", "canvas", "code", "simulator", "toolbar", "output"}
TOOLBAR = {"start", "resolution"}

COMMON = {"balloon", "anchor", "hold", "speed"}
STEPS = {
    "title": {"seconds"},
    "create": set(),
    "add": {"widgets", "cursor", "seconds_each"},
    "fill": {"page", "pages", "per_frame"},
    "select": {"widget"},
    "set": {"widget", "prop", "value"},
    "page": {"name"},
    "code": {"handler", "module", "lines", "chars_per_frame"},
    "start": set(),
    "tap": {"widget", "x", "y"},
    "drag": {"widget", "x", "y", "x_to", "y_to", "ms"},
    "press": {"widget", "x", "y"},
    "release": {"widget", "x", "y"},
    "wait": {"seconds"},
    "stop": set(),
    "end": {"seconds", "text"},
}


class StoryboardError(ValueError):
    pass


def load(example, path=None):
    """The storyboard of an example folder: path, or its showreel.toml, or the default one."""
    folder = Path(example)
    if folder.is_file():
        folder = folder.parent
    path = Path(path) if path else folder / "showreel.toml"
    project = json.loads((folder / "project.json").read_text(encoding="utf-8"))
    if not path.is_file():
        return default(project)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise StoryboardError(f"{path}: {exc}") from None
    return check(data, str(path))


def check(data, where="storyboard"):
    unknown = set(data) - {"video", "step"}
    if unknown:
        raise StoryboardError(f"{where}: unknown table {', '.join(sorted(unknown))}; only [video] and [[step]]")
    video = dict(VIDEO)
    for key, value in data.get("video", {}).items():
        if key not in VIDEO:
            raise StoryboardError(f"{where}: [video] has no field {key!r}; known: {', '.join(VIDEO)}")
        video[key] = value
    steps = data.get("step", [])
    if not steps:
        raise StoryboardError(f"{where}: no [[step]]")
    gif = video["gif"]
    if not isinstance(gif, dict) or set(gif) - GIF:
        raise StoryboardError(f"{where}: [video] gif is a table with {', '.join(sorted(GIF))}")
    for number, step in enumerate(steps, 1):
        anchor = step.get("anchor")
        if anchor is not None:
            head, _, rest = str(anchor).partition(".")
            if head not in ANCHORS or (head == "toolbar" and rest not in TOOLBAR) or (head == "events" and not rest):
                raise StoryboardError(f"{where}: step {number} has anchor = {anchor!r}; known: {', '.join(sorted(ANCHORS))}, "
                                      "toolbox.<type>, canvas.<widget>, properties.<prop>, properties.events, events.<event>, "
                                      "code.editor, code.signature, toolbar.start, toolbar.resolution")
        kind = step.get("do")
        if kind not in STEPS:
            raise StoryboardError(f"{where}: step {number} has do = {kind!r}; known: {', '.join(STEPS)}")
        extra = set(step) - STEPS[kind] - COMMON - {"do"}
        if extra:
            raise StoryboardError(f"{where}: step {number} ({kind}) has no field {', '.join(sorted(extra))}")
    return {"video": video, "step": steps}


def only(storyboard, phase):
    """The design steps (up to Start), or the run steps with the project made whole at once."""
    steps = storyboard["step"]
    first_run = next((index for index, step in enumerate(steps) if step["do"] == "start"), len(steps))
    if phase == "design":
        kept = steps[:first_run] + [step for step in steps if step["do"] == "end"]
    else:
        kept = [{"do": "create"}, {"do": "fill", "pages": "rest", "per_frame": 1000}] + steps[first_run:]
    return dict(storyboard, step=kept)


def default(project):
    """title, create, a few widgets added, the first page filled, a handler typed, the other pages, run."""
    pages = project.get("pages", [])
    first = pages[0] if pages else {"name": "", "widgets": []}
    display = project.get("display", {})
    size = f"{display.get('width', '?')}×{display.get('height', '?')}"
    steps = [
        {"do": "title", "seconds": 2.5},
        {"do": "create", "balloon": f"A new project, {size}", "anchor": "project"},
    ]
    # Widgets seen on the canvas: a timer or a buzzer has no size.
    names = [widget["name"] for widget in first["widgets"] if not widget.get("parentId") and "width" in widget.get("props", {})][:3]
    if names:
        steps.append({"do": "add", "widgets": names, "balloon": "Drag widgets from the Toolbox onto the page", "anchor": "toolbox"})
    rest = len(first["widgets"]) - len(names)
    if rest > 0:
        steps.append({"do": "fill", "page": first["name"], "per_frame": 3, "balloon": f"…and the rest of the page: {rest} more widgets", "anchor": "canvas"})
    on_first = {widget["name"] for widget in first["widgets"]}
    handlers = (project.get("code") or {}).get("handlers") or {}
    handler = next((name for name, code in handlers.items() if code.get("widget") in on_first and code.get("body", "").strip()), None)
    if handler:
        steps.append({"do": "code", "handler": handler, "balloon": "Events tab, double click: the handler is plain MicroPython", "anchor": "code.editor"})
    if len(pages) > 1:
        steps.append({"do": "fill", "pages": "rest", "per_frame": 6, "balloon": f"{len(pages) - 1} more pages", "anchor": "project"})
    steps += [
        {"do": "start", "balloon": "Start: the real MicroPython and LVGL, compiled for the PC", "anchor": "simulator"},
        {"do": "wait", "seconds": 4},
        {"do": "end", "seconds": 3},
    ]
    video = dict(VIDEO, title=project.get("projectName") or "LVGL MPY Studio")
    return check({"video": video, "step": steps}, "default storyboard")


def to_toml(storyboard):
    """The storyboard written as TOML, to start a showreel.toml from the default one."""
    lines = ["[video]"]
    for key, value in storyboard["video"].items():
        lines.append(f"{key} = {_value(value)}")
    for step in storyboard["step"]:
        lines += ["", "[[step]]"]
        lines += [f"{key} = {_value(value)}" for key, value in step.items()]
    return "\n".join(lines) + "\n"


def _value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{key} = {_value(item)}" for key, item in value.items()) + " }"
    raise TypeError(f"cannot write {value!r} as TOML")
