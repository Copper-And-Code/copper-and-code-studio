# Status: what is verified, and how

Version 0.8.0, the first under the name Copper and Code Studio, is published as a GitHub release, with
an AppImage for Linux; the portable package for Windows is that of 0.7.1, under the old name. This page separates what has been
checked from what has only been written.

## Read this first

The project was built broad on purpose: features expected to be useful were included from the
start, so that the design would not need to be reopened later. The automated tests are many.
**Human testing is scarce**: few people have used the IDE, and much of what is listed below has
never been tried by a person on a real task. Expect rough edges, and treat every "not tried"
below as an open question, not as a formality.

## How each area was checked

- **Tests**: covered by the automated suite, more than 1250 tests.
- **Self-test**: exercised in the real IDE window by `copper-and-code-studio selftest`.
  Besides, suites run by hand (`pytest tests/manual --manual`) trigger every menu entry,
  toolbar button and context menu entry of the IDE in five states, with every dialog answered
  with Cancel and with OK, look at every dialog in English and Italian, compare pictures of the
  window, and cause faults such as a full disk or a board pulled out; they check that nothing
  breaks, not that the result is right. They are not a person using the IDE. [How it is tested](testing.md) describes every check and what none of them sees.
- **Board**: tried on real hardware, with the board named.
- **Not tried**: written and tested by machine only, or not at all.

| Area | Tests | Self-test | Board or real use | Not tried |
|---|---|---|---|---|
| Designer, properties, undo | yes | yes | author's use | other users |
| Code editor, handlers, Python modules | yes | yes | ESP32-4848S040 (modules) | |
| Simulator on the PC | yes | yes | author's use | |
| Files, commands and the network on the PC ([page](pc-programs.md)) | | | the examples, on the Linux runtime; the modules listed from each runtime, Windows under Wine | a real Windows |
| MicroPython generation, upload as bytecode | yes: Upload and Run of an example on a virtual board, through the real `mpremote` | | ESP32-4848S040, STM32H7_CORE, Waveshare RP2350 | |
| Live editing on a board | yes | | ESP32-4848S040 | the other boards |
| Pictures in a project | yes | yes | STM32H7_CORE (seen on the display) | RP2350, ESP32-S3 |
| Fonts of a project, kerning | yes, against LVGL's Montserrat | yes | STM32H7_CORE (seen), RP2350 (loaded) | ESP32-S3 |
| Font memory warning | yes | | Waveshare RP2350, when fonts were text in `ui.py`. ESP32-4848S040, 23 November 2026: a font in three sizes, 70 kB of files, takes 103 kB of the heap read from files and 196 kB as text in `ui.py`, measured with `gc.mem_alloc()` on a project of three labels | the peak while a font loads; the RP2350 with fonts in files |
| Upload of only the files that changed; fonts and pictures as files on the board | yes: on a virtual board through the real `mpremote`: a second upload, a file changed on the board by hand, a file the board cannot read, a project with a font and three pictures started twice | | ESP32-4848S040, 23 November 2026, driven by a script through the IDE's code: Weather uploaded twice (15.7 s, then 6.3 s with 10 files of 11 copied on the board); with a font in three sizes 49.8 s, then 12.4 s after a change to a text (6 kB of 90 kB sent); the app started each time with its pictures and fonts read from their files; Block Drop, Star Guard and Crossword uploaded and started. 24 November 2026, the small files written by one script: a project with 30 pictures, 37 files and 18 kB, in 15.1 s where one copy for each file took 34.9 s; Weather in 9.8 s where it took 18.2 s | from the IDE's window by a person; the other boards; a firmware without `hashlib`; Windows |
| C export | yes, pixel parity with MicroPython in the simulator | | | in a real C project; fonts in C on a board |
| Device Console as a terminal (keys as typed, ANSI colours and cursor) | yes: the VT100 sequences cell by cell, the keys, the port taken and given back | | STM32H7_CORE V1.3 and ESP32-4848S040, 13 November 2026, driven by a script through the IDE's code: the shell typed to and read back, the console stopped and started again three times | typed by a person; full-screen editors on a board; Windows |
| Programs without pages in the simulator (Run Program) | yes: the service while waiting for a key, Ctrl-C, the flash that cannot be left, reset, the IDE | yes: Run Program and typing in the terminal, on Linux | the shell of `mpy-lvgl-boards` with `edit` and `vi`, driven by the tests of this work, not yet used by a person | used by a person; Windows, not available |
| Display driver contract 1 for programs (Ctrl-C reaches the program, the screen goes on) | yes: the names, and 30 Ctrl-C of 30 in a loop, in `stdin.read()` and with an `lv.timer` busy; the shell stopping `sleep 2` 10 times of 10 | | on the boards it is the firmware's own driver, measured in mpy-lvgl-boards. ESP32-4848S040 with firmware v0.1.7, through the IDE by the owner, 14 November 2026: Ctrl-C in `sleep 5` several times, during long output and on an empty line, prompt back each time, screen on, no traceback; Stop back to `>>>`; a project with pages run and stopped | the browser, by a person; STM32H7_CORE V1.3 and RP2350 with v0.1.7 through the IDE |
| Upload Files, Run File on Board | yes, with a board simulated in memory and a fake serial port, also the question when a folder would hide a module; on a virtual board with the real `mpremote`: no reset, Cancel, the cable pulled | yes, with a board the self-test keeps in memory | STM32H7_CORE V1.3 (over its USB) and ESP32-4848S040, 13 November 2026: the shell of `examples/shell` copied (6 files, 110 kB, about 32 s) and started, `pwd`, `ls`, `uname -a`, `cd`, `exit`. ESP32-4848S040, 14 November 2026, by the owner: Run on the Board of the shell asked about `shell` hiding `/shell.py`, No uploaded nothing, Yes uploaded and ran it; the folder deleted from the Files panel | the editors on a board; the RP2350; used by a person |
| Programs without pages in the browser (the shell demo) | yes: the page in headless Chromium, `help` answered; the build of the page | | | Firefox, Safari, a phone with its on-screen keyboard; used by a person |
| Files panel and file tabs | yes, with a board simulated in memory; the board's files also on a virtual board with the real `mpremote` | yes: folder, tabs, New File and Rename from the menu; the files of a board kept in memory | the board's files: the service on the STM32H7_CORE V1.3 (USB) and the ESP32-4848S040 (list, read, write, rename, folder, delete), and the panel driven through the IDE on the ESP32-4848S040 (list, open, edit, save, restore; Run on the Board with the shell: upload, start, `pwd`, `exit` in 38 s), 13 November 2026 | used by a person; the panel on the STM32H7 |
| Board definitions from a file (import, export, delete) | yes: the store, the Board Profile Manager, the command line and MCP, with a made-up board and an adapter the IDE has no code for; a project whose board was deleted | | a board that is not built in, by the owner, 17 November 2026: imported from the Board Profile Manager, connected, a project uploaded and run on it | Export and Delete used by a person; the command line and MCP on hardware |
| Upload progress window | yes | | RP2350: the figures it shows | the window itself, watched by a person |
| Buzzer | yes | yes, in the simulator | | on a board |
| Block: Digital Output | yes, with a fake `machine` | yes, in the simulator | STM32H7_CORE: the two LEDs of the board on pins `B0` and `B1`, driven from a Timer, the pin levels read back and the LEDs seen by the author | other boards |
| Block: Digital Input | yes, with a fake `machine` | yes, in the simulator | STM32H7_CORE: the two keys of the board on pins `A0` and `A1`; the author saw the LEDs follow the keys | other boards; the debounce, which was not measured |
| Block Manager, blocks from other people | yes | | | used by a person; a block written by someone else |
| Browser version (WebAssembly) | yes | | Chromium, two resolutions | Firefox, Safari, phones |
| Single-file executables | yes, on Linux and under Wine | | Linux | Windows, natively |
| Windows | yes, under Wine, and natively in continuous integration | yes, on Windows 11 from the portable package and in continuous integration | the portable package of 0.6.0 started by the author on Windows 11 | boards and builds on Windows |
| MCP server | yes, and a recorded session | | | the board tools, on hardware |
| Visual tests | yes | | used on the EIM-01 example | |
| Print Sources | yes | | a PDF, read | a real printer |
| Self-test, visible mode (`--show`) | | | | never run |
| AppImage for Linux | | yes, run from inside the package | the package of 0.8.0, released, built from a clean clone of the tag: `--version`, self-test from an empty folder (105 steps passed) and a single-file game built by it, started with `--selftest`, on the author's computer. The package of 0.7.2, released: `--version`, self-test from an empty folder (105 steps passed) and a single-file game built by it, started with `--selftest`, on the author's computer. The package of 0.7.1, released: self-test from an empty folder, 82 steps passed, on the author's computer. The package of 0.7.0, released: the same self-test on the author's computer and, on 14 November 2026, on Ubuntu 24.04, Debian 13, Fedora 43 and Arch Linux in containers without a display; it needs glibc 2.38, so it does not start on Debian 12 or Ubuntu 22.04. On a Chromebook, by the author: installed in the Linux development environment on Debian 13, glibc 2.41, the self-test passed, the simulator with touch and sound, a board over USB ([Running on a Chromebook](chromebook.md)). The package of 0.6.1, released: self-test, 82 steps passed. The package of 0.6.0, on the author's computer: self-test, visual tests of EIM-01, board and C generation, single-file games for Linux (needing glibc 2.34 or later) and Windows, browser version | on Ubuntu 22.04 and Debian 12, where it does not start; the window seen on another Linux system |
| Portable Windows package | | | the package of 0.6.0: contents inspected (no bundled ICU, the icon in the program file, the blocks) and started by the author on a real Windows. The package of 0.6.1, released: contents inspected, started by the author on Windows, no console windows flashing | the packages of 0.7.0 and 0.7.1 (0.7.2 and 0.8.0 have no package of their own), released: contents inspected (version, no bundled ICU, the launcher, the display driver of contract 1), not started on Windows yet; the installer, never built |

"Author's use" means the author uses it while developing; it is not a test plan.

## Project website

The English documentation and six browser demos are published at
<https://copper-and-code.github.io/copper-and-code-studio/> from the `gh-pages` branch. On 12 November
2026, the public home, manual, gallery, and the five demos of that day were checked in Chromium. Each demo
reported a running WebAssembly application and a non-black canvas; a simulated touch changed the
Fifteen screen, and no requests went to external domains. The IDE test for **Help → Online
Documentation** also passed and opens the same public address.

Firefox, Safari, and a real phone with touch and sound have not been tried.

## The IDE in the browser

The whole IDE in the browser is built in [copper-and-code-studio-web](https://github.com/Copper-And-Code/copper-and-code-studio-web), a repository of its own
that holds this one as a git submodule at a tag and runs its `core/`, `gen/` and `build/` in
Pyodide. It is published at <https://copper-and-code.github.io/copper-and-code-studio-web/>. It is a work in progress: experimental, but already
usable, in the author's judgement. Its checks are recorded in that repository, not here.

## Known defects and open points

- **Windows.** The portable package of 0.4 did not start on a real Windows: it bundled a copy
  of ICU that hid the system's. The package of 0.6.0 is built without it and starts on
  Windows 11. The self-test run there passed 76 steps of 78. The step that failed was a
  mistake of the self-test, which compared a path written with `\` with the same path written
  with `/`; the step after it was skipped. The run also showed a real defect: when the program
  ended while a measurement was running, a simulator process stayed alive and its temporary
  folder could not be removed. Both are corrected, and the author ran the corrected package on Windows 11 without that
  error. Tests under Wine had shown neither. A third defect, reported by the author, is
  corrected: started from the program file, a console window flashed four times at almost
  every operation. On 13 November 2026 the author saw no such window with the package of 0.6.1.
  With a package built on 13 November 2026 from the branch `programs-without-pages`, the author
  used a board on a COM port; the window's icon and pinning it to the taskbar did not work.
  Not looked into yet.
- **The new name, Copper and Code Studio, came with 0.8.0.** What was tried, on the author's
  computer, 20 November 2026: the whole suite, the self-test and the suites run by hand (the
  monkey in `test_save_and_reopen.py` crashes the IDE, as it already did with the code before the
  new name, and one long random sequence of `test_random_use.py` failed once, but not when it
  was replayed on its own); an
  AppImage built under the new name, `--version` and the self-test from an empty folder (105
  steps passed); the settings and a project written by the code of 0.7.2, read by the renamed IDE
  (language, layout of the panels, recent files and the configuration folder kept, the project
  saved again byte for byte the same); the three commands. Not tried: the lines the IDE reads back
  from a board, now beginning with `LMS_`, on a real board (only on the virtual board and the boards
  kept in memory by the tests); the Windows packages under the new name, and the installer over
  an installation of LVGL MPY Studio; the project website at its new address. See
  [The new name](renamed.md).
- **The IDE does not know the pins of a board.** A block takes the pin the user types, a
  number or a name such as `PA5`, and nothing warns when it is one the display or the memory
  already uses.
- **The RAM budget** shown in the status bar is measured in the 64-bit simulator and is an
  overestimate for 32-bit boards. It also counts the fonts and pictures of the project as text
  in `ui.py`, as the simulator has them, while a board reads them from files: for fonts 2.8
  times their size where the ESP32-4848S040 uses 1.5.
- **Renaming a Python module** does not rewrite the code that imports it; the IDE warns.
- **Reference images that hold a changing value** fail when the generator changes: the EIM-01
  example shows the free memory on a page, and its image had to be regenerated for 0.6.
- **Continuous integration covers tests, not packages.** Since the repository became public,
  each push runs the whole suite and the self-test on Linux, and on Windows the tests of the
  core, of the runtime and of the IDE, and the self-test. On the Linux machine 72 tests are
  skipped, because they need what is not built there: the launchers of single-file games, the
  WebAssembly runtime, Wine, a browser. Packages are built and checked by hand.
- **An upload that sends only what changed is tried on one board**, the ESP32-4848S040. Whether
  the firmware of the other boards has the `hashlib` it needs is not checked: without it every
  file is sent, as before. Fonts read from files take less memory than before, but more on the
  ESP32-4848S040 (1.46 times their size) than on the virtual board (1.03), and why is not
  understood: of three sizes loaded one at a time, the largest kept about twice its size.

## What is not there

- C on boards: only MicroPython is uploaded. The C export is source code for another project.
- An online catalogue of blocks, and blocks that depend on other blocks.
- Extensions that run inside the IDE: blocks are data and MicroPython code, nothing more.
- Blocks for PWM, ADC, I2C, SPI and UART: planned in [the plan](https://github.com/Copper-And-Code/copper-and-code-studio/blob/main/docs/plugins-plan.md), not written.
- A debugger. Errors are reported with file and line; there are no breakpoints.
- macOS.

## How to check for yourself

```bash
.venv/bin/python -m pytest -q        # the whole suite, about ten minutes
.venv/bin/copper-and-code-studio selftest   # the IDE uses itself, about twenty seconds
```

The self-test writes `report.txt` with one line for each step. A step that fails is a defect
worth reporting.
