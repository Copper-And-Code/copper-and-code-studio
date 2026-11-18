"""Every action of the window, and every entry of its context menus, in five states, answered
once with Cancel and once with OK.

    pytest tests/manual/test_every_action.py --manual
    LMS_PROGRESS=1 pytest -s tests/manual/test_every_action.py --manual    # a line per entry

An action is what a menu entry or a toolbar button does; the context menus are those of the
canvas, the project tree, the Files panel, the board's files, the terminals and the code
editor, opened as a right click opens them. Each entry is triggered as choosing it does;
every dialog it opens is answered by a watcher, as a person would answer it. After each: no
exception, no Qt warning, no dialog left open, the window answers, the project is as valid
as before, and undo brings it back to where it was. A new action or menu entry is tested
without writing a test.

The report, with the dialogs each entry opened and how long it took, is written to
build/manual/every-action/; the differences from the last run are printed, as a list of
things to look at by hand. The shared machinery is in sweep.py.
"""
import pytest

from sweep import STATES, Sweep

pytestmark = pytest.mark.manual


@pytest.mark.parametrize("answer", ["cancel", "ok"])
@pytest.mark.parametrize("state_class", STATES, ids=[state.name for state in STATES])
def test_every_action(qtbot, tmp_path, monkeypatch, state_class, answer):
    with Sweep(qtbot, monkeypatch, tmp_path, state_class) as sweep:
        sweep.run_entries(sweep.action_entries(), answer)
    sweep.report("every-action", f"{state_class.name}-{answer}")


@pytest.mark.parametrize("answer", ["cancel", "ok"])
@pytest.mark.parametrize("state_class", STATES, ids=[state.name for state in STATES])
def test_every_context_menu(qtbot, tmp_path, monkeypatch, state_class, answer):
    with Sweep(qtbot, monkeypatch, tmp_path, state_class) as sweep:
        sweep.run_entries(sweep.menu_entries(), answer)
    sweep.report("every-action", f"menus-{state_class.name}-{answer}")
