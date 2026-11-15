"""The clock of the video: numbered PNG frames at a fixed rate.

The same picture held for many frames is written once and hard-linked, so a hold of a few
seconds costs one file. PNG files are written by a few threads, so that grabbing does not wait
for the compression.
"""
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PNG_QUALITY = 80        # Qt maps it to zlib level 1: large files, fast to write


class Timeline:
    def __init__(self, folder, fps=25):
        self.folder = Path(folder)
        if self.folder.exists():
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True)
        self.fps = fps
        self.count = 0
        self.marks = {}                 # name -> frame number, for the GIF cut and the poster
        self._last = None
        self._pool = ThreadPoolExecutor(max_workers=4)
        self._pending = []

    @property
    def seconds(self):
        return self.count / self.fps

    def frames_for(self, seconds):
        return max(1, round(seconds * self.fps))

    def path(self, number):
        return self.folder / f"{number:06d}.png"

    def mark(self, name):
        self.marks.setdefault(name, self.count)

    def add(self, image, frames=1):
        """Write a QImage as the next frame, then repeat it for the other frames."""
        if frames <= 0:
            return
        target = self.path(self.count)
        self._pending.append(self._pool.submit(_save, image, target))
        self._last = target
        self.count += 1
        self.repeat(frames - 1)

    def repeat(self, frames=1):
        """Repeat the last frame; links are made when the files are written (see finish)."""
        for _ in range(frames):
            if self._last is None:
                return
            self._pending.append(self._pool.submit(_link, self._last, self.path(self.count), self._pending[-1]))
            self.count += 1

    def finish(self):
        for future in self._pending:
            future.result()
        self._pending.clear()
        self._pool.shutdown()


def _save(image, target):
    if not image.save(str(target), "PNG", PNG_QUALITY):
        raise OSError(f"could not write {target}")


def _link(source, target, before):
    before.result()                     # the source exists only after its own save
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)
