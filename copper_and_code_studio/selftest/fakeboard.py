"""A board that lives in memory, for the scenarios of the self-test: no real board is touched.

It answers what the window asks of a DeviceSession (ports, connection, files, console) the way
a board with MicroPython does, without the protocol: the protocol is tested in tests/.
"""

import posixpath
import time
from pathlib import Path

from copper_and_code_studio.device.common import DeviceError
from copper_and_code_studio.device.service import DeviceSession

PORT = "selftest:board"


class FakeConsole:
    """The serial console of the board: what the IDE types is kept, nothing comes back."""

    def __init__(self, board):
        self.board = board

    def read_some(self):
        time.sleep(0.005)
        return b""

    def write(self, data):
        self.board.typed.append(bytes(data))

    def close(self):
        pass


class FakeBoard(DeviceSession):
    def __init__(self, files=None):
        super().__init__(runner=self._refuse, process_factory=self._refuse, uart_factory=self._refuse, console_factory=lambda port: FakeConsole(self))
        self.files = dict(files or {"/flash/main.py": b"print('main of the board')\n", "/flash/boot.py": b""})
        self.typed = []

    def _refuse(self, *arguments, **options):
        raise DeviceError("device.command", "the self-test board does not run mpremote")

    def _folders(self):
        found = {"/", "/flash"}
        for path in self.files:
            parent = posixpath.dirname(path)
            while parent not in found:
                found.add(parent)
                parent = posixpath.dirname(parent)
        return found | getattr(self, "_made", set())

    # ---- what the window asks ----

    def list_ports(self):
        return [{"port": PORT, "id": "selftest", "usb": "0000:0000", "description": "Board simulated by the self-test"}]

    def connect(self, port, profile):
        if port != PORT:
            raise DeviceError("device.absent", port)
        self.port, self.profile, self.state = port, profile, "ready"
        return {"compatible": True, "width": profile["logicalWidth"], "height": profile["logicalHeight"], "version": [1, 25, 0], "deviceId": "selftest", "memoryFree": 4_000_000}

    def info(self):
        return {"compatible": True, "deviceId": "selftest"}

    def list_dir(self, path):
        path = self._board_path(path)
        prefix = path.rstrip("/") + "/"
        entries = {}
        for name in set(self.files) | self._folders():
            if name.startswith(prefix) and name != path:
                rest = name[len(prefix):]
                first = rest.split("/")[0]
                folder = "/" in rest or name in self._folders()
                entries[first] = {"name": first, "dir": folder or entries.get(first, {}).get("dir", False), "size": -1 if folder else len(self.files.get(name, b""))}
        return sorted(entries.values(), key=lambda entry: (not entry["dir"], entry["name"].lower()))

    def read_file(self, path, local):
        path = self._board_path(path)
        if path not in self.files:
            raise DeviceError("device.command", f"OSError: [Errno 2] ENOENT: {path}")
        Path(local).write_bytes(self.files[path])
        return Path(local)

    def write_file(self, path, data):
        self.files[self._board_path(path)] = bytes(data)

    def upload_files(self, items, destination, compile_python=False, progress=None, cancel=None):
        destination = "/" + destination.strip().strip("/") if destination.strip().strip("/") else "/"
        written = []
        for local, name in items:
            target = posixpath.join(destination, name.strip("/"))
            self.files[target] = Path(local).read_bytes()
            written.append(target)
        return {"destination": destination, "files": written, "bytes": sum(len(self.files[path]) for path in written), "warnings": []}

    def make_dir(self, path):
        self._made = getattr(self, "_made", set()) | {self._board_path(path)}

    def rename_path(self, old, new):
        old, new = self._board_path(old), self._board_path(new)
        for path in [path for path in self.files if path == old or path.startswith(old + "/")]:
            self.files[new + path[len(old):]] = self.files.pop(path)

    def remove_path(self, path):
        path = self._board_path(path)
        for name in [name for name in self.files if name == path or name.startswith(path + "/")]:
            del self.files[name]
