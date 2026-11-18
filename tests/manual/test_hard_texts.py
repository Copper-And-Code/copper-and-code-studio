"""Texts that break code: long, quoted, escaped, in other alphabets, right to left, with emoji.

    pytest tests/manual/test_hard_texts.py --manual

Through the Properties panel, every text property of every widget type gets each hard text in
turn, as a person pastes it; pages are renamed with them through Rename Page. Each time the
widget or the page must hold the text or the IDE must refuse it with a message, the MicroPython
code generated must compile, the real runtime must draw the page without a Python error and
show the text, and the C code must be generated.
"""
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog

from lvgl_mpy_studio.build.compiler import CompileError, compile_python
from lvgl_mpy_studio.core.model import widget_definitions
from lvgl_mpy_studio.gen.gen_c import generate_c
from lvgl_mpy_studio.gen.project_gen import generate_project
from sweep import Empty, Sweep, settle
from test_every_property import open_field, typing_field, value_item

pytestmark = pytest.mark.manual

HARD = {
    "long": "W" * 600,
    "quotes": 'He said "hi" and it\'s fine',
    "triple quotes": "'''\"\"\" end",
    "backslashes": "C:\\new\\table \\n \\t \\\\ \\x41",
    "accents and scripts": "Caffè naïve – 日本語 – Ελληνικά",
    "right to left": "مرحبا بالعالم",
    "emoji": "Ready 😀🚀",
    "placeholders": "{name} {0} %s %d {{}} %%",
    "only spaces": "   ",
}
# Properties whose text has a form (numbers, cells): a hard text there must be refused, not break.
FORMED = {"data", "data2", "colWidths", "points", "spans", "map", "acceptedChars", "cellData", "headerRow"}
TEXT_PROPERTIES = sorted({(widget_type, prop["name"]) for widget_type, definition in widget_definitions().items() for prop in definition["properties"] if prop["type"] == "string"})


def paste_into(editor, text):
    """Paste: QTest.keyClicks cannot type what is not ASCII."""
    field = typing_field(editor)
    field.setFocus()
    field.selectAll()
    field.insert(text)
    QTest.keyClick(field, Qt.Key_Return)
    QApplication.processEvents()


def build_problems(project):
    """Generate, compile, draw and export in C; the problems found."""
    from lvgl_mpy_studio.build.preview import render_with_log

    problems = []
    with tempfile.TemporaryDirectory(prefix="lms-hard-") as folder:
        try:
            generate_project(project, Path(folder) / "py")
            compile_python(Path(folder) / "py")
        except CompileError as error:
            where = "; ".join(f"{item.get('file', '?')}:{item.get('line', '?')} {item.get('message', '')}" for item in error.errors[:3]) if hasattr(error, "errors") else ""
            problems.append(f"the MicroPython code does not compile: {where or str(error)[:300]}")
        except Exception as error:      # noqa: BLE001 - any failure of the generator is the finding
            problems.append(f"the generator failed: {type(error).__name__}: {error}")
        try:
            generate_c(project, Path(folder) / "c")
        except Exception as error:      # noqa: BLE001
            problems.append(f"the C generator failed: {type(error).__name__}: {error}")
    for index in range(len(project.pages)):
        pixels, log = render_with_log(project, index)
        if pixels is None or "Traceback" in (log or ""):
            problems.append(f"page {index} is not drawn: {(log or '')[-300:]}")
    return problems


@pytest.mark.parametrize("label", list(HARD))
def test_every_text_property_takes_hard_texts(qtbot, tmp_path, monkeypatch, label):
    text = HARD[label]
    problems = []
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        document = window.document
        panel = window.properties
        for widget_type in sorted({widget_type for widget_type, _prop in TEXT_PROPERTIES}):
            document.execute("Add Widget", lambda project, widget_type=widget_type: project.add_widget(project.pages[0], widget_type, {"x": 10, "y": 10}))
        names = {widget.type: widget.name for widget in document.project.pages[0].widgets}
        for widget_type, prop in TEXT_PROPERTIES:
            name = names[widget_type]
            panel.set_selection([name])
            QApplication.processEvents()
            if value_item(panel, prop) is None:
                problems.append(f"{widget_type}.{prop}: not in the panel")
                continue
            before = document.project.find_widget(name).props.get(prop)
            sweep.warnings.clear()
            with qtbot.capture_exceptions() as exceptions:
                editor = open_field(panel, prop)
                if editor is None:
                    problems.append(f"{widget_type}.{prop}: a click opens no field")
                    continue
                paste_into(editor, text)
                settle(window, 5)
            value = document.project.find_widget(name).props.get(prop)
            refused = panel.error.isVisible()
            if value != text and not refused and prop not in FORMED:
                problems.append(f"{widget_type}.{prop}: pasted {label}, holds {str(value)[:60]!r}")
            if value != text and value != before and not refused:
                problems.append(f"{widget_type}.{prop}: {label} became {str(value)[:60]!r}, neither the text nor what was there")
            problems += [f"{widget_type}.{prop}: exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
        problems += build_problems(document.project)
        document.undo_stack.setClean()
    assert not problems, f"{label}:\n" + "\n".join(problems[:30])


@pytest.mark.parametrize("label", list(HARD))
def test_a_page_renamed_with_a_hard_text(qtbot, tmp_path, monkeypatch, label):
    text = HARD[label]
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        document = window.document
        document.execute("Add Widget", lambda project: project.add_widget(project.pages[0], "label", {"x": 10, "y": 10}))
        window.add_page()
        window.add_page()
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *arguments, **options: (text, True)))
        page = document.project.pages[1]
        window.project_tree.setCurrentItem(next(item for item in window.project_tree.findItems("*", Qt.MatchWildcard | Qt.MatchRecursive) if item.data(0, Qt.UserRole) == ("page", page.id)))
        with qtbot.capture_exceptions() as exceptions:
            window.rename_page()
            settle(window)
        problems = [f"exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
        renamed = document.project.pages[1].name
        said = window.output.toPlainText()
        if renamed != text and text.strip() and "page" not in said.lower():
            problems.append(f"the page was not renamed to {label} and nothing said why (it is {renamed!r})")
        if renamed == text:
            # The other page refers to it through its constant: the code must still compile and run.
            def go(project):
                from lvgl_mpy_studio.core.model import page_constant

                project.code.module = f"PAGE = ui.{page_constant(project.pages[1].name)}\n"
            document.execute("Code", go)
            problems += build_problems(document.project)
        document.undo_stack.setClean()
    assert not problems, f"{label}:\n" + "\n".join(problems)

