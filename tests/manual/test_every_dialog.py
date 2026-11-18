"""Every dialog the IDE opens, looked at before it is answered, in English and in Italian.

    pytest tests/manual/test_every_dialog.py --manual

The actions and context menus of the window are triggered as in test_every_action; each
dialog they open is, before it is closed:
- photographed, to build/manual/every-dialog/<language>/, for a person to look through;
- checked for text cut off: a label, button or column of a list narrower than its text;
- checked for widgets that cover each other or stick out, and for text with too little contrast;
- checked to fit its screen, and to need no more than a screen of 1024×700;
- walked with Tab: every field that takes the focus is reached, and the focus stays inside;
- closed with Escape, as a person closes it; a dialog that stays open is a problem.

Qt's own file, print and input dialogs are photographed but not checked: their layout is Qt's.
"""
import re

import pytest
from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractSpinBox, QApplication, QComboBox, QFileDialog, QInputDialog, QLineEdit, QListView,
    QMessageBox, QPlainTextEdit, QRadioButton, QTextEdit, QTreeView, QWidget,
)

from looks import cut_off, low_contrast, name_of, overlapping
from sweep import REPORTS, STATES, Sweep, Watcher, describe

pytestmark = pytest.mark.manual

SMALL_SCREEN = (1024, 700)                     # a small laptop, less the panels of the desktop
QT_OWN = (QFileDialog, QPrintDialog, QPrintPreviewDialog, QInputDialog)
FIELDS = (QLineEdit, QAbstractSpinBox, QComboBox, QAbstractButton, QPlainTextEdit, QTextEdit, QListView, QTreeView)


def fields(dialog):
    return [
        widget for widget in dialog.findChildren(QWidget)
        if isinstance(widget, FIELDS) and widget.isVisibleTo(dialog) and widget.isEnabled()
        and widget.focusPolicy() & Qt.TabFocus and widget.window() is dialog and widget.focusProxy() is None
    ]


def tab_walk(dialog):
    """(fields Tab never reached, the focus left the dialog)."""
    wanted = fields(dialog)
    if not wanted:
        return [], False
    dialog.activateWindow()
    wanted[0].setFocus(Qt.TabFocusReason)
    QApplication.processEvents()
    if QApplication.focusWidget() is None:
        return [], False                       # the platform gives no focus: nothing to say
    reached, left = set(), False
    for _step in range(len(wanted) * 3 + 5):
        focus = QApplication.focusWidget()
        if focus is not None and focus.window() is not dialog:
            left = True
            break
        reached.add(id(focus))
        QTest.keyClick(focus or dialog, Qt.Key_Tab)
        QApplication.processEvents()
    missing = [widget for widget in wanted if id(widget) not in reached and not any(id(child) in reached for child in widget.findChildren(QWidget))]
    # In a group of radio buttons Tab stops on the chosen one; the arrows move among them.
    reached_groups = {id(widget.parentWidget()) for widget in wanted if isinstance(widget, QRadioButton) and id(widget) in reached}
    missing = [widget for widget in missing if not (isinstance(widget, QRadioButton) and widget.autoExclusive() and id(widget.parentWidget()) in reached_groups)]
    return [name_of(widget) for widget in missing], left


class Inspector(Watcher):
    """Looks at each dialog, then closes it with Escape."""

    language = "en"

    def __init__(self, files):
        super().__init__(files)
        self.photos = {}                       # file name of the photo → the dialog it shows

    def _cancel(self, dialog):
        self._inspect(dialog)
        focus = QApplication.focusWidget()
        target = focus if focus is not None and focus.window() is dialog else dialog
        QTest.keyClick(target, Qt.Key_Escape)

    def _inspect(self, dialog):
        title = describe(dialog)
        folder = REPORTS / "every-dialog" / self.language
        folder.mkdir(parents=True, exist_ok=True)
        text = re.sub(r"<[^>]+>", " ", dialog.text()).split("/")[0][:40] if isinstance(dialog, QMessageBox) else ""
        name = re.sub(r"[^\w]+", "-", f"{type(dialog).__name__}-{dialog.windowTitle()}-{text}").strip("-")
        if name not in self.photos:
            self.photos[name] = title
            dialog.grab().save(str(folder / f"{name}.png"))
        if isinstance(dialog, QT_OWN):
            return
        # QWidget.width(dialog), not dialog.width(): a dialog may have a field called width.
        size, room, least = QWidget.size(dialog), dialog.screen().availableGeometry(), dialog.minimumSizeHint()
        if size.width() > room.width() or size.height() > room.height():
            self.problems.append(f"{title} is {size.width()}×{size.height()}: larger than its screen, {room.width()}×{room.height()}")
        if least.width() > SMALL_SCREEN[0] or least.height() > SMALL_SCREEN[1]:
            self.problems.append(f"{title} needs at least {least.width()}×{least.height()}: more than a screen of {SMALL_SCREEN[0]}×{SMALL_SCREEN[1]}")
        self.problems += [f"{title}: cut off: {text}" for text in cut_off(dialog)]
        self.problems += [f"{title}: {text}" for text in overlapping(dialog)]
        self.problems += [f"{title}: low contrast: {text}" for text in low_contrast(dialog)]
        missing, left = tab_walk(dialog)
        if missing:
            self.problems.append(f"{title}: Tab never reaches {', '.join(missing[:5])}")
        if left:
            self.problems.append(f"{title}: Tab takes the focus out of the dialog")


# Example and Board open nearly every dialog: Empty, Simulating and Program add only messages
# that say the same in other words, and are swept by test_every_action.
DIALOG_STATES = [state for state in STATES if state.name in ("example", "board")]


@pytest.mark.parametrize("language", ["en", "it"])
@pytest.mark.parametrize("state_class", DIALOG_STATES, ids=[state.name for state in DIALOG_STATES])
def test_every_dialog(qtbot, tmp_path, monkeypatch, state_class, language):
    inspector = type("Inspector", (Inspector,), {"language": language})
    with Sweep(qtbot, monkeypatch, tmp_path, state_class, watcher_class=inspector, language=language) as sweep:
        sweep.run_entries(sweep.action_entries() + sweep.menu_entries(), "cancel")
        photos = sweep.watcher.photos
    print(f"\n{language}, {state_class.name}: {len(photos)} dialogs photographed in {REPORTS / 'every-dialog' / language}")
    sweep.report("every-dialog", f"{state_class.name}-{language}")
