# Forecast

A weather station for the ESP32-4848S040 (480×480): the weather of now and of five days from
[Open-Meteo](https://open-meteo.com/), for up to five places, swiped left and right. It connects
over WiFi, keeps its settings on the SD card or in the flash, dims the backlight at night and
speaks English or Italian.

**SET** opens the setup in four steps: WiFi network, places, style (theme, units, refresh,
language, brightness) and night.

In the simulator there is no WiFi: the networks, the places found and the weather are demo
data, so every page can be tried. Open `project.json` and press F5. It is the English version of
an example the author made in Italian; this version was checked in the simulator, not on a board.
