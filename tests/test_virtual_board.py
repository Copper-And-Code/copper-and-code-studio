"""The IDE's board code against a virtual board: the real protocol, no hardware. See virtual_board.py."""
import pytest

from lvgl_mpy_studio.core.boards import builtin_profiles
from lvgl_mpy_studio.device.common import DeviceError
from lvgl_mpy_studio.device.service import DeviceSession

from virtual_board import VirtualBoard, available

pytestmark = pytest.mark.skipif(not available(), reason="needs the Linux runtime: runtime/build.sh")


@pytest.fixture
def board(tmp_path):
    with VirtualBoard(tmp_path / "board", {"/flash/main.py": "print('main of the board')\n"}) as board:
        yield board


@pytest.fixture
def session(board):
    session = DeviceSession(interrupt=lambda port: None)
    session.port = board.port
    session.profile = next(profile for profile in builtin_profiles() if profile["id"].startswith("stm32h7_core"))
    yield session
    session.disconnect()


def running_app(session):
    """Something the board is running, as an app started by Upload and Run would be: a reset loses it."""
    # A module in sys.modules stays until the interpreter restarts. (builtins would not do: MicroPython ignores what is set on it.)
    session._exec("import sys\nsys.modules['lms_test_app'] = sys", 10)


def app_alive(session):
    return "LMS_TEST_APP=True" in session._exec("import sys\nprint('LMS_TEST_APP=' + str('lms_test_app' in sys.modules))", 10)


def test_the_board_lists_reads_and_writes_files(session, board, tmp_path):
    assert [entry["name"] for entry in session.list_dir("/flash")] == ["main.py"]
    session.write_file("/flash/notes.txt", b"one\ntwo\n")
    assert board.file("/flash/notes.txt") == b"one\ntwo\n"
    assert not board.exists("/flash/notes.txt.lms-part")
    local = session.read_file("/flash/main.py", tmp_path / "main.py")
    assert local.read_text() == "print('main of the board')\n"


def test_uploading_files_does_not_restart_the_board(session, board, tmp_path):
    """mpremote fs cp without resume soft-reset the board before each file: the running app died."""
    folder = tmp_path / "game"
    folder.mkdir()
    (folder / "game.py").write_text("print('game')\n")
    (folder / "level.bin").write_bytes(bytes(range(256)) * 64)
    running_app(session)
    resets = board.resets
    result = session.upload_files([(folder / "game.py", "game/game.py"), (folder / "level.bin", "game/level.bin")], "/flash")
    assert result["files"] == ["/flash/game/game.py", "/flash/game/level.bin"]
    assert board.file("/flash/game/level.bin") == bytes(range(256)) * 64
    assert board.resets == resets and app_alive(session)


def test_saving_a_file_of_the_board_does_not_restart_it(session, board):
    running_app(session)
    resets = board.resets
    session.write_file("/flash/main.py", b"print('edited')\n")
    assert board.file("/flash/main.py") == b"print('edited')\n"
    assert board.resets == resets and app_alive(session)


def test_paths_outside_the_board_are_refused_before_anything_is_sent(session, board):
    sent = len(board.received)
    for bad in ("relative.py", "/flash/../../etc/passwd"):
        with pytest.raises(DeviceError):
            session.read_file(bad, "unused")
    assert len(board.received) == sent


# ---- A project on the board: what Upload and Run does ----

DRIVER = "runtime/program/display_driver.py"   # the simulator's display driver, as a board has its own


@pytest.fixture
def esp32(tmp_path):
    from virtual_board import ROOT

    files = {"/flash/display_driver.py": (ROOT / DRIVER).read_text(), "/flash/gt911.py": ""}  # gt911: the touch module the profile asks for
    with VirtualBoard(tmp_path / "board", files, size=(480, 480)) as board:
        yield board


def esp32_profile():
    return next(profile for profile in builtin_profiles() if profile["id"].startswith("esp32_4848"))


def test_connect_reads_what_the_board_has(esp32):
    session = DeviceSession(interrupt=lambda port: None)
    info = session.connect(esp32.port, esp32_profile())
    assert info["compatible"] is True
    assert info["modules"]["lvgl"] and info["modules"]["display_driver"]
    assert isinstance(info["mpy"], int) and info["fonts"]
    assert esp32.resets == 0          # reading the board does not restart it
    session.disconnect()


def test_a_board_without_the_touch_module_is_named(tmp_path):
    from virtual_board import ROOT

    with VirtualBoard(tmp_path / "board", {"/flash/display_driver.py": (ROOT / DRIVER).read_text()}, size=(480, 480)) as board:
        session = DeviceSession(interrupt=lambda port: None)
        info = session.connect(board.port, esp32_profile())
        assert info["compatible"] is False and "gt911" in info["errors"]
        with pytest.raises(DeviceError, match="device.prerequisites"):
            session.upload(_weather(), tmp_path / "out")
        session.disconnect()


def _weather():
    from lvgl_mpy_studio.core.model import Project
    from virtual_board import ROOT

    project = Project.load(ROOT / "examples" / "weather" / "project.json")
    project.board = esp32_profile()
    return project


def test_upload_and_run_puts_the_app_on_the_board_and_starts_it(esp32, tmp_path):
    session = DeviceSession(interrupt=lambda port: None)
    session.connect(esp32.port, esp32_profile())
    result = session.upload(_weather(), tmp_path / "out", run=True)
    assert result["active"] is True and result["appPath"].startswith("/lms_apps/")
    app = esp32.flash / result["appPath"].lstrip("/")
    assert (app / "app_main.py").is_file() and (app / "ui.mpy").is_file() and (app / "forecast.mpy").is_file()  # the module of the example too, compiled for the board
    assert not (esp32.flash / (result["appPath"].lstrip("/") + ".uploading")).exists()
    again = session.upload(_weather(), tmp_path / "out", run=True)  # a second upload keeps the first as .previous
    assert again["appPath"] == result["appPath"]
    assert (esp32.flash / (result["appPath"].lstrip("/") + ".previous")).is_dir()
    assert "LVGL_MPY_STUDIO_STOPPED" in session.stop()
    session.disconnect()


# ---- When things go wrong half way ----

def test_cancel_during_a_copy_leaves_the_old_file(session, board, tmp_path):
    import threading

    board_file = b"the old content\n"
    (board.flash / "flash" / "big.bin").write_bytes(board_file)
    big = tmp_path / "big.bin"
    big.write_bytes(bytes(range(256)) * 8000)      # 2 MB: seconds to copy through the terminal
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    with pytest.raises(DeviceError, match="device.cancelled"):
        session.upload_files([(big, "big.bin")], "/flash", cancel=cancel)
    assert board.file("/flash/big.bin") == board_file   # written under another name first: the old file stays


def test_a_board_unplugged_during_a_copy_gives_an_error_not_a_hang(session, board, tmp_path):
    import threading
    import time

    big = tmp_path / "big.bin"
    big.write_bytes(bytes(range(256)) * 8000)
    threading.Timer(0.5, board.unplug).start()
    started = time.monotonic()
    with pytest.raises(DeviceError):
        session.upload_files([(big, "big.bin")], "/flash")
    assert time.monotonic() - started < 20
