#!/usr/bin/env python3
"""The kit of the ESP32-4848S040: everything a board needs, in one zip, for a person without the repositories.

    tools/esp32_kit.py --boards ~/copper-and-code-mcu-boards dist/esp32-4848s040-kit.zip

The zip holds:

    firmware/   MicroPython with LVGL for the board, from a release of copper-and-code-mcu-boards
    flash/      the files of the flash: main.py, which starts the home of the card, boot.py and
                cac_settings.py for the WiFi and the settings, and the shell for a board with no card
    sd/         the content of the SD card, as tools/esp32_sd.py writes it: the home, its
                programs and the apps, the menu, an empty photos folder
    README.md, LEGGIMI.md   how to put it on a board, in English and in Italian
    GUIDE.md, GUIDA.md      how to use the board, for the person who receives it

What goes in it is the list of tools/esp32_sd.json, with its "kit" section. The firmware is
downloaded from the release the list names and checked against that release's SHA256SUMS;
--firmware gives a file already downloaded instead.
"""

import argparse
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import esp32_sd  # noqa: E402
from esp32_sd import BOARDS_REPOSITORY, PLAN, Problem, ROOT  # noqa: E402

TEXTS = Path(__file__).with_name("esp32_kit")   # README.md, LEGGIMI.md, GUIDE.md, GUIDA.md
DATE = (2026, 1, 1, 0, 0, 0)                     # every file of the zip: the same kit gives the same bytes


def _download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "copper-and-code-studio-kit"})
    with urllib.request.urlopen(request, timeout=60) as answer:
        return answer.read()


def fetch_firmware(firmware, folder, download=_download, say=print):
    """The firmware of the kit in folder, checked against the SHA256SUMS of its release. Returns its path."""
    release, name = firmware["release"], firmware["file"]
    base = f"{BOARDS_REPOSITORY}/releases/download/{release}"
    say(f"Downloading {name} from the release {release} of {BOARDS_REPOSITORY}...")
    sums = download(f"{base}/SHA256SUMS").decode("utf-8")
    wanted = next((line.split()[0] for line in sums.splitlines() if line.split()[-1:] == [name]), None)
    if wanted is None:
        raise Problem(f"{name}: not in the SHA256SUMS of the release {release}")
    data = download(f"{base}/{name}")
    if hashlib.sha256(data).hexdigest() != wanted:
        raise Problem(f"{name}: the file downloaded is not the one of the release {release}")
    path = Path(folder) / name
    path.write_bytes(data)
    return path


def kit_files(plan, boards, staging, firmware, bytecode, say=print):
    """{path in the zip: local file} and the empty folders of the card."""
    kit = plan.get("kit") or {}
    staging, boards = Path(staging), Path(boards)
    files = {}
    card, _folders = esp32_sd.build_card(plan, boards, staging / "card", bytecode, say)
    files.update({f"sd/{path}": source for path, source in card.items()})
    for target, relative in kit.get("flashBoardFiles", {}).items():
        source = boards / relative
        if not source.is_file():
            raise Problem(f"{source}: not found. --boards must be a copy of {BOARDS_REPOSITORY}")
        files[f"flash/{target}"] = source
    for target, relative in kit.get("flashStudioFiles", {}).items():
        files[f"flash/{target}"] = ROOT / relative
    files[f"firmware/{Path(firmware).name}"] = Path(firmware)
    for name in ("README.md", "LEGGIMI.md", "GUIDE.md", "GUIDA.md"):
        files[name] = TEXTS / name
    for source in files.values():
        if not Path(source).is_file():
            raise Problem(f"{source}: not found")
    return files, [f"sd/{folder}/" for folder in kit.get("cardFolders", [])]


def write_zip(path, files, folders, top):
    """The kit, every file under top/, in a fixed order and with a fixed date."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in sorted(folders):
            archive.writestr(zipfile.ZipInfo(f"{top}/{folder}", DATE), b"")
        for name in sorted(files):
            info = zipfile.ZipInfo(f"{top}/{name}", DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, Path(files[name]).read_bytes())


def main(arguments=None, say=print, download=_download):
    parser = argparse.ArgumentParser(description="Make the kit of the ESP32-4848S040: firmware, flash and SD card in one zip.")
    parser.add_argument("zip", help="the zip to write, such as dist/esp32-4848s040-kit.zip")
    parser.add_argument("--boards", default=os.environ.get("CAC_MCU_BOARDS"), help=f"a copy of {BOARDS_REPOSITORY} (or the variable CAC_MCU_BOARDS)")
    parser.add_argument("--plan", default=str(PLAN), help="another list of what goes in the kit")
    parser.add_argument("--firmware", help="the firmware file, already downloaded, instead of the one of the release the list names")
    parser.add_argument("--source", action="store_true", help="Python sources on the card instead of bytecode")
    options = parser.parse_args(arguments)
    try:
        if not options.boards:
            raise Problem(f"--boards is needed: a copy of {BOARDS_REPOSITORY}")
        plan = esp32_sd.load_plan(options.plan)
        if "firmware" not in (plan.get("kit") or {}) and not options.firmware:
            raise Problem("the list has no kit.firmware: give --firmware")
        with tempfile.TemporaryDirectory(prefix="copper-and-code-studio-kit-") as staging:
            bytecode = None if options.source else esp32_sd.local_bytecode_version(staging)
            if bytecode is None and not options.source:
                say("No compiler for bytecode: the apps go as sources.")
            firmware = options.firmware or fetch_firmware(plan["kit"]["firmware"], staging, download, say)
            say("Building the card...")
            files, folders = kit_files(plan, options.boards, staging, firmware, bytecode, say)
            top = Path(options.zip).stem
            write_zip(options.zip, files, folders, top)
        size = Path(options.zip).stat().st_size
        say(f"{options.zip}: {len(files)} files, {size // 1024} kB.")
        return 0
    except Problem as problem:
        say(f"esp32_kit: {problem}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
