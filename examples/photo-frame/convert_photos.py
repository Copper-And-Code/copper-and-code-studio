#!/usr/bin/env python3
"""Photos for the Photo Frame example: JPEG, PNG and the other formats Qt reads, cut to the size of
the display and written as LVGL images in RGB565, ready for /sd/photos on the board.

    python convert_photos.py PHOTO_OR_FOLDER... --output photos [--size 480x480] [--fit]

Each photo is turned upright from its EXIF orientation, scaled to cover the screen and cut at the
centre (--fit keeps the whole photo, with black bands). RGB565 has 32 levels of red and blue and
64 of green: an ordered dither keeps the skies and the faces free of bands. The result is a .bin
file of LVGL 9, a 12-byte header and the pixels, about 460 KB for 480×480; the board draws it in
a few milliseconds, with no decoder. Copy the folder to the SD card with the FTP Server example,
for example `curl -T beach.bin --user mpy:PASSWORD ftp://ADDRESS/sd/photos/`.

It uses PySide6, which comes with Copper and Code Studio: run it with Studio's Python.
"""
import argparse
import struct
import sys
from pathlib import Path

MAGIC = 0x19                      # LV_IMAGE_HEADER_MAGIC
RGB565 = 0x12                     # LV_COLOR_FORMAT_RGB565
SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".heic"}
BAYER = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)


def tables():
    """For each of the 16 cells of the dither: the 5-bit and the 6-bit value of each 8-bit level."""
    fives, sixes = [], []
    for cell in BAYER:
        nudge = (cell + 0.5) / 16 - 0.5
        fives.append(bytes(min(31, max(0, round(v * 31 / 255 + nudge))) for v in range(256)))
        sixes.append(bytes(min(63, max(0, round(v * 63 / 255 + nudge))) for v in range(256)))
    return fives, sixes


def header(width, height):
    return struct.pack("<BBHHHHH", MAGIC, RGB565, 0, width, height, width * 2, 0)


def rgb565(rgb, width, height, fives, sixes):
    """RGB888 rows (no padding) to little-endian RGB565 with an ordered dither."""
    out = bytearray(width * height * 2)
    o = 0
    for y in range(height):
        row = (y & 3) * 4
        base = y * width * 3
        for x in range(width):
            cell = row + (x & 3)
            i = base + x * 3
            value = (fives[cell][rgb[i]] << 11) | (sixes[cell][rgb[i + 1]] << 5) | fives[cell][rgb[i + 2]]
            out[o] = value & 0xFF
            out[o + 1] = value >> 8
            o += 2
    return out


def convert(source, target, width, height, fit, fives, sixes):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QImageReader, QPainter

    reader = QImageReader(str(source))
    reader.setAutoTransform(True)                     # the EXIF orientation of a phone's photo
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString())
    mode = Qt.KeepAspectRatio if fit else Qt.KeepAspectRatioByExpanding
    scaled = image.scaled(width, height, mode, Qt.SmoothTransformation)
    canvas = QImage(width, height, QImage.Format_RGB888)
    canvas.fill(Qt.black)
    painter = QPainter(canvas)
    painter.drawImage((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
    painter.end()
    rows = bytearray()
    for y in range(height):                          # the rows of a QImage are padded to 4 bytes
        rows += bytes(canvas.constScanLine(y))[:width * 3]
    target.write_bytes(header(width, height) + rgb565(rows, width, height, fives, sixes))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sources", nargs="+", type=Path, help="photos, or folders of photos")
    parser.add_argument("--output", type=Path, required=True, help="folder for the .bin files")
    parser.add_argument("--size", default="480x480", help="size of the display, default 480x480")
    parser.add_argument("--fit", action="store_true", help="keep the whole photo, with black bands")
    args = parser.parse_args(argv)
    width, height = (int(n) for n in args.size.lower().split("x"))

    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication(["convert_photos", "-platform", "offscreen"])
    photos = []
    for source in args.sources:
        if source.is_dir():
            photos += sorted(p for p in source.iterdir() if p.suffix.lower() in SUFFIXES)
        else:
            photos.append(source)
    args.output.mkdir(parents=True, exist_ok=True)
    fives, sixes = tables()
    failed = 0
    for n, photo in enumerate(photos, 1):
        target = args.output / (photo.stem + ".bin")
        try:
            convert(photo, target, width, height, args.fit, fives, sixes)
            print("%d/%d %s -> %s" % (n, len(photos), photo.name, target.name))
        except (OSError, ValueError) as error:
            failed += 1
            print("%d/%d %s: not converted: %s" % (n, len(photos), photo.name, error), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
