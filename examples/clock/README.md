# Clock

An analog clock for a 480×480 touch screen, made for the ESP32-4848S040: a dark round face with a
tick for each minute, the numbers, the hands of the hours and of the minutes, a thin orange second
hand, and the date in English or Italian.

At night the face turns dark red and the backlight goes down to 15%, so that the clock does not
light the room. The night is that of the [Forecast](../forecast/README.md) example, from its
`/sd/weather.json`, or 22:00 to 7:00 without it; by day the brightness is the one of the
[Settings](../settings/README.md) example.

The time comes from the network (NTP) through the networks of the Settings example, and is
Italian time: CET, and CEST from the last Sunday of March to the last Sunday of October. Until
the network has set it, a small orange dot under the face says that the time may be wrong. The
language of the date is the one chosen on the Display page of Settings, English if none.

The face is drawn once; each second only the hands move, and the redraw covers the area they
sweep, not the whole screen.

In the simulator the clock shows the time of the simulator. Open `project.json` and press F5.

On the ESP32-4848S040 it can be started from the board's home menu, and made the app of power-on
on the Start page of Settings: see [the home menu of the board](../settings/README.md#the-home-menu-of-the-board).
