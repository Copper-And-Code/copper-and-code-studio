"""The looks of the IDE: pictures of fixed states compared with the last accepted ones, and checks
that need no picture.

    pytest tests/manual/test_looks.py --manual                     # offscreen: light theme only
    tools/manual_on_x.sh 1366x768 tests/manual/test_looks.py        # a real display: light and dark
    LMS_LOOKS_ACCEPT=1 pytest tests/manual/test_looks.py --manual  # the pictures of now become the reference

The window with an example open, then each of its panels and tabs, in light and dark theme, in
English and Italian, at 1024×700 and 1920×1080. The pictures go to build/manual/looks/now/; the
reference is build/manual/looks/accepted/, kept on this PC only: fonts differ between machines,
so the CI never compares them. A picture that differs from the reference is a thing to look at,
listed with its share of changed pixels; the first run makes the reference.

Without a reference, on every state: no text cut off, no widgets covering each other or
sticking out of their parent, no label with too little contrast.
"""
import os
import shutil
from array import array

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QApplication, QDockWidget

from looks import cut_off, low_contrast, overlapping
from sweep import REPORTS, Example, Sweep, wait

pytestmark = pytest.mark.manual

NOW, ACCEPTED = REPORTS / "looks" / "now", REPORTS / "looks" / "accepted"
ACCEPT = bool(os.environ.get("LMS_LOOKS_ACCEPT"))
CHANGED = 0.002                                # share of pixels: above it, the picture changed
SIZES = [(1024, 700), (1920, 1080)]


def changed_share(first, second):
    """Share of the pixels that differ; 1.0 when the sizes differ."""
    if first.size() != second.size():
        return 1.0
    one = array("I", first.convertToFormat(QImage.Format_RGB32).constBits().tobytes())
    two = array("I", second.convertToFormat(QImage.Format_RGB32).constBits().tobytes())
    return sum(1 for a, b in zip(one, two) if a != b) / max(len(one), 1)


def set_scheme(dark):
    """True if the platform took the colour scheme: offscreen does not."""
    wanted = Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light
    QGuiApplication.styleHints().setColorScheme(wanted)
    wait(lambda: QGuiApplication.styleHints().colorScheme() == wanted, 2)
    wait(lambda: False, 0.2)                  # the IDE redraws at the next turn
    return QGuiApplication.styleHints().colorScheme() == wanted or not dark


def pictures(window):
    """(name, widget) of what is photographed: the window, each dock, each tab."""
    found = [("window", window)]
    for dock in sorted(window.findChildren(QDockWidget), key=lambda dock: dock.objectName()):
        found.append((dock.objectName(), dock))
    for index in range(window.tabs.count()):
        found.append((f"tab-{index}", window.tabs.widget(index)))
    return found


def show(window, name, widget):
    if isinstance(widget, QDockWidget):
        widget.show()
        widget.raise_()
    elif name.startswith("tab-"):
        window.tabs.setCurrentWidget(widget)
    QApplication.processEvents()
    # A page of the designer shows the real rendering when it comes, from a thread.
    renderer = window.preview_renderer
    wait(lambda: not renderer.busy and not renderer._timer.isActive(), 15)
    wait(lambda: False, 0.2)


@pytest.mark.parametrize("size", SIZES, ids=[f"{width}x{height}" for width, height in SIZES])
@pytest.mark.parametrize("language", ["en", "it"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_looks(qtbot, tmp_path, monkeypatch, scheme, language, size):
    if QGuiApplication.platformName() == "offscreen" and scheme == "dark":
        pytest.skip("offscreen has no dark theme: run it with tools/manual_on_x.sh")
    case = f"{scheme}-{language}-{size[0]}x{size[1]}"
    folder, reference = NOW / case, ACCEPTED / case
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    problems, to_look_at = [], []
    with Sweep(qtbot, monkeypatch, tmp_path, Example, language=language) as sweep:
        window = sweep.window
        try:
            if not set_scheme(scheme == "dark"):
                pytest.skip("this platform did not take the dark theme")
            window.resize(*size)
            wait(lambda: False, 0.3)
            for name, widget in pictures(window):
                show(window, name, widget)
                picture = widget.grab().toImage()
                picture.save(str(folder / f"{name}.png"))
                problems += [f"{name}: cut off: {text}" for text in cut_off(widget)]
                problems += [f"{name}: {text}" for text in overlapping(widget)]
                problems += [f"{name}: low contrast: {text}" for text in low_contrast(widget)]
                accepted = reference / f"{name}.png"
                if accepted.is_file() and not ACCEPT:
                    share = changed_share(QImage(str(accepted)), picture)
                    if share > CHANGED:
                        to_look_at.append(f"{name}: {share:.1%} of the pixels changed")
        finally:
            set_scheme(False)
    if ACCEPT or not reference.exists():
        if reference.exists():
            shutil.rmtree(reference)
        shutil.copytree(folder, reference)
        print(f"\n{case}: the pictures of now are the reference, in {reference}")
    if to_look_at:
        print(f"\n{case}: pictures to look at (now in {folder}, before in {reference}):\n  " + "\n  ".join(to_look_at))
    problems = sorted(set(problems))
    assert not problems, f"{len(problems)} problems of looks in {case}:\n" + "\n".join(problems)
