import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1] / "examples"
PROJECTS = sorted(ROOT.glob("*/project.json"))
TEXT_PROPS = ("text", "placeholder", "options")


def builtin_glyph(ch):
    # The built-in Montserrat of LVGL: ASCII, the degree sign, the bullet and the LV_SYMBOL icons.
    return ch == "\n" or " " <= ch <= "~" or ch in "°•" or "" <= ch <= ""


@pytest.mark.parametrize("path", PROJECTS, ids=lambda p: p.parent.name)
def test_example_opens_on_the_simulator(path):
    # A board as run target makes F5 ask for a serial port: an example must start in the simulator.
    assert "runTarget" not in json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", PROJECTS, ids=lambda p: p.parent.name)
def test_example_texts_have_glyphs_of_the_builtin_font(path):
    missing = []
    for page in json.loads(path.read_text(encoding="utf-8"))["pages"]:
        for widget in page["widgets"]:
            props = widget.get("props", {})
            if any("font" in key.lower() and key != "fontSize" for key in props):
                continue
            for key in TEXT_PROPS:
                value = props.get(key)
                if isinstance(value, str):
                    missing += [f"{widget.get('name')}.{key}: {ch!r}" for ch in value if not builtin_glyph(ch)]
    assert not missing, missing


@pytest.mark.parametrize("path", PROJECTS, ids=lambda p: p.parent.name)
def test_example_draws_what_it_asks(path):
    # Font sizes the board lacks fill the Output panel with warnings when the example starts.
    from copper_and_code_studio.core.model import Project

    assert Project.load(path).text_warnings() == []
