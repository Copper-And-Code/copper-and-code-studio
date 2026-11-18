# How LVGL MPY Studio is tested

Few people have used the IDE so far, so most of the checking is done by machine. This page
says what is checked, by what, how to run it, and what no automated check can see.
[What is verified](status.md) says, area by area, which of these checks it has had.

## The layers

| Check | What it is | When it runs | Time |
|---|---|---|---|
| Test suite | more than 1,380 pytest tests: generation, fuzzing, the runtime, the GUI, the protocol with the board, all the widgets, MicroPython/C pixel parity | at each push, in the CI | about 11 minutes |
| Self-test | the real IDE window driven as a person would, through 13 scenarios and 105 steps | at each push, in the CI, on Linux and Windows | about 30 seconds |
| Visual tests | the pages of a project compared pixel by pixel with stored pictures, also after touches | by hand, per project | seconds per page |
| Suites run by hand | every action and context menu, every dialog, the looks, faults, random use, in `tests/manual` | when someone decides to | minutes each |
| Board tests | tests on a real board | only with its owner present | |
| Use by a person | the author, now and then | | |

### Test suite

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

The tests use a temporary configuration folder and never open a real board's port. Boards
are replaced by fakes that answer as `mpremote` or the board's REPL would, and, on Linux, by a
virtual board (`tests/virtual_board.py`): the MicroPython of the runtime behind a
pseudo-terminal, which the IDE's board code reaches with the real `mpremote` and the real raw
REPL. Its flash is a folder of the PC it cannot leave; it counts the soft resets, so a test can
tell whether an operation restarted the board. Tests that need a
built runtime, the Windows cross-compiler or a browser are skipped, and say why, when those
are missing.

Some cheap checks of the looks run here too, in English and in Italian
(`tests/test_window_checks.py`, `tests/test_fit_screen.py`): no shortcut used twice, no menu
with two entries on the same underlined letter, no text cut off and no widgets covering each
other in the main window at 1280×800, the window and the large dialogs no larger than the
screen, and no text, tooltip or menu entry left in English after switching to Italian.

The CI (`.github/workflows/ci.yml`) runs at each push to `main` and on pull requests. On Linux
it runs the whole suite and the self-test; on Windows the parts that depend on the system
(the core, the Windows runtime and packages, the GUI) and the self-test. It does not build
the packages.

### Self-test

```bash
.venv/bin/lvgl-mpy-studio selftest
```

It creates a project, takes widgets from the toolbox, sets properties, types a handler,
saves, starts the simulator and touches the screen; other scenarios cover pages, resolution,
pictures and fonts, Python modules, the Timer and the Buzzer, errors and hardware blocks, the
Files panel and its tabs (open a folder, edit, save, New File and Rename from the panel's
menu), programs without pages (Run Program, typing in the terminal; Linux only), Project
Settings and board profiles (a profile duplicated in the Profile Manager, then used by the
project), and the files of a board (Connect, the board's files in the Files panel, Upload
Files, Run File on Board). The board is one the self-test keeps in memory: it answers what
the window asks, without the serial protocol, which the test suite covers with its own fakes.
See the [manual](manual.md#self-test) for its options and report.

### Visual tests

```bash
lvgl-mpy-studio test project.json
```

The reference pictures live next to the project, in `visual/<width>x<height>/`. The examples
`eim-01` and `weather` have them. See the [manual](manual.md#13-visual-tests).

### Suites run by hand

`tests/manual` holds suites too long for every push. They are skipped unless pytest gets
`--manual`, and the CI never runs them:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/manual --manual
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/manual/test_every_action.py --manual
LMS_PROGRESS=1 QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q -s tests/manual/test_every_action.py --manual   # a line per entry
tools/manual_on_x.sh                         # the self-test and every suite on a real X display
```

| Suite | Time | What it checks |
|---|---|---|
| `test_every_action.py` | about 10 minutes | every menu entry, toolbar button and context menu entry |
| `test_every_shortcut.py` | about 1 minute | every keyboard shortcut, pressed with the focus in each place a person has it |
| `test_every_dialog.py` | about 6 minutes | every dialog, in English and Italian: size, text cut off, Tab, Escape |
| `test_looks.py` | about 1 minute | pictures of the window and its panels against the last accepted ones |
| `test_faults.py` | seconds | the disk full, read-only folders, the runtime killed or hanging, a broken project, a board pulled out |
| `test_random_use.py` | about 1 minute; longer with `LMS_RANDOM_EXAMPLES` | random sequences of what a person does |

What the suites share (the window, its states, the watcher that answers dialogs, the guard
against real boards) is in `tests/manual/sweep.py`; the checks of the looks are in
`tests/looks.py`, also used by the CI.

**Every action.** Every menu entry and toolbar button is triggered as choosing it does, in
five states of the IDE:

- an empty project;
- an example open, with two widgets selected and one change to undo;
- the simulator running;
- a program without pages running;
- a board connected: on Linux the virtual board, reached with the real `mpremote`, so that
  Upload and Run, Stop, Autostart, Upload Files and the rest of the Device menu go through the
  real protocol; elsewhere a fake.

Every dialog it opens is answered by a watcher, once with Cancel and once with OK:

- a file dialog gets a file prepared for it;
- a print dialog prints to a PDF, never to a printer;
- links are not opened.

After each action the suite checks:

- no exception and no Qt warning;
- no dialog left open;
- the window still answers;
- the project is still valid;
- undo brings it back to where it was.

A new menu entry is tested without writing a test for it.

The context menus are swept the same way: those of the canvas (on a widget and on the empty
page), the project tree (a page, a widget, the Python Modules branch, a module), the Files
panel (a program, a text file, a folder, the empty space), the board's files, the terminals
and the code editor. Each menu is opened as a right click opens it, and opened again before
each of its entries, since an entry can change what is under the pointer. Delete… of the Files
panel moves files to a folder of the test, never to the trash of the PC. A menu that does not
open is a problem, unless its widget is disabled, as the canvas is while the simulator runs.

The report is written to `build/manual/every-action/`, one file per state and answer, with
the dialogs each action opened and how long it took. Each run prints what changed since the
last one: entries added or removed, other dialogs, a result that changed. That list is the
place to start when trying the IDE by hand.

The suite never reaches a real board: listing ports finds only the virtual board, and
anything that would run `mpremote` towards another port, or open one, makes the test fail. Three entries are not triggered, and the
suite says why: Exit, which closes the window, and the two Build Executable entries, which
build for minutes in the background and are tested in `tests/test_release.py`.

It checks that nothing breaks, not that the result is right: that is what the test suite
and the self-test are for.

**Every shortcut.** Each shortcut of each enabled action is pressed as keys, with the focus
in the canvas, the project tree, the Files panel, the code editor, a field of the Properties
panel (opened with a click, as a person opens it) and the terminals, with an example open, a
program running and a board connected. Where the focus is not a text, the shortcut must reach
its action; a text field or a terminal may take it on purpose (Ctrl+C copies the text, or
stops the program), which the report notes. An ambiguous shortcut shows as the Qt warning it
causes. The first run found that leaving the field of a property shared by several selected
widgets with different values, without typing, gave all of them the value the field opened
on.

**Every dialog.** The actions and context menus of an example and of a connected board are
triggered again, in English and in Italian, and every dialog they open is looked at before it
is closed with Escape:

- a picture of it goes to `build/manual/every-dialog/<language>/`, to look through by hand;
- it must fit its screen, and need no more than 1024×700;
- no label, button or column of a list may cut its text; no widgets may cover each other or
  stick out; no label may have a contrast below 3:1 on what is behind it;
- Tab must reach every field and stay inside the dialog (in a group of radio buttons, the
  chosen one);
- Escape must close it.

Qt's own file, print and input dialogs are photographed but not checked. The first run found
the Board Profile Manager wider than a small screen, with its columns cutting the names of
the boards and, in Italian, a row of buttons wider than 800 pixels.

**Looks.** The window with an example open, then each panel and tab, in light and dark
theme, English and Italian, at 1024×700 and 1920×1080. The pictures go to
`build/manual/looks/now/`; the reference is `build/manual/looks/accepted/`, kept on the PC
that makes it, since fonts differ between machines. A picture that changed is listed with
its share of changed pixels, as something to look at, and does not fail the test; the first
run, or `LMS_LOOKS_ACCEPT=1`, makes the reference. The checks that need no reference (text
cut off, widgets covering each other, contrast) fail it. The dark theme needs a real display:
offscreen skips it. The first run found the message of the Files panel without a folder cut
in half when the panel is narrow.

**Faults.** Each one through the window, as it would happen to a person: the disk full
during a save (the file on disk and the changes in the window are kept, no temporary file is
left), a read-only project folder (Save, Start and New File… say so), a build folder that
cannot be written, the runtime killed (the project is editable again and Start works), the
runtime hanging (Stop ends it within seconds), the project changed outside (nothing is
overwritten without a choice), broken project files (the open project stays), the board
pulled out during an upload (an error, not a hang).

**On a real display.** `tools/manual_on_x.sh [WIDTHxHEIGHT] [suites]` runs the self-test and
the suites on Xvfb with the xcb platform instead of offscreen, so that real fonts, window
activation and the dark theme are there; nothing appears on the screen of the PC. When a
window manager is installed (openbox, fluxbox, icewm, xfwm4 or metacity) it starts it, and
the sweeps also check that the window gets the focus back after each action.
`LMS_SCREEN_SCALE=2` scales Qt twice, as on a high-resolution screen.

**Random use.** A [hypothesis](https://hypothesis.readthedocs.io) state machine chooses what to
do next, through the window as a person would, with the self-test's driver: a widget from the
toolbox, a click or a drag on the page, arrow keys, a property typed in the panel, Edit and
Arrange entries, undo and redo, pages, the code of a handler, save and open again. After every
step it checks that the canvas shows the widgets of its page, that the Properties panel shows
what is selected, that the `*` of the title says whether there is something to save, that the
project is valid and that nothing raised. At the end, undo all must give the project of the
start, and redo all must give it back.

When a check fails, hypothesis shortens the sequence as far as it can and prints it, with the
state of the last ten steps and a line to replay it; a short sequence becomes an ordinary test.
`LMS_RANDOM_EXAMPLES` (default 25) and `LMS_RANDOM_STEPS` (default 30) make a run longer;
`LMS_RANDOM_TRACE=1` prints the state after every step. On its first runs it found the
Properties panel showing a widget that was not selected, in three ways: after New or Open,
after Cut and Undo, and on another page.

### Board tests

Tests marked `board` run only with `--board PORT`, and only with the owner of the board
present, because they write to it. None is written yet.

## What the automated checks do not see

- **Whether the IDE is clear and pleasant to use.** No check can say it.
- **Whether the IDE looks right.** The suites compare its pictures with the last accepted
  ones and check sizes, cut text and contrast; whether a picture is good is for a person.
- **Real boards.** The board code is tested against fakes and against a virtual board (`tests/virtual_board.py`: the runtime's MicroPython behind a pseudo-terminal, reached by the real `mpremote`, Linux only); touch, speed and the firmware's
  own behaviour are seen only on hardware.
- **The system around the IDE.** The system's own file dialogs, dragging from the file
  manager, a real high-resolution screen: the checks run with Qt's own dialogs, offscreen or
  on Xvfb, where a window manager is used only if one is installed.

How much of the code the checks run, measured on 17 November 2026 with coverage.py: 87 % of
the lines of the user interface (`lvgl_mpy_studio/ui`) and 90 % of the whole package. The
number says less than it seems. The bugs fixed on that day were in lines the tests ran: they
came from order and timing, such as closing a window while a file was still being written to
the board. This is why the suites run by hand drive the IDE through sequences of real
actions rather than calling its functions one at a time.

## Rules for new tests

- A test never touches the settings, recent files or board profiles of whoever runs it, and
  never opens a serial port; `tests/conftest.py` sees to the first and part of the second.
- A test of the user interface should go through what a person uses (an action, a click, a
  key) when it can. A test that calls a method directly does not see how that method is
  reached. Device → Run File on Board… failed from its menu entry while its test, which
  called the method, passed.
- A bug found by a suite run by hand also gets a test in the normal suite, so the CI keeps
  it from coming back.
