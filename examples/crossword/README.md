# Crossword

A crossword for a 480×480 touch screen, made for the ESP32-4848S040, in English (the default)
or in Italian. Every puzzle is new: the board builds it from a list of words with their clues,
the modules `words_en` (205 words) and `words_it` (178 words). The first word goes across or
down the middle of an 11×11 grid, then words that cross it are added, up to twelve, never
touching side by side.

Tap a square to choose it, tap it again to switch between Across and Down. Type with the keys
at the bottom; **Del** clears. **<** and **>** go to the previous and the next word. **Check**
marks the wrong letters in red, **Reveal** fills in the word you are on, in blue. The button on
the top right switches language and starts a new puzzle in it.

The language is kept in the shared settings file, `cac_settings.json`, section `crossword`
(see the `settings` example). Italian words are written without accents, as in Italian
crosswords; in the clues an accent is an apostrophe (piu', caffe'), because the built-in
fonts have only ASCII.

To add words, append `"WORD|clue"` lines to `words_en` or `words_it`: 3 to 11 letters A-Z.

Open `project.json` and press F5. It was checked in the simulator.
