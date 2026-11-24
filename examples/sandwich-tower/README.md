# Sandwich Tower

A game for a 480×480 touch screen. A chef runs on four floors joined by ladders. Each layer of a
sandwich has to be stepped on in four places to fall by one floor, and pushes down the layer under
it; from the last floor the layers land on the plates. A chili, an olive and a gherkin chase the
chef: a falling layer squashes them, the spray stuns them. Three lives, five sprays per level;
speed and sound in **Options**.

Keys on the screen: left, down, up, right (held down) and **Spray**. The code is written for the
ESP32: the objects are created once and the game loop does not allocate.

Open `project.json` and press F5. It is the English version of an example the author made in
Italian. On the ESP32-4848S040 it runs from the board's home menu, with its texts in English or Italian, the language chosen on the Display page of [Settings](../settings/README.md):
see [the home menu of the board](../settings/README.md#the-home-menu-of-the-board).
