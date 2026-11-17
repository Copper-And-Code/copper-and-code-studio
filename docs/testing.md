# How LVGL MPY Studio is tested

Few people have used the IDE so far, so most of the checking is done by machine. This page
says what is checked, by what, how to run it, and what no automated check can see.
[What is verified](status.md) says, area by area, which of these checks it has had.

## The layers

| Check | What it is | When it runs | Time |
|---|---|---|---|
| Test suite | more than 1,380 pytest tests: generation, fuzzing, the runtime, the GUI, the protocol with the board, all the widgets, MicroPython/C pixel parity | at each push, in the CI | about 11 minutes |
| Self-test | the real IDE window driven as a person would, through 9 scenarios and 82 steps | at each push, in the CI, on Linux and Windows | under a minute |
| Visual tests | the pages of a project compared pixel by pixel with stored pictures, also after touches | by hand, per project | seconds per page |
| Suites run by hand | checks too long for every push, in `tests/manual` | when someone decides to | minutes each |
| Board tests | tests on a real board | only with its owner present | |
| Use by a person | the author, now and then | | |

### Test suite

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

The tests use a temporary configuration folder and never open serial ports: boards are
replaced by fakes that answer as `mpremote` or the board's REPL would. Tests that need a
built runtime, the Windows cross-compiler or a browser are skipped, and say why, when those
are missing.

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
pictures and fonts, Python modules, the Timer and the Buzzer, errors and hardware blocks.
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
```

| Suite | Time | What it checks |
|---|---|---|
| `test_every_action.py` | about 8 minutes | every menu entry and toolbar button |

**Every action.** Every menu entry and toolbar button is triggered as choosing it does, in
five states of the IDE:

- an empty project;
- an example open, with two widgets selected and one change to undo;
- the simulator running;
- a program without pages running;
- a fake board connected.

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

The report is written to `build/manual/every-action/`, one file per state and answer, with
the dialogs each action opened and how long it took. Each run prints what changed since the
last one: entries added or removed, other dialogs, a result that changed. That list is the
place to start when trying the IDE by hand.

The suite never reaches a real board: listing ports finds none, and anything that would run
`mpremote` or open a port makes the test fail. Three entries are not triggered, and the
suite says why: Exit, which closes the window, and the two Build Executable entries, which
build for minutes in the background and are tested in `tests/test_release.py`.

It checks that nothing breaks, not that the result is right: that is what the test suite
and the self-test are for.

### Board tests

Tests marked `board` run only with `--board PORT`, and only with the owner of the board
present, because they write to it. None is written yet.

## What the automated checks do not see

- **Whether the IDE is clear and pleasant to use.** No check can say it.
- **How the IDE looks.** The self-test and the suites check behaviour; nothing compares
  pictures of the IDE's own window yet.
- **Real boards.** The board code is tested against fakes; touch, speed and the firmware's
  own behaviour are seen only on hardware.
- **The system around the IDE.** The system's own file dialogs, dragging from the file
  manager, a real high-resolution screen, a window manager: the checks run without a
  display (`QT_QPA_PLATFORM=offscreen`) and with Qt's own dialogs.
- **Context menus** of the canvas, the project tree and the Files panel are not in the
  suite of every action.
- **The Upload Files dialog** is never opened by a test.

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
