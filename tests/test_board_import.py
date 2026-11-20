"""Boards defined by a file: import, export and delete, in the store, the manager, the CLI and MCP.

The board here is made up: test_linux_board, with an adapter the IDE has no code for.
"""
import json

import pytest

from copper_and_code_studio import mcp_server
from copper_and_code_studio.cli import main
from copper_and_code_studio.core.boards import (
    ProfileError, ProfileStore, adapter_requirements, builtin_profiles, profile_diagnostics, read_profile_file, write_profile_file,
)
from copper_and_code_studio.core.model import Project
from copper_and_code_studio.gen.board_gen import generate_board
from helpers import call, payload


def board(**changes):
    profile = {
        "schemaVersion": 1,
        "id": "test_linux_board",
        "revision": 1,
        "name": "Test Linux board (320×240)",
        "adapter": "generic_test",
        "firmware": {"microPython": "1.29.0", "lvgl": "9.5.0", "modules": ["lvgl", "display_driver"]},
        "physicalWidth": 320,
        "physicalHeight": 240,
        "logicalWidth": 320,
        "logicalHeight": 240,
        "scale": 1,
        "colorFormat": "RGB565",
        "fonts": [14, 16, 24],
        "orientations": [0],
        "config": {"driver": "display_driver", "buffers": "driver", "eventLoop": "driver", "appRoot": "/lms_apps", "mainPath": "/main.py"},
    }
    profile.update(changes)
    return profile


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    return tmp_path


def board_file(folder, file_name="board.json", **changes):
    path = folder / file_name
    path.write_text(json.dumps(board(**changes), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---- The adapter ----


def test_an_adapter_without_code_takes_its_needs_from_the_profile():
    assert profile_diagnostics(board()) == []
    assert adapter_requirements(board()) == {"colorFormats": {"RGB565"}, "modules": ["lvgl", "display_driver"], "eventLoop": "driver"}
    assert adapter_requirements({"adapter": "esp32_4848s040"})["modules"] == ["lvgl", "display_driver", "gt911"]   # the table stays


@pytest.mark.parametrize("adapter", ["Generic", "generic-test", "../x", "", "a" * 65, 7, None])
def test_an_adapter_that_is_not_an_identifier_is_refused(adapter):
    assert any(error["code"] in ("profile.adapter", "profile.required") for error in profile_diagnostics(board(adapter=adapter)))


def test_board_code_is_generated_for_an_adapter_without_code(tmp_path):
    project = Project("linux")
    project.set_display_size(320, 240)
    project.board = board()
    project.add_widget(project.pages[0], "button")
    result = generate_board(project, project.board, tmp_path)
    assert "ADAPTER = 'generic_test'" in (tmp_path / "board_adapter.py").read_text()
    assert result["manifest"]["profileId"] == "test_linux_board"


# ---- The store ----


def test_import_keeps_the_board_after_a_new_start(config):
    path = board_file(config, origin="builtin")             # origin is the catalog's, not the file's
    store = ProfileStore()
    profile = store.import_profile(path)
    assert "origin" not in profile
    loaded = ProfileStore()
    assert loaded.get("test_linux_board")["origin"] == "imported"
    assert loaded.get("test_linux_board")["adapter"] == "generic_test"
    data = json.loads(loaded.path.read_text(encoding="utf-8"))
    assert data["imported"] == ["test_linux_board"]


def test_import_refuses_a_built_in_id_and_replaces_an_imported_one_only_when_asked(config):
    store = ProfileStore()
    builtin = builtin_profiles()[0]["id"]
    with pytest.raises(ProfileError) as refused:
        store.import_profile(board_file(config, id=builtin))
    assert refused.value.code == "profile.import.builtin"
    assert store.get(builtin)["origin"] == "builtin"
    store.import_profile(board_file(config))
    with pytest.raises(ProfileError) as exists:
        store.import_profile(board_file(config, name="Second"))
    assert exists.value.code == "profile.import.exists"
    assert store.import_profile(board_file(config, name="Second", revision=2), replace=True)["name"] == "Second"
    assert ProfileStore().get("test_linux_board")["revision"] == 2


def test_import_refuses_a_large_file_text_that_is_not_json_and_an_invalid_board(config):
    large = config / "large.json"
    large.write_text(" " * (64 * 1024 + 1), encoding="utf-8")
    broken = config / "broken.json"
    broken.write_bytes(b"{\"id\": ")
    latin = config / "latin.json"
    latin.write_bytes(json.dumps(board(name="café"), ensure_ascii=False).encode("latin-1"))
    codes = []
    for path in (large, broken, latin, board_file(config, scale=0)):
        with pytest.raises(ProfileError) as error:
            read_profile_file(path)
        codes.append(error.value.code)
    assert codes == ["profile.import.size", "profile.import.json", "profile.import.json", "profile.import.invalid"]
    assert not ProfileStore().path.exists()                 # nothing written


def test_export_then_import_gives_the_same_board(config):
    store = ProfileStore()
    store.import_profile(board_file(config))
    first = write_profile_file(store.get("test_linux_board"), config / "exported.json")
    assert read_profile_file(first) == board()
    second = write_profile_file(read_profile_file(first), config / "again.json")
    assert second.read_bytes() == first.read_bytes()


def test_delete_removes_an_imported_board_and_hides_a_built_in_one(config):
    store = ProfileStore()
    store.import_profile(board_file(config))
    builtin = builtin_profiles()[0]["id"]
    store.delete("test_linux_board")
    store.delete(builtin)
    store.save()
    loaded = ProfileStore()
    assert loaded.get("test_linux_board") is None and loaded.custom == {} and loaded.imported == []
    assert loaded.get(builtin) is None and loaded.hidden == [builtin]
    loaded.restore_hidden()
    assert loaded.get(builtin)["origin"] == "builtin"


# ---- The IDE ----


def test_a_project_whose_board_was_deleted_opens_with_a_warning(qtbot, config):
    from copper_and_code_studio.ui.main_window import MainWindow

    project = Project("linux")
    project.set_display_size(320, 240)
    project.board = board()
    path = config / "linux.json"
    project.save(path)
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.open_project(path)
    assert window.document.project.board["adapter"] == "generic_test"
    assert "Test Linux board (320×240) of this project is not among the boards of the IDE" in window.output.toPlainText()
    assert window.errors.topLevelItemCount() == 0             # a warning, not an error
    generate_board(window.document.project, window.document.project.board, config / "build")
    window.profile_store.import_profile(board_file(config))
    assert window.open_project(path)
    assert "not among the boards" not in window.output.toPlainText()
    window.document.undo_stack.setClean()


def test_the_manager_imports_keeps_the_adapter_when_edited_exports_and_deletes(qtbot, config, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from copper_and_code_studio.ui.profile_manager import ProfileManagerDialog

    questions, warnings = [], []
    monkeypatch.setattr(QMessageBox, "question", lambda parent, title, text: questions.append(text) or QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    store = ProfileStore()
    dialog = ProfileManagerDialog(store)
    qtbot.addWidget(dialog)
    assert dialog.import_file(str(board_file(config)))["id"] == "test_linux_board"
    assert dialog.selected()["id"] == "test_linux_board"
    assert dialog.tree.currentItem().text(1) == "Imported" and dialog.adapter.currentText() == "generic_test"
    dialog.name.setText("Renamed")
    dialog.apply_edit()                                        # the adapter is not lost to the first of the list
    assert dialog.selected()["adapter"] == "generic_test" and dialog.selected()["origin"] == "imported"
    assert dialog.import_file(str(board_file(config, name="From the file")))["name"] == "From the file"
    assert "already there" in questions[-1]
    assert dialog.import_file(str(board_file(config, file_name="builtin.json", id=builtin_profiles()[0]["id"]))) is None
    assert "built-in board" in warnings[-1]
    dialog.apply_to_store()
    loaded = ProfileStore()
    assert loaded.get("test_linux_board")["origin"] == "imported" and loaded.get("test_linux_board")["name"] == "From the file"
    dialog = ProfileManagerDialog(loaded)
    qtbot.addWidget(dialog)
    dialog.refresh("test_linux_board")
    exported = dialog.export_file(str(config / "out.json"))
    assert read_profile_file(exported)["adapter"] == "generic_test"
    dialog.delete()
    dialog.apply_to_store()
    assert ProfileStore().get("test_linux_board") is None


def test_the_import_and_export_buttons_ask_for_a_file(qtbot, config, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QPushButton

    from copper_and_code_studio.ui.profile_manager import ProfileManagerDialog

    path = board_file(config)
    asked = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *arguments, **keywords: asked.append("open") or (str(path), ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *arguments, **keywords: asked.append("save") or (str(config / "saved.json"), ""))
    dialog = ProfileManagerDialog(ProfileStore())
    qtbot.addWidget(dialog)
    buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}
    buttons["Import…"].click()                                  # clicked passes checked=False: it must not be taken for a path
    assert asked == ["open"] and dialog.selected()["id"] == "test_linux_board"
    buttons["Export…"].click()
    assert asked == ["open", "save"] and read_profile_file(config / "saved.json") == board()


# ---- CLI and MCP ----


def test_the_command_line_lists_imports_exports_and_deletes(config, capsys):
    path = board_file(config)
    assert main(["board", "import", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "test_linux_board"
    with pytest.raises(SystemExit):
        main(["board", "import", str(path)])
    assert "--replace" in capsys.readouterr().err
    assert main(["board", "import", str(path), "--replace"]) == 0
    assert main(["board", "list"]) == 0
    assert "test_linux_board\t320x240\timported\t" in capsys.readouterr().out
    assert main(["board", "export", "test_linux_board", str(config / "out.json")]) == 0
    assert read_profile_file(config / "out.json") == board()
    assert main(["board", "delete", "test_linux_board"]) == 0
    assert ProfileStore().get("test_linux_board") is None


def test_mcp_imports_lists_selects_and_deletes_a_board(config):
    mcp_server.set_enabled(True)
    project = config / "linux.json"
    assert not call("create_project", path=str(project), width=320, height=240).get("isError")
    assert payload(call("import_board", file=str(board_file(config))))["id"] == "test_linux_board"
    listed = next(item for item in payload(call("list_boards")) if item["id"] == "test_linux_board")
    assert listed == {"id": "test_linux_board", "name": "Test Linux board (320×240)", "width": 320, "height": 240, "fonts": [14, 16, 24], "origin": "imported"}
    again = call("import_board", file=str(board_file(config)))
    assert again["isError"] and "profile.import.exists" in again["content"][0]["text"]
    assert not call("set_board", project=str(project), board="test_linux_board").get("isError")
    assert Project.load(project).board["adapter"] == "generic_test"
    assert payload(call("delete_board", board="test_linux_board")) == {"deleted": "test_linux_board", "hidden": False}
    assert all(item["id"] != "test_linux_board" for item in payload(call("list_boards")))
    assert Project.load(project).board["id"] == "test_linux_board"      # the project keeps its copy
