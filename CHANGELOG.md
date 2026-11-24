# Changelog

## Unreleased

### Added

- **Five more examples:** the games Frog, Orbit and Sandwich Tower for a 480×480 touch screen, a touch C64 Keyboard that sends the key matrix on a UART, and Forecast, a weather station for the ESP32-4848S040 over WiFi. Each has a README.
- **Settings, the WiFi networks of a board kept once for every app.** The Settings example keeps up to five networks in `cac_settings.json` in the flash; `cac_settings.py` connects to the best one in range, and a `boot.py` does it at power-on. Forecast uses it instead of its own network page. A Display page keeps the brightness in the same file.
- **FTP Server**, an example for the ESP32-4848S040: the files of the flash and of the SD card for a PC on the same WiFi network, with FileZilla, WinSCP, a file manager or `curl`. The network comes from the Settings example, the password stays in `cac_settings.json`.
- **Photo Frame**, an example for the ESP32-4848S040: the photos of `/sd/photos` one after the other in a random order, swiped by hand, with the display off at night (22:00 to 5:30 by default) in Italian time from the network. `convert_photos.py` makes the photos on the PC, cut to the display and dithered to RGB565.
- **Three more games for a 480×480 touch screen:** Block Drop, falling pieces of four blocks that fill rows; Star Guard, a squadron of drones to shoot down before it lands; and Crossword, a new puzzle built on the board each time from a list of words with clues, in English or in Italian, with the language kept in `cac_settings.json`.

### Changed

- **A second upload sends only what changed.** A file that the board already has, with the same size and SHA-256, is copied inside the board instead of through the serial link; the IDE says how many were not sent again. A firmware without `hashlib` gets every file, as before, and so does a board that cannot read one of its files.
- **A first upload is faster too.** The small files of an app, up to 8 kB each, are written by one script for every 16 kB instead of one copy each, which was several exchanges with the board for every file. On the ESP32-4848S040 a project with 30 pictures, 37 files, took 15 s where it took 35, and Weather 10 s where it took 18.
- **The memory budget counts fonts and pictures as a board holds them**, in files of their own, no longer also as text in `ui.py`: for a font of 59 kB the status bar showed 139 kB of RAM and 79 kB of flash more, and now shows 60 kB of each.
- **A warning when the general code uses the name of a handler.** A function or variable of **(General)** named like a handler, such as `button1_clicked`, was replaced by the handler without a word, and a handler that called it called itself. The output now says so at Run, at Upload and in the MCP `validate` tool, with the line.
- **An upload puts the fonts and images of the project in files of their own on the board**, next to the app, instead of base64 text in `ui.py`. After a change to the pages they stay on the board: on the ESP32-4848S040, a project with a font in three sizes and three images took 50 s to upload and 12 s after a change to a text, with 6 kB of 90 kB sent. They also take less RAM: on that board 70 kB of fonts took 103 kB where before they took 196 kB. The warning about the memory of the fonts counts one and a half times their size, plus the largest font once more while it loads. The simulator, **Export MicroPython Code** and live editing still embed them in `ui.py`.

### Fixed

- **Forecast: a swipe left or right changes the place.** It did nothing: a function of the example had the name of the handler generated for the gesture of the page, `forecast_gesture`, so the handler replaced it and called itself. Found on the ESP32-4848S040 with two places set. A test now checks that no example defines a function twice.

## 0.8.0 — 2026-11-20

Renamed from LVGL MPY Studio to Copper and Code Studio. Settings, the configuration folder and projects are kept, and the old commands still work. The Windows package is that of 0.7.1, under the old name.

### Changed

- **Renamed from LVGL MPY Studio to Copper and Code Studio**, a visual GUI builder for MicroPython and LVGL. The old name began with the name of somebody else's project. A user has nothing to do: settings and projects are kept, and the old command still works.
- **New names for the command, the packages and the settings.** The command is `copper-and-code-studio` (`lvgl-mpy-studio` and `lvgl-ide` still work), the packages are `Copper_and_Code_Studio-x86_64.AppImage` and `Copper_and_Code_Studio-<version>-Setup-win64.exe`, and the MCP server calls itself `copper-and-code-studio`. Settings and the configuration folder are copied once from the old name. The Windows installer upgrades an installation of LVGL MPY Studio.
- **The lines the IDE reads back from a board begin with `LMS_`**, as everything else it puts on a board, instead of `LVGL_MPY_STUDIO_`; so do the environment variables `LMS_TOOLCHAIN` and `LMS_MPREMOTE` (the old names are still read) and the include guards of the exported C headers. [The new name](https://copper-and-code.github.io/copper-and-code-studio/renamed/) lists every change.

### Fixed

- **The self-test no longer fails at random at Upload Files.** Its watcher of dialogs took the Upload Files dialog for an unexpected one when the dialog it opens, to choose a folder, had just closed: on a slow computer, as in the CI, the step failed now and then. The self-test of the 0.7.2 package has this fault.

## 0.7.2 — 2026-11-18

Board definitions from a file, and fixes found by new automated tests of the user interface: a property of several widgets changed by looking at it, a crash dragging a tab of the Output panel, a simulator crash with a timer in the general code, large projects that did not start, files of the Files panel half written after a failed save, and more. The Windows package is that of 0.7.1.

### Added

- **Videos** of the IDE building and running `eim-01`, `weather` and `snake`, on a new page of the website, and a short one at the top of the README. They are made by `tools/showreel`, which drives the real IDE offscreen through a storyboard (`examples/<name>/showreel.toml`) with comic-style balloons; they say they are a scripted replay, sped up.
- **A virtual board for the tests** (`tests/virtual_board.py`): the MicroPython of the runtime behind a pseudo-terminal, with its flash in a folder it cannot leave. The IDE's board code talks to it with the real `mpremote`: connect, file operations, Upload and Run of an example, Cancel and a cable pulled during a copy. It counts soft resets, and catches the reset that copying files used to cause.
- **Four scenarios of the self-test** (now 13 scenarios, 105 steps): the Files panel and its tabs; programs without pages and their terminal (Linux); Project Settings and board profiles; the files of a board with Upload Files and Run File on Board, on a board the self-test keeps in memory, so no real board is touched.
- **Random use** (`tests/manual/test_random_use.py`): random sequences of what a person does in the window, checked after every step, shortened to the fewest steps when a check fails.
- **Suites run by hand** (`tests/manual`, `pytest --manual`), for checks too long for every push. The first triggers every menu entry and toolbar button in five states of the IDE, answering every dialog with Cancel and with OK, and checks that nothing breaks. See [How it is tested](docs/testing.md), a new page of the documentation.
- **More suites run by hand**: every keyboard shortcut pressed with the focus in each place a person has it; the language changed in each state; the window at five sizes and its docks floated, closed and restored; a long session that must not grow; every property of every widget changed through the Properties panel; every example started and touched in the simulator; random events anywhere in the window; the canvas under the mouse (drops, moves at three zooms, every handle, selection); typing in the code editor; what is saved opened again and compared; hard texts (long, quoted, foreign, emoji) in every text property; files and text dropped from outside; programs printing without pause into every console; a large project timed; an agent working through MCP while the window has the project open; the IDE killed while it saves; the IDE used with the keyboard only; `tools/mutation_probe.py`, which shows where the tests are blind, and tests where it found them; redo after undo for every action; every entry of every context menu (canvas, project tree, Files panel, files of the board, terminals, code editor) in the same five states; every dialog in English and Italian, photographed and checked for size, text cut off, Tab and Escape; pictures of the window and its panels in light and dark theme against the last accepted ones; faults such as a full disk, a read-only folder, the runtime killed or hanging and a board pulled out during an upload. `tools/manual_on_x.sh` runs them, and the self-test, on a real X display.
- **Checks of the main window in the CI**, in English and Italian: no shortcut used twice, no menu with two entries on the same underlined letter, no text cut off at 1280×800, no window or large dialog bigger than the screen, and nothing left in English after switching to Italian.

- **Boards from a file.** A board the IDE does not ship is added from a `.json` board definition, with no change to the IDE: **Import…** and **Export…** in the Board Profile Manager, `lvgl-mpy-studio board list|import|export|delete`, and the MCP tools `import_board` and `delete_board`. A board can name an adapter the IDE has no code for; it then needs what its profile lists. A project whose board was deleted keeps its copy and opens with a notice. See [Board definitions from a file](docs/boards.md#board-definitions-from-a-file).

### Fixed

- **Windows fit the screen.** The main window opened at 1400×900 and the Board Profile Manager at 1050×600 whatever the screen, so on a small laptop their edges and buttons were out of sight; they now open no larger than the screen has room for, as do the Block Manager and Upload Files. The Board Profile Manager shows the whole name and adapter of each board, and puts its buttons on two rows, which in Italian needed more than 800 pixels on one. Found by the new suite of every dialog.
- **The Files panel without a folder shows its whole message** when the panel is narrow: it had one line for two, cut in half. Found by the new suite of the looks.
- **A property shared by several selected widgets is not changed by looking at it.** With two widgets at different positions selected, the x cell is empty; clicking it opened a field on 0, and leaving the field without typing moved both widgets to 0. A field left as it opened now changes nothing; typing a value still gives it to all. Found by the new suite of every shortcut.
- **A screen reader can name every list and field of the window.** The toolbox, the project tree, the files of the PC and of the board, the Properties panel and its order, the Components, the Output, the Errors, the code editor and its lists, and the terminals had no name, so a screen reader said only "list" or "text". They are named, in the language of the IDE. Found by the new keyboard suite.
- **A file saved from a tab of the Files panel is never left half written.** Save emptied the file, then wrote it: a full disk, a crash or a power cut in between left the program empty or cut. It is now written to a copy next to it, which then replaces it, keeping its permissions.
- **A large project starts in the simulator.** A project of 30 pages and about 2000 widgets did not start: mpy-cross said `MemoryError` on its 838 KB `ui.py`, then the simulator ran out of its 2 MB heap. mpy-cross now gets 64 MB, and projects with pages the same 32 MB heap as programs without pages, about the RAM of the STM32H7_CORE. Found by the new suite of a large project.
- **A timer or a style created in the general code works in the simulator.** The general code ran before LVGL was initialised there, so `lv.timer_create` at start-up crashed the simulator, while on a board it works. LVGL is now initialised first, as on a board.
- **The Device Console keeps up with a board that prints without pause.** Each few bytes the board printed queued a message for the window, which stopped answering and went on showing old output long after Ctrl-C. The output now reaches the window in bounded pieces; if the board prints faster than the console can show, the oldest is left out and a grey line says how much.
- **The terminals take a tenth of the memory.** A full history of 10,000 lines took over 100 MB; equal characters are now shared.
- **No more crash when dragging a tab of the Output panel.** Qt 6.11 and 6.12 leave on the screen an old tab bar of a group of docks when a second group is made: at the start the IDE showed "Output | Errors" twice, once over the Output panel, and dragging a tab of that old bar crashed the IDE. The old bar is now hidden. Found by the monkey suite, run for hours by `tools/monkey_night.sh`.
- **Names MicroPython cannot take are refused.** A widget or a page could get a name of hundreds of letters; MicroPython refuses names over 255 characters, so the project no longer compiled. Names of widgets and pages are now limited to 200 characters, with a message. Found by the new suite of hard texts.
- **A thin widget keeps its size when moved or pulled sideways.** A widget under 8 pixels, such as a line 5 pixels high, is drawn 8 pixels high so that the mouse can grab it; moving it with the mouse wrote those 8 pixels into the project, and so did a handle pulled sideways. Found by the new suite of the canvas.
- **Add Page no longer makes a page with the name of another.** It named the new page after the number of pages, so after a deletion it could make a second `page3`, and the project could no longer be validated or started. It now takes the first free name. Found by the new monkey suite.
- **Stop no longer prints a traceback in the Output.** Stopping the simulator interrupts the app as Ctrl-C does on a board, and its `KeyboardInterrupt` showed as a Python error each time. It is now left out; what the app printed is kept. A program without pages still shows it in its terminal, as a board does.
- **Opening a project no longer keeps the pages of the last one in memory.** Their designers were taken out of the tabs but not deleted, with their scenes and items: about 1.7 MB for each project opened in a session. Found by the new soak suite.
- **Save, Cancel, Close and the other standard buttons are in Italian** when the IDE is: Qt's own translation, which PySide carries, was not loaded. Found by the new check of the dialogs in Italian.
- **Changing the language keeps what the IDE wrote since.** A label the IDE changes, such as the folder of the Files panel, went back to the text it had at the first change of language: open a folder, switch to Italian, open another, switch back, and the panel named the first. The tooltips of the resolution menu and of the Ctrl-C and Ctrl-D buttons of the Device Console stayed in English. Found by a new check of the visible texts.

- `eim-01` and `eim-01-480` asked for font sizes their boards do not have (193 and 194 labels), so the Output panel filled with warnings at each Start. They now ask for the size that was drawn anyway, so they look the same; a test checks that no example has such warnings. The visual baselines of `eim-01` were still those before the em dash fix of 0.7.1, and are updated.
- **Files copied to the board no longer restart it.** Uploading files, or saving a file of the board, went through `mpremote fs cp` without `resume`, so the board was soft-reset before each file and an app running there stopped while the IDE still showed it as active. Large files also had a fixed 30 s limit: the limit now grows with the size, and Cancel stops the copy.
- **A file of the board is closed only when the board has it.** Saving a `[board]` tab writes it in the background; closing the tab or the window right after Save could lose the changes. The tab and the window now close when the write is done, and stay open with the changes if it fails. What is typed while the file is being written stays marked as unsaved.
- **The Properties panel shows only what is selected on the page in front.** It kept showing, and editing, a widget that was not selected: after File → New or Open, when a project with a widget of the same name was opened; after the widget was cut or deleted and brought back by Undo; and on another page, where the widget was not. Found by the new random use suite.
- **Run → Stop stops a program without pages while the target is a board.** The program runs in the simulator whatever the target, but Stop was disabled and would have stopped the board: the program could not be stopped. Found by the suite of every action, on the virtual board.
- **The console of the board opens after Device → Connect.** It stayed “Console not available” until another operation on the board ended. Found by the new board scenario of the self-test.
- **Device → Run File on Board…** failed at once when chosen from the menu, without asking which file: the menu passed its checked state where the file was expected. Found by the new suite of every action.
- **Run on the Board uploads a program, not whatever folder it is in.** For `~/test.py` it walked the whole home folder on the window's thread and queued every file for the board. A folder with more than 2000 files or 64 MB is now refused at once, as the simulator already did by size; hidden folders, caches and version control are not walked. A path with a space or a parenthesis, such as `my project/main.py`, now runs on the board instead of being typed at its prompt as Python.
- **Open tabs follow a rename in the Files panel.** After renaming a file, or a folder above it, Save wrote the old file again next to the new one. Deleting closes the tabs of the deleted files that have nothing unsaved. A rename or a new file that the system refuses shows why, instead of an error in the log.
- **A folder under a hidden one shows its files.** Open Folder, or Run Program, in `~/.config/x` or `~/.local/share/x` showed the whole filesystem, and New, Rename and Delete acted there.
- **`machine.reset()` in a program keeps its flash, as on a board.** The simulator started the program again by copying its folder over the flash, so a file the program had written was put back as shipped.
- **Text from a program is not broken in the terminal.** A character of more than one byte cut between two reads of the simulator's output showed as two `�`.
- **A board whose files cannot be read is not asked again and again.** If listing the board failed, or the board had no files, the Files panel asked again after each answer, without end, stopping the console every time. It now asks once per connection; Refresh asks again.

## 0.7.1 — 2026-11-15

Fixes to the examples and to the C export, the System Monitor example, and documentation for the PC, Chromebooks and the IDE in the browser. The release also carries the two files the IDE in the browser downloads.

### Added

- **System Monitor** (`examples/sysmon`), the seventh demo of the website: CPU, memory and disk from `/proc`, a chart, and the busiest processes from `ps` through `os.system`; on a board or in the browser it shows what MicroPython knows there. Its gallery entry carries a prompt for an agent, written afterwards and marked as such.
- **Documentation:** [files, commands and the network on the PC](docs/pc-programs.md), what MicroPython can do in the simulator and the executables; [running on a Chromebook](docs/chromebook.md); the IDE in the browser, work in progress, in the README and on the website; [the files for the IDE in the browser](https://github.com/Copper-And-Code/lvgl-mpy-studio/blob/main/docs/packaging.md) in a release.

### Changed

- Python 3.12 or later is required to run from the sources: with Python 3.11, PySide6 6.12.0 crashed in the self-test. The documentation states that the AppImage needs glibc 2.38 or later, that is Ubuntu 24.04, Debian 13, Fedora 39, Linux Mint 22 or newer.

### Fixed

- The examples `eim-01`, `eim-01-480` and `weather` start in the simulator: they carried the board as run target from the session that uploaded them, so Start asked for a serial port, in the browser IDE too. Three labels of `eim-01` showed an empty box in place of an em dash, which the built-in font does not have. A test checks both for every example.
- The C export builds with GCC of Ubuntu 26.04: its Makefile, and the script of the Windows C library, compiled the LVGL sources with `-Werror`, and that GCC warns about `lv_sprintf_builtin.c`. `-Werror` now applies to the generated code only.

## 0.7.0 — 2026-11-14

The Files panel, programs without pages in the simulator, in the browser and on the board, and contract 1 of the boards' display driver.

### Added

- **Files panel and file tabs**, as in Thonny: the folder of a program next to the project tree, and its files in tabs of their own with the editor of the Code tab (completion of `lv.`, syntax check with mpy-cross while typing). Ctrl+S saves the current file; a file changed on disk is reloaded, or the tab asks; Run Program and Run in the Browser save the folder's files first; new, rename and move to the trash from the panel. The panel also shows the connected board, as Thonny does: its files open in tabs marked `[board]` and are saved back with the safe write of Upload Files; download, upload, new folder, rename, delete (never `/`, `/flash`, `/sd`) and run on the board from the menu. **Run → Run on the Board…**, also in the panel's menu of a `.py` file, uploads the program's folder and runs the file there in one step, as Run Program does in the simulator. While the panel reads the board, an operation asked by the user waits for it instead of being refused. The window layout of earlier versions is reset once, to place the panel.

- **Programs without pages in the browser.** The site has a sixth demo, the shell of `examples/shell` with its editors, running in WebAssembly as an STM32H7_CORE at 1024×600: the keyboard of the page is its serial port and its files live in the browser's memory. `build_program_web` builds such a page; the site builder knows the demo kind `program`. No change to the WebAssembly runtime: the program gets through `sys.modules` a `sys`, `time`, `select`, `micropython` and `machine` that wait by serving LVGL and letting the browser run, and `print` reaches `os.dupterm`. In the browser LVGL runs only while the program waits, and native code is not available: `ansiterm.py` draws with `framebuf` there, identical byte for byte to its viper functions, which it still uses on boards.

- **Device → Upload Files…** copies files or folders of the PC to a folder of the board, outside any project, binaries included: each file is written under a temporary name and renamed, nothing else on the board changes, the space is checked first, and Python files can become bytecode. **Device → Run File on Board…** starts a file of the board from its prompt, so that it reads its keys from the Device Console.

- **Programs without pages in the simulator** (Linux). **Run → Run Program…** runs a MicroPython file and its folder as a board would: a flash of its own that keeps the files the program writes, `/` limited to that flash, a terminal under the screen as the serial port, LVGL served in the background while the program waits for a key, `os.dupterm`, `os.uname()` and `machine.reset()`, and a REPL when the program ends. The Linux-like shell of `mpy-lvgl-boards`, with its two editors, runs this way. Projects with pages start as before.

### Changed

- **The display driver of programs follows contract 1 of the boards** (firmware v0.1.7 of mpy-lvgl-boards). It has `CONTRACT`, `running()`, `backlight()` and `PERIOD_MS`. A Ctrl-C reaches the program and the screen goes on, in the simulator and in the browser. Before, the driver had a "stopped by Ctrl-C" path that stopped the screen. `_task`, `_timer` and `_arm()` stay for one version. `examples/shell` has the fixes of the same work: a Ctrl-C after a command has ended no longer leaves the shell, and one during a long `cat` no longer turns off the terminal on the display.
- **An upload asks first when a folder would hide a module.** MicroPython's `import shell` finds a folder `shell/` before `shell.py`. Upload Files, Run on the Board and the Files panel now name the folder and the module, and wait for a yes. This happened with the shell on an ESP32-S3.
- **A new project is for the STM32H7_CORE V1.3, 1024×600**, and runs in the simulator, unless other defaults were saved with **Use as default for new projects**. It was 800×480 without a board. Programs without pages always run as that board.
- **The screen of the simulator grows only by whole multiples** (×1, ×2…) and shrinks smoothly: at 1.4 times some rows of pixels were doubled and others not, and small bitmap fonts were hard to read.
- **The Device Console is a terminal.** Every key goes to the board as it is typed, as in PuTTY or picocom: arrows, Tab, Home and End, the Ctrl keys, the history of the prompt. It shows the colours and the cursor movements of ANSI sequences, so a full-screen program on the board, such as an editor, works in it. It follows the board whenever it is connected and the IDE is not using it, not only while an app runs. Copy and paste are on Ctrl+Shift+C and Ctrl+Shift+V, because Ctrl+C goes to the board; Ctrl-C and Ctrl-D also have buttons. The IDE's own messages are grey.
- The console opens the serial port itself, as mpremote opens it, instead of running `mpremote repl`. On Windows `mpremote repl` reads the keyboard of a console window that the IDE does not have, so nothing typed could have reached the board.

## 0.6.1 — 2026-11-12

The first release with packages: an AppImage for Linux and a portable package for Windows.

### Added

- **Project website** with the English documentation and five demos that run in the browser: Fifteen, Weather, Breakout, Simon and EIM-01.
- **One engine, four places it runs**, in `docs/stack.md`: the board, the simulator, the executables and the browser version run the same compiled MicroPython and LVGL, so upstream fixes reach all of them.
- **`docs/packaging.md`**: how to build the packages, in which order, and what to check before handing one out.

### Fixed

- The self-test accepts a relative `--output` folder: the projects are saved through the file dialog, which read a relative path from its own folder.
- The page of a game exported for the browser declares English as its language.
- The recorded MCP session is checked again against its own result, `examples/weather/mcp-result.json`. The Weather example had been reworked for the website, with icons and a new layout, and no longer matched; the pages now say which version is which.
- The tests import `tools/build_site.py` also when started as `pytest`, as continuous integration does.

## 0.6.0 — 2026-11-12

### Added

- **Hardware blocks.** Two new components under **Hardware** in the toolbox: **Digital Output** (a pin on or off: LED, relay) and **Digital Input** (a pin that is read, with debounce and the events PRESSED, RELEASED and CHANGED). The pin is typed as a number or as a name such as `PA5`. They work in the simulator, where the output writes its changes in the Output panel and the input is set from code with `simulate()`. Both were tried on the STM32H7_CORE board, with its two LEDs and its two keys.
- **Blocks from other people.** **Settings → Manage Blocks…** lists the blocks with their origin, author and licence, adds one from a folder, removes it, reloads them and opens the blocks folder; the toolbox follows at once. A project keeps a copy of such blocks, so it opens on a computer that lacks them; a project that uses blocks is saved as version 4, which earlier IDEs refuse instead of misreading. The module a block provides for the simulator runs on the PC, like the code of a project: use blocks from people you trust.
- **Pages for whoever evaluates the project**: the stack from the display controller to the agent, how the project was built and by whom, what is verified and how, and a case study. The README is now a front page; its reference material moved to `docs/development.md`.
- **`examples/eim-01`**: an industrial monitor of 5 pages and 256 widgets with simulated data, built by an AI agent through the MCP server, with a 480×480 version and visual tests.
- **Help → Online Documentation** (F1) opens the pages of the project, `https://copper-and-code.github.io/lvgl-mpy-studio/`; the address is also in the About window. The English documentation and five playable browser demos are published on GitHub Pages.
- **Writing a block.** `docs/blocks.md` builds one step by step, and `examples/blocks/blinker` is the finished example, ready to install.
- MCP: `list_blocks` describes the blocks with their properties, methods and events; `project_info` says which blocks the project uses.
- The self-test has a ninth scenario for the blocks, and now fails a step when the IDE raises an error that it would otherwise only print.

### Changed

- The launcher of single-file executables no longer carries the old name: its modules are `lms_boot` and `lms_licenses`, its marker is `LMSAPP01`, and the Windows runtimes describe themselves as LVGL MPY Studio. Games already built keep working, because each carries its own launcher.
- **Blocks, first step** (see `docs/plugins-plan.md`). The Buzzer is no longer written inside the IDE: it is a block, a folder with a description and its MicroPython modules, read by the new `core/blocks.py`. Nothing changes for projects and for the generated files, which are the same byte for byte. Blocks copied into the `blocks` folder of the settings are read and checked, but not offered yet.

## 0.5.1 — 2026-11-12

### Added

- **Self-test.** `lvgl-mpy-studio selftest` uses the IDE as a person would — toolbox, page, Properties panel, code editor, Save As, simulator and touch — and writes a report with `PASSED` or `FAILED` for each step, with pictures of what failed. `--show` shows the IDE at work. Eight scenarios: the full tour, save and open again, pages, resolution, pictures and fonts, Python modules, Timer and Buzzer, and errors.
- **Print Sources.** **File → Print Sources…** (Ctrl+P) prints the source open in the editor or all the sources of the project, with line numbers, the colours of the editor, wrapped long lines, and a header and footer on each page. It has a preview, and a PDF comes from the system print dialog.

### Changed

- **Upload progress.** Sending an application to a board opens a small window with a bar that follows the bytes sent, the file being written, the time elapsed and an estimate of the time left, and a Cancel button. On boards reached through mpremote the bar moves inside a file by estimate, from the speed of the last upload to that board. It appears when the upload lasts more than a moment. Until now the only sign was a file count in the status bar, which stood still for most of a long upload.
- Changing the resolution, or the board of the project, fits the page to the window again, as **View → Fit to Window** does. Each page is fitted when it is shown; other changes keep the zoom.

### Fixed

- A widget chosen with a double click in the toolbox was placed twice in a project with several pages: once where you clicked, and again at the first click on another page. Found by the self-test.
- On Windows, started from `LVGL_MPY_STUDIO.exe`, a console window flashed four times at almost every operation: the IDE compiles four files with `mpy-cross` and each run opened its own window. The compiler, the C toolchain and `mpremote` are now started without a window. It had been so since the first Windows package.
- On Windows, closing the IDE or ending a command while the RAM measurement or a page preview was running left a simulator process alive for some seconds and printed an error, because its temporary folder could not be removed. Such processes are now stopped first. Found by running the self-test on Windows 11.
- The warning about fonts and free RAM appeared by mistake from the second upload on: the memory was read while the previous application was still running. It is now read after the reset, with the display driver loaded.
- When the application did not start after an upload, the warnings found before were lost; they are now shown with the error, in the IDE, on the command line and through MCP.
- The portable Windows package did not start on Windows: it carried a copy of ICU 72 next to Qt, which hid the `icuuc.dll` of the system and lacks the functions Qt asks for. The package no longer includes ICU; the package of 0.6.0 starts on a real Windows. Wine did not show the fault, because it starts a program even when imported functions are missing.
- The Windows packages had no icon: the program file, the taskbar and the windows showed a generic one. The windows have the icon on Linux too.

## 0.5.0 — not released

### Added

- **Images.** A picture chosen for an Image widget is converted to PNG, made no larger than the screen and stored inside the project file. It is drawn in the simulator, on boards, in executables, in the browser version and in the C export. MCP tools `add_image` and `remove_image`; `project_info` lists the images. Pictures that cost much memory, and image widgets whose picture is missing, are reported as warnings. Until now a chosen file path was written into the generated code and never drawn, and a project with assets could not be uploaded to a board.
- **Fonts.** A TrueType or OpenType file chosen for the `font` property is stored in the project and converted to LVGL's format for each size in use, by a converter written for the IDE on top of Qt: no Node.js or other tool is needed. Compared with LVGL's built-in Montserrat, made by the official converter from the same file, the metrics are the same and fewer than two pixels in a thousand differ, by one level of sixteen. Kerning is converted too, with the same values wherever the built-in font has it. On upload a warning says when the fonts would take more than half the free RAM of the board. MCP tools `add_font` and `remove_font`. The C export includes them too, loaded from memory, which needs `LV_USE_FS_MEMFS`.
- **From a prompt to an app.** `examples/weather` is a weather station built by an AI agent through the MCP server, with the recorded session of its 24 tool calls; `docs/mcp-demo.md` describes it and a test replays it.
- MCP: `list_widget_types` takes `names_only` and `types` and returns the default values; `list_boards` returns the font sizes of each board.
- A font size the target lacks and characters outside the built-in font are reported as warnings, by the MCP tools and when generating.

### Changed

- **Shorter names on the board and in generated files.** Applications are installed under `/lms_apps` instead of `/lvgl_ide_apps`; the generated modules are `lms_buzzer` and `lms_probe`; the web page loads `lms_web.js`; the markers in exported C are `lms:new-handlers`. An autostart installed by 0.4 is still recognised, and C files exported by 0.4 keep working with their markers. Applications already on a board under the old folder are left there: remove the folder by hand. Module names starting with `lms_` are reserved.
- The ESP32-4848S040 and Waveshare RP2350 profiles list the Montserrat sizes read from the real boards: 14, 16, 24, 32 and 40.
- A new project is named “Untitled”.
- MCP answers are compact JSON instead of indented: an agent reads about half the characters.
- **The product is now LVGL MPY Studio.** The command is `lvgl-mpy-studio` (`lvgl-ide` still works), the Python package is `lvgl_mpy_studio`, and the packages are named `LVGL_MPY_STUDIO-…`. Settings and the `~/.config/lvgl-ide` folder of earlier versions are copied on first start.
- English is the language of the code: interface texts, comments, messages, examples and documents. The Italian interface is unchanged and the Italian documents remain next to the new English manual and web publishing guide.
- Three English interface texts changed: the F5 action is **Start**, the toolbar is **Run toolbar** and a custom board profile is **Custom profile**.
- The examples are `examples/<game>/project.json`, with English names and comments; `tris` is now `tictactoe`.
- The IDE, the command line and the MCP server start in English. Italian is still available under **Settings → Language** and with `--language it`.
- Deleting a container deletes the widgets inside it. Copy, cut and duplicate take them too, and they keep their place inside the copy.
- `lvgl-mpy-studio build` writes to `dist/` next to the project, as the IDE does, when `--output` is not given.
- App packages no longer contain `project.json`.
- A handler set on a page without an event is `SCREEN_LOADED`. An event the object does not have is refused.
- The MCP tool `remove_widget` returns the names of everything it removed.
- The IDE package is 4.7 MB smaller: it ships only the names the code editor completes instead of the whole binding API.
- The Simulator panel no longer has an unused path for running the C build.

### Fixed

- Choosing a picture that is still above 512 kB once converted to PNG raised an error inside the undo step instead of showing a message.
- The free space of an STM32H7 board was reported as zero: it was read from the root instead of the filesystem apps are written to.
- Text in sizes 32 and 40 was drawn at 24 in the simulator and on boards, although the runtime has those fonts. The sizes now come from the target: a board profile can list them in `fonts`, the upload reads them from the board, and a project without a board uses the five sizes of the simulator. The STM32H7_CORE profile lists the five its firmware has.
- The order of the widget declarations in the exported `ui.c` changed from one export to the next.
- Deleting a container left its children on the page at the wrong position.
- Widgets inside a container were checked against the screen with coordinates relative to the container, so `outOfBounds` and the "outside the screen" notice were wrong for them.
- The simulator always started from the first page, while boards started from the initial page of the project.
- `simulate` and visual scenarios could not read a widget the project code never names (`ui.<name>` raised `AttributeError`).
- About eighty error messages reached agents and the command line in Italian whatever the language.
- An unexpected error could end the MCP server.
- After an unexpected error during an upload, every later upload answered `device.session.busy`.
- A traceback of the app on the board containing words such as "resource" or "not found" was reported as a busy or missing serial port.
- A board profile without minimum firmware versions raised an error when the board answered.
- A broken custom board profile file stopped the IDE from starting.
- A simulated wait could block for a very long time when the app stopped answering.
- Uploads over UART are about 4.5 times faster: measured on the STM32H7 board, 100 kB take 22 s.

## 0.4.0 — 2026-11-10

### Added

- **Python modules.** A project can hold its own `.py` modules, which handlers, the general code and other modules import by name (`import utils`).
  - The project tree has a **Python Modules** node. Its context menu offers New, Open, Rename and Delete, and a double click opens a module.
  - Modules are edited in the existing code editor, with undo and redo, highlighting, completion and syntax checks.
  - Module names cannot be paths, MicroPython modules, files the IDE generates or handler names.
  - A module created in the editor starts with `import lvgl as lv` and `import ui`, and a hint explains why they are needed.
  - **What do you want to do?** lists each module like a component: import it, call its public functions, classes and upper-case constants. The open module shows its own functions.
- **Modules in every pipeline.** Modules are included in the simulator, the upload to boards (as bytecode, with precompilation) and the MicroPython export for a board. They are also included in Debug and Release folder builds, in the single-file executables for Linux and Windows, and in the browser version.
  - The generated folder has a `manifest.json` with the ordered list of modules. Every build takes its modules from it, and stops with a clear error if it is missing or inconsistent.
  - A module that was removed or renamed is deleted from the generated folder, together with its bytecode.
  - The C export warns that Python modules are not part of it.
- **MCP tools for modules.** The new tools are `list_modules`, `create_module`, `rename_module` and `delete_module`; `get_code` and `patch_code` take `module` as an alternative to `handler`. `project_info` lists the modules. Existing tools keep their arguments and answers.
- **Project revisions.**
  - `project_info`, `get_code` and `list_modules` return a SHA-256 revision of the project file.
  - Every MCP tool that writes the project accepts `expected_revision` and returns the revision it wrote. A file changed in the meantime is reported as a structured `revision_conflict` error, and nothing is written.
- **Changes made outside the IDE.**
  - Before saving, the IDE checks that the file on disk is still the one it opened or last saved, for example when an MCP agent or the command line wrote it meanwhile. If the file changed, the IDE asks whether to reload it, save a copy, overwrite it or cancel; Cancel is the default. A deleted file can be recreated or saved elsewhere.
  - **Save As** asks before replacing another file.
- **Single-file executable for Windows.** **Run → Build Single-File Executable…** now works on Windows too. The `--for windows` and `--for linux` options build for the other system. A Linux game built on Windows comes as a `.tar.gz`, to keep its execute permission.
- **Games in the browser.** **Run → Open in Browser**, `lvgl-mpy-studio build --web` and `lvgl-mpy-studio web` build a folder with the page, a WebAssembly runtime of MicroPython and LVGL, and the compiled game, ready for a static host. The folder includes an `.htaccess` for Apache and LiteSpeed hosts. The runtime is built by `runtime/build_web.sh`. A publishing guide is available in Italian.
- **Italian user manual,** `docs/manual.it.md`.
- **Project schema 3** for projects with modules. Projects without modules are still written as schema 2, byte for byte.

### Changed

- **Errors in modules.**
  - A syntax error names the module and its line, and is never reported on the handler that imports the module.
  - In a runtime traceback, the line where the error happened comes first in the Errors panel. The handler that led there is marked "called from here".
  - Double-clicking a row opens the module or handler at that line and highlights it.
- **Confirmations before risky module changes.** Renaming or deleting a module that code still imports asks first, with a warning that the old imports will stop with `ImportError`. Imports are never rewritten.
- **Read-only code while running.** While the simulator runs, a bar above the code editor explains why the code is read-only and offers **Stop and Edit**.
- **Resolution sizes.**
  - The resolution menu lists the common sizes 240×240, 480×480, 1024×600 and 1024×1024, even when a board has the same size.
  - Project settings list the common sizes and those of the known boards.

### Fixed

- Runtime errors in the simulator did not appear in the Errors panel. The simulator prints tracebacks on standard output, while the IDE read only standard error. This also affected handler errors in 0.3.
- **Custom…** in the resolution menu raised an error and did nothing.
- The **Change Port**, **Manage Board Profiles**, **Use as Default** and **Remove Default** entries of the destination menu did nothing.
- Boards whose firmware starts a MicroPython shell that needs a second Ctrl+C, such as some ESP32-4848S040 builds, failed every operation with `could not enter raw repl`. The IDE now sends repeated Ctrl+C when it connects, and retries once after that error.

### Known limitations

- **Modules.**
  - Renaming or deleting a module does not update the code that imports it; the IDE warns and lists those places.
  - Modules created through MCP start empty, without the imports the editor adds.
  - The C export does not include Python modules.
  - Projects with modules (schema 3) cannot be opened by 0.3, which refuses them clearly.
- **External changes.**
  - There is no file watcher: the IDE notices a change only when it saves.
  - The revision check is not a lock: a program writing at the very moment of the save can still be overwritten. The same applies to `expected_revision` over MCP.
- **Simulator.** The code is read-only while the simulator runs.
- **Browser version.** It has been checked in Chromium only.
- **Documentation.** The user manual and the web publishing guide are available in Italian only.
