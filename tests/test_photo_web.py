"""The web server of examples/photo-frame (photo_web), run in CPython on localhost."""
import json
import struct
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from test_ftp_server_example import micropython_os, micropython_time

PROJECT = Path(__file__).parents[1] / "examples" / "photo-frame" / "project.json"


def load_module():
    import types

    modules = {m["name"]: m["source"] for m in json.loads(PROJECT.read_text(encoding="utf-8"))["modules"]}
    module = types.ModuleType("photo_web_under_test")
    exec(compile(modules["photo_web"], "photo_web.py", "exec"), module.__dict__)
    module.time = micropython_time()
    module.os = micropython_os()
    return module


@pytest.fixture
def server(tmp_path):
    module = load_module()
    notes = []
    server = module.Server(folder=str(tmp_path / "photos"), pin="4821", port=0, language="it", note=notes.append)
    server.port = 0
    server.start()
    port = server._listener.getsockname()[1]
    running = True

    def serve():
        while running:
            server.poll(15)
            time.sleep(0.002)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield module, server, port, notes, tmp_path / "photos"
    running = False
    thread.join(2)
    server.stop()


def request(port, method, path, data=None, pin="4821"):
    headers = {"X-Pin": pin} if pin is not None else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=headers), timeout=10) as reply:
            return reply.status, reply.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def photo(module, value=0):
    return struct.pack("<BBHHHHH", 0x19, 0x12, 0, module.WIDTH, module.HEIGHT, module.WIDTH * 2, 0) + bytes([value]) * (module.WIDTH * module.HEIGHT * 2)


def test_the_page_is_open_and_the_rest_asks_the_pin(server):
    _module, _server, port, _notes, _folder = server
    status, page = request(port, "GET", "/", pin=None)
    assert status == 200 and b"<title>Photo Frame</title>" in page and b'LANG = "it"' in page and b"W = 480" in page
    assert request(port, "GET", "/list", pin=None)[0] == 403 and request(port, "GET", "/list", pin="0000")[0] == 403
    assert request(port, "GET", "/list?pin=4821", pin=None)[0] == 200   # the PIN of the QR code, in the address


def test_a_photo_is_written_whole_listed_and_deleted(server):
    module, served, port, notes, folder = server
    data = photo(module, 7)
    assert request(port, "PUT", "/photo/beach.bin", data) == (201, b'{"name": "beach.bin"}')
    assert (folder / "beach.bin").read_bytes() == data and not list(folder.glob("*.part"))
    assert served.count == 1 and notes == ["received beach.bin"]
    listed = json.loads(request(port, "GET", "/list")[1])
    assert listed["photos"] == [{"name": "beach.bin", "size": module.PHOTO_BYTES}] and listed["free"] > 0
    assert request(port, "PUT", "/photo/beach.bin", photo(module, 9))[0] == 201   # the same name replaces it
    assert (folder / "beach.bin").read_bytes() == photo(module, 9)
    assert request(port, "DELETE", "/photo/beach.bin")[0] == 200 and not (folder / "beach.bin").exists()
    assert request(port, "DELETE", "/photo/beach.bin")[0] == 404


def test_what_is_not_a_photo_of_the_display_is_refused(server):
    module, _served, port, _notes, folder = server
    assert request(port, "PUT", "/photo/small.bin", b"12345")[0] == 413
    wrong = bytearray(photo(module))
    wrong[4] = 0x40                                         # 320 wide
    assert request(port, "PUT", "/photo/wrong.bin", bytes(wrong))[0] == 400
    assert request(port, "PUT", "/photo/..%2F..%2Fboot.bin", photo(module))[0] == 201   # the name keeps letters and digits only
    assert sorted(p.name for p in folder.iterdir()) == ["2f2fboot.bin"]   # inside the folder, whatever the name
    assert request(port, "GET", "/nowhere")[0] == 404 and request(port, "POST", "/photo/x.bin")[0] == 405


def test_a_photo_cut_half_way_is_not_kept(server):
    import socket

    module, _served, port, _notes, folder = server
    with socket.create_connection(("127.0.0.1", port)) as link:
        link.sendall(b"PUT /photo/half.bin HTTP/1.0\r\nX-Pin: 4821\r\nContent-Length: %d\r\n\r\n" % module.PHOTO_BYTES + photo(module)[:100000])
        time.sleep(0.3)
    deadline = time.time() + 3
    while list(folder.glob("half*")) and time.time() < deadline:
        time.sleep(0.05)
    assert not list(folder.glob("half*"))


def test_safe_names():
    module = load_module()
    assert module.safe_name("Beach Day.bin") == "beachday.bin" and module.safe_name("IMG_2024-01.BIN") == "img_2024-01.bin"
    assert module.safe_name("../..") is None and module.safe_name("x" * 60 + ".bin") == "x" * 40 + ".bin"
