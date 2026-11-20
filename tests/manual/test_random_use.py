"""Random use of the IDE: sequences of what a person does, with checks after every step.

    pytest tests/manual/test_random_use.py --manual
    LMS_RANDOM_EXAMPLES=200 pytest tests/manual/test_random_use.py --manual   # longer

A hypothesis state machine chooses the next operation: a widget from the toolbox, a click or a
drag on the page, arrow keys, a property typed in the panel, Edit and Arrange entries, undo and
redo, pages, the code of a handler, save and open again. Each one goes through the window as a
person's would, with the self-test's driver. After every step: the canvas shows the widgets of
its page, the Properties panel follows the selection, the title's * says whether there is
something to save, the project is valid and nothing raised. At the end: undo all gives the
project of the start, redo all gives it back.

When a check fails, hypothesis makes the sequence as short as it can and prints it, with a line
to replay it: a short sequence becomes an ordinary test.
"""
import json
import os

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule, run_state_machine_as_test

from copper_and_code_studio.core.validation import validate_project

pytestmark = pytest.mark.manual

EXAMPLES = int(os.environ.get("LMS_RANDOM_EXAMPLES", "25"))
STEPS = int(os.environ.get("LMS_RANDOM_STEPS", "30"))
TYPES = ["button", "label", "slider", "switch", "panel", "checkbox", "bar"]
EDIT = ["copy", "paste", "cut", "duplicate", "delete", "select_all"]
ARRANGE = ["Align Left", "Align Center", "Align Right", "Align Top", "Align Middle", "Align Bottom", "Distribute Horizontally", "Distribute Vertically", "Bring to Front", "Send to Back"]


def snapshot(project):
    data = project.to_dict()
    data.pop("currentPageId", None)            # which page is shown is not a change of the project
    data.pop("projectId", None)                # Save As to another file makes another project, on purpose
    return json.dumps(data, sort_keys=True, default=str)


def make_machine(directory):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest

    from copper_and_code_studio.selftest.driver import Ide, StepFailed, sleep
    from copper_and_code_studio.selftest.report import Report

    class RandomUse(RuleBasedStateMachine):
        def __init__(self):
            super().__init__()
            RandomUse.runs = getattr(RandomUse, "runs", 0) + 1
            self.directory = directory / f"run-{RandomUse.runs}"
            self.directory.mkdir(parents=True)
            self.ide = Ide(Report(self.directory / "report", echo=lambda text: None), "random use", self.directory)
            self.ide.choose(self.ide.window.new_action)
            self.start = snapshot(self.project)
            self.saves = 0

        # ---- helpers ----

        @property
        def window(self):
            return self.ide.window

        @property
        def project(self):
            return self.window.document.project

        def view(self):
            return self.window.current_designer()

        def page(self):
            view = self.view()
            return next(page for page in self.project.pages if page.id == view.designer_scene.page_id)

        def designer_shown(self):
            return self.view() is not None

        def selected(self):
            return self.view().designer_scene.selected_names() if self.designer_shown() else []

        def point(self, fx, fy):
            display = self.project.display
            return QPointF(fx * (display.width - 1), fy * (display.height - 1))

        def step(self, what):
            """Run what; a dialog nobody expected is answered with Cancel, as the watcher does, and noted."""
            what()
            sleep(30)
            self.ide._unexpected.clear()       # Cancel is a fine answer to an unknown question

        # ---- what a person does ----

        @precondition(lambda self: self.designer_shown())
        @rule(kind=st.sampled_from(TYPES), fx=st.floats(0.05, 0.9), fy=st.floats(0.05, 0.9))
        def add_from_toolbox(self, kind, fx, fy):
            point = self.point(fx, fy)
            self.step(lambda: self.ide.add_widget(kind, point.x(), point.y()))

        @precondition(lambda self: self.designer_shown())
        @rule(fx=st.floats(0, 1), fy=st.floats(0, 1), shift=st.booleans())
        def click_on_the_page(self, fx, fy, shift):
            view = self.view()
            position = view.mapFromScene(self.point(fx, fy))
            QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.ShiftModifier if shift else Qt.NoModifier, position)
            sleep(30)

        @precondition(lambda self: len(self.selected()) >= 1)
        @rule(dx=st.integers(-120, 120), dy=st.integers(-120, 120))
        def drag_the_selection(self, dx, dy):
            view = self.view()
            item = view.designer_scene.widget_items[self.project.find_widget(self.selected()[0]).id]
            start = view.mapFromScene(item.sceneBoundingRect().center())
            end = start + QPoint(dx, dy)
            QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
            for fraction in (0.33, 0.66, 1.0):
                QTest.mouseMove(view.viewport(), start + QPoint(int(dx * fraction), int(dy * fraction)))
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, end)
            sleep(30)

        @precondition(lambda self: len(self.selected()) >= 1)
        @rule(key=st.sampled_from([Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]), shift=st.booleans())
        def arrow_keys(self, key, shift):
            view = self.view()
            view.setFocus()
            QTest.keyClick(view.viewport(), key, Qt.ShiftModifier if shift else Qt.NoModifier)
            sleep(30)

        @precondition(lambda self: len(self.selected()) == 1)
        @rule(prop=st.sampled_from(["x", "y", "width", "height"]), value=st.integers(0, 400))
        def type_a_property(self, prop, value):
            if prop in ("width", "height"):
                value = max(10, value)
            self.ide.set_property(prop, value)

        @precondition(lambda self: self.designer_shown())
        @rule(entry=st.sampled_from(EDIT))
        def edit_menu(self, entry):
            action = {"copy": self.window.copy_action, "paste": self.window.paste_action, "cut": self.window.cut_action, "duplicate": self.window.duplicate_action,
                      "delete": self.window.delete_action, "select_all": self.window.select_all_action}[entry]
            if action.isEnabled():
                self.view().setFocus()
                self.step(action.trigger)

        @precondition(lambda self: len(self.selected()) >= 1)
        @rule(entry=st.sampled_from(ARRANGE))
        def arrange_menu(self, entry):
            action = next(action for action in self.window.arrange_menu.actions() if action.text().replace("&", "") == entry)
            if action.isEnabled():
                self.step(action.trigger)

        @rule(redo=st.booleans(), times=st.integers(1, 3))
        def undo_or_redo(self, redo, times):
            action = self.window.redo_action if redo else self.window.undo_action
            for _ in range(times):
                if action.isEnabled():
                    self.step(action.trigger)

        @precondition(lambda self: len(self.project.pages) < 4)
        @rule()
        def add_a_page(self):
            self.step(lambda: self.ide.choose(self.window.add_page_action))

        @rule(index=st.integers(0, 3))
        def show_a_page(self, index):
            pages = self.project.pages
            page = pages[index % len(pages)]
            entry = self.window.designers.get(page.id)
            if entry is not None:
                bar = self.window.tabs.tabBar()
                QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(self.window.tabs.indexOf(entry[1])).center())
                sleep(30)

        @precondition(lambda self: len(self.selected()) == 1 and self.project.find_widget(self.selected()[0]).type == "button")
        @rule(text=st.sampled_from(["print('clicked')", "ui.load_page(0)", "x = 1\nprint(x)"]))
        def write_a_handler(self, text):
            self.ide.open_handler("CLICKED")
            self.ide.type_code(text, replace=True)
            bar = self.window.tabs.tabBar()
            QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(0).center())   # back to the first page
            sleep(30)

        @precondition(lambda self: self.saves < 2)
        @rule()
        def save_and_open_again(self):
            self.saves += 1
            path = self.directory / f"project-{self.saves}.json"
            before = snapshot(self.project)
            self.ide.save_as(path)
            self.ide.choose(self.window.new_action)
            assert self.window.open_project(path), f"{path} did not open"
            sleep(30)
            assert snapshot(self.project) == before, "the project opened again is not the one saved"
            self.start = snapshot(self.project)    # the undo history starts again from the file

        # ---- checks after every step ----

        @invariant()
        def trace(self):
            """The state after the last steps, kept for the message of a failed check; LMS_RANDOM_TRACE=1 also prints it."""
            shown = self.page().name if self.designer_shown() else self.window.tabs.tabText(self.window.tabs.currentIndex())
            line = f"on {shown}: canvas {self.selected()} panel {self.window.properties.names} pages {[page.name for page in self.project.pages]} undo {self.window.document.undo_stack.index()}/{self.window.document.undo_stack.count()}"
            self.history = (getattr(self, "history", []) + [line])[-10:]
            if os.environ.get("LMS_RANDOM_TRACE"):
                print("    " + line)

        def recent(self):
            return "\nthe last steps:\n  " + "\n  ".join(getattr(self, "history", []))

        @invariant()
        def nothing_raised(self):
            crashes, self.ide._crashes[:] = list(self.ide._crashes), []
            assert not crashes, "the IDE raised:\n" + "\n".join(crashes)

        @invariant()
        def the_project_is_valid(self):
            validate_project(self.project)

        @invariant()
        def the_canvas_shows_its_page(self):
            if not self.designer_shown():
                return
            from copper_and_code_studio.gen.components import is_component

            scene = self.view().designer_scene
            drawn = set(scene.widget_items)
            wanted = {widget.id for widget in self.page().widgets if not is_component(widget.type)}
            assert drawn == wanted, f"the canvas draws {sorted(drawn - wanted)} more and {sorted(wanted - drawn)} less than its page"

        @invariant()
        def the_properties_follow_the_selection(self):
            if not self.designer_shown():
                return
            try:
                self.ide.wait(lambda: sorted(self.window.properties.names) == sorted(self.selected()), "the Properties panel to follow the selection", 1000)
            except StepFailed:
                raise AssertionError(f"selection {self.selected()}, Properties panel {self.window.properties.names}" + self.recent()) from None

        @invariant()
        def the_title_says_if_there_is_something_to_save(self):
            modified = self.window.document.modified
            assert ("*" in self.window.windowTitle()) == modified, f"title {self.window.windowTitle()!r}, modified {modified}"

        # ---- at the end ----

        def teardown(self):
            try:
                end = snapshot(self.project)
                stack = self.window.document.undo_stack
                index = stack.index()
                stack.setIndex(0)
                sleep(30)
                assert snapshot(self.project) == self.start, "undo all does not give the project of the start"
                stack.setIndex(stack.count())
                sleep(30)
                redone = snapshot(self.project)
                if index == stack.count():
                    assert redone == end, "redo all does not give the project back"
            finally:
                self.window.document.undo_stack.setClean()
                self.ide.close()

    return RandomUse


def test_random_use(qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs)
    monkeypatch.setattr(QMessageBox, "question", vars(QMessageBox)["question"])   # the driver's watcher answers
    machine = make_machine(tmp_path)
    run_state_machine_as_test(machine, settings=settings(max_examples=EXAMPLES, stateful_step_count=STEPS, deadline=None,
                                                         suppress_health_check=list(HealthCheck), print_blob=True))
