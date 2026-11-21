# Forecast

A weather station for the ESP32-4848S040 (480×480): the weather of now and of five days from
[Open-Meteo](https://open-meteo.com/), for up to five places, swiped left and right. It keeps its
settings on the SD card or in the flash, dims the backlight at night and speaks English or
Italian.

The WiFi networks are those of the [Settings](../settings/README.md) app, in
`cac_settings.json`: Forecast connects with `cac_settings.connect()`, a module of the project.
Without a saved network in range it says so in its status line. A `weather.json` of the earlier
version, which kept one network of its own, gives it to `cac_settings.json` on the first start.

**SET** opens the setup in three steps: places, style (theme, units, refresh, language,
brightness) and night.

In the simulator there is no WiFi: the places found and the weather are demo data, so every page
can be tried. Open `project.json` and press F5. It is the English version of
an example the author made in Italian; this version was checked in the simulator, not on a board.
