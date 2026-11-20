import atexit
import os
import subprocess
from pathlib import Path
import sys


IS_WINDOWS = sys.platform == "win32"
CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def exe_name(name):
    name = str(name)
    return name if not IS_WINDOWS or name.lower().endswith(".exe") else name + ".exe"


# The heap of the unix port is 2 MB by default; boards with a display have far more (28 MB on the
# STM32H7_CORE): a project of 2000 widgets ran out of memory in the simulator, a terminal on the
# display keeps copies of the framebuffer. Projects and programs get the same.
RUNTIME_HEAP = "32M"
# With main.py as a script MicroPython puts the absolute folder in sys.path: on Windows it
# arrives in ANSI, is not valid UTF-8 and imports fail if the path has accented letters.
RUNTIME_ENTRY = ["-X", f"heapsize={RUNTIME_HEAP}", "-c", "import main; main.main()"]


LVSIM_VARIABLES = ("LVSIM_SOCKET", "LVSIM_CONNECT", "LVSIM_TOKEN", "LVSIM_HEADLESS", "LVSIM_DUMP", "LVSIM_FRAMES", "LVSIM_TICK_MS",
                   "LVSIM_WIDTH", "LVSIM_HEIGHT", "LMS_FLASH", "LMS_ENTRY", "LMS_CODE", "LMS_BOARD")


def runtime_environment(**settings):
    """Environment for the simulator runtime: modules from the current folder and only the LVSIM_ settings given.

    A setting inherited from the shell would silently change the backend, for example to headless.
    """
    environment = {name: value for name, value in os.environ.items() if name not in LVSIM_VARIABLES}
    return {**environment, "MICROPYPATH": ".", **settings}


def root_dir():
    return Path(__file__).resolve().parents[1]


def runtime_path(root=None):
    base = Path(root) if root is not None else root_dir()
    output = "out-win64" if IS_WINDOWS else "out"
    return base / "runtime" / output / exe_name("lvsim-runtime")


def mpy_cross_path(root=None):
    base = Path(root) if root is not None else root_dir()
    output = "out-win64" if IS_WINDOWS else "out"
    return base / "runtime" / output / exe_name("mpy-cross")


CONFIG_NAME = "copper-and-code-studio"
# the names up to 0.7 and up to 0.4, newest first: the first one found is copied on first start
OLD_CONFIG_NAMES = ("lvgl-mpy-studio", "lvgl-ide")


def config_dir():
    """Folder of the settings outside QSettings: board profiles, MCP, autostart backups.

    XDG_CONFIG_HOME applies on every system, so whoever set it finds their files; on Windows,
    without that variable, files already written in ~/.config stay valid and new ones go to APPDATA.
    """
    explicit = os.environ.get("XDG_CONFIG_HOME")
    if explicit:
        base = Path(explicit)
    elif IS_WINDOWS and os.environ.get("APPDATA") and not any((Path.home() / ".config" / name).exists() for name in (CONFIG_NAME, *OLD_CONFIG_NAMES)):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path.home() / ".config"
    return adopt_old_config(base)


def adopt_old_config(base):
    """The configuration folder under base; if only one with an old name exists, copy the newest.

    Copy, not move: the autostart backups in there are needed to restore the main.py of the
    boards, and an earlier version of the IDE must still be able to find them.
    """
    import shutil

    current = Path(base) / CONFIG_NAME
    if current.exists():
        return current
    for name in OLD_CONFIG_NAMES:
        old = Path(base) / name
        if old.is_dir():
            try:
                shutil.copytree(old, current)
            except OSError:
                return old  # it cannot be copied: real files under the old name are better than an empty folder
            break
    return current


def micropython_path(*entries):
    return os.pathsep.join(str(entry) for entry in entries)


_background = set()


def run_background(command, timeout, **options):
    """subprocess.run for a process started from a background thread, output captured.

    If the program exits while the process runs, the process is stopped: left alone it would go
    on for seconds and, on Windows, keep its files open so that their folder cannot be removed."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    _background.add(process)
    try:
        output, errors = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    finally:
        _background.discard(process)
    return subprocess.CompletedProcess(command, process.returncode, output, errors)


def stop_background():
    """Stop the processes started by run_background that are still running, and wait for them to end."""
    for process in list(_background):
        try:
            process.kill()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


atexit.register(stop_background)
