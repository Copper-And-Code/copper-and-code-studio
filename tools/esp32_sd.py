#!/usr/bin/env python3
"""Fill a new SD card of the ESP32-4848S040, or bring one up to date.

The card holds the home of the board (the shell and the touch menu of apps, from the repository
copper-and-code-mcu-boards), the programs of its menu and the apps made with Copper and Code
Studio: the examples of this repository, generated for the board as an upload does, each in a
folder of its own in /sd/apps. What goes on the card, and the menu, are in esp32_sd.json next
to this file: add an entry there and run the script again.

    tools/esp32_sd.py --boards ~/copper-and-code-mcu-boards /media/you/CARD     # the card in this computer
    tools/esp32_sd.py --boards ~/copper-and-code-mcu-boards --port /dev/ttyUSB0 # the card in the board

Only the files that are missing or different are written. In the folder of a Studio app the files
it no longer has are removed; nothing else on the card is removed or touched: photos, settings,
programs and apps that are not in the list stay. The menu, /sd/home.json, is written from the
list, and the one it replaces is kept as home.json.previous.

On the board, in the flash, the home needs its main.py (examples/home of the board repository)
and, for the Wi-Fi and the brightness, the boot.py and cac_settings.py of examples/settings.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from copper_and_code_studio.core.boards import builtin_profiles, compatible, portable_profile  # noqa: E402
from copper_and_code_studio.core.model import Project  # noqa: E402
from copper_and_code_studio.gen.board_gen import _bytecode_file, generate_board, precompile_board  # noqa: E402

PLAN = Path(__file__).with_name("esp32_sd.json")
BOARDS_REPOSITORY = "https://github.com/Copper-And-Code/copper-and-code-mcu-boards"
CARD = "/sd"            # where the board mounts the card
APPS = "apps"           # programs and app folders, on the card
MENU = "home.json"
HASH_BATCH = 40         # files the board is asked about in one command


class Problem(Exception):
    """Something the person who runs the script has to put right: said in one line, without a traceback."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_plan(path=PLAN):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(plan.get("menu"), list) or not plan["menu"]:
        raise Problem(f"{path}: the menu is missing")
    return plan


def profile_of(plan):
    wanted = plan.get("board", "esp32_4848s040_480")
    profile = next((item for item in builtin_profiles() if item["id"] == wanted), None)
    if profile is None:
        raise Problem(f"unknown board {wanted!r} in the plan")
    return portable_profile(profile)


def local_bytecode_version(folder):
    """The bytecode version of this IDE's compiler, as sys.implementation._mpy has it in its low byte."""
    source = Path(folder) / "probe.py"
    source.write_text("x = 1\n", encoding="utf-8")
    data = _bytecode_file(source, Path(folder) / "probe.mpy")
    return data[1] if data and data[:1] == b"M" else None


def entries(menu):
    """Every app and program of the menu, folders opened."""
    for entry in menu:
        if "apps" in entry:
            yield from entries(entry["apps"])
        else:
            yield entry


def card_path(entry):
    """Where the menu finds an entry, on the board."""
    if "example" in entry:
        return f"{CARD}/{APPS}/{entry['example']}/app_main.py"
    if "program" in entry:
        return f"{CARD}/{APPS}/{Path(entry['program']).name}"
    return entry["path"]  # something already on the board: only listed


def menu_text(menu):
    """home.json as the home reads it, one entry on each line so that it is easy to read and to compare."""
    def line(entry, indent):
        if "apps" in entry:
            inner = ",\n".join(line(item, indent + "  ") for item in entry["apps"])
            return f'{indent}{{"name": {json.dumps(entry["name"])}, "apps": [\n{inner}\n{indent}]}}'
        return indent + json.dumps({"name": entry["name"], "path": card_path(entry)})

    return '{"apps": [\n' + ",\n".join(line(entry, "  ") for entry in menu) + "\n]}\n"


def check_plan(plan):
    names = {}
    for entry in entries(plan["menu"]):
        if not entry.get("name") or sum(key in entry for key in ("example", "program", "path")) != 1:
            raise Problem(f"menu entry {entry!r}: a name and one of example, program or path are needed")
        if "path" in entry:
            continue
        stem = entry["example"] if "example" in entry else Path(entry["program"]).stem
        if stem in names and names[stem] != entry:
            # import finds a folder before a module of the same name, and a program is run by its file
            raise Problem(f"{stem}: two entries of the menu would have the same name in /sd/{APPS}")
        names[stem] = entry


def build_app(example, profile, folder, bytecode):
    """A Studio example as an upload puts it on the board, in folder. Returns its file names and warnings."""
    source = ROOT / "examples" / example / "project.json"
    if not source.is_file():
        raise Problem(f"examples/{example}: there is no such example in this repository")
    project = Project.load(source)
    project.board = profile
    if not compatible(project, profile):
        raise Problem(f"examples/{example}: made for another screen size, not {profile['logicalWidth']}x{profile['logicalHeight']}")
    generated = generate_board(project, profile, folder, asset_files=True)
    if bytecode is not None:
        generated = precompile_board(generated, folder, bytecode)
    return generated["files"], generated["warnings"]


def build_card(plan, boards, staging, bytecode=None, say=print):
    """The files of the card in staging. Returns ({path on the card: local file}, [app folders on the card])."""
    check_plan(plan)
    boards, staging, profile = Path(boards), Path(staging), profile_of(plan)
    files, folders = {}, []

    def from_boards(relative, target):
        source = boards / relative
        if not source.is_file():
            raise Problem(f"{source}: not found. --boards must be a copy of {BOARDS_REPOSITORY}")
        (staging / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, staging / target)
        files[target] = staging / target

    for target, relative in plan.get("boardFiles", {}).items():
        from_boards(relative, target)
    for entry in entries(plan["menu"]):
        if "program" in entry:
            from_boards(entry["program"], f"{APPS}/{Path(entry['program']).name}")
        elif "example" in entry:
            folder = f"{APPS}/{entry['example']}"
            if folder in folders:
                continue
            names, warnings = build_app(entry["example"], profile, staging / folder, bytecode)
            for warning in warnings:
                say(f"  {entry['example']}: {warning}")
            files.update({f"{folder}/{name}": staging / folder / name for name in names})
            folders.append(folder)
    (staging / MENU).write_text(menu_text(plan["menu"]), encoding="utf-8", newline="\n")
    files[MENU] = staging / MENU
    return files, folders


# ---- where the card is ----

class Folder:
    """The card in this computer: a folder."""

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise Problem(f"{self.root}: not a folder. Give the folder where the card is mounted, or --port for a card in the board")

    def describe(self):
        return str(self.root)

    def digests(self, sizes):
        """The SHA-256 of each file of sizes that the card has with that size; the others are missing or different."""
        found = {}
        for path, size in sizes.items():
            target = self.root / path
            if target.is_file() and target.stat().st_size == size:
                found[path] = digest(target.read_bytes())
        return found

    def read(self, path):
        target = self.root / path
        return target.read_bytes() if target.is_file() else None

    def names(self, folder):
        target = self.root / folder
        return sorted(item.name for item in target.iterdir() if item.is_file()) if target.is_dir() else []

    def write(self, items, say):
        for path, source in items:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_name(target.name + ".part")  # a card pulled half way keeps the old file, not half a new one
            shutil.copyfile(source, part)
            os.replace(part, target)

    def write_bytes(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def remove(self, path):
        (self.root / path).unlink(missing_ok=True)

    def close(self, changed):
        if changed and hasattr(os, "sync"):
            os.sync()  # the card can be taken out when the script has ended


class Board:
    """The card in the board, through the serial port and the IDE's own device code."""

    def __init__(self, port, profile, mounted=None, wait=8, session=None):
        from copper_and_code_studio.device.common import DeviceError
        from copper_and_code_studio.device.service import DeviceSession, mpremote_command

        self.port, self.profile, self.wait = port, profile, wait
        self.error, self.command = DeviceError, mpremote_command
        self.session = session or DeviceSession()
        self._connect()
        if mounted is None:
            mounted = self._mounted()
            if not mounted:  # after a soft reset main.py has not run, and it is main.py that mounts the card
                self._restart()
                self._connect()
                mounted = self._mounted()
        if not mounted:
            raise Problem(f"the board does not have its card at {CARD}: is it in, and is the home's main.py in the flash?")

    def _connect(self):
        try:
            self.info = self.session.connect(self.port, self.profile)
        except self.error as error:
            raise Problem(f"{self.port}: {error}") from error

    def _mounted(self):
        script = f"import os\na=os.statvfs('/')\ntry:\n b=os.statvfs({CARD!r})\n print('LMS_CARD=%d' % (a[2]!=b[2] or a[0]!=b[0]))\nexcept OSError:\n print('LMS_CARD=0')"
        return "LMS_CARD=1" in self.session.evaluate(script)

    def _restart(self):
        """A reset as at power-on: main.py runs and mounts the card. Then the board needs a moment."""
        self.session.disconnect()
        subprocess.run(self.command() + ["connect", self.port, "reset"], capture_output=True, timeout=30)
        time.sleep(self.wait)

    def describe(self):
        return f"{CARD} of the board on {self.port}"

    def bytecode(self):
        return self.info.get("mpy") if isinstance(self.info.get("mpy"), int) else None

    def digests(self, sizes):
        found, paths = {}, list(sizes)
        for start in range(0, len(paths), HASH_BATCH):
            batch = {path: sizes[path] for path in paths[start:start + HASH_BATCH]}
            script = f"""import os,json,hashlib,binascii
_r={{}}
_b=bytearray(4096)
_m=memoryview(_b)
for _p,_z in json.loads({json.dumps(batch)!r}).items():
 try:
  if os.stat({CARD + '/'!r}+_p)[6]!=_z:continue
  _d=hashlib.sha256()
  with open({CARD + '/'!r}+_p,'rb') as _f:
   while True:
    _k=_f.readinto(_b)
    if not _k:break
    _d.update(_m[:_k])
  _r[_p]=binascii.hexlify(_d.digest()).decode()
 except OSError:
  pass
print('LMS_CARD_FILES='+json.dumps(_r))"""
            output = self.session.evaluate(script)
            line = next((item for item in output.splitlines() if item.startswith("LMS_CARD_FILES=")), None)
            if line is None:
                raise Problem(f"the board did not answer about its files: {output.strip()[-200:]}")
            found.update(json.loads(line.split("=", 1)[1]))
        return found

    def read(self, path):
        with tempfile.TemporaryDirectory(prefix="copper-and-code-studio-card-") as temporary:
            try:
                return self.session.read_file(f"{CARD}/{path}", Path(temporary) / "file").read_bytes()
            except self.error:
                return None

    def names(self, folder):
        try:
            return sorted(entry["name"] for entry in self.session.list_dir(f"{CARD}/{folder}") if not entry["dir"])
        except self.error:
            return []

    def write(self, items, say):
        total = sum(source.stat().st_size for _path, source in items)
        seen = []

        def progress(sent, _total, name, _size):
            if name and name not in seen:
                seen.append(name)
                say(f"  {name}  ({sent * 100 // max(total, 1)}%)" if len(items) > 1 else f"  {name}")

        try:
            self.session.upload_files([(source, path) for path, source in items], CARD, progress=progress)
        except self.error as error:
            raise Problem(f"copy to the board stopped: {error}") from error

    def write_bytes(self, path, data):
        self.session.write_file(f"{CARD}/{path}", data)

    def remove(self, path):
        self.session.remove_path(f"{CARD}/{path}")

    def close(self, changed):
        try:
            self.session.evaluate(f"import os\nos.umount({CARD!r})")  # what was written is on the card before the reset
        except self.error:
            pass
        self._restart()  # the shell and the menu again, with the new list


def update_card(files, folders, target, dry_run=False, say=print):
    """Write on the card the files that are missing or different. Returns (written, removed, kept)."""
    sizes = {path: source.stat().st_size for path, source in files.items()}
    there = target.digests(sizes)
    changed = [(path, source) for path, source in sorted(files.items()) if there.get(path) != digest(source.read_bytes())]
    stale = [f"{folder}/{name}" for folder in folders for name in target.names(folder) if f"{folder}/{name}" not in files]
    kept = len(files) - len(changed)
    for path, _source in changed:
        say(f"  write   {path}")
    for path in stale:
        say(f"  remove  {path}")
    if dry_run or not (changed or stale):
        return len(changed), len(stale), kept
    if any(path == MENU for path, _source in changed):
        previous = target.read(MENU)
        if previous is not None:
            target.write_bytes(MENU + ".previous", previous)
    target.write([(path, source) for path, source in changed if path != MENU], say)
    target.write([(path, source) for path, source in changed if path == MENU], say)  # last: it names what is there by now
    for path in stale:
        target.remove(path)
    return len(changed), len(stale), kept


def main(arguments=None, say=print):
    parser = argparse.ArgumentParser(description="Fill a new SD card of the ESP32-4848S040, or bring one up to date.", epilog=f"The list of what goes on the card is {PLAN.name}, next to this script.")
    parser.add_argument("card", nargs="?", help="the folder where the card is mounted on this computer")
    parser.add_argument("--port", help="the serial port of the board, with the card in it, instead of a folder")
    parser.add_argument("--boards", default=os.environ.get("CAC_MCU_BOARDS"), help=f"a copy of {BOARDS_REPOSITORY} (or the variable CAC_MCU_BOARDS)")
    parser.add_argument("--plan", default=str(PLAN), help="another list of what goes on the card")
    parser.add_argument("--source", action="store_true", help="Python sources instead of bytecode: slower to start, for a firmware of another MicroPython version")
    parser.add_argument("--dry-run", action="store_true", help="say what would be written and removed, and do nothing")
    options = parser.parse_args(arguments)
    try:
        if bool(options.card) == bool(options.port):
            raise Problem("give the folder of the card, or --port for a card in the board: one of the two")
        if not options.boards:
            raise Problem(f"--boards is needed: a copy of {BOARDS_REPOSITORY}")
        plan = load_plan(options.plan)
        target = Board(options.port, profile_of(plan)) if options.port else Folder(options.card)
        written = removed = kept = 0
        try:
            with tempfile.TemporaryDirectory(prefix="copper-and-code-studio-card-") as staging:
                bytecode = None
                if not options.source:
                    bytecode = target.bytecode() if options.port else local_bytecode_version(staging)
                    if bytecode is None:
                        say("No bytecode for this firmware: the apps go as sources.")
                say(f"Building the card for {plan.get('board', 'esp32_4848s040_480')}...")
                files, folders = build_card(plan, options.boards, Path(staging) / "card", bytecode, say)
                say(f"{len(files)} files, {sum(source.stat().st_size for source in files.values()) // 1024} kB, to {target.describe()}:")
                written, removed, kept = update_card(files, folders, target, options.dry_run, say)
        finally:
            target.close(bool(written or removed) and not options.dry_run)  # a board is started again whatever happened
        verb = "to write" if options.dry_run else "written"
        say(f"{written} {verb}, {removed} {'to remove' if options.dry_run else 'removed'}, {kept} already there.")
        return 0
    except Problem as problem:
        say(f"esp32_sd: {problem}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
