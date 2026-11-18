"""Windows and dialogs open no larger than the screen has room for."""
from lvgl_mpy_studio.core.boards import ProfileStore


def fits(widget):
    room = widget.screen().availableGeometry()
    return widget.width() <= room.width() and widget.height() <= room.height()


def test_the_main_window_and_the_large_dialogs_fit_the_screen(qtbot, tmp_path):
    from PySide6.QtCore import QSettings

    from lvgl_mpy_studio.ui.blocks_manager import BlocksDialog
    from lvgl_mpy_studio.ui.device_files import UploadFilesDialog
    from lvgl_mpy_studio.ui.document import ProjectDocument
    from lvgl_mpy_studio.ui.main_window import MainWindow
    from lvgl_mpy_studio.ui.profile_manager import ProfileManagerDialog

    window = MainWindow()
    qtbot.addWidget(window)
    widgets = [
        window,
        ProfileManagerDialog(ProfileStore(tmp_path / "profiles.json")),
        BlocksDialog(ProjectDocument()),
        UploadFilesDialog(QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)),
    ]
    for widget in widgets[1:]:
        qtbot.addWidget(widget)
    room = window.screen().availableGeometry()
    assert room.width() < 1400 or room.height() < 900, "the test screen is large enough for everything: it shows nothing"
    assert [type(widget).__name__ for widget in widgets if not fits(widget)] == []
