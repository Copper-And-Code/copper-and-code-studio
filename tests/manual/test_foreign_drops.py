"""Files and text dragged from outside the IDE, dropped anywhere in the window.

    pytest tests/manual/test_foreign_drops.py --manual

The IDE takes no files from the file manager. What a person drags there by mistake must do no
harm: an image, a font, a project, a program, a folder, or text from another application,
dropped on the canvas, the toolbox, the project tree, the Files panel, the Properties panel,
the code editor, the terminals and the window itself. No exception, no Qt warning, the window
answers, and the project is unchanged, except a text field that takes dropped text as text,
which undo takes back.
"""
import json

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QImage
from PySide6.QtWidgets import QApplication, QDockWidget

from sweep import QT_NOISE, ROOT, Example, Sweep, answers_within, settle

pytestmark = pytest.mark.manual


def payloads(folder):
    image = QImage(32, 32, QImage.Format_RGB32)
    image.fill(QColor("#336699"))
    image.save(str(folder / "picture.png"))
    (folder / "font.ttf").write_bytes(b"\0\1\0\0not really a font")
    (folder / "main.py").write_text("print('dropped')\n", encoding="utf-8")
    (folder / "project.json").write_text((ROOT / "examples" / "weather" / "project.json").read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "a folder").mkdir()
    found = {}
    for name in ("picture.png", "font.ttf", "main.py", "project.json", "a folder"):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(folder / name))])
        found[f"file {name}"] = mime
    several = QMimeData()
    several.setUrls([QUrl.fromLocalFile(str(folder / name)) for name in ("picture.png", "main.py")])
    found["two files"] = several
    text = QMimeData()
    text.setText("print('text from another application')")
    found["text"] = text
    return found


def targets(window):
    found = []
    view = next(view for _index, view in window.designers.values())
    found.append(("canvas", lambda: (window.tabs.setCurrentWidget(view), view.viewport())[1]))
    found.append(("toolbox", lambda: window.toolbox_panel.toolbox.viewport()))
    found.append(("project tree", lambda: window.project_tree.viewport()))
    found.append(("Files panel", lambda: window.files_panel.tree.viewport()))
    found.append(("Properties panel", lambda: window.properties.view.viewport()))
    found.append(("code editor", lambda: (window.tabs.setCurrentWidget(window.code_panel), window.code_panel.editor.viewport())[1]))
    found.append(("Device Console", lambda: window.device_console.terminal.viewport()))
    found.append(("Output", lambda: window.output.viewport()))
    found.append(("window", lambda: window))
    return found


def drop(widget, mime):
    point = widget.rect().center()
    enter = QDragEnterEvent(point, Qt.CopyAction | Qt.MoveAction | Qt.LinkAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, enter)
    if not enter.isAccepted():
        return False
    QApplication.sendEvent(widget, QDragMoveEvent(point, Qt.CopyAction | Qt.MoveAction | Qt.LinkAction, mime, Qt.LeftButton, Qt.NoModifier))
    QApplication.sendEvent(widget, QDropEvent(QPointF(point), Qt.CopyAction | Qt.MoveAction | Qt.LinkAction, mime, Qt.LeftButton, Qt.NoModifier))
    return True


def test_what_is_dropped_from_outside_does_no_harm(qtbot, tmp_path, monkeypatch):
    folder = tmp_path / "outside"
    folder.mkdir()
    problems, taken = [], []
    with Sweep(qtbot, monkeypatch, tmp_path, Example) as sweep:
        window = sweep.window
        for dock in window.findChildren(QDockWidget):
            dock.show()
        document = window.document
        for what, mime in payloads(folder).items():
            for place, find in targets(window):
                widget = find()
                QApplication.processEvents()
                before = json.dumps(document.project.to_dict(), sort_keys=True, default=str)
                index = document.undo_stack.index()
                sweep.warnings.clear()
                with qtbot.capture_exceptions() as exceptions:
                    accepted = drop(widget, mime)
                    settle(window, 5)
                name = f"{what} on the {place}"
                problems += [f"{name}: exception: {kind.__name__}: {error}" for kind, error, _trace in exceptions]
                problems += [f"{name}: Qt warning: {text}" for text in sweep.warnings if not any(noise in text for noise in QT_NOISE)]
                if not answers_within(window):
                    problems.append(f"{name}: the window does not answer")
                after = json.dumps(document.project.to_dict(), sort_keys=True, default=str)
                if after != before:
                    if place == "code editor":
                        taken.append(name)
                        document.undo_stack.setIndex(index)
                        QApplication.processEvents()
                        if json.dumps(document.project.to_dict(), sort_keys=True, default=str) != before:
                            problems.append(f"{name}: undo does not take back what the editor took")
                    else:
                        problems.append(f"{name}: the project changed")
                elif accepted:
                    taken.append(f"{name} (accepted, nothing changed)")
        document.undo_stack.setClean()
    print("\ntaken: " + ("; ".join(taken) or "nothing"))
    assert not problems, "\n".join(problems)
