"""The canvas under the mouse: widgets dropped, moved, resized, selected, at several zooms.

    pytest tests/manual/test_canvas_mouse.py --manual

In the real window, on an empty page:
- every widget type dropped from the toolbox lands where the pointer was, selected, and one
  undo takes it away;
- each widget dragged moves by what the pointer moved, at zoom 1, 2 and 0.5, as one undo step;
- each of the eight handles resizes as it should, never below the least size;
- a rubber band selects what it covers, Ctrl+click adds and removes, a click on the empty page
  clears; the Properties panel follows;
- with the grid on, moves land on the grid; the arrow keys move by 1, with Shift by 10;
- a widget dropped on a panel goes inside it, and moves with it.
After each part, undo all gives the empty page again.
"""
import json

import pytest
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from lvgl_mpy_studio.core.components import is_component
from lvgl_mpy_studio.core.model import widget_definitions
from lvgl_mpy_studio.ui.designer.scene import MINIMUM_SIZE, WIDGET_MIME, ResizeHandle
from sweep import Empty, Sweep, wait

pytestmark = pytest.mark.manual

VISUAL = sorted(widget_type for widget_type in widget_definitions() if not is_component(widget_type))


def snapshot(document):
    return json.dumps(document.project.to_dict(), sort_keys=True, default=str)


def view_of(window):
    view = window._active_designer() or next(view for _index, view in window.designers.values())
    window.tabs.setCurrentWidget(view)
    QApplication.processEvents()
    return view


def drop(view, widget_type, scene_point):
    """What a drag from the toolbox delivers: enter, a move, the drop."""
    point = view.mapFromScene(scene_point)
    mime = QMimeData()
    mime.setData(WIDGET_MIME, widget_type.encode())
    mime.setText(widget_type)
    for kind in (QDragEnterEvent, QDragMoveEvent):
        QApplication.sendEvent(view.viewport(), kind(point, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    QApplication.sendEvent(view.viewport(), QDropEvent(QPointF(point), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    QApplication.processEvents()


def drag(view, start, end, modifiers=Qt.NoModifier):
    """Press at start, move in steps, release at end: points of the viewport."""
    QTest.mousePress(view.viewport(), Qt.LeftButton, modifiers, start)
    for fraction in (0.25, 0.5, 0.75, 1.0):
        middle = QPointF(start) + (QPointF(end) - QPointF(start)) * fraction
        QApplication.sendEvent(view.viewport(), QMouseEvent(QEvent.MouseMove, middle, view.viewport().mapToGlobal(middle), Qt.LeftButton, Qt.LeftButton, modifiers))
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, modifiers, end)
    QApplication.processEvents()


def geometry(widget):
    return tuple(int(widget.props.get(key, 0)) for key in ("x", "y", "width", "height"))


@pytest.fixture
def canvas(qtbot, tmp_path, monkeypatch):
    with Sweep(qtbot, monkeypatch, tmp_path, Empty) as sweep:
        window = sweep.window
        window.resize(1400, 900)
        yield window, view_of(window)
        window.document.undo_stack.setClean()


def test_every_widget_type_dropped_from_the_toolbox(canvas):
    window, view = canvas
    document = window.document
    start, problems = snapshot(document), []
    for widget_type in VISUAL:
        before = len(document.project.pages[0].widgets)
        index = document.undo_stack.index()
        target = QPointF(220, 160)
        drop(view, widget_type, target)
        widgets = document.project.pages[0].widgets
        if len(widgets) != before + 1 or widgets[-1].type != widget_type:
            problems.append(f"{widget_type}: the drop added {len(widgets) - before} widgets")
            continue
        widget = widgets[-1]
        x, y, width, height = geometry(widget)
        centre = (x + width / 2, y + height / 2)
        if abs(centre[0] - target.x()) > 2 and x != 0 or abs(centre[1] - target.y()) > 2 and y != 0:
            problems.append(f"{widget_type}: dropped at {target.x():.0f},{target.y():.0f}, centred at {centre[0]:.0f},{centre[1]:.0f}")
        if view.designer_scene.selected_names() != [widget.name]:
            problems.append(f"{widget_type}: after the drop the selection is {view.designer_scene.selected_names()}")
        if not wait(lambda: window.properties.names == [widget.name], 2):
            problems.append(f"{widget_type}: the Properties panel shows {window.properties.names}")
        if document.undo_stack.index() != index + 1:
            problems.append(f"{widget_type}: the drop made {document.undo_stack.index() - index} undo steps")
        document.undo_stack.undo()
        QApplication.processEvents()
        if len(document.project.pages[0].widgets) != before or widget.id in view.designer_scene.widget_items:
            problems.append(f"{widget_type}: one undo does not take the drop away")
    if snapshot(document) != start:
        problems.append("the page is not empty again")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("zoom", [1.0, 2.0, 0.5])
def test_widgets_move_with_the_pointer_at_every_zoom(canvas, zoom):
    window, view = canvas
    document = window.document
    start, problems = snapshot(document), []
    view.resetTransform()
    view.scale(zoom, zoom)
    QApplication.processEvents()
    for widget_type in VISUAL:
        drop(view, widget_type, QPointF(200, 150))
        widget = document.project.pages[0].widgets[-1]
        item = view.designer_scene.widget_items[widget.id]
        view.centerOn(item)
        QApplication.processEvents()
        before = geometry(widget)
        index = document.undo_stack.index()
        grab = item.mapToScene(QPointF(min(6, item.rect().width() / 2), min(6, item.rect().height() / 2)))
        begin = view.mapFromScene(grab)
        end = view.mapFromScene(grab + QPointF(37, 23))
        drag(view, begin, end)
        after = geometry(document.project.find_widget(widget.name))
        moved = (after[0] - before[0], after[1] - before[1])
        # At zoom 0.5 a pixel of the screen is two of the page: the pointer moves by what it can.
        pointed = view.mapToScene(end) - view.mapToScene(begin)
        wanted = (round(pointed.x()), round(pointed.y()))
        if moved != wanted or after[2:] != before[2:]:
            problems.append(f"{widget_type} at zoom {zoom}: dragged by {wanted[0]},{wanted[1]}, moved by {moved[0]},{moved[1]}, size {before[2:]} → {after[2:]}")
        if document.undo_stack.index() != index + 1:
            problems.append(f"{widget_type} at zoom {zoom}: the drag made {document.undo_stack.index() - index} undo steps")
        document.undo_stack.undo()
        if geometry(document.project.find_widget(widget.name)) != before:
            problems.append(f"{widget_type} at zoom {zoom}: undo does not put it back")
        document.undo_stack.undo()
    view.resetTransform()
    if snapshot(document) != start:
        problems.append("the page is not empty again")
    assert not problems, "\n".join(problems)


def test_every_handle_resizes_and_keeps_the_least_size(canvas):
    window, view = canvas
    document = window.document
    start, problems = snapshot(document), []
    drop(view, "button", QPointF(300, 220))
    widget = document.project.pages[0].widgets[-1]

    def selected_item():
        """The canvas makes its items again after each change: looked up each time, and clicked if needed."""
        item = view.designer_scene.widget_items[widget.id]
        if not item.isSelected():
            QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=view.mapFromScene(item.sceneBoundingRect().center()))
            item = view.designer_scene.widget_items[widget.id]
        return item

    # index: 0 top left, 1 top, 2 top right, 3 right, 4 bottom right, 5 bottom, 6 bottom left, 7 left
    for index in range(8):
        handles = {handle.index: handle for handle in selected_item().childItems() if isinstance(handle, ResizeHandle)}
        if index not in handles or not handles[index].isVisible():
            problems.append(f"handle {index}: not shown on the selected widget")
            continue
        x, y, width, height = geometry(document.project.find_widget(widget.name))
        begin = view.mapFromScene(handles[index].scenePos())
        drag(view, begin, begin + QPoint(15, 11))
        left, right, top, bottom = index in (0, 6, 7), index in (2, 3, 4), index in (0, 1, 2), index in (4, 5, 6)
        expected = (
            x + 15 if left else x, y + 11 if top else y,
            width - 15 if left else width + 15 if right else width,
            height - 11 if top else height + 11 if bottom else height,
        )
        got = geometry(document.project.find_widget(widget.name))
        if got != expected:
            problems.append(f"handle {index}: dragged by 15,11 from {(x, y, width, height)}: expected {expected}, got {got}")
        document.undo_stack.undo()
        QApplication.processEvents()
        if geometry(document.project.find_widget(widget.name)) != (x, y, width, height):
            problems.append(f"handle {index}: undo does not give the size back")
    handles = {handle.index: handle for handle in selected_item().childItems() if isinstance(handle, ResizeHandle)}
    begin = view.mapFromScene(handles[4].scenePos())
    drag(view, begin, begin - QPoint(400, 400))   # far past the top left corner
    _x, _y, width, height = geometry(document.project.find_widget(widget.name))
    if width < MINIMUM_SIZE or height < MINIMUM_SIZE:
        problems.append(f"a handle dragged far inwards left a button of {width}×{height}, below {MINIMUM_SIZE}")
    document.undo_stack.setIndex(0)
    if snapshot(document) != start:
        problems.append("the page is not empty again")
    assert not problems, "\n".join(problems)


def test_selecting_with_the_rubber_band_ctrl_and_clicks(canvas):
    window, view = canvas
    document, scene = window.document, view.designer_scene
    for x, y in ((60, 60), (220, 60), (60, 260)):
        drop(view, "button", QPointF(x, y))
    names = [widget.name for widget in document.project.pages[0].widgets]
    problems = []

    def centre(name):
        item = scene.widget_items[document.project.find_widget(name).id]
        return view.mapFromScene(item.sceneBoundingRect().center())

    def follows(expected):
        if sorted(scene.selected_names()) != sorted(expected):
            problems.append(f"expected {sorted(expected)} selected, the canvas has {sorted(scene.selected_names())}")
        elif not wait(lambda: sorted(window.properties.names) == sorted(expected), 2):
            problems.append(f"the Properties panel shows {window.properties.names} for {sorted(expected)}")

    empty = view.mapFromScene(QPointF(390, 400))
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=empty)
    follows([])
    drag(view, view.mapFromScene(QPointF(5, 5)), view.mapFromScene(QPointF(330, 120)))   # covers the two at the top
    follows(names[:2])
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.ControlModifier, centre(names[2]))
    follows(names)
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=empty)
    follows([])
    QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=centre(names[1]))
    follows(names[1:2])
    document.undo_stack.setIndex(0)
    assert not problems, "\n".join(problems)


def test_the_grid_and_the_arrow_keys(canvas):
    window, view = canvas
    document, scene = window.document, view.designer_scene
    drop(view, "button", QPointF(200, 150))
    widget = document.project.pages[0].widgets[-1]
    problems = []
    window.grid_action.trigger()               # View → Grid
    QApplication.processEvents()
    assert scene.grid_size > 1, "View → Grid did not turn the grid on"
    grid = scene.grid_size
    item = scene.widget_items[widget.id]
    begin = view.mapFromScene(item.mapToScene(QPointF(5, 5)))
    drag(view, begin, begin + QPoint(13, 7))
    x, y, _width, _height = geometry(document.project.find_widget(widget.name))
    if x % grid or y % grid:
        problems.append(f"with a grid of {grid} a move landed at {x},{y}")
    window.grid_action.trigger()
    QApplication.processEvents()
    view.setFocus()
    x, y, _width, _height = geometry(document.project.find_widget(widget.name))
    QTest.keyClick(view, Qt.Key_Right)
    QTest.keyClick(view, Qt.Key_Down, Qt.ShiftModifier)
    after = geometry(document.project.find_widget(widget.name))[:2]
    if after != (x + 1, y + 10):
        problems.append(f"Right and Shift+Down from {x},{y} gave {after}")
    document.undo_stack.setIndex(0)
    assert not problems, "\n".join(problems)


def test_a_widget_dropped_on_a_panel_goes_inside_and_moves_with_it(canvas):
    window, view = canvas
    document, scene = window.document, view.designer_scene
    drop(view, "panel", QPointF(250, 200))
    panel = document.project.pages[0].widgets[-1]
    px, py, pwidth, pheight = geometry(panel)
    drop(view, "label", QPointF(px + pwidth / 2, py + pheight / 2))
    label = document.project.pages[0].widgets[-1]
    problems = []
    if label.parentId != panel.id:
        problems.append("the label dropped on the panel is not inside it")
    before = document.project.screen_position(label)
    item = scene.widget_items[panel.id]
    scene.clearSelection()
    grab = item.mapToScene(QPointF(3, 3))
    drag(view, view.mapFromScene(grab), view.mapFromScene(grab + QPointF(30, 20)))
    after = document.project.screen_position(document.project.find_widget(label.name))
    if (after[0] - before[0], after[1] - before[1]) != (30, 20):
        problems.append(f"the panel moved by 30,20, the label inside it by {after[0] - before[0]},{after[1] - before[1]}")
    document.undo_stack.setIndex(0)
    assert not problems, "\n".join(problems)
