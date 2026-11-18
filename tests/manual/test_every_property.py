"""Every property of every widget type, changed in the Properties panel as a person changes it.

    pytest tests/manual/test_every_property.py --manual

For each widget type, a widget is placed on an empty page and clicked on the canvas; then each
of its properties is changed through its field: a number, a text, a choice or a colour typed
and confirmed with Enter, a check box toggled with the space bar, an image or a font given as
a file. After each one the widget must hold what was typed, with no exception, no Qt warning
and no error shown by the panel. After all of them the page must be drawn by the real
runtime without a Python error, and undo must bring back the empty page.
"""
import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QLineEdit, QSpinBox

from lvgl_mpy_studio.core.model import widget_definitions
from lvgl_mpy_studio.ui.properties.panel import DESCRIPTOR_ROLE
from sweep import QT_NOISE, ROOT, Empty, Sweep, settle, wait

pytestmark = pytest.mark.manual

FONT = ROOT / ".reference" / "lvgl-bindings" / "lvgl" / "scripts" / "built_in_font" / "Montserrat-Medium.ttf"
# Texts for the properties whose text has a form; one line, since the field has one.
TEXTS = {
    "data": "5,15,25", "data2": "1,2,3", "colWidths": "80,90,100", "headerRow": "A,B,C", "points": "0,0 100,50",
    "acceptedChars": "0123456789", "options": "One", "items": "One", "tabs": "One", "buttons": "OK", "map": "1,2,3",
    "spans": "Hi|14|#FF0000", "cellData": "A,B,C",
}


def value_item(panel, name):
    def visit(parent):
        for row in range(parent.rowCount()):
            label, value = parent.child(row, 0), parent.child(row, 1)
            if value is not None and (value.data(DESCRIPTOR_ROLE) or {}).get("name") == name:
                return value
            found = visit(label) if label is not None else None
            if found is not None:
                return found
        return None
    return visit(panel.model.invisibleRootItem())


def open_field(panel, name):
    """Click the value of the property, as a person does; the field to type in, or None."""
    def editor():
        return next((child for kind in (QAbstractSpinBox, QComboBox, QLineEdit) for child in panel.view.viewport().findChildren(kind) if child.isVisible()), None)

    for click in (QTest.mouseClick, QTest.mouseClick, QTest.mouseDClick):
        item = value_item(panel, name)
        if item is None:
            return None
        panel.view.expandAll()
        panel.view.scrollTo(item.index())
        click(panel.view.viewport(), Qt.LeftButton, pos=panel.view.visualRect(item.index()).center())
        QApplication.processEvents()
        if editor() is not None:
            return editor()
    return None


def typing_field(editor):
    if isinstance(editor, (QSpinBox, QComboBox)):
        return editor.lineEdit()
    if isinstance(editor, QLineEdit):
        return editor
    return editor.findChild(QLineEdit)        # colour, image and font: a field and a button


def type_into(editor, text):
    field = typing_field(editor)
    field.setFocus()
    field.selectAll()
    QTest.keyClicks(field, text)
    QTest.keyClick(field, Qt.Key_Return)
    QApplication.processEvents()


def wanted(descriptor, current, files):
    """(text to type, the value the widget must hold afterwards), or None to leave it."""
    kind, name = descriptor["type"], descriptor["name"]
    if kind == "number":
        low, high = int(descriptor.get("min", -100000)), int(descriptor.get("max", 100000))
        value = min(max(int(current or 0) + 3, low), high)
        if value == int(current or 0):
            value = max(min(int(current or 0) - 3, high), low)
        return str(value), value
    if kind == "string":
        text = TEXTS.get(name, "Sweep")
        return text, text
    if kind == "select":
        options = [option for option in descriptor.get("options") or [] if option != current]
        return (options[0], options[0]) if options else None
    if kind == "color":
        color = "#3366CC" if str(current).upper() != "#3366CC" else "#CC6633"
        return color, color
    if kind == "image":
        return str(files["image"]), "image"
    if kind == "font":
        return (str(FONT), "font") if FONT.exists() else None
    return None


@pytest.fixture
def files(tmp_path):
    image = QImage(48, 32, QImage.Format_RGB32)
    image.fill(QColor("#3366CC"))
    path = tmp_path / "picture.png"
    assert image.save(str(path))
    return {"image": path}


@pytest.mark.parametrize("widget_type", sorted(widget_definitions()))
def test_every_property_through_the_panel(qtbot, tmp_path, monkeypatch, files, widget_type):
    from lvgl_mpy_studio.build.preview import render_with_log

    problems, changed = [], []
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        document = window.document
        start = json.dumps(document.project.to_dict(), sort_keys=True, default=str)
        index = document.undo_stack.index()
        document.execute("Add Widget", lambda project: project.add_widget(project.pages[0], widget_type, {"x": 40, "y": 40}))
        name = document.project.pages[0].widgets[-1].name
        view = window._active_designer()
        window.tabs.setCurrentWidget(view)
        item = view.designer_scene.widget_items[document.project.pages[0].widgets[-1].id]
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.mapFromScene(item.sceneBoundingRect().center()))
        wait(lambda: window.properties.names == [name], 2)
        if window.properties.names != [name]:
            view.designer_scene.clearSelection()
            item.setSelected(True)             # a widget covered by its own parts: selected as the tree would
            wait(lambda: window.properties.names == [name], 2)
        panel = window.properties
        for definition in widget_definitions()[widget_type]["properties"]:
            prop = definition["name"]
            if prop == "Name":
                continue
            item = value_item(panel, prop)
            if item is None:
                problems.append(f"{prop}: not in the panel")
                continue
            descriptor = item.data(DESCRIPTOR_ROLE)
            widget = document.project.find_widget(name)
            current = widget.props.get(prop)
            sweep.warnings.clear()
            with qtbot.capture_exceptions() as exceptions:
                if descriptor["type"] == "boolean":
                    open_field(panel, prop)    # the click puts the cell in front
                    QTest.keyClick(panel.view, Qt.Key_Space)
                    expected = not bool(current)
                else:
                    plan = wanted(descriptor, current, files)
                    if plan is None:
                        continue
                    text, expected = plan
                    editor = open_field(panel, prop)
                    if editor is None:
                        problems.append(f"{prop}: a click opens no field")
                        continue
                    type_into(editor, text)
                settle(window, 5)
                wait(lambda: False, 0.05)       # the panel is rebuilt after a change
            value = document.project.find_widget(name).props.get(prop)
            if expected == "image":
                ok = bool(value) and value != current
            elif expected == "font":
                ok = bool(value)
            elif descriptor["type"] == "color":
                ok = str(value).upper() == str(expected).upper()
            else:
                ok = value == expected
            if not ok:
                problems.append(f"{prop} ({descriptor['type']}): typed {expected!r}, the widget holds {value!r}")
            else:
                changed.append(prop)
            if panel.error.isVisible():
                problems.append(f"{prop}: the panel shows an error: {panel.error.text()}")
            problems += [f"{prop}: exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
            problems += [f"{prop}: Qt warning: {text}" for text in sweep.warnings if not any(noise in text for noise in QT_NOISE)]
        pixels, log = render_with_log(document.project, 0)
        if pixels is None or "Traceback" in (log or "") or "Error" in (log or ""):
            problems.append(f"the page is not drawn: {(log or '')[-400:]}")
        document.undo_stack.setIndex(index)
        QApplication.processEvents()
        if json.dumps(document.project.to_dict(), sort_keys=True, default=str) != start:
            problems.append("undo does not bring back the empty page")
        document.undo_stack.setClean()
    print(f"\n{widget_type}: {len(changed)} properties changed through the panel")
    assert changed, f"{widget_type}: no property was changed"
    assert not problems, f"{widget_type}:\n" + "\n".join(problems)

