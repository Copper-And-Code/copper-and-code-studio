"""The IDE killed while it saves: every file is the old one or the new one, never half of one.

    pytest tests/manual/test_killed_while_saving.py --manual

A second process runs the real window, offscreen, and saves without pause: a large project, a
program open in a tab of the Files panel, and the board profiles. This test kills it with
SIGKILL at a random moment, forty times. After each kill the project must open and validate,
the program must be one of the versions written whole, and the profiles must load. Linux only.
"""
import json
import os
import random
import signal
import subprocess
import sys
import time

import pytest

from copper_and_code_studio.core.boards import ProfileStore
from copper_and_code_studio.core.model import Project
from copper_and_code_studio.core.validation import validate_project
from sweep import ROOT

pytestmark = [pytest.mark.manual, pytest.mark.skipif(sys.platform != "linux", reason="SIGKILL and /proc: Linux")]

KILLS = int(os.environ.get("LMS_KILLS", "40"))
LINES = 20000                                  # long enough for a kill to fall inside the write

CHILD = r'''
import sys, json
sys.path.insert(0, ROOT)
sys.path.insert(0, ROOT + "/tests/manual")
from PySide6.QtWidgets import QApplication
app = QApplication([])
from copper_and_code_studio.ui.main_window import MainWindow
from copper_and_code_studio.core.boards import ProfileStore
from test_big_project import big_project
folder = sys.argv[1]
project = big_project()
project.save(folder + "/project.json")
window = MainWindow()
window.open_project(folder + "/project.json")
window.files_panel.set_folder(folder)
window.open_file(folder + "/program.py")
tab = window.file_tabs[-1]
store = ProfileStore()
print("READY", flush=True)
LINES = int(sys.argv[2])
round = 0
while True:
    round += 1
    def move(project, round=round):
        project.pages[0].widgets[-1].props["x"] = round
    window.document.execute("Move", move)
    window.save_project()
    tab.editor.setPlainText("# version %d\n" % round + "x = %d\n" % round * LINES)
    tab.save()
    profile = store.new_profile()
    profile["name"] = "kill %d" % round
    store.save_profile(profile)
    store.save()
    app.processEvents()
'''


def program_versions(text):
    """A program is whole when it is the first version, or a version with all of its lines."""
    if text == "print('first')\n":
        return True
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# version "):
        return False
    number = lines[0].split()[-1]
    return len(lines) == LINES + 1 and all(line == f"x = {number}" for line in lines[1:])


def test_killed_while_saving_leaves_whole_files(tmp_path):
    folder = tmp_path / "work"
    folder.mkdir()
    (folder / "program.py").write_text("print('first')\n", encoding="utf-8")
    config = tmp_path / "config"
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "XDG_CONFIG_HOME": str(config)}
    chance = random.Random(int(os.environ.get("LMS_KILL_SEED", "3")))
    problems = []
    for kill in range(KILLS):
        child = subprocess.Popen([sys.executable, "-c", CHILD.replace("ROOT", repr(str(ROOT))), str(folder), str(LINES)], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready = child.stdout.readline()
            if "READY" not in ready:
                problems.append(f"kill {kill}: the child did not start: {child.stderr.read()[-500:]}")
                break
            time.sleep(chance.uniform(0.05, 1.5))
        finally:
            child.send_signal(signal.SIGKILL)
            child.wait(10)
        try:
            project = Project.load(folder / "project.json")
            validate_project(project)
        except Exception as error:        # noqa: BLE001 - any failure to open is the finding
            problems.append(f"kill {kill}: the project does not open: {type(error).__name__}: {str(error)[:200]}")
        text = (folder / "program.py").read_text(encoding="utf-8")
        if not program_versions(text):
            problems.append(f"kill {kill}: the program is half written: {len(text)} characters, {text[:40]!r}")
        try:
            os.environ["XDG_CONFIG_HOME"], previous = str(config), os.environ.get("XDG_CONFIG_HOME")
            try:
                ProfileStore()
            finally:
                if previous is not None:
                    os.environ["XDG_CONFIG_HOME"] = previous
        except Exception as error:        # noqa: BLE001
            problems.append(f"kill {kill}: the board profiles do not load: {error}")
        leftovers = sorted(path.name for path in folder.iterdir() if path.name.endswith(".tmp"))
        if leftovers:
            json.dumps(leftovers)           # left by a kill in the middle: noted, not a loss
    assert not problems, "\n".join(problems[:15])
