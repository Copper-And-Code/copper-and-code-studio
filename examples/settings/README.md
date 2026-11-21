# Settings

The settings of a board, kept once for every app: the WiFi networks and the brightness of the
display. **Settings** adds up to five networks, from a scan, with their passwords; touches one to
choose it, **Connect** tries it, **Forget** removes it. The networks are kept from the most
recently used. **Display** sets the brightness.

They live in one file in the flash, `cac_settings.json`:

```json
{"version": 1, "wifi": [{"ssid": "Home", "password": "..."}], "display": {"brightness": 70}}
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

The home menu of the ESP32-4848S040 in `mpy-lvgl-boards` (`examples/home`) reads the same file:
it sets the brightness and connects before it starts an app.

## In the simulator

There is no WiFi: the scan shows three demo networks, and the networks are saved in a file next
to the running program, which the simulator throws away. Open `project.json` and press F5. It was
checked in the simulator and by the tests of `tests/test_cac_settings.py`, not on a board.
