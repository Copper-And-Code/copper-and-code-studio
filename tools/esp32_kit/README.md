# The kit of the ESP32-4848S040

Everything the ESP32-4848S040 (a 4" 480×480 touch screen with an ESP32-S3) needs to work as a
weather station, a clock, a photo frame and a few games, with no PC once it is set up. Made with
[Copper and Code Studio](https://github.com/Copper-And-Code/copper-and-code-studio); the
firmware comes from [copper-and-code-mcu-boards](https://github.com/Copper-And-Code/copper-and-code-mcu-boards).
In Italian: [LEGGIMI.md](LEGGIMI.md). How to use the board once it is set up: [GUIDE.md](GUIDE.md).

| Folder | What it is | Where it goes |
|---|---|---|
| `firmware/` | MicroPython 1.29 with LVGL 9.5 for this board | the flash of the board, with `esptool` |
| `flash/` | `main.py`, which starts the home of the card; `boot.py` and `cac_settings.py`, for the WiFi and the settings; the shell, for a board with no card | the flash of the board, with `mpremote` |
| `sd/` | the home and its menu, the apps, the games, an empty `photos` folder | a microSD card, FAT32 |

You need a computer with Python 3 and a USB-C cable that carries data. The board shows up as a
serial port: `/dev/ttyUSB0` on Linux, `COM3` or similar on Windows (Device Manager, "Ports"),
`/dev/cu.usbserial-…` on a Mac. Below it is `PORT`.

## 1. The firmware

Once for each board. It erases everything in the flash, saved WiFi networks too.

```bash
pip install esptool
esptool.py --chip esp32s3 -p PORT erase_flash
esptool.py --chip esp32s3 -p PORT -b 460800 write_flash 0x0 firmware/ESP32_4848S040-v0.1.8.bin
```

(With a recent esptool the command is `esptool` and the subcommands `erase-flash` and
`write-flash`.) Without Python, [ESP Tool](https://espressif.github.io/esptool-js/) of Espressif
does the same from Chrome or Edge: Connect, Erase Flash, then the file at address `0x0`.

## 2. The files of the flash

```bash
pip install mpremote
cd flash
mpremote connect PORT cp main.py boot.py cac_settings.py shell.py ansiterm.py ansifont.py OFL.txt :
mpremote connect PORT reset
```

[Thonny](https://thonny.org/) does it too: interpreter "MicroPython (ESP32)" on that port, then
each file with **Upload to /**.

## 3. The SD card

A microSD card of up to 32 GB, formatted FAT32. Copy **the content** of `sd/` to the top of the
card, not the folder itself: the card must have `home.json`, `apps/`, `bin/`, `lib/` and `photos/`
at its top. Put it in the board with the board unplugged.

## 4. Power on

Plug the board in: Forecast starts. Then, on the board, the Settings app (pull down from the
top edge, the home button, Settings): **WiFi** for the network, **Display** for the language,
English or Italian, **Start** for the app of power-on. See [GUIDE.md](GUIDE.md).

## Updating

A newer kit: copy the content of its `sd/` over the card, replacing the files. Photos and
settings stay: photos are in `photos/`, which the kit does not fill, and the settings are in
the flash. The firmware and the flash files need writing again only when the notes of the
release say so.

Whoever has the repositories can do the same with `tools/esp32_sd.py` of Copper and Code
Studio, which writes only what changed, also through the serial port with the card in the
board.
