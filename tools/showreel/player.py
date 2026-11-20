"""Plays the steps of a storyboard on the IDE and writes the frames.

Design steps change the project, wait until the IDE has settled, grab the window once and hold
that picture with the overlay drawn on it: the result does not depend on the speed of the
computer. Run steps grab the window at the video rate, in real time, while the simulator runs.
"""
import time

from PySide6.QtCore import QPointF

from .ide import IdeError
from .overlay import CAPTION, URL, Overlay, blend, ease

DESIGN = {"title", "create", "add", "fill", "select", "set", "page", "code", "end"}
RUN = {"start", "tap", "drag", "press", "release", "wait", "stop"}
REGRAB_EVERY = 5        # in the run phase, grab now and then even without a new simulator frame
CROSSFADE = 10          # frames from a card to the window and back
READ_SECONDS = 1.2      # a balloon stays at least this long, plus the time to read it
READ_CHARS = 18         # characters read per second


class Player:
    def __init__(self, ide, timeline, storyboard, example, workdir, log=print):
        self.ide = ide
        self.timeline = timeline
        self.storyboard = storyboard
        self.video = storyboard["video"]
        self.example = example
        self.workdir = workdir
        self.log = log
        self.notes = []                 # what was skipped or done differently, for the summary
        self.overlay = Overlay(tuple(self.video["window"]))
        self.base = None                # the last grab of the window, without overlay
        self.card = None                # the last card, to cross-fade from
        self.faded = 0                  # frames of that cross-fade written so far

    def play(self):
        steps = self.storyboard["step"]
        for number, step in enumerate(steps, 1):
            kind = step["do"]
            started = time.monotonic()
            before = self.timeline.count
            handler = getattr(self, "do_" + kind, None)
            if handler is None:
                self.note(f"step {number} ({kind}) is not implemented yet: skipped")
                continue
            self.timeline.mark(kind)
            self.overlay.caption = kind in DESIGN
            if kind not in ("title", "end"):
                self.balloon(step)
            handler(step)
            if kind in DESIGN and kind not in ("title", "end"):
                self.hold(step.get("hold", 1))
            self.read_balloon()
            self.log(f"  {number:2d} {kind:<7} {self.timeline.count - before:5d} frames, {time.monotonic() - started:5.1f} s")
        self.ide.stop()

    def note(self, text):
        self.notes.append(text)
        self.log("  note: " + text)

    # ---- Balloons ----

    def balloon(self, step):
        if step.get("balloon"):
            self.overlay.show_balloon(step["balloon"], step.get("anchor"))
        else:
            self.overlay.hide_balloon()

    def read_balloon(self):
        """Hold the picture until the balloon has been on screen long enough to be read."""
        balloon = self.overlay.balloon
        if balloon is None or self.base is None:
            return
        needed = self.timeline.frames_for(READ_SECONDS + len(balloon.text) / READ_CHARS)
        if balloon.frames < needed:
            if self.ide.running():
                self.record((needed - balloon.frames) / self.timeline.fps)
            else:
                self.emit(needed - balloon.frames)

    def _resolve(self):
        for balloon in self.overlay.balloons:
            if balloon.anchor is not None and balloon.target:
                balloon.rect = self.ide.anchor(balloon.anchor)

    # ---- Frames ----

    def render(self):
        frame = self.overlay.draw(self.base)
        self.overlay.tick()
        return frame

    def emit(self, frames=1):
        """Write frames of the current picture; frames are drawn one by one only while something moves."""
        for written in range(frames):
            if self.card is not None:
                self.faded += 1
                amount = min(1.0, self.faded / CROSSFADE)
                self.timeline.add(blend(self.card, self.render(), amount))
                if amount >= 1.0:
                    self.card = None
                continue
            if written and not self.overlay.animating:
                self.repeat(frames - written)
                return
            self.timeline.add(self.render())

    def repeat(self, frames=1):
        self.timeline.repeat(frames)
        self.overlay.advance(frames)

    def shot(self, frames=1):
        """Grab the settled window and write it."""
        self.ide.settle()
        self.base = self.ide.grab()
        self._resolve()
        self.emit(frames)

    def hold(self, seconds):
        if seconds and self.base is not None:
            self.emit(self.timeline.frames_for(seconds))

    def record(self, seconds, motion=None):
        """Grab the running IDE at the video rate for some seconds of real time.

        motion(t), if given, is called before each frame with the seconds elapsed: it moves the
        cursor and sends the touches, so the frame shows the cursor where the touch is.
        """
        fps = self.timeline.fps
        first = self.timeline.count
        start = time.monotonic()
        seen = -1
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= seconds:
                break
            due = first + int(elapsed * fps) + 1          # frames that should exist by now
            if self.timeline.count < due:
                late = due - self.timeline.count - 1
                if late and self.timeline.count > first:
                    self.repeat(late)                   # the computer fell behind: keep real speed
                if motion is not None:
                    motion(elapsed)
                fresh = self.ide.sim_frames != seen or (self.timeline.count - first) % REGRAB_EVERY == 0
                if fresh or motion is not None or self.overlay.animating or self.base is None:
                    seen = self.ide.sim_frames
                    self.base = self.ide.grab()
                    self._resolve()
                    self.timeline.add(self.render())
                else:
                    self.repeat()
            self.ide.app.processEvents()
            time.sleep(0.002)
        missing = first + self.timeline.frames_for(seconds) - self.timeline.count
        self.repeat(max(0, missing))

    # ---- The cursor ----

    def move_cursor(self, to, seconds=0.6):
        cursor = self.overlay.cursor
        start = cursor.pos if cursor.pos is not None else QPointF(self.overlay.width * 0.55, self.overlay.height * 0.6)
        frames = max(2, self.timeline.frames_for(seconds))
        for frame in range(1, frames + 1):
            t = ease(frame / frames)
            cursor.pos = QPointF(start.x() + (to.x() - start.x()) * t, start.y() + (to.y() - start.y()) * t)
            self.timeline.add(self.render())

    def click(self, frames=4):
        self.overlay.cursor.pressed = True
        self.emit_each(frames)
        self.overlay.cursor.pressed = False

    def emit_each(self, frames):
        for _ in range(frames):
            self.timeline.add(self.render())

    # ---- Design steps ----

    def do_title(self, step):
        self.overlay.caption = False
        self.base = self.ide.grab()
        self.card = self.overlay.card(self.base, self.video["title"], self.video.get("subtitle", ""))
        self.faded = 0
        self.timeline.add(self.card, self.timeline.frames_for(step.get("seconds", 2.5)))

    def do_end(self, step):
        self.overlay.hide_balloon()
        self.overlay.cursor.pos = None
        if self.base is None:
            self.base = self.ide.grab()
        lines = [step.get("text") or "Made with Copper and Code Studio", URL, CAPTION]
        card = self.overlay.card(self.base, self.video["title"], "", lines)
        last = self.overlay.draw(self.base)
        for frame in range(1, CROSSFADE + 1):
            self.timeline.add(blend(last, card, frame / CROSSFADE))
        self.timeline.add(card, self.timeline.frames_for(step.get("seconds", 3)))

    def do_create(self, step):
        # What the storyboard types later is left out of the project now.
        handlers = [code["handler"] for code in self.storyboard["step"] if code["do"] == "code" and code.get("handler")]
        module = next((code for code in self.storyboard["step"] if code["do"] == "code" and code.get("module")), None)
        lines = tuple(module.get("lines") or ()) if module else None
        if module and len(lines) != 2:
            raise IdeError("a code step with module = true needs lines = [first, last]")
        self.ide.open_empty(self.example, self.workdir, handlers, lines)
        self.shot()

    def do_add(self, step):
        """Each widget: the cursor takes its Toolbox entry and drops it where the widget goes."""
        with_cursor = step.get("cursor", True)
        for name in step.get("widgets", []):
            page_index, widget = self.ide.widget(name)
            self.ide.show_page(page_index)
            if not with_cursor:
                self.ide.add(page_index, [widget] + self._children(page_index, widget), f"Add {widget.name}")
                self.shot(self.timeline.frames_for(step.get("seconds_each", 0.6)))
                continue
            self.ide.settle()
            self.base = self.ide.grab()
            self._resolve()
            source = self.ide.toolbox_item(widget.type)
            self.base = self.ide.grab()            # the Toolbox may have scrolled
            if source is None:
                raise IdeError(f"the Toolbox has no entry for the type {widget.type} of {name}")
            # Add it now to learn where it goes; the frames still show the page before the drop.
            self.ide.add(page_index, [widget] + self._children(page_index, widget), f"Add {widget.name}")
            target = self.ide.canvas_item(widget.name)
            self.move_cursor(QPointF(source.center()), 0.5)
            self.click(3)
            self.overlay.cursor.ghost = self.ide.toolbox_entry(widget.type)
            drop = QPointF(target.center()) if target is not None else self.overlay.cursor.pos
            self.move_cursor(drop, 0.7)
            self.overlay.cursor.ghost = None
            self.shot(self.timeline.frames_for(step.get("seconds_each", 0.6)))

    def _children(self, page_index, parent):
        """The widgets inside a parent, at any depth, in the order of project.json."""
        inside = {parent.id}
        found = []
        for widget in self.ide.full.pages[page_index].widgets:
            if widget.parentId in inside:
                inside.add(widget.id)
                found.append(widget)
        return found

    def do_fill(self, step):
        self.overlay.cursor.pos = None
        if step.get("pages") == "rest":
            indexes = [i for i in range(len(self.ide.full.pages)) if self.ide.missing(i)]
        else:
            indexes = [self.ide.page_index(step["page"])] if "page" in step else [0]
        per_frame = max(1, int(step.get("per_frame", 3)))
        for index in indexes:
            self.ide.show_page(index)
            missing = self.ide.missing(index)
            for offset in range(0, len(missing), per_frame):
                self.ide.add(index, missing[offset:offset + per_frame])
                self.shot()
            self.hold(0.4)

    def do_select(self, step):
        self.select(step["widget"])
        self.ide.show_properties_tab(events=False)
        self.shot()

    def select(self, name):
        """The cursor clicks the widget on the canvas; the Properties panel shows it."""
        page_index, _widget = self.ide.widget(name)
        self.ide.show_page(page_index)
        self.ide.settle()
        self.base = self.ide.grab()
        self._resolve()
        target = self.ide.canvas_item(name)
        if target is None:
            raise IdeError(f"{name} is not on the canvas: add it before selecting it")
        self.move_cursor(QPointF(target.center()), 0.6)
        self.click(3)
        self.ide.select(name)

    def point_at(self, rect, seconds=0.5, double=False):
        """The cursor goes to a rect of the window and clicks it."""
        self.base = self.ide.grab()
        self._resolve()
        self.move_cursor(QPointF(rect.center()), seconds)
        self.click(2)
        if double:
            self.emit_each(1)
            self.click(2)

    def do_set(self, step):
        name, prop = step["widget"], step["prop"]
        if self.ide.window.properties.names != [name]:
            self.select(name)
        self.ide.show_properties_tab(events=False)
        _item, rect = self.ide.property_row(prop)
        self.point_at(rect)
        self.shot(self.timeline.frames_for(0.4))
        self.ide.set_property(prop, step["value"])
        self.shot()

    def do_code(self, step):
        per_frame = max(1, int(step.get("chars_per_frame", 3)))
        if step.get("module"):
            first, _last = step["lines"]
            self.overlay.cursor.pos = None
            self.ide.open_general_code(first)
            self.shot(self.timeline.frames_for(0.8))
            self.type(self.ide.module_text(*step["lines"]), per_frame)
            self.ide.mark_typed(module=True)
            return
        handler = step["handler"]
        code = self.ide.full.code.handlers.get(handler)
        if code is None:
            raise IdeError(f"the example has no handler {handler!r}")
        on_canvas = False
        if self.ide.full.find_widget(code.widget):
            page_index, _widget = self.ide.widget(code.widget)
            self.ide.show_page(page_index)
            on_canvas = self.ide.canvas_item(code.widget) is not None    # a timer or a buzzer is not
        if on_canvas:
            # As a user does: select the widget, Events tab, double click on the event.
            self.select(code.widget)
            self.shot()
            self.point_at(self.ide.anchor("properties.events"))
            self.ide.show_properties_tab(events=True)
            self.shot(self.timeline.frames_for(0.3))
            _index, rect = self.ide.event_row(code.event)
            self.point_at(rect, double=True)
            self.ide.activate_event(code.event)
        else:
            self.ide.open_handler(handler)
        self.overlay.cursor.pos = None
        self.shot(self.timeline.frames_for(0.8))
        self.type(self.ide.handler_body(handler), per_frame)
        self.ide.mark_typed(handler=handler)

    def type(self, text, per_frame):
        """Type text into the code editor, a few characters per frame; indentation comes at once."""
        chunks = []
        position = 0
        while position < len(text):
            if text[position] == "\n":
                end = position + 1
                while end < len(text) and text[end] in " \t":
                    end += 1                    # the editor indents: the spaces come with the line break
            else:
                end = position + per_frame
                newline = text.find("\n", position)
                if newline != -1:
                    end = min(end, newline)
            chunks.append(text[position:end])
            position = end
        for chunk in chunks:
            self.ide.type_text(chunk)
            self.base = self.ide.grab()
            self._resolve()
            self.timeline.add(self.render())

    def do_page(self, step):
        self.ide.show_page(self.ide.page_index(step["name"]))
        self.shot()

    # ---- Run steps ----

    def do_start(self, step):
        restored = self.ide.restore_hidden()
        if restored:
            self.note("before Start, code put back without frames: " + ", ".join(restored))
        incomplete = [self.ide.full.pages[i].name for i in range(len(self.ide.full.pages)) if self.ide.missing(i)]
        if incomplete:
            # The code may touch widgets of every page: the project must be whole before Start.
            self.note("before Start, completed without frames: " + ", ".join(incomplete))
            for index in range(len(self.ide.full.pages)):
                self.ide.add(index, self.ide.missing(index))
        button = self.ide.anchor("toolbar.start")
        if button is not None and self.base is not None:
            self.move_cursor(QPointF(button.center()), 0.6)
            self.click(3)
        self.overlay.cursor.pos = None
        self.ide.save()
        self.ide.start()
        self.record(step.get("hold", 1.5))

    def touch_point(self, step, prefix=""):
        """The display point of a step: widget = name (its centre), or x, y."""
        if not prefix and step.get("widget"):
            rect = self.ide.display_rect(step["widget"])
            return rect.center().x(), rect.center().y()
        try:
            return float(step[prefix + "x"]), float(step[prefix + "y"])
        except KeyError:
            raise IdeError(f"a {step['do']} step needs widget = name, or {prefix}x and {prefix}y") from None

    def glide(self, to, seconds, pressed=None):
        """Move the cursor in real time to a display point; with pressed, send the touch along the way."""
        cursor = self.overlay.cursor
        if cursor.pos is None:
            width, height = self.ide.display_size()
            cursor.pos = self.ide.sim_to_window(width * 0.8, height * 0.9)
        start = QPointF(cursor.pos)
        end = self.ide.sim_to_window(*to)
        from_display = self._display_of(start)

        def motion(elapsed):
            t = ease(elapsed / seconds) if seconds else 1.0
            cursor.pos = QPointF(start.x() + (end.x() - start.x()) * t, start.y() + (end.y() - start.y()) * t)
            if pressed is not None and from_display is not None:
                self.ide.pointer(from_display[0] + (to[0] - from_display[0]) * t, from_display[1] + (to[1] - from_display[1]) * t, pressed)

        self.record(seconds, motion)
        cursor.pos = end
        if pressed is not None:
            self.ide.pointer(*to, pressed)

    def _display_of(self, point):
        """The display point under a window point, or None if it is outside the simulator screen."""
        width, height = self.ide.display_size()
        top_left = self.ide.sim_to_window(0, 0)
        bottom_right = self.ide.sim_to_window(width, height)
        if not (top_left.x() <= point.x() <= bottom_right.x() and top_left.y() <= point.y() <= bottom_right.y()):
            return None
        return ((point.x() - top_left.x()) * width / (bottom_right.x() - top_left.x()),
                (point.y() - top_left.y()) * height / (bottom_right.y() - top_left.y()))

    def press_at(self, point, pressed):
        self.overlay.cursor.pressed = pressed
        self.ide.pointer(*point, pressed)

    def _need_running(self, step):
        if not self.ide.running():
            raise IdeError(f"a {step['do']} step needs the app running: put a start step before it")

    def do_tap(self, step):
        self._need_running(step)
        point = self.touch_point(step)
        self.glide(point, step.get("speed", 0.5))
        self.press_at(point, True)
        self.record(0.12)
        self.press_at(point, False)
        self.record(step.get("hold", 1))

    def do_drag(self, step):
        self._need_running(step)
        start = self.touch_point(step)
        if "x_to" not in step or "y_to" not in step:
            raise IdeError("a drag step needs x_to and y_to, in display pixels")
        end = (float(step["x_to"]), float(step["y_to"]))
        self.glide(start, step.get("speed", 0.5))
        self.press_at(start, True)
        self.record(0.1)
        self.glide(end, step.get("ms", 600) / 1000, pressed=True)
        self.press_at(end, False)
        self.record(step.get("hold", 1))

    def do_press(self, step):
        self._need_running(step)
        point = self.touch_point(step)
        self.glide(point, step.get("speed", 0.5))
        self.press_at(point, True)
        self.record(step.get("hold", 0.5))

    def do_release(self, step):
        self._need_running(step)
        point = self.touch_point(step) if (step.get("widget") or "x" in step) else self._display_of(self.overlay.cursor.pos)
        if point is None:
            raise IdeError("release: the cursor is not on the simulator screen; give widget or x, y")
        self.glide(point, step.get("speed", 0.3), pressed=True)
        self.press_at(point, False)
        self.record(step.get("hold", 1))

    def do_wait(self, step):
        if self.ide.running():
            self.record(step.get("seconds", 1))
        else:
            self.hold(step.get("seconds", 1))

    def do_stop(self, step):
        self.ide.stop()
        self.shot()
