# Orbit

A game for a 480×480 touch screen. A swarm of geometric drones comes down towards an orbital ring;
drag a finger in the band at the bottom to move the ship, which fires by itself. The swarm fires
back, speeds up when few drones are left and changes shape at every wave: diamond, ring, trident,
wall. Three lives; speed and sound in **Options**.

The code is written for the ESP32: the objects are created once, the whole swarm is one
container, and the game loop uses small integers and lists made in advance.

Open `project.json` and press F5. It is the English version of an example the author made in
Italian. On the ESP32-4848S040 it runs from the board's home menu, with its texts in English or Italian, the language chosen on the Display page of [Settings](../settings/README.md):
see [the home menu of the board](../settings/README.md#the-home-menu-of-the-board).
