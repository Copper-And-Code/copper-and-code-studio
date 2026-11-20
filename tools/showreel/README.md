# Showreel

A video of the real IDE building an example and running it, with comic-style balloons that say
what happens. The videos of the [Videos page](https://copper-and-code.github.io/copper-and-code-studio/videos/)
and the GIF at the top of the README are made with it.

```bash
.venv/bin/python -m tools.showreel examples/eim-01
# build/showreel/eim-01/: eim-01.mp4, eim-01.webm, eim-01.gif, eim-01-poster.png
```

It needs the simulator runtime (as the IDE does) and the `ffmpeg` program. Linux only.

## What it does

The tool opens the IDE offscreen (`QT_QPA_PLATFORM=offscreen`), with a temporary configuration
folder, and saves the example with empty pages under `/tmp/showreel/<example>/`. Then it plays
the storyboard of the example: it adds the widgets, changes properties, creates handlers from the
Events tab and types their code, presses Start and touches the simulator screen. After each
step it grabs the window and draws the balloon, the highlight and the cursor on the picture.

- **Design steps** wait until the canvas shows the real LVGL rendering, then hold the picture:
  the video does not depend on the speed of the computer.
- **Run steps** grab the window 25 times a second while the app runs, in real time.
- Every frame of the design part carries the caption "Scripted replay, sped up", and so does
  the end card: the videos are a reconstruction, not a recording of a person.
- The project is rebuilt through the IDE's own paths (the undo stack, the Events tab, the code
  editor), so at Start it is the example again, apart from what the storyboard changed on purpose.

`ide.py` is the only module that touches the IDE; if the IDE changes, it is the file to fix.
`tests/test_showreel.py` replays a short storyboard of `weather` in CI.

## Options

| Option | |
|---|---|
| `--storyboard FILE` | Another storyboard than `<example>/showreel.toml`. |
| `--name NAME` | Base name of the files, and of the output folder `build/showreel/NAME`. |
| `--out FOLDER` | Output folder. |
| `--only design` / `--only run` | Stop before Start; or build the project at once and record only the run. |
| `--no-webm` | Skip the WebM, the slowest to encode. |
| `--keep-frames` | Keep the PNG frames in `frames/`. |
| `--print-storyboard` | Print the storyboard as TOML, the default one if the example has none, and stop. |

## The storyboard

`examples/<name>/showreel.toml`. Without it the tool makes a default one: title, a new project,
three widgets dragged from the Toolbox, the rest of the first page, a handler typed, the other
pages, Start, four seconds of the run, end card. `--print-storyboard` writes it out to start from.

```toml
[video]
title = "Weather"
subtitle = "Built and run in Copper and Code Studio"
window = [1600, 1000]
fps = 25
gif = { from = "start", seconds = 12, fps = 12, width = 960 }   # the cut for the GIF
poster = "start"                    # a step name or a second; the poster is one second later

[[step]]
do = "code"
handler = "refresh_clicked"
balloon = "The Refresh button shows the next city"
anchor = "code.editor"
```

| `do` | Fields | What happens |
|---|---|---|
| `title` | `seconds` | Title card over the blurred window. |
| `create` | | The example with empty pages, opened. What `code` steps type is left out. |
| `add` | `widgets`, `cursor`, `seconds_each` | The cursor drags each widget from the Toolbox to its place; children come with their parent. |
| `fill` | `page` or `pages = "rest"`, `per_frame` | The missing widgets of a page, a few per frame. |
| `select` | `widget` | A click on the widget on the canvas. |
| `set` | `widget`, `prop`, `value` | The cursor on the row of the Properties panel; the value changes. |
| `page` | `name` | Shows a page. |
| `code` | `handler`, or `module = true` and `lines = [first, last]`; `chars_per_frame` | A handler of a widget: click on the widget, Events tab, double click on the event, then the body is typed. With `module`, those lines of the general code are typed. |
| `start` | | The cursor on Start; waits for the first frame of the simulator. |
| `tap`, `press`, `release` | `widget`, or `x`, `y` | Touches on the simulator screen, in display pixels. |
| `drag` | `widget` or `x`, `y`; `x_to`, `y_to`, `ms` | Press, move, release. |
| `wait` | `seconds` | The run goes on. |
| `stop` | | Stops the simulator. |
| `end` | `seconds`, `text` | End card with the URL of the repository. |

Every step takes `balloon`, `anchor` (where its tail points), `hold` (seconds the result stays,
default 1) and `speed` (seconds of the cursor movement of `tap`, `drag`, `press`, `release`).
A balloon stays on screen long enough to be read.

Anchors: `toolbox`, `toolbox.<type>`, `project`, `properties`, `properties.<prop>`,
`properties.events`, `events.<event>`, `canvas`, `canvas.<widget>`, `code`, `code.editor`,
`code.signature`, `simulator`, `toolbar.start`, `toolbar.resolution`, `output`. A balloon whose
anchor is not on screen yet waits for it.

Before Start, the pages are completed and any code left out is put back, so the app runs; the
summary lists what was completed without frames.

## Rules

- No change to the IDE for the sake of the tool.
- No personal data in the frames: the project lives under `/tmp/showreel/`, and the Output panel
  prints that path. Check the frames of a new storyboard.
- Fonts come from the computer that makes the video: make the published videos on one computer.

## The videos of the website

`tools/build_site.py` copies `build/showreel/{eim-01,weather,snake}/` and
`build/showreel/eim-01-short/eim-01-short.gif` into the site, and adds the Videos page; without
them it leaves the page out and says so. To make them:

```bash
for example in eim-01 weather snake; do .venv/bin/python -m tools.showreel examples/$example; done
.venv/bin/python -m tools.showreel examples/eim-01 --storyboard examples/eim-01/showreel-short.toml --name eim-01-short --no-webm
```
