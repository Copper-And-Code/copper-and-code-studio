# Star Guard

A shooting game for a 480×480 touch screen, made for the ESP32-4848S040. A squadron of forty
drones marches across the sky a step at a time and comes down a row at every edge: shoot them
all before they land. The fewer are left, the faster they march, and every new wave starts
lower. Four shields crumble a square at a time, under your shots and theirs; now and then a
comet crosses the top of the sky for a bonus of 50 to 300 points. Three lives.

Keys: **Left** and **Right**, held down, and **Fire**, which fires again while held as soon as
the shot is gone (one shot on the screen at a time). Tap the sky to start, to pause and to go on.

The code is written for the ESP32: every object is made once, and the forty drones are children
of one container, so a step of the squadron moves a single object.

Open `project.json` and press F5. It was checked in the simulator.
