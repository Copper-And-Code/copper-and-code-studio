"""The window at many sizes, and its docks moved, floated, closed and brought back.

    pytest tests/manual/test_sizes_and_docks.py --manual

With an example open: the window from 800×600 to 2560×1440, with no text cut off, no widgets
covering each other and no Qt warning at each size. Then each dock is floated and docked
again, closed and opened again from its entry of View, as a person does; the panels must
show their content again and nothing may raise. Last, a layout changed by hand (a dock
floated, one closed) must come back as it was when the IDE is closed and opened again.
"""
import pytest
from PySide6.QtWidgets import QApplication, QDockWidget

from looks import cut_off, overlapping
from sweep import QT_NOISE, Example, Sweep, settle, wait

pytestmark = pytest.mark.manual

SIZES = [(800, 600), (1024, 700), (1366, 768), (1920, 1080), (2560, 1440)]


def docks(window):
    return sorted(window.findChildren(QDockWidget), key=lambda dock: dock.objectName())


def warnings_of(sweep):
    return [text for text in sweep.warnings if not any(noise in text for noise in QT_NOISE)]


def test_the_window_at_every_size(qtbot, tmp_path, monkeypatch):
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        with qtbot.capture_exceptions() as exceptions:
            for width, height in SIZES:
                sweep.warnings.clear()
                window.resize(width, height)
                settle(window)
                size = f"{width}×{height}"
                if (window.width(), window.height()) != (width, height):
                    least = window.minimumSizeHint()
                    if width >= 1024 and height >= 700:
                        problems.append(f"{size}: the window stays {window.width()}×{window.height()} (it needs at least {least.width()}×{least.height()})")
                    continue                   # smaller than the window can be: Qt keeps its least size
                problems += [f"{size}: cut off: {text}" for text in cut_off(window)]
                problems += [f"{size}: {text}" for text in overlapping(window)]
                problems += [f"{size}: Qt warning: {text}" for text in warnings_of(sweep)]
        problems += [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
    problems = sorted(set(problems))
    assert not problems, "\n".join(problems)


def test_every_dock_floats_closes_and_comes_back(qtbot, tmp_path, monkeypatch):
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        sweep.warnings.clear()
        with qtbot.capture_exceptions() as exceptions:
            for dock in docks(window):
                name = dock.objectName()
                dock.show()
                dock.raise_()
                settle(window)
                dock.setFloating(True)
                settle(window)
                if not dock.isFloating() or not dock.isVisible():
                    problems.append(f"{name}: does not float")
                problems += [f"{name}, floating: cut off: {text}" for text in cut_off(dock)]
                dock.setFloating(False)
                settle(window)
                if dock.isFloating():
                    problems.append(f"{name}: does not dock again")
                toggle = dock.toggleViewAction()
                toggle.trigger()               # View → the panel: closes it
                settle(window)
                if dock.isVisible():
                    problems.append(f"{name}: its entry of View does not close it")
                toggle.trigger()               # and opens it again
                dock.raise_()
                settle(window)
                if not dock.isVisible() or dock.widget() is None or not dock.widget().isVisible():
                    problems.append(f"{name}: its entry of View does not bring it back with its content")
        problems += [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
        problems += [f"Qt warning: {text}" for text in warnings_of(sweep)]
    problems = sorted(set(problems))
    assert not problems, "\n".join(problems)


def test_a_layout_changed_by_hand_comes_back_after_a_restart(qtbot, tmp_path, monkeypatch):
    from copper_and_code_studio.ui.main_window import MainWindow

    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        components = window.findChild(QDockWidget, "componentsDock")
        errors = window.findChild(QDockWidget, "errorsDock")
        components.setFloating(True)
        errors.toggleViewAction().trigger()
        room = window.screen().availableGeometry()
        window.resize(room.width() - 40, room.height() - 60)   # another size, that fits the screen
        settle(window)
        before = {dock.objectName(): (dock.isVisible(), dock.isFloating()) for dock in docks(window)}
        size = (window.width(), window.height())
        window.document.undo_stack.setClean()
        window.close()                         # saves the layout, as at the end of a session
        wait(lambda: not window.isVisible(), 5)
    again = MainWindow()
    qtbot.addWidget(again)
    again.show()
    wait(lambda: False, 0.3)
    try:
        after = {dock.objectName(): (dock.isVisible(), dock.isFloating()) for dock in docks(again)}
        assert after == before
        assert (again.width(), again.height()) == size
    finally:
        for dock in docks(again):
            dock.setFloating(False)
            dock.show()
        again.document.undo_stack.setClean()
        again.close()
        QApplication.processEvents()
