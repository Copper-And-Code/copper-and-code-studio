"""The FTP server of examples/ftp-server, run in CPython on localhost against Python's ftplib."""
import ftplib
import io
import json
import os
import socket
import threading
import time
import types
from pathlib import Path

import pytest

PROJECT = Path(__file__).parents[1] / "examples" / "ftp-server" / "project.json"


def micropython_time():
    """The ticks of MicroPython's time module, over CPython's clock."""
    shim = types.SimpleNamespace(**{name: getattr(time, name) for name in ("time", "localtime", "gmtime", "sleep")})
    shim.ticks_ms = lambda: int(time.monotonic() * 1000)
    shim.ticks_add = lambda a, b: a + b
    shim.ticks_diff = lambda a, b: a - b
    return shim


def micropython_os():
    shim = types.SimpleNamespace(**{name: getattr(os, name) for name in ("stat", "mkdir", "rmdir", "remove", "rename", "statvfs", "listdir")})
    shim.ilistdir = lambda path: ((name, 0, 0) for name in os.listdir(path))
    return shim


def load_server():
    modules = {m["name"]: m["source"] for m in json.loads(PROJECT.read_text(encoding="utf-8"))["modules"]}
    module = types.ModuleType("ftp_server_under_test")
    exec(compile(modules["ftp_server"], "ftp_server.py", "exec"), module.__dict__)
    module.time = micropython_time()
    module.os = micropython_os()
    return module


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    module = load_server()
    notes = []
    port = free_port()
    instance = module.Server(root=str(tmp_path), user="mpy", password="123456", port=port, note=lambda who, what: notes.append(what))
    instance.start()
    stop = threading.Event()

    def run():
        while not stop.is_set():
            instance.poll(10)
            time.sleep(0.005)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    yield instance, port, notes, tmp_path
    stop.set()
    thread.join(2)
    instance.stop()


def client(port):
    ftp = ftplib.FTP()
    ftp.connect("127.0.0.1", port, timeout=10)
    return ftp


def test_a_client_uploads_lists_downloads_renames_and_deletes(server):
    instance, port, notes, root = server
    ftp = client(port)
    ftp.login("mpy", "123456")
    ftp.mkd("photos")
    ftp.cwd("photos")
    data = os.urandom(200_000)
    ftp.storbinary("STOR beach.bin", io.BytesIO(data))
    assert (root / "photos" / "beach.bin").read_bytes() == data
    assert ftp.size("beach.bin") == len(data)
    assert ftp.nlst() == ["beach.bin"]
    assert any("beach.bin" in line for line in _lines(ftp, "LIST"))
    assert [name for name, facts in ftp.mlsd()] == ["beach.bin"]
    back = io.BytesIO()
    ftp.retrbinary("RETR beach.bin", back.write)
    assert back.getvalue() == data
    resumed = io.BytesIO()
    ftp.retrbinary("RETR beach.bin", resumed.write, rest=150_000)
    assert resumed.getvalue() == data[150_000:]
    ftp.rename("beach.bin", "sea.bin")
    ftp.delete("sea.bin")
    ftp.cwd("/")
    ftp.rmd("photos")
    assert list(root.iterdir()) == []
    ftp.quit()
    assert instance.received == len(data) and instance.sent >= len(data)
    assert "logged in" in notes


def test_the_client_cannot_leave_the_root(server):
    _instance, port, _notes, root = server
    (root / "inside.txt").write_text("x")
    ftp = client(port)
    ftp.login("mpy", "123456")
    ftp.cwd("../../..")
    assert ftp.pwd() == "/"
    assert ftp.nlst() == ["inside.txt"]
    ftp.quit()


def test_three_wrong_passwords_close_the_connection(server):
    _instance, port, notes, _root = server
    ftp = client(port)
    for _ in range(3):
        with pytest.raises(ftplib.error_perm):
            ftp.login("mpy", "wrong")
    with pytest.raises((EOFError, OSError, ftplib.Error)):
        ftp.login("mpy", "123456")
    assert notes.count("wrong password") == 3


def test_nothing_before_login(server):
    _instance, port, _notes, _root = server
    ftp = client(port)
    with pytest.raises(ftplib.error_perm, match="530"):
        ftp.nlst()
    ftp.close()


def _lines(ftp, command):
    lines = []
    ftp.retrlines(command, lines.append)
    return lines
