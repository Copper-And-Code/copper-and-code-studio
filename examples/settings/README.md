# Settings

The settings of a board, kept once for every app: the WiFi networks, the brightness of the
display and the app that starts at power-on. **Settings** adds up to five networks, from a scan,
with their passwords; touches one to choose it, **Connect** tries it, **Forget** removes it. The
networks are kept from the most recently used. **Display** sets the brightness and the language,
English or Italian, of every app of the board. **Start** chooses
what the [home menu of the board](#the-home-menu-of-the-board) starts at power-on instead of the
shell: one of the apps of its menu, not those of a folder such as Games, or the shell itself.

They live in one file in the flash, `cac_settings.json`:

```json
{"version": 1, "wifi": [{"ssid": "Home", "password": "..."}], "display": {"brightness": 70}, "general": {"language": "en"}, "home": {"start": "/sd/apps/forecast/app_main.py"}}
```

`cac_settings.section("display")` and `cac_settings.set_section("display", ...)` read and write a
section; the networks and the other sections stay.

It is `/cac_settings.json` on the ESP32 and the RP2350, and `/flash/cac_settings.json` on the
STM32. The passwords are in clear text, as in MicroPython's own examples: whoever can read the
flash can read them.

| File | What it does |
|---|---|
| `cac_settings.py` | reads and writes the file and its sections, scans, and connects to the best saved network in range: the most recently used first, then the strongest. Hidden networks are not tried. |
| `boot.py` | connects at power-on, so that every app finds the network ready |
| `project.json` | the Settings app, for the ESP32-4848S040 (480×480) |

## On a board

1. **Device → Upload Files…**: `boot.py` and `cac_settings.py` to the root of the flash, `/` on
   the ESP32 and the RP2350, `/flash` on the STM32.
2. Open `project.json`, choose the board as the target and run it, or install it with **Install
   Autostart**; add the networks.
3. Any other app that needs the network has `cac_settings.py` as one of its Python modules and
   calls `cac_settings.connect()`, which returns the name of the network or `None`.
   [Forecast](../forecast/README.md) does so.

At power-on `boot.py` costs one scan, a couple of seconds, when no saved network is in range.

## The home menu of the board

The board repository has a home for the ESP32-4848S040, [`examples/home`](https://github.com/Copper-And-Code/copper-and-code-mcu-boards/tree/main/examples/home): a shell on the
display at power-on, and on a tap a menu of apps, with folders and a home button over each app
(hidden until a pull down from the top edge, so that it covers nothing). It
reads the same `cac_settings.json`: it sets the brightness and connects before it starts an app.

The Studio installs an app in `/lms_apps/app_<id>/`, where the id comes from the project, so it
is the same on every board. These are the lines of `/sd/home.json` for the examples:

```json
{"name": "Settings", "path": "/lms_apps/app_265fef53d674/app_main.py"},
{"name": "Forecast", "path": "/lms_apps/app_1130d29ac8f6/app_main.py"},
{"name": "FTP Server", "path": "/lms_apps/app_055fd10dc1ca/app_main.py"},
{"name": "Photo Frame", "path": "/lms_apps/app_9094b9139352/app_main.py"}
```

Upload each app once from the Studio (**Device → Upload Project**), then add its line to the menu. Started
from the Studio instead, an app has no home button: there is no menu to go back to.

The apps can live on the SD card instead of the flash. [`tools/esp32_sd.py`](../../tools/esp32_sd.py)
of this repository fills a card, in a PC or in the board, with the home, its programs and the
examples made for this screen, each in a folder of `/sd/apps`, and writes the menu for them: see
[Development](../../docs/development.md#the-sd-card-of-the-esp32-4848s040).

At power-on the home starts the app chosen on **Start**, or, before a choice, the one the menu
names in `"start"`: Forecast, on a card filled by `tools/esp32_sd.py`. For two seconds the screen
shows its name, and a touch then gives the shell instead. The home button of an app always goes
to the shell. The choice is kept in the flash, so a new card does not change it; a choice that is
not on the card gives the shell.

## In the simulator

There is no WiFi: the scan shows three demo networks, and the networks are saved in a file next
to the running program, which the simulator throws away. Open `project.json` and press F5. It was
checked in the simulator and by the tests of `tests/test_cac_settings.py`, not on a board.
