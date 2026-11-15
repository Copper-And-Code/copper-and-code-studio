"""Encoding the frames with the ffmpeg program."""
import shutil
import subprocess


class EncodeError(RuntimeError):
    pass


def ffmpeg():
    program = shutil.which("ffmpeg")
    if program is None:
        raise EncodeError("ffmpeg is not on the PATH: install it (for example `sudo apt install ffmpeg`) to make the videos; the frames are kept")
    return program


def _run(arguments):
    result = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *arguments], capture_output=True, text=True)
    if result.returncode:
        raise EncodeError("ffmpeg failed:\n" + result.stderr[-2000:])


def _frames(timeline, start=0):
    # Even sizes for yuv420p; a 1600×1000 window is already even.
    return ["-framerate", str(timeline.fps), "-start_number", str(start), "-i", str(timeline.folder / "%06d.png")]


def mp4(timeline, target):
    _run([*_frames(timeline), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-preset", "medium",
          "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)])
    return target


def webm(timeline, target):
    _run([*_frames(timeline), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-deadline", "good", "-cpu-used", "4",
          "-row-mt", "1", "-pix_fmt", "yuv420p", str(target)])
    return target


def gif(timeline, target, start=0, frames=None, fps=12, width=960):
    """A GIF of a range of frames: scaled, fewer frames per second, one palette for the whole cut."""
    frames = timeline.count - start if frames is None else min(frames, timeline.count - start)
    scale = f"fps={fps},scale={width}:-1:flags=lanczos"
    _run([*_frames(timeline, start), "-t", f"{frames / timeline.fps:.3f}", "-vf",
          f"{scale},split[a][b];[a]palettegen=stats_mode=diff:max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
          "-loop", "0", str(target)])
    return target


def poster(timeline, target, frame):
    shutil.copyfile(timeline.path(min(max(0, frame), timeline.count - 1)), target)
    return target
