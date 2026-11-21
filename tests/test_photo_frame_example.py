"""The Photo Frame example: Italian time from UTC, and the photos converted by convert_photos.py."""
import calendar
import json
import re
import struct
import sys
import time
import types
from pathlib import Path

import pytest

FOLDER = Path(__file__).parents[1] / "examples" / "photo-frame"
sys.path.insert(0, str(FOLDER))
import convert_photos  # noqa: E402


def italy_offset():
    """italy_offset() of the project's code, with MicroPython's mktime and gmtime (both UTC)."""
    code = json.loads((FOLDER / "project.json").read_text(encoding="utf-8"))["code"]["module"]
    functions = re.search(r"def _last_sunday.*?(?=\n\n\ndef local_time)", code, re.S).group(0)
    shim = types.SimpleNamespace(mktime=lambda t: calendar.timegm(t[:6] + (0, 0, 0)), gmtime=time.gmtime)
    namespace = {"time": shim}
    exec(functions, namespace)
    return namespace["italy_offset"]


def utc(*fields):
    return calendar.timegm(fields + (0,) * (6 - len(fields)))


@pytest.mark.parametrize("moment, offset", [
    (utc(2026, 1, 15, 12), 3600),
    (utc(2026, 3, 29, 0, 59), 3600),        # the last Sunday of March 2026, before 01:00 UTC
    (utc(2026, 3, 29, 1, 0), 7200),
    (utc(2026, 7, 1), 7200),
    (utc(2026, 10, 25, 0, 59), 7200),       # the last Sunday of October 2026
    (utc(2026, 10, 25, 1, 0), 3600),
    (utc(2027, 3, 28, 1, 0), 7200),         # 2027: March 28 and October 31
    (utc(2027, 10, 31, 0, 59), 7200),
    (utc(2027, 10, 31, 1, 0), 3600),
])
def test_italian_time_follows_the_european_summer_time(moment, offset):
    assert italy_offset()(moment) == offset


def test_a_photo_becomes_an_lvgl_image_of_the_display(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage

    QGuiApplication.instance() or QGuiApplication(["test", "-platform", "offscreen"])
    wide = QImage(600, 300, QImage.Format_RGB32)
    wide.fill(Qt.red)
    for x in range(250, 350):                  # a blue band in the middle, which the cut keeps
        for y in range(300):
            wide.setPixel(x, y, 0xFF0000FF)
    wide.save(str(tmp_path / "wide.png"))
    assert convert_photos.main([str(tmp_path / "wide.png"), "--output", str(tmp_path / "out"), "--size", "480x480"]) == 0
    data = (tmp_path / "out" / "wide.bin").read_bytes()
    magic, cf, flags, width, height, stride, _ = struct.unpack("<BBHHHHH", data[:12])
    assert (magic, cf, width, height, stride) == (0x19, 0x12, 480, 480, 960)
    assert len(data) == 12 + 480 * 480 * 2

    def pixel(x, y):
        value = struct.unpack_from("<H", data, 12 + (y * 480 + x) * 2)[0]
        return value >> 11, (value >> 5) & 63, value & 31

    assert pixel(240, 240) == (0, 0, 31)       # the blue band, scaled by 1.6 and cut at the centre
    assert pixel(5, 240) == (31, 0, 0)         # red at the sides


def test_a_file_that_is_not_a_photo_is_reported(tmp_path, capsys):
    (tmp_path / "notes.png").write_text("not a picture")
    assert convert_photos.main([str(tmp_path / "notes.png"), "--output", str(tmp_path / "out")]) == 1
    assert "not converted" in capsys.readouterr().err
