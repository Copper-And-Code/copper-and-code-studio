# Block Drop

A falling-block puzzle for a 480×480 touch screen, made for the ESP32-4848S040. Pieces of four
blocks fall into a well ten cells wide and twenty tall: move and turn them so they fill whole
rows. A full row goes away; every ten rows the level goes up and the pieces fall faster. A dim
shadow shows where the piece will land, and the box on the right shows the next one.

Keys on the right: **Rotate**; **Left** and **Right**, which repeat while held; **Down**, which
drops faster while held (1 point a row); **Drop**, straight to the bottom (2 points a row). Tap
the well to start, to pause and to go on. Rows score 100, 300, 500 or 800 points for 1 to 4 at
once, times the level.

The code is written for the ESP32: the 200 cells of the well are LVGL objects created once, and
a frame changes the colour only of the cells that changed, so a move redraws a few blocks.

Open `project.json` and press F5. It was checked in the simulator.
