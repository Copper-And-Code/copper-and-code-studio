"""tools/esp32_sd.py: the SD card of the ESP32-4848S040, filled and brought up to date."""
import json
from pathlib import Path

import pytest

from tools import esp32_sd

ROOT = Path(__file__).parents[1]
PLAN = {
    "board": "esp32_4848s040_480",
    "start": "Settings",
    "boardFiles": {"lib/home.py": "examples/home/home.py"},
    "menu": [
        {"name": "Settings", "example": "settings"},
        {"name": "Mine", "path": "/sd/mine/main.py"},
        {"name": "Games", "apps": [{"name": "Snake", "program": "examples/snake.py"}, {"name": "Star Guard", "example": "star-guard"}]},
    ],
}


@pytest.fixture
def boards(tmp_path):
    """A stand-in for the board repository: the two files the plan of these tests takes from it."""
    folder = tmp_path / "boards"
    (folder / "examples" / "home").mkdir(parents=True)
    (folder / "examples" / "home" / "home.py").write_text("# the home\n")
    (folder / "examples" / "snake.py").write_text("print('snake')\n")
    return folder


def fill(tmp_path, boards, plan=PLAN, name="staging"):
    staging = tmp_path / name
    said = []
    files, folders = esp32_sd.build_card(plan, boards, staging, esp32_sd.local_bytecode_version(tmp_path), said.append)
    return files, folders, said


def test_the_card_has_the_home_the_programs_and_each_app_in_a_folder(tmp_path, boards):
    files, folders, _said = fill(tmp_path, boards)
    assert folders == ["apps/settings", "apps/star-guard"]
    assert {"home.json", "lib/home.py", "apps/snake.py", "apps/settings/app_main.py", "apps/star-guard/app_main.py"} <= set(files)
    assert all(source.is_file() for source in files.values())
    # an app is what an upload puts on the board: bytecode where the IDE's compiler makes it, its modules, its manifest
    assert "apps/settings/manifest.json" in files and any(name.startswith("apps/settings/cac_settings.") for name in files)
    if esp32_sd.local_bytecode_version(tmp_path) is not None:
        assert "apps/settings/ui.mpy" in files and "apps/settings/ui.py" not in files
    menu = json.loads(files["home.json"].read_text())
    assert menu == {"start": "/sd/apps/settings/app_main.py", "apps": [
        {"name": "Settings", "path": "/sd/apps/settings/app_main.py"},
        {"name": "Mine", "path": "/sd/mine/main.py"},   # something already on the card: listed, nothing copied
        {"name": "Games", "apps": [{"name": "Snake", "path": "/sd/apps/snake.py"}, {"name": "Star Guard", "path": "/sd/apps/star-guard/app_main.py"}]},
    ]}


def test_a_second_run_writes_only_what_changed_and_leaves_the_rest_of_the_card(tmp_path, boards):
    card = tmp_path / "card"
    (card / "photos").mkdir(parents=True)
    (card / "photos" / "one.bin").write_bytes(b"a photo")
    (card / "weather.json").write_text("{}")
    (card / "home.json").write_text('{"apps": []}\n')
    (card / "apps" / "old").mkdir(parents=True)
    (card / "apps" / "old" / "app_main.py").write_text("# an app that is no longer in the list\n")
    files, folders, _said = fill(tmp_path, boards)
    target = esp32_sd.Folder(card)
    assert esp32_sd.update_card(files, folders, target, say=lambda line: None) == (len(files), 0, 0)
    assert (card / "home.json.previous").read_text() == '{"apps": []}\n'   # the menu it replaced
    for path, source in files.items():
        assert (card / path).read_bytes() == source.read_bytes(), path
    assert esp32_sd.update_card(files, folders, target, say=lambda line: None) == (0, 0, len(files))

    (boards / "examples" / "snake.py").write_text("print('snake, changed')\n")
    (card / "apps" / "settings" / "lms_font_old.bin").write_bytes(b"a font the app no longer has")
    files, folders, _said = fill(tmp_path, boards, name="again")
    said = []
    assert esp32_sd.update_card(files, folders, target, dry_run=True, say=said.append) == (1, 1, len(files) - 1)
    assert said == ["  write   apps/snake.py", "  remove  apps/settings/lms_font_old.bin"]
    assert (card / "apps" / "snake.py").read_text() == "print('snake')\n"   # a dry run only says
    assert esp32_sd.update_card(files, folders, target, say=lambda line: None) == (1, 1, len(files) - 1)
    assert (card / "apps" / "snake.py").read_text() == "print('snake, changed')\n"
    assert not (card / "apps" / "settings" / "lms_font_old.bin").exists()
    # nothing else is touched: photos, settings, an app that left the list
    assert (card / "photos" / "one.bin").read_bytes() == b"a photo" and (card / "weather.json").read_text() == "{}"
    assert (card / "apps" / "old" / "app_main.py").is_file()
    assert not list(card.rglob("*.part"))


def test_what_is_wrong_is_said_in_one_line(tmp_path, boards, capsys):
    said = []
    assert esp32_sd.main(["--boards", str(boards)], said.append) == 1 and "one of the two" in said[-1]
    assert esp32_sd.main([str(tmp_path / "nowhere"), "--boards", str(boards)], said.append) == 1 and "not a folder" in said[-1]
    card = tmp_path / "card"
    card.mkdir()
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({**PLAN, "start": None, "menu": [{"name": "Snake", "program": "examples/missing.py"}]}))
    assert esp32_sd.main([str(card), "--boards", str(boards), "--plan", str(plan)], said.append) == 1 and "not found" in said[-1]
    plan.write_text(json.dumps({**PLAN, "start": None, "menu": [{"name": "Eim", "example": "eim-01"}]}))   # an example for another screen
    assert esp32_sd.main([str(card), "--boards", str(boards), "--plan", str(plan)], said.append) == 1 and "another screen size" in said[-1]
    plan.write_text(json.dumps({**PLAN, "start": None, "menu": [{"name": "Snake", "program": "examples/snake.py"}, {"name": "Snake too", "example": "snake"}]}))
    assert esp32_sd.main([str(card), "--boards", str(boards), "--plan", str(plan)], said.append) == 1 and "same name" in said[-1]
    plan.write_text(json.dumps({**PLAN, "start": "Star Guard"}))   # in the folder Games: not an app of power-on
    assert esp32_sd.main([str(card), "--boards", str(boards), "--plan", str(plan)], said.append) == 1 and "first level" in said[-1]
    assert not list(card.iterdir())   # nothing was written before the mistake was found


def test_the_script_run_as_a_command_fills_a_folder(tmp_path, boards):
    card = tmp_path / "card"
    card.mkdir()
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(PLAN))
    said = []
    assert esp32_sd.main([str(card), "--boards", str(boards), "--plan", str(plan), "--dry-run"], said.append) == 0
    assert not list(card.iterdir()) and "to write" in said[-1]
    assert esp32_sd.main([str(card), "--boards", str(boards), "--plan", str(plan), "--source"], said.append) == 0
    assert (card / "apps" / "settings" / "ui.py").is_file() and not (card / "apps" / "settings" / "ui.mpy").exists()   # --source: no bytecode
    assert json.loads((card / "home.json").read_text())["apps"][0]["path"] == "/sd/apps/settings/app_main.py"
    plan.write_text(json.dumps({key: value for key, value in PLAN.items() if key != "start"}))
    assert esp32_sd.main([str(card), "--boards", str(boards), "--plan", str(plan)], said.append) == 0
    assert "start" not in json.loads((card / "home.json").read_text())   # without a start the shell starts


def test_the_list_in_the_repository_names_examples_for_this_board():
    plan = esp32_sd.load_plan()
    esp32_sd.check_plan(plan)
    profile = esp32_sd.profile_of(plan)
    from copper_and_code_studio.core.boards import compatible
    from copper_and_code_studio.core.model import Project

    examples = [entry["example"] for entry in esp32_sd.entries(plan["menu"]) if "example" in entry]
    assert len(examples) >= 8
    for example in examples:
        project = Project.load(ROOT / "examples" / example / "project.json")
        assert compatible(project, profile), example


def test_a_card_in_the_board_is_brought_up_to_date_through_the_serial_port(tmp_path, boards):
    """On a virtual board, with the real mpremote: the same files as on a card in the computer."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from virtual_board import ROOT as REPOSITORY, VirtualBoard, available

    if not available():
        pytest.skip("needs the Linux runtime: runtime/build.sh")
    from copper_and_code_studio.device.service import DeviceSession

    driver = (REPOSITORY / "runtime/program/display_driver.py").read_text()
    with VirtualBoard(tmp_path / "board", {"/flash/display_driver.py": driver, "/flash/gt911.py": "", "/sd/photos/one.bin": "a photo", "/sd/home.json": "{}"}, size=(480, 480)) as virtual:
        profile = esp32_sd.profile_of(PLAN)
        # mounted: on the virtual board the card is a folder of the same disk, there is nothing to tell them apart
        board = esp32_sd.Board(virtual.port, profile, mounted=True, session=DeviceSession(interrupt=lambda port: None))
        staging = tmp_path / "staging"
        files, folders = esp32_sd.build_card(PLAN, boards, staging, board.bytecode(), lambda line: None)
        said = []
        assert esp32_sd.update_card(files, folders, board, say=said.append) == (len(files), 0, 0)
        for path, source in files.items():
            assert virtual.file("/sd/" + path) == source.read_bytes(), path
        assert virtual.file("/sd/home.json.previous") == b"{}" and virtual.file("/sd/photos/one.bin") == b"a photo"
        assert esp32_sd.update_card(files, folders, board, say=said.append) == (0, 0, len(files))
        (virtual.flash / "sd" / "apps" / "settings" / "lms_image_old.png").write_bytes(b"old")
        (virtual.flash / "sd" / "apps" / "snake.py").write_text("print('changed on the card')\n")
        assert esp32_sd.update_card(files, folders, board, say=said.append) == (1, 1, len(files) - 1)
        assert virtual.file("/sd/apps/snake.py") == b"print('snake')\n" and not virtual.exists("/sd/apps/settings/lms_image_old.png")
        board.session.disconnect()
