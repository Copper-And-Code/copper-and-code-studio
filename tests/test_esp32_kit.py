"""tools/esp32_kit.py: firmware, flash and SD card of the ESP32-4848S040 in one zip."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from tools import esp32_kit, esp32_sd

ROOT = Path(__file__).parents[1]
FIRMWARE = b"\xe9 not really a firmware"
PLAN = {
    "board": "esp32_4848s040_480",
    "start": "Settings",
    "boardFiles": {"lib/home.py": "examples/home/home.py"},
    "kit": {
        "firmware": {"release": "v9.9.9", "file": "ESP32_4848S040-v9.9.9.bin"},
        "flashBoardFiles": {"main.py": "examples/home/main.py"},
        "flashStudioFiles": {"boot.py": "examples/settings/boot.py", "cac_settings.py": "examples/settings/cac_settings.py"},
        "cardFolders": ["photos"],
    },
    "menu": [{"name": "Settings", "example": "settings"}, {"name": "Snake", "program": "examples/snake.py"}],
}


@pytest.fixture
def boards(tmp_path):
    folder = tmp_path / "boards"
    (folder / "examples" / "home").mkdir(parents=True)
    (folder / "examples" / "home" / "home.py").write_text("# the home\n")
    (folder / "examples" / "home" / "main.py").write_text("# main.py of the flash\n")
    (folder / "examples" / "snake.py").write_text("print('snake')\n")
    return folder


def release(asked, sums=None):
    """A stand-in for the release of the board repository, which notes the addresses asked for."""
    def download(url):
        asked.append(url)
        if url.endswith("/SHA256SUMS"):
            return (sums or f"{hashlib.sha256(FIRMWARE).hexdigest()}  ESP32_4848S040-v9.9.9.bin\n0000  OTHER.bin\n").encode()
        return FIRMWARE
    return download


def make(tmp_path, boards, download, plan=PLAN):
    tmp_path.mkdir(parents=True, exist_ok=True)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan))
    said = []
    code = esp32_kit.main([str(tmp_path / "out" / "kit-test.zip"), "--boards", str(boards), "--plan", str(plan_file)], said.append, download)
    return code, said, tmp_path / "out" / "kit-test.zip"


def test_the_kit_has_firmware_flash_card_and_texts_under_one_folder(tmp_path, boards):
    asked = []
    code, said, kit = make(tmp_path, boards, release(asked))
    assert code == 0, said
    assert asked == [f"{esp32_sd.BOARDS_REPOSITORY}/releases/download/v9.9.9/SHA256SUMS",
                     f"{esp32_sd.BOARDS_REPOSITORY}/releases/download/v9.9.9/ESP32_4848S040-v9.9.9.bin"]
    with zipfile.ZipFile(kit) as archive:
        names = archive.namelist()
        assert all(name.startswith("kit-test/") for name in names)   # one folder when extracted
        inside = {name[len("kit-test/"):]: name for name in names}
        assert archive.read(inside["firmware/ESP32_4848S040-v9.9.9.bin"]) == FIRMWARE
        assert archive.read(inside["flash/main.py"]) == b"# main.py of the flash\n"
        assert archive.read(inside["flash/cac_settings.py"]) == (ROOT / "examples/settings/cac_settings.py").read_bytes()
        assert archive.read(inside["flash/boot.py"]) == (ROOT / "examples/settings/boot.py").read_bytes()
        assert {"sd/home.json", "sd/lib/home.py", "sd/apps/snake.py", "sd/apps/settings/app_main.py", "sd/photos/"} <= set(inside)
        assert json.loads(archive.read(inside["sd/home.json"]))["start"] == "/sd/apps/settings/app_main.py"
        for text in ("README.md", "LEGGIMI.md", "GUIDE.md", "GUIDA.md"):
            assert archive.read(inside[text]) == (ROOT / "tools/esp32_kit" / text).read_bytes()


def test_the_same_kit_twice_is_the_same_zip(tmp_path, boards):
    first = make(tmp_path / "a", boards, release([]))[2].read_bytes()
    second = make(tmp_path / "b", boards, release([]))[2].read_bytes()
    assert first == second


def test_a_firmware_that_is_not_the_one_of_the_release_stops_the_kit(tmp_path, boards):
    code, said, kit = make(tmp_path, boards, release([], sums="0123  ESP32_4848S040-v9.9.9.bin\n"))
    assert code == 1 and not kit.exists()
    assert "is not the one of the release v9.9.9" in said[-1]
    code, said, _kit = make(tmp_path, boards, release([], sums="0123  ANOTHER.bin\n"))
    assert code == 1 and "not in the SHA256SUMS" in said[-1]


def test_the_kit_of_the_repository_names_files_that_exist():
    plan = esp32_sd.load_plan()
    kit = plan["kit"]
    assert kit["firmware"]["file"].startswith("ESP32_4848S040-") and kit["firmware"]["release"] in kit["firmware"]["file"]
    assert {"main.py", "shell.py"} <= set(kit["flashBoardFiles"]) and {"boot.py", "cac_settings.py"} <= set(kit["flashStudioFiles"])
    for relative in kit["flashStudioFiles"].values():
        assert (ROOT / relative).is_file()
    # the texts name the firmware of the list, and the guides the names of the menu
    for text in ("README.md", "LEGGIMI.md"):
        assert kit["firmware"]["file"] in (ROOT / "tools/esp32_kit" / text).read_text()
    english, italian = (" ".join((ROOT / "tools/esp32_kit" / name).read_text().split()) for name in ("GUIDE.md", "GUIDA.md"))
    for entry in esp32_sd.entries(plan["menu"]):
        assert entry["name"] in english, entry["name"]
        assert entry.get("name_it", entry["name"]) in italian, entry["name"]
