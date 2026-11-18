"""A virtual board for the tests: the MicroPython of the runtime behind a pseudo-terminal.

mpremote and the IDE's serial code talk to it through a real serial device path, with the real
protocol (raw REPL, raw paste, fs cp), the way they talk to a board. Its flash is a folder of the
PC seen through lms_sandbox, so "/" and ".." stay inside it.

What a board does and the Linux MicroPython does not, the bridge between the two terminals does:
Ctrl-D in the raw REPL ends the Linux process; a board soft-resets. The bridge says
"MPY: soft reboot", starts the runtime again and, if it was in the raw REPL, goes back there.
It counts the resets: a test can tell whether an operation restarted the board.

Linux only (pseudo-terminals); the tests that use it skip elsewhere.
"""
import os
import select
import signal
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]
BOOT = '''import os
import sys
from lms_sandbox import SandboxVfs
os.umount("/")
os.mount(SandboxVfs(os.getenv("LMS_FLASH")), "/")
os.chdir("/")
sys.path[:] = ["", "/lib", "/flash", "/flash/lib"]
'''


def available():
    from lvgl_mpy_studio.platform import runtime_path

    return sys.platform.startswith("linux") and runtime_path().exists()


class VirtualBoard:
    def __init__(self, folder, files=None, size=(480, 480)):
        import pty
        import tty

        from lvgl_mpy_studio.platform import runtime_path

        self.folder = Path(folder)
        self.flash = self.folder / "flash"             # the root filesystem of the board
        (self.flash / "flash").mkdir(parents=True, exist_ok=True)
        for name, data in (files or {}).items():
            target = self.flash / name.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data if isinstance(data, bytes) else data.encode())
        self.boot = self.folder / "boot"
        self.boot.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "runtime" / "program" / "lms_sandbox.py", self.boot / "lms_sandbox.py")
        (self.boot / "lms_board_boot.py").write_text(BOOT, encoding="utf-8")
        self.runtime = str(runtime_path())
        self.resets = 0
        self.size = size
        self.received = bytearray()                    # everything the host sent, for the tests to read
        self._raw = False
        self._closing = False
        # The host side: what mpremote opens as the serial port.
        self._host, host_device = pty.openpty()
        tty.setraw(host_device)
        self.port = os.ttyname(host_device)
        self._host_device = host_device                # kept open: a pty whose device nobody holds hangs up
        self._start()
        self._thread = threading.Thread(target=self._bridge, name="virtual-board", daemon=True)
        self._thread.start()
        self.wait_for_prompt()

    # ---- the MicroPython process ----

    def _start(self):
        import pty
        import tty

        self._board, device = pty.openpty()
        tty.setraw(device)
        environment = {**os.environ, "LVSIM_HEADLESS": "1", "MICROPYPATH": ".", "LMS_FLASH": str(self.flash), "LVSIM_WIDTH": str(self.size[0]), "LVSIM_HEIGHT": str(self.size[1])}
        self.process = subprocess.Popen([self.runtime, "-i", "-c", "import lms_board_boot"], cwd=self.boot, stdin=device, stdout=device, stderr=device, env=environment, close_fds=True)
        os.close(device)
        self._banner = bytearray()
        self._tail = b""

    def _restart(self):
        """What a board does on a soft reset: the interpreter starts again, the files stay."""
        os.close(self._board)
        self.resets += 1
        os.write(self._host, b"MPY: soft reboot\r\n")
        was_raw = self._raw
        self._start()
        if was_raw:
            self._read_board_until(b">>> ", 5)           # the new interpreter's banner is not shown: a board prints its own
            os.write(self._board, b"\x01")

    def _read_board_until(self, marker, seconds):
        data, end = b"", time.monotonic() + seconds
        while marker not in data and time.monotonic() < end:
            ready, _, _ = select.select([self._board], [], [], 0.05)
            if ready:
                data += os.read(self._board, 4096)
        return data

    # ---- the bridge ----

    def _bridge(self):
        while not self._closing:
            try:
                ready, _, _ = select.select([self._host, self._board], [], [], 0.05)
            except (OSError, ValueError):
                return
            if self._host in ready:
                try:
                    data = os.read(self._host, 4096)
                except OSError:
                    data = b""
                if data:
                    self.received += data
                    self._follow_mode(data)
                    try:
                        os.write(self._board, data)
                    except OSError:
                        pass
                    if b"\x03" in data and not self._at_prompt():
                        self._interrupt()
            if self._board in ready:
                try:
                    data = os.read(self._board, 4096)
                except OSError:                        # the process ended: Ctrl-D, or machine.reset()
                    data = b""
                if data:
                    self._tail = (self._tail + data)[-16:]
                    os.write(self._host, data)
            if self.process.poll() is not None and not self._closing:
                self._drain_board()
                self._restart()

    def _at_prompt(self):
        """The board waits at the prompt of its REPL, raw or not: nothing runs to interrupt."""
        return self._tail.endswith((b">>> ", b"\n>", b"... "))

    def _interrupt(self):
        """Ctrl-C while a program runs. A board's UART sees it at once and raises KeyboardInterrupt;
        the MicroPython of the PC behind a raw pseudo-terminal does not read its input while it runs,
        so the signal a terminal would send is sent here."""
        try:
            self.process.send_signal(signal.SIGINT)
        except (OSError, ProcessLookupError):
            pass

    def _drain_board(self):
        while True:
            try:
                ready, _, _ = select.select([self._board], [], [], 0)
                if not ready:
                    return
                data = os.read(self._board, 4096)
            except OSError:
                return
            if not data:
                return
            os.write(self._host, data)

    def _follow_mode(self, data):
        for byte in data:
            if byte == 0x01:
                self._raw = True
            elif byte == 0x02:
                self._raw = False

    # ---- for the tests ----

    def wait_for_prompt(self, seconds=10):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.process.poll() is None:
                return True
            time.sleep(0.01)
        raise RuntimeError("the virtual board did not start")

    def unplug(self):
        """The cable pulled out: the port goes away under whoever has it open."""
        self._closing = True
        self._thread.join(2)
        for fd in (self._host, self._host_device):
            try:
                os.close(fd)
            except OSError:
                pass
        self._host = self._host_device = -1

    def file(self, path):
        return (self.flash / path.lstrip("/")).read_bytes()

    def exists(self, path):
        return (self.flash / path.lstrip("/")).exists()

    def close(self):
        self._closing = True
        self._thread.join(2)
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(5)
        for fd in (self._board, self._host, self._host_device):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        self.close()
