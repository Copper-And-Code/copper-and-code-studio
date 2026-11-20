"""The only module of the showreel that touches the IDE.

It drives a real MainWindow, offscreen, through what the IDE already has: the project document,
the page tabs, the background preview and the simulator panel. If the IDE changes, this file is
the one to fix.
"""
import copy
import os
import shutil
import tempfile
import time
from pathlib import Path


def prepare_environment():
    """Offscreen Qt and a temporary configuration folder; call before anything imports Qt."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    config = tempfile.mkdtemp(prefix="showreel-config-")
    os.environ["XDG_CONFIG_HOME"] = config     # the owner's QSettings stay untouched
    return config


class IdeError(RuntimeError):
    pass


class Ide:
    """A MainWindow with an example opened as an empty project, and the steps to fill and run it."""

    def __init__(self, size=(1600, 1000)):
        from PySide6.QtWidgets import QApplication, QMessageBox

        from copper_and_code_studio.ui import theme

        self.app = QApplication.instance() or QApplication(["copper-and-code-studio-showreel"])
        self.app.setWindowIcon(theme.app_icon())
        # Nothing must wait for an answer that nobody can give offscreen.
        self._question = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *arguments, **options: QMessageBox.Discard)
        from copper_and_code_studio.ui.main_window import MainWindow

        self.window = MainWindow()
        self.window.resize(*size)
        self.window.show()
        if not self.window.preview_action.isChecked():
            self.window.preview_action.setChecked(True)
        self.full = None                      # the example as it is in examples/
        self.added = set()                    # ids of the widgets already on the pages
        self.hidden = set()                   # handlers left out, to be typed
        self.module_lines = None              # lines of the general code left out, to be typed
        self.sim_frames = 0
        self._renders = 0
        self.window.preview_renderer.rendered.connect(self._rendered)
        self.window.sim_panel.frameReady.connect(self._sim_frame)

    def _rendered(self, *_result):
        self._renders += 1

    def _sim_frame(self):
        self.sim_frames += 1

    # ---- Time ----

    def pump(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.002)
        self.app.processEvents()

    def wait_for(self, condition, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(0.002)
        self.app.processEvents()
        return condition()

    def settle(self, timeout=5.0):
        """Wait until the canvas of the current page shows the project as it is now."""
        from copper_and_code_studio.build.preview import design_key
        from copper_and_code_studio.ui.designer.scene import DesignerView

        self.app.processEvents()
        view = self.window.tabs.currentWidget()
        if not isinstance(view, DesignerView):
            self.pump(0.05)
            return True
        renderer = self.window.preview_renderer
        project = self.window.document.project
        page_id = view.designer_scene.page_id
        index = next((i for i, page in enumerate(project.pages) if page.id == page_id), None)
        if index is None:
            return True
        key = design_key(project, index)
        start = self._renders

        def idle():
            if renderer.busy or renderer._timer.isActive():
                return False
            # Done when the frame of this design arrived, or when a render ended without one.
            return renderer._done.get(page_id) == key or self._renders > start

        settled = self.wait_for(idle, timeout)
        self.pump(0.02)                       # let the scene paint the new frame
        return settled

    # ---- The project ----

    def open_empty(self, example, workdir, handlers=(), module_lines=None):
        """Save the example with empty pages into workdir and open it.

        Code and modules are kept, except what the storyboard types later: the handlers named
        in handlers, and the lines (first, last) of the general code in module_lines.
        """
        from copper_and_code_studio.core.model import Project

        source = Path(example)
        if source.is_dir():
            source = source / "project.json"
        if not source.is_file():
            raise IdeError(f"{source} does not exist")
        self.full = Project.load(source)
        empty = Project.load(source)
        for page in empty.pages:
            page.widgets[:] = []
        for name in handlers:
            if name not in empty.code.handlers:
                raise IdeError(f"the example has no handler {name!r}")
            del empty.code.handlers[name]
        self.hidden = set(handlers)
        self.module_lines = None
        if module_lines:
            first, last = module_lines
            lines = empty.code.module.split("\n")
            if not 1 <= first <= last <= len(lines):
                raise IdeError(f"the general code has {len(lines)} lines: lines {first}-{last} do not exist")
            empty.code.module = "\n".join(lines[:first - 1] + lines[last:])
            self.module_lines = (first, last)
        workdir = Path(workdir)
        if workdir.exists():
            shutil.rmtree(workdir)
        workdir.mkdir(parents=True)
        target = workdir / "project.json"
        empty.save(target)
        self.window.open_project(target)
        self.added.clear()
        self.show_page(0)
        self.settle()
        return target

    def pages(self):
        return [(page.name, len(page.widgets)) for page in self.full.pages]

    def page_index(self, name):
        for index, page in enumerate(self.full.pages):
            if page.name == name or page.id == name:
                return index
        raise IdeError(f"no page named {name!r}; the pages are " + ", ".join(page.name for page in self.full.pages))

    def missing(self, page_index):
        """The widgets of a page not added yet, in the order of project.json (parents first)."""
        return [widget for widget in self.full.pages[page_index].widgets if widget.id not in self.added]

    def widget(self, name):
        for index, page in enumerate(self.full.pages):
            for widget in page.widgets:
                if widget.name == name or widget.id == name:
                    return index, widget
        raise IdeError(f"no widget named {name!r} in the example")

    def add(self, page_index, widgets, description=None):
        """Add widgets to a page in one undoable change, as the IDE does for a paste."""
        widgets = [widget for widget in widgets if widget.id not in self.added]
        if not widgets:
            return

        hidden = self.hidden

        def mutate(project):
            for widget in copy.deepcopy(widgets):
                # A handler still to be typed is not linked yet: the Events tab links it.
                widget.events = {event: name for event, name in widget.events.items() if name not in hidden}
                project.pages[page_index].widgets.append(widget)

        self.window.document.execute(description or f"Add {len(widgets)} widgets", mutate)
        self.added.update(widget.id for widget in widgets)

    def show_page(self, page_index):
        page_id = self.window.document.project.pages[page_index].id
        entry = self.window.designers.get(page_id)
        if entry is None:
            raise IdeError(f"the page {page_index} has no designer tab")
        self.window.tabs.setCurrentWidget(entry[1])
        self.app.processEvents()

    def save(self):
        if not self.window.save_project():
            raise IdeError("the project could not be saved")

    # ---- Running ----

    def start(self, timeout=20.0):
        """Start in the simulator and wait for its first frame."""
        frames = self.sim_frames
        if not self.window.run_project():
            raise IdeError("Start failed; the Output panel says:\n" + self.output_text()[-2000:])
        if not self.wait_for(lambda: self.sim_frames > frames, timeout):
            raise IdeError("the simulator sent no frame; the Output panel says:\n" + self.output_text()[-2000:])

    def running(self):
        return self.window.sim_panel.running

    def stop(self):
        if self.running():
            self.window.stop_simulation()
            self.wait_for(lambda: not self.running(), 5)

    def output_text(self):
        return self.window.output.toPlainText()

    def errors_text(self):
        errors = self.window.errors
        if hasattr(errors, "topLevelItemCount"):
            return "\n".join(errors.topLevelItem(i).text(0) for i in range(errors.topLevelItemCount()))
        return ""

    # ---- Frames ----

    def grab(self):
        """The whole window as a QImage, as a screenshot would show it."""
        return self.window.grab().toImage()

    def close(self):
        from PySide6.QtWidgets import QMessageBox

        self.stop()
        self.window.close()
        self.app.processEvents()
        QMessageBox.question = self._question

    # ---- Places of the window, for balloons and the cursor ----

    def _in_window(self, widget, rect=None):
        """A rect of a widget, in the coordinates of the window; None if the widget is not shown."""
        from PySide6.QtCore import QRect

        if widget is None or not widget.isVisible():
            return None
        rect = widget.rect() if rect is None else rect
        return QRect(widget.mapTo(self.window, rect.topLeft()), rect.size())

    def _designer(self):
        from copper_and_code_studio.ui.designer.scene import DesignerView

        view = self.window.tabs.currentWidget()
        return view if isinstance(view, DesignerView) else None

    def anchor(self, name):
        """The rect of a named place of the window (see the plan, section 6), or None if not shown."""
        if name is None:
            return None
        head, _, rest = name.partition(".")
        window = self.window
        if head == "toolbox":
            return self.toolbox_item(rest) if rest else self._in_window(window.toolbox_panel)
        if head == "project":
            return self._in_window(window.project_tree)
        if head == "properties" and rest == "events":
            tabs = window.properties.tabs
            return self._in_window(tabs.tabBar(), tabs.tabBar().tabRect(1))
        if head == "properties" and rest:
            try:
                return self.property_row(rest)[1]
            except IdeError:
                return None                   # not selected yet: the balloon waits
        if head == "properties":
            return self._in_window(window.properties)
        if head == "events" and rest:
            try:
                return self.event_row(rest)[1]
            except IdeError:
                return None
        if head == "canvas":
            return self.canvas_item(rest) if rest else self._in_window(self._designer())
        if head == "code" and rest == "editor":
            return self._in_window(window.code_panel.editor)
        if head == "code" and rest == "signature":
            return self._in_window(window.code_panel.signature)
        if head == "code":
            return self._in_window(window.code_panel)
        if head == "simulator":
            return self._in_window(window.sim_panel.screen)
        if head == "toolbar" and rest == "start":
            return self._in_window(window.run_button)
        if head == "toolbar" and rest == "resolution":
            return self._in_window(window.resolution_selector)
        if head == "output":
            return self._in_window(window.output)
        raise IdeError(f"unknown anchor {name!r}")

    def toolbox_item(self, widget_type):
        """The rect of the Toolbox entry of a widget type, scrolled into view."""
        from PySide6.QtCore import Qt

        toolbox = self.window.toolbox
        for item in toolbox.widget_items():
            if item.data(Qt.UserRole) == widget_type:
                toolbox.scrollToItem(item)
                self.app.processEvents()
                return self._in_window(toolbox.viewport(), toolbox.visualItemRect(item))
        return None

    def toolbox_entry(self, widget_type):
        """(icon, text) of the Toolbox entry of a widget type, for the dragged ghost."""
        from PySide6.QtCore import Qt

        for item in self.window.toolbox.widget_items():
            if item.data(Qt.UserRole) == widget_type:
                return item.icon(), item.text()
        return None, widget_type

    def canvas_item(self, name):
        """The rect of a widget on the canvas of the current page, by name or id."""
        view = self._designer()
        if view is None:
            return None
        project = self.window.document.project
        ids = {widget.id for widget in project.widgets if widget.name == name or widget.id == name}
        for widget_id, item in view.designer_scene.widget_items.items():
            if widget_id in ids:
                polygon = view.mapFromScene(item.sceneBoundingRect())
                rect = polygon.boundingRect().intersected(view.viewport().rect())
                return self._in_window(view.viewport(), rect) if not rect.isEmpty() else None
        return None

    def select(self, name):
        """Select a widget on the canvas of its page, as a click would; the Properties panel follows."""
        page_index, widget = self.widget(name)
        self.show_page(page_index)
        view = self._designer()
        scene = view.designer_scene
        scene.clearSelection()
        item = scene.widget_items.get(widget.id)
        if item is None:
            raise IdeError(f"{name} is not on the canvas yet: add it before selecting it")
        item.setSelected(True)
        self.app.processEvents()

    # ---- Events, code and properties ----

    def show_properties_tab(self, events):
        tabs = self.window.properties.tabs
        tabs.setCurrentIndex(1 if events else 0)
        self.app.processEvents()

    def event_row(self, event):
        """(index, rect) of an event in the Events tab of the selected widget."""
        panel = self.window.properties
        model = panel.events_model
        for row in range(model.rowCount()):
            if model.item(row, 0).text() == event:
                index = model.index(row, 0)
                panel.events_view.scrollTo(index)
                self.app.processEvents()
                rect = panel.events_view.visualRect(index).united(panel.events_view.visualRect(model.index(row, 2)))
                return index, self._in_window(panel.events_view.viewport(), rect)
        raise IdeError(f"the selected widget has no event {event!r} in the Events tab")

    def activate_event(self, event):
        """Double click on the event: the IDE creates the handler and opens it in the Code tab."""
        index, _rect = self.event_row(event)
        self.window.properties.events_view.doubleClicked.emit(index)
        self.app.processEvents()

    def open_handler(self, handler):
        """Open a handler of a page (or any handler) in the Code tab, creating it as the IDE does."""
        code = self.full.code.handlers[handler]

        def mutate(project):
            project.ensure_handler(code.widget, code.event)

        self.window.document.execute("Create Handler", mutate)
        self.window.open_handler(code.widget, code.event)
        self.app.processEvents()

    def handler_body(self, handler):
        return self.full.code.handlers[handler].body

    def open_general_code(self, line):
        """The general code in the Code tab, with the cursor at the start of a line."""
        from PySide6.QtGui import QTextCursor

        panel = self.window.code_panel
        self.window.tabs.setCurrentWidget(panel)
        panel.object_combo.setCurrentIndex(0)
        editor = panel.editor
        block = editor.document().findBlockByNumber(max(0, line - 1))
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.StartOfBlock)
        editor.setTextCursor(cursor)
        editor.centerCursor()
        editor.setFocus()
        self.app.processEvents()

    def module_text(self, first, last):
        """The lines of the general code left out, with the line break that ends them."""
        lines = self.full.code.module.split("\n")
        return "\n".join(lines[first - 1:last]) + "\n"

    def type_text(self, text):
        """Insert text at the cursor of the code editor, as typing would; the IDE stores it."""
        editor = self.window.code_panel.editor
        cursor = editor.textCursor()
        cursor.insertText(text)
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        self.app.processEvents()

    def restore_hidden(self):
        """Whatever was left out to be typed and was not typed: put back, so that the app runs."""
        restored = []
        handlers = [name for name in self.hidden if not self.window.document.project.code.handlers.get(name)
                    or not self.window.document.project.code.handlers[name].body.strip()]
        lines = self.module_lines
        if not handlers and not lines:
            return restored
        full = self.full

        def mutate(project):
            for name in handlers:
                code = full.code.handlers[name]
                project.ensure_handler(code.widget, code.event)
                project.code.handlers[name].body = code.body
            if lines:
                project.code.module = full.code.module

        self.window.document.execute("Restore code", mutate)
        restored += handlers + (["general code lines %d-%d" % lines] if lines else [])
        self.hidden.clear()
        self.module_lines = None
        return restored

    def mark_typed(self, handler=None, module=False):
        if handler:
            self.hidden.discard(handler)
        if module:
            self.module_lines = None

    def property_row(self, prop):
        """(value item, rect) of a property of the selected widget in the Properties tab."""
        from copper_and_code_studio.ui.properties.panel import DESCRIPTOR_ROLE

        panel = self.window.properties
        model = panel.model

        def rows(parent):
            for row in range(parent.rowCount()):
                yield parent.child(row, 0), parent.child(row, 1)
                yield from rows(parent.child(row, 0))

        known = []
        for label, value in rows(model.invisibleRootItem()):
            descriptor = value.data(DESCRIPTOR_ROLE) if value is not None else None
            if descriptor:
                known.append(descriptor.get("name"))
            if descriptor and descriptor.get("name") == prop:
                panel.view.scrollTo(value.index())
                self.app.processEvents()
                rect = panel.view.visualRect(label.index()).united(panel.view.visualRect(value.index()))
                return value, self._in_window(panel.view.viewport(), rect)
        raise IdeError(f"the Properties panel has no property {prop!r} for {', '.join(panel.names) or 'no widget'}; it has: {', '.join(map(str, known))}")

    def set_property(self, prop, value):
        """Change a property the way the Properties panel does when a value is typed in its row."""
        from PySide6.QtCore import Qt

        item, _rect = self.property_row(prop)
        panel = self.window.properties
        panel.view.setCurrentIndex(item.index())
        if isinstance(value, bool):
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)
        else:
            item.setText(str(value))
        self.app.processEvents()

    # ---- Input in the simulator ----

    def display_rect(self, name):
        """A widget's rect in display pixels, from the designer scene, whose coordinates are the display's."""
        page_index, widget = self.widget(name)
        page_id = self.window.document.project.pages[page_index].id
        entry = self.window.designers.get(page_id)
        item = entry[1].designer_scene.widget_items.get(widget.id) if entry else None
        if item is None:
            raise IdeError(f"{name} is not in the project: it cannot be touched")
        return item.sceneBoundingRect()

    def display_size(self):
        display = self.window.document.project.display
        return display.width, display.height

    def sim_to_window(self, x, y):
        """A point of the display, in the coordinates of the window, where the simulator shows it."""
        from PySide6.QtCore import QPointF

        screen = self.window.sim_panel.screen
        target = screen._target()
        width, height = self.display_size()
        local = QPointF(target.x() + x * target.width() / width, target.y() + y * target.height() / height)
        return QPointF(screen.mapTo(self.window, local.toPoint()))

    def pointer(self, x, y, pressed):
        """Touch input to the running app, as the mouse on the simulator screen sends it."""
        width, height = self.display_size()
        x, y = int(min(max(0, x), width - 1)), int(min(max(0, y), height - 1))
        self.window.sim_panel.send_pointer(x, y, pressed)
