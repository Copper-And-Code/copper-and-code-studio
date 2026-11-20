from pathlib import Path
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QTabBar, QToolButton
from shiboken6 import isValid

from copper_and_code_studio.core.i18n import tr
from copper_and_code_studio.device.common import DeviceError
from copper_and_code_studio.platform import config_dir
from copper_and_code_studio.build.program import program_files
from copper_and_code_studio.ui.device_files import folder_items
from copper_and_code_studio.ui.files import FileTab, FilesPanel


class EditorTabsMixin:
    """Files of the PC in tabs of their own, next to the pages, the Code and the Simulator. A part of MainWindow."""

    def _make_files_panel(self):
        self.files_panel = FilesPanel(self.settings)
        self.files_panel.openRequested.connect(self.open_file)
        self.files_panel.runRequested.connect(lambda path: self.run_program(path))
        self.files_panel.browserRequested.connect(lambda path: self.program_in_browser(path))
        self.files_panel.uploadRequested.connect(self._upload_local_to_board)
        self.files_panel.boardRunRequested.connect(self.run_program_on_board)
        self.files_panel.renamed.connect(self._files_renamed)
        self.files_panel.deleted.connect(self._files_deleted)
        board = self.files_panel.board
        board.listRequested.connect(self._board_list)
        board.openRequested.connect(self.open_board_file)
        board.downloadRequested.connect(self.download_board_file)
        board.uploadRequested.connect(self.upload_to_board_folder)
        board.mkdirRequested.connect(self.board_new_folder)
        board.renameRequested.connect(self.board_rename)
        board.deleteRequested.connect(self.board_delete)
        board.runRequested.connect(lambda path: self.run_file_on_board(path))
        self._board_pending = []
        self._close_when_written = False  # the window closes once the board has the files being written
        return self.files_panel

    def _files_shown(self, visible):
        self.files_panel.board.shown = visible
        self.files_panel.board.ensure_listed()

    @property
    def file_tabs(self):
        return [self.tabs.widget(index) for index in range(self.tabs.count()) if isinstance(self.tabs.widget(index), FileTab)]

    def _file_tab(self, path):
        path = Path(path).resolve()
        return next((tab for tab in self.file_tabs if tab.path == path), None)

    def open_file(self, path, remote=None):
        """Open a file of the PC in a tab, or bring forward the tab that has it; remote: its path on the board."""
        tab = self._file_tab(path)
        if tab is None:
            try:
                tab = FileTab(path, remote=remote)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, tr("Open"), str(exc))
                return None
            index = self.tabs.addTab(tab, tab.title())
            self.tabs.setTabToolTip(index, str(tab.path))
            close = QToolButton()
            close.setAutoRaise(True)
            close.setText("×")
            close.setToolTip(tr("Close"))
            close.clicked.connect(lambda: self.close_file(tab))
            self.tabs.tabBar().setTabButton(index, QTabBar.RightSide, close)
            tab.titleChanged.connect(lambda: self.tabs.setTabText(self.tabs.indexOf(tab), tab.title()))
        self.tabs.setCurrentWidget(tab)
        tab.editor.setFocus(Qt.OtherFocusReason)
        return tab

    def _tabs_under(self, path):
        """The tabs of files of the PC at path or inside it, with the part of their path below it."""
        path = Path(path).resolve()
        return [(tab, tab.path.relative_to(path)) for tab in self.file_tabs if not tab.remote and tab.path.is_relative_to(path)]

    def _files_renamed(self, old, new):
        """Renamed in the Files panel: the tabs follow, so that Save does not write the old file again."""
        for tab, below in self._tabs_under(old):
            tab.move_to(Path(new) / below)
            self.tabs.setTabToolTip(self.tabs.indexOf(tab), str(tab.path))

    def _files_deleted(self, path):
        """Moved to the trash from the Files panel: a tab with nothing unsaved closes; one with changes stays, to be saved again."""
        for tab, _below in self._tabs_under(path):
            if not tab.modified:
                self.tabs.removeTab(self.tabs.indexOf(tab))
                tab.deleteLater()

    def close_file(self, tab):
        """Close a tab, asking about unsaved changes. A file of the board closes when the board has it: False until then."""
        if tab.board_writes:
            tab.close_when_written = True
            self.statusBar().showMessage(tr("{name} is being written on the board: the tab closes when it is done.", name=tab.path.name), 5000)
            return False
        if tab.modified:
            answer = QMessageBox.question(self, tr("Unsaved Changes"), tr("Save changes to {name}?", name=tab.path.name), QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if answer == QMessageBox.Cancel:
                return False
            if answer == QMessageBox.Save and not self._save_file(tab):
                return False
            if tab.board_writes:
                tab.close_when_written = True
                return False
        self.tabs.removeTab(self.tabs.indexOf(tab))
        tab.deleteLater()
        return True

    def _save_file(self, tab):
        """Save a tab. A file of the board is written there in the background: True means it is on its way."""
        if tab.remote and not self.device.port:
            QMessageBox.warning(self, tr("Save"), tr("{name} is a file of the board: connect to the board to save it.", name=tab.path.name))
            return False
        try:
            tab.save()
        except OSError as exc:
            QMessageBox.warning(self, tr("Save"), str(exc))
            return False
        if tab.remote:
            # The local copy is written; the tab stays modified until the board has the file.
            document = tab.editor.document()
            document.setModified(True)
            data, revision, remote = tab.path.read_bytes(), document.revision(), tab.remote
            tab.board_writes += 1

            def saved(_result):
                self._board_write_done(tab, None)
                if isValid(tab) and document.revision() == revision:  # nothing typed during the write
                    document.setModified(False)
                self.statusBar().showMessage(tr("Saved {path} on the board", path=remote), 3000)
                if isValid(tab) and tab.close_when_written and not tab.board_writes:
                    tab.close_when_written = False
                    self.close_file(tab)

            self._board_task(lambda: self.device.write_file(remote, data), saved, lambda error: self._board_write_done(tab, error))
        return True

    def _board_write_done(self, tab, error):
        if isValid(tab):
            tab.board_writes = max(0, tab.board_writes - 1)
            if error is not None:
                tab.close_when_written = False  # the tab stays, with its changes, to try again
        if error is not None:
            self._close_when_written = False

    def board_writes_pending(self):
        return any(tab.board_writes for tab in self.file_tabs)

    def _close_after_board_writes(self):
        """Closing the window waits for the files of the board being written; it goes on when they are."""
        if self._close_when_written and self._worker is None and not self.board_writes_pending():
            self._close_when_written = False
            QTimer.singleShot(0, self.close)

    def save_current(self):
        """Ctrl+S: the file of the current tab, or the project."""
        tab = self.tabs.currentWidget()
        if isinstance(tab, FileTab):
            saved = self._save_file(tab)
            if saved and not tab.remote:
                self.statusBar().showMessage(tr("Saved {path}", path=tab.path), 3000)
            return saved
        return self.save_project()

    def save_files_in(self, folder):
        """Before a program runs: its files modified in the editor go to disk, as F5 saves the project."""
        folder = Path(folder).resolve()
        for tab in self.file_tabs:
            if tab.modified and folder in tab.path.parents and not self._save_file(tab):
                return False
        return True

    def confirm_files(self):
        """When the window closes: each modified file is saved, discarded, or the closing stops."""
        for tab in self.file_tabs:
            if not tab.modified or tab.board_writes:
                continue
            self.tabs.setCurrentWidget(tab)
            answer = QMessageBox.question(self, tr("Unsaved Changes"), tr("Save changes to {name}?", name=tab.path.name), QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if answer == QMessageBox.Cancel or (answer == QMessageBox.Save and not self._save_file(tab)):
                return False
        if self.board_writes_pending():
            self.wait_for_board_writes()
            return False
        return True

    def wait_for_board_writes(self):
        self._close_when_written = True
        self.statusBar().showMessage(tr("Writing files on the board: the window closes when they are written."))

    def current_python_file(self):
        """The .py file of the current tab, if any: Run Program and Run in the Browser offer it first."""
        tab = self.tabs.currentWidget()
        return tab.path if isinstance(tab, FileTab) and tab.path.suffix == ".py" else None

    # ---- Files of the board ----

    def _board_task(self, operation, completed=None, failed=None):
        """One operation on the board, now or as soon as the board is free: the IDE does one at a time.

        failed(error) is called if it fails, or if the board goes away before it runs."""
        if not self.device.port:
            self.statusBar().showMessage(tr("Board not connected"), 3000)
            if failed:
                failed(DeviceError("device.absent", ""))
            return
        if self._worker is not None or not self._device_task(operation, completed, background=True, failed=failed):
            self._board_pending.append((operation, completed, failed))

    def _run_board_pending(self):
        if self._board_pending and self._worker is None and self.device.port:
            operation, completed, failed = self._board_pending.pop(0)
            self._device_task(operation, completed, background=True, failed=failed)
        elif not self.device.port:
            pending, self._board_pending = self._board_pending, []
            for _operation, _completed, failed in pending:
                if failed:
                    failed(DeviceError("device.absent", ""))
        self._close_after_board_writes()

    def _board_list(self, path):
        self._board_task(lambda: self.device.list_dir(path), lambda entries: self.files_panel.board.show_listing(path, entries))

    def _board_cache(self, remote):
        """Where a file of the board is copied to be edited: one folder per port, in the settings."""
        port = re.sub(r"[^A-Za-z0-9_.-]", "_", self.device.port or "board")
        return config_dir() / "board-files" / port / remote.lstrip("/")

    def open_board_file(self, remote):
        tab = next((tab for tab in self.file_tabs if tab.remote == remote), None)
        if tab is not None:
            self.tabs.setCurrentWidget(tab)
            return
        local = self._board_cache(remote)
        local.parent.mkdir(parents=True, exist_ok=True)
        self._board_task(lambda: self.device.read_file(remote, local), lambda _path: self.open_file(local, remote=remote))

    def download_board_file(self, remote):
        folder = self.files_panel.folder
        if folder is None:
            if not self.files_panel.choose_folder():
                return
            folder = self.files_panel.folder
        target = folder / remote.rsplit("/", 1)[-1]
        if target.exists():
            answer = QMessageBox.question(self, tr("Download to the Computer"), tr("{path} exists. Replace it?", path=target))
            if answer != QMessageBox.Yes:
                return
        self._board_task(lambda: self.device.read_file(remote, target), lambda _path: self.statusBar().showMessage(tr("Downloaded to {path}", path=target), 3000))

    def upload_to_board_folder(self, remote_folder):
        start = str(self.files_panel.folder or Path.home())
        paths, _filter = QFileDialog.getOpenFileNames(self, tr("Upload Files Here…"), start)
        if paths:
            self._confirm_and_upload_files([(path, Path(path).name) for path in paths], remote_folder)

    def _upload_local_to_board(self, local, remote_folder):
        local = Path(local)
        items = list(folder_items(local)) if local.is_dir() else [(local, local.name)]
        self._confirm_and_upload_files(items, remote_folder)

    def _ask_board_name(self, title, text=""):
        name, accepted = QInputDialog.getText(self, title, tr("Name:"), text=text)
        name = name.strip()
        if not accepted or not name:
            return None
        if "/" in name or name in (".", ".."):
            QMessageBox.warning(self, title, tr("A name without / or \\, please."))
            return None
        return name

    @staticmethod
    def _parent(remote):
        return remote.rsplit("/", 1)[0] or "/"

    def board_new_folder(self, remote_folder):
        name = self._ask_board_name(tr("New Folder…"))
        if name:
            path = remote_folder.rstrip("/") + "/" + name
            self._board_task(lambda: self.device.make_dir(path), lambda _result: self.files_panel.board.reload_folder(remote_folder))

    def board_rename(self, remote):
        name = self._ask_board_name(tr("Rename…"), remote.rsplit("/", 1)[-1])
        if name and name != remote.rsplit("/", 1)[-1]:
            target = self._parent(remote).rstrip("/") + "/" + name
            self._board_task(lambda: self.device.rename_path(remote, target), lambda _result: self.files_panel.board.reload_folder(self._parent(remote)))

    def board_delete(self, remote, folder):
        question = tr("Delete the folder {path} from the board, with everything in it?", path=remote) if folder else tr("Delete {path} from the board?", path=remote)
        if QMessageBox.question(self, tr("Delete…"), question) != QMessageBox.Yes:
            return
        self._board_task(lambda: self.device.remove_path(remote), lambda _result: self.files_panel.board.reload_folder(self._parent(remote)))

    def _board_program_root(self):
        """Where a program goes on the board when no folder is chosen: the flash of the STM32 boards, else the root."""
        board = self.document.project.board or {}
        return "/flash" if str(board.get("config", {}).get("appRoot", "")).startswith("/flash") else "/"

    def run_program_on_board(self, entry):
        """As Run Program, on the board: its folder is uploaded, then the file runs from the board's prompt."""
        entry = Path(entry).resolve()
        if not self.save_files_in(entry.parent):
            return False
        view = self.files_panel.board
        destination = view.current_folder() if view.connected and view.tree.currentItem() else self._board_program_root()
        remote = f"{destination.rstrip('/')}/{entry.parent.name}/{entry.name}"
        try:
            items = [(path, f"{entry.parent.name}/{relative.as_posix()}") for path, relative in program_files(entry.parent)]
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Run on the Board"), str(exc))
            return False
        self.statusBar().showMessage(tr("Uploading {folder} to {destination} on the board, then running {name}…", folder=entry.parent.name, destination=destination, name=entry.name))
        return self._confirm_and_upload_files(items, destination, then=lambda: self.run_file_on_board(remote))

    def ask_run_on_board(self):
        last = self.current_python_file() or self._last_program()
        path, _filter = QFileDialog.getOpenFileName(self, tr("Run on the Board"), str(last or ""), tr("MicroPython program (*.py)"))
        if not path:
            return False
        self.settings.setValue("simulator/program", path)
        self.files_panel.set_folder(Path(path).parent)
        return self.run_program_on_board(path)
