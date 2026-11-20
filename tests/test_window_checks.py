"""Cheap checks of the main window, in English and in Italian: no shortcut used twice, no menu
with two entries on the same underlined letter, no text cut off at a common laptop size."""
import pytest
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu

from looks import cut_off, english_left, overlapping


@pytest.fixture(params=["en", "it"])
def window(qtbot, request):
    from copper_and_code_studio.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.change_language(request.param)
    yield window
    window.change_language("en")


def test_no_shortcut_is_used_twice(window):
    used = {}
    for action in window.findChildren(QAction):
        for sequence in action.shortcuts():
            key = sequence.toString(QKeySequence.PortableText)
            if key:
                used.setdefault(key, set()).add(action.text().replace("&", ""))
    assert {key: names for key, names in used.items() if len(names) > 1} == {}


def test_no_menu_underlines_the_same_letter_twice(window):
    def letter(text):
        index = text.replace("&&", "").find("&")
        return text.replace("&&", "")[index + 1].lower() if index >= 0 and index + 1 < len(text.replace("&&", "")) else None

    clashes = []
    menus = [window.menuBar()] + window.findChildren(QMenu)
    for menu in menus:
        seen = {}
        for action in menu.actions():
            key = letter(action.text()) if not action.isSeparator() and action.isVisible() else None
            if key:
                if key in seen:
                    clashes.append(f"{menu.title() or 'menu bar'}: “{seen[key]}” and “{action.text()}” on {key}")
                seen[key] = action.text()
    assert clashes == []


def test_no_text_is_cut_off_at_1280_by_800(window):
    window.resize(1280, 800)
    window.show()
    for _ in range(5):
        QApplication.processEvents()
    assert cut_off(window) == []
    assert overlapping(window) == []


def test_nothing_stays_in_english_after_switching_to_italian(qtbot):
    from copper_and_code_studio.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.change_language("it")
    try:
        english = english_left(window)
    finally:
        window.change_language("en")
    assert english == []


def test_a_text_the_ide_changed_is_kept_when_the_language_changes(qtbot, tmp_path):
    from copper_and_code_studio.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()
    window.files_panel.set_folder(tmp_path / "first")
    window.change_language("it")
    window.files_panel.set_folder(tmp_path / "second")
    window.change_language("en")
    assert window.files_panel.folder_label.text() == "second"
    assert window.files_panel.folder_label.toolTip() == str((tmp_path / "second").resolve())


def test_the_standard_buttons_follow_the_language(qtbot):
    """Save, Cancel and Close come from Qt's own translation, which the IDE loads."""
    from PySide6.QtWidgets import QMessageBox

    from copper_and_code_studio.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    def buttons():
        box = QMessageBox(QMessageBox.Question, "", "", QMessageBox.Save | QMessageBox.Cancel)
        return sorted(button.text().replace("&", "") for button in box.buttons())

    window.change_language("it")
    try:
        assert buttons() == ["Annulla", "Salva"]
    finally:
        window.change_language("en")
    assert buttons() == ["Cancel", "Save"]


def test_no_old_tab_bar_of_the_docks_is_left_on_the_screen(qtbot):
    """Qt 6.12 left "Output | Errors" over the Output panel, a second bar for docks that the real
    one shows; dragging its tabs crashed Qt."""
    from PySide6.QtWidgets import QTabBar

    from copper_and_code_studio.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    bars = [bar for bar in window.findChildren(QTabBar) if bar.parent() is window and bar.isVisible()]
    docks = [{bar.tabData(index) for index in range(bar.count())} for bar in bars]
    shown_twice = [[bar.tabText(index) for index in range(bar.count())] for bar, mine in zip(bars, docks) if any(mine < other for other in docks)]
    assert shown_twice == []


def test_every_control_has_a_name_for_a_screen_reader(window):
    """A list or a field without text, tooltip or accessible name is read as "list" or "text":
    the toolbox, the trees, the Properties panel and the Output had no name."""
    from looks import nameless

    window.resize(1400, 900)
    window.show()
    QApplication.processEvents()
    assert nameless(window) == []
