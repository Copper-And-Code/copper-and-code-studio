# Photo Frame

A digital photo frame for the ESP32-4848S040 (480×480): the photos of `/sd/photos` on the SD card,
one every 10 seconds in a random order with no repeats; a swipe to the left or to the right goes
to the next or the previous one. A touch shows the time, the name of the photo and **Options**.
At night, from 22:00 to 5:30, the display goes off; a touch turns it on for a minute. Photos
copied to the folder while the frame runs come in at the next round.

**Options** sets the time of each photo (5 s to 5 min), the night on or off and its hours. They
are kept in `cac_settings.json`, section `frame`; the brightness is that of the Display page of
the [Settings](../settings/README.md) example.

The time comes from the network (NTP), through the WiFi networks saved by Settings, and is
Italian time: CET, and CEST from the last Sunday of March to the last Sunday of October. Without
a network there is no time: the clock shows `--:--` and the display stays on.

## The photos

The firmware of the board decodes PNG but not JPEG, and a PNG of 480×480 takes more than half a
second. So the photos are prepared on the PC as LVGL images in RGB565, drawn at once with no
decoder, about 460 KB each:

```bash
python convert_photos.py ~/Pictures/holidays --output photos
```

Run it with the Python of Copper and Code Studio, which has PySide6. Each photo is turned upright
from its EXIF orientation, scaled to cover the screen and cut at the centre (`--fit` keeps the
whole photo with black bands; `--size` for another display), and dithered, so that the skies have
no bands in the 65 thousand colours of the display. Then copy the folder to `/sd/photos` with the
[FTP Server](../ftp-server/README.md) example, about four seconds a photo:

```bash
for f in photos/*.bin; do curl -T "$f" --ftp-create-dirs --user mpy:PASSWORD ftp://ADDRESS/sd/photos/; done
```

## In the simulator

There is no SD card and no network: three demo pictures take turns, and the clock is the
simulator's. Open `project.json` and press F5. `tests/test_photo_frame_example.py` checks the
summer time and the converter.

On the ESP32-4848S040 it can be started from the board's home menu: see [the home menu of the board](../settings/README.md#the-home-menu-of-the-board).
