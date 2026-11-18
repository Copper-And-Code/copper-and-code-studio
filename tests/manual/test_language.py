"""The language changed in each state of the IDE, and back.

    pytest tests/manual/test_language.py --manual

In each of the five states of the suite of every action: View → Language → Italiano, then
English. After the change to Italian nothing that has a translation may show in English;
after the change back nothing may stay in Italian. The project, the undo history, what is
selected and what runs are the same before and after; no exception, no Qt warning. Twice in
a row, since the first change of language records the texts and the second uses them.
"""
import json

import pytest

from looks import english_left, italian_left
from sweep import QT_NOISE, STATES, Sweep, settle, wait

pytestmark = pytest.mark.manual


def picture(window):
    """What a change of language must not touch."""
    document = window.document
    view = window._active_designer()
    return {
        "project": json.dumps(document.project.to_dict(), sort_keys=True, default=str),
        "undo": (document.undo_stack.count(), document.undo_stack.index()),
        "modified": document.modified,
        "selected": view.designer_scene.selected_names() if view is not None else None,
        "running": (window.sim_panel.running, bool(window.sim_panel.program)),
        "board": window.device.port,
        "tab": window.tabs.currentIndex(),
    }


@pytest.mark.parametrize("state_class", STATES, ids=[state.name for state in STATES])
def test_the_language_changes_and_comes_back_in_every_state(qtbot, tmp_path, monkeypatch, state_class):
    with Sweep(qtbot, monkeypatch, tmp_path, state_class) as sweep:
        window = sweep.window
        before = picture(window)
        problems = []
        sweep.warnings.clear()
        with qtbot.capture_exceptions() as exceptions:
            for turn in (1, 2):
                window.change_language("it")
                settle(window)
                problems += [f"turn {turn}, Italian: still in English: {where} “{text}”" for where, text in english_left(window)]
                window.change_language("en")
                settle(window)
                problems += [f"turn {turn}, English: still in Italian: {where} “{text}”" for where, text in italian_left(window)]
        wait(lambda: False, 0.2)
        after = picture(window)
        problems += [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
        problems += [f"Qt warning: {text}" for text in sweep.warnings if not any(noise in text for noise in QT_NOISE)]
        problems += [f"the change of language changed {key}: {before[key]!r} → {after[key]!r}" for key in before if before[key] != after[key] and key != "project"]
        if before["project"] != after["project"]:
            problems.append("the change of language changed the project")
    problems = sorted(set(problems))
    assert not problems, f"{len(problems)} problems in the state {state_class.name}:\n" + "\n".join(problems)
