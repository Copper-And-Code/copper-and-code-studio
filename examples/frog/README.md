# Frog

A game for a 480×480 touch screen. At night a frog crosses a path and a pond to catch three
fireflies: on the path it dodges insects and robot mowers, in the pond it rides the water lilies.
With three fireflies caught the next night comes, faster. Three lives; speed and sound in
**Options**.

The four keys at the bottom make the frog hop by one cell. The code is written for the ESP32:
the objects are created once, a row moves as one container, and the score digits are clipped
columns, so the game loop does not allocate.

Open `project.json` and press F5. It is the English version of an example the author made in
Italian. On the ESP32-4848S040 it runs from the board's home menu, with its texts in English or Italian, the language chosen on the Display page of [Settings](../settings/README.md):
see [the home menu of the board](../settings/README.md#the-home-menu-of-the-board).
