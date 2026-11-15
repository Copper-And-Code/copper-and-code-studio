"""python -m tools.showreel EXAMPLE [--out FOLDER]"""
import argparse
import shutil
import sys
import time
from pathlib import Path

from . import storyboard as boards


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tools.showreel", description="Record the real IDE building and running an example.")
    parser.add_argument("example", type=Path, help="an example folder, for example examples/eim-01")
    parser.add_argument("--out", type=Path, help="output folder (default build/showreel/<example>)")
    parser.add_argument("--storyboard", type=Path, help="a storyboard file (default <example>/showreel.toml, or a default one)")
    parser.add_argument("--name", help="base name of the files written (default the example's folder name)")
    parser.add_argument("--only", choices=("design", "run"), help="design: stop before Start; run: the project whole at once, then the run steps")
    parser.add_argument("--no-webm", action="store_true", help="skip the WebM, the slowest to encode")
    parser.add_argument("--keep-frames", action="store_true", help="keep the PNG frames after encoding")
    parser.add_argument("--print-storyboard", action="store_true", help="print the storyboard as TOML and stop")
    arguments = parser.parse_args(argv)

    example = arguments.example.resolve()
    if example.is_file():
        example = example.parent
    if not (example / "project.json").is_file():
        parser.error(f"{arguments.example} has no project.json")
    try:
        board = boards.load(example, arguments.storyboard)
    except boards.StoryboardError as exc:
        parser.exit(1, f"showreel: {exc}\n")
    if arguments.print_storyboard:
        sys.stdout.write(boards.to_toml(board))
        return 0

    if arguments.only:
        board = boards.only(board, arguments.only)
    name = example.name
    out = (arguments.out or Path("build/showreel") / (arguments.name or name)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # A neutral path: the Output panel prints the build folder, and it is in the frames.
    workdir = Path("/tmp/showreel") / name

    from .ide import Ide, IdeError, prepare_environment

    config = prepare_environment()
    from . import encode
    from .player import Player
    from .timeline import Timeline

    video = board["video"]
    started = time.monotonic()
    print(f"showreel: {name}, {len(board['step'])} steps, window {video['window'][0]}×{video['window'][1]}, {video['fps']} fps")
    ide = Ide(tuple(video["window"]))
    timeline = Timeline(out / "frames", video["fps"])
    player = Player(ide, timeline, board, example, workdir)
    try:
        player.play()
    except IdeError as exc:
        print(f"showreel: {exc}", file=sys.stderr)
        return 1
    finally:
        ide.close()
        timeline.finish()
        shutil.rmtree(config, ignore_errors=True)
    print(f"frames: {timeline.count} ({timeline.seconds:.1f} s of video) in {time.monotonic() - started:.0f} s")

    stem = arguments.name or name
    try:
        made = [encode.mp4(timeline, out / f"{stem}.mp4")]
        if not arguments.no_webm:
            made.append(encode.webm(timeline, out / f"{stem}.webm"))
        start, frames = gif_cut(video["gif"], timeline)
        made.append(encode.gif(timeline, out / f"{stem}.gif", start, frames, video["gif"].get("fps", 12), video["gif"].get("width", 960)))
        made.append(encode.poster(timeline, out / f"{stem}-poster.png", mark_frame(video["poster"], timeline) + timeline.fps))
    except (encode.EncodeError, ValueError) as exc:
        print(f"showreel: {exc}; the frames are in {timeline.folder}", file=sys.stderr)
        return 1
    for target in made:
        size = target.stat().st_size / 1e6
        warning = "  (over 8 MB: shorten the gif cut)" if target.suffix == ".gif" and size > 8 else ""
        print(f"wrote {target} ({size:.1f} MB){warning}")
    if not arguments.keep_frames:
        shutil.rmtree(timeline.folder)
    for note in player.notes:
        print("note:", note)
    return 0


def mark_frame(where, timeline):
    """A frame number from a step name (its first frame) or a time in seconds."""
    if isinstance(where, (int, float)) and not isinstance(where, bool):
        return min(timeline.count - 1, int(where * timeline.fps))
    if where not in timeline.marks:
        raise ValueError(f"no {where!r} step in the storyboard; steps played: {', '.join(timeline.marks)}")
    return timeline.marks[where]


def gif_cut(gif, timeline):
    start = mark_frame(gif.get("from", 0), timeline)
    seconds = gif.get("seconds")
    return start, None if seconds is None else int(seconds * timeline.fps)


if __name__ == "__main__":
    sys.exit(main())
