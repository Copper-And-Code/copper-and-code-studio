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


@pytest.mark.parametrize("path", PROJECTS, ids=lambda p: p.parent.name)
def test_example_code_defines_each_function_once(path):
    """The handler of an event is a function named after its widget and event: a function of the
    project with the same name is replaced by it, and a handler that calls it then calls itself.
    Forecast's swipe between places did nothing for that reason."""
    import ast
    from collections import Counter

    from copper_and_code_studio.core.model import Project
    from copper_and_code_studio.gen.project_gen import generate_app_events

    source, _sourcemap = generate_app_events(Project.load(path))
    names = Counter(node.name for node in ast.parse(source).body if isinstance(node, (ast.FunctionDef, ast.ClassDef)))
    assert [name for name, count in names.items() if count > 1] == []


def _card_examples():
    plan = json.loads((Path(__file__).parents[1] / "tools" / "esp32_sd.json").read_text(encoding="utf-8"))

    def walk(menu):
        for entry in menu:
            if "apps" in entry:
                yield from walk(entry["apps"])
            elif "example" in entry:
                yield entry["example"]

    return sorted(set(walk(plan["menu"])))


@pytest.mark.parametrize("name", _card_examples())
def test_every_app_of_the_card_speaks_english_and_italian(name):
    """The language is the one of cac_settings, chosen in Settings. An app with an IT dict translates
    each text of its pages with it, so each must be there, in letters the board's fonts have."""
    import ast

    project = json.loads((ROOT / name / "project.json").read_text(encoding="utf-8"))
    code = project["code"]["module"]
    assert "cac_settings.language()" in code or "cac_settings.translator(IT)" in code, name
    if "cac_settings.translator(IT)" not in code:
        return                            # Forecast, Crossword and Clock have texts of their own for each language
    tree = ast.parse(code)
    italian = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "IT")
    texts = {w["props"].get(key) for page in project["pages"] for w in page["widgets"] for key in ("text", "options", "placeholder")}
    missing = sorted(t for t in texts if isinstance(t, str) and any(c.isalpha() for c in t) and t not in italian)
    assert missing == [], f"{name}: no Italian for {missing}"
    assert [t for t in italian.values() if not all(builtin_glyph(c) for c in t)] == []
    assert "translate_once()" in json.dumps(project["code"]["handlers"])


@pytest.mark.parametrize("path", PROJECTS, ids=lambda p: p.parent.name)
def test_no_function_hides_the_translator(path):
    """t is the translator of the app: a function that makes a local t of its own and calls t() breaks."""
    import ast

    for node in ast.walk(ast.parse(json.loads(path.read_text(encoding="utf-8"))["code"]["module"])):
        if isinstance(node, (ast.FunctionDef, ast.Lambda)):
            names = [n for n in ast.walk(node) if isinstance(n, ast.Name) and n.id == "t"]
            local = any(isinstance(n.ctx, ast.Store) for n in names) or any(isinstance(a, ast.arg) and a.arg == "t" for a in ast.walk(node))
            called = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "t" for c in ast.walk(node))
            assert not (local and called), getattr(node, "name", "lambda")
