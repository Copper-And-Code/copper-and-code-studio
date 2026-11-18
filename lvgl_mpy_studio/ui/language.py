from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QAbstractButton, QComboBox, QDockWidget, QGroupBox, QLabel, QLineEdit, QMenu, QPlainTextEdit, QTabWidget, QTreeWidget, QWidget
from PySide6.QtGui import QAction

from lvgl_mpy_studio.core.i18n import set_language, tr


def _translate_property(obj, prop, setter, value=None):
    """Translate a text from the one it was made from. A text the IDE changed since the last
    translation (a folder's name, a status) is taken as it is now, not put back as it was:
    tr() finds the English of a text already translated."""
    key, shown_key = f"_lvgl_source_{prop}", f"_lvgl_shown_{prop}"
    current = getattr(obj, prop)() if value is None else value
    source = obj.property(key)
    # The & of an underlined letter is not a change: the window places it after each translation.
    if source is None or _bare(current) not in (_bare(obj.property(shown_key)), _bare(source)):
        if not current:
            return
        source = current
        obj.setProperty(key, source)
    shown = tr(source)
    obj.setProperty(shown_key, shown)
    setter(shown)


def _bare(text):
    return (text or "").replace("&", "")


def retranslate_widget(root):
    objects = [root, *root.findChildren(object)]
    for obj in objects:
        if hasattr(obj, "retranslate"):
            obj.retranslate()
        if isinstance(obj, QAction):
            _translate_property(obj, "text", obj.setText)
            _translate_property(obj, "toolTip", obj.setToolTip)
            _translate_property(obj, "statusTip", obj.setStatusTip)
        if isinstance(obj, (QAbstractButton, QLabel)):
            _translate_property(obj, "text", obj.setText)
        if isinstance(obj, QWidget):
            _translate_property(obj, "toolTip", obj.setToolTip)
        if isinstance(obj, (QLineEdit, QPlainTextEdit)):
            _translate_property(obj, "placeholderText", obj.setPlaceholderText)
        if isinstance(obj, QDockWidget):
            _translate_property(obj, "windowTitle", obj.setWindowTitle)
        if isinstance(obj, (QGroupBox, QMenu)):
            _translate_property(obj, "title", obj.setTitle)
        if isinstance(obj, QComboBox) and not obj.property("_lvgl_dynamic_items"):
            for index in range(obj.count()):
                key = f"_lvgl_source_item_{index}"
                source = obj.property(key)
                if source is None:
                    source = obj.itemText(index)
                    obj.setProperty(key, source)
                obj.setItemText(index, tr(source))
        if isinstance(obj, QTabWidget):
            for index in range(obj.count()):
                page = obj.widget(index)
                if page.property("_lvgl_dynamic_tab"):
                    continue
                source = page.property("_lvgl_source_tab")
                if source is None:
                    source = obj.tabText(index)
                    page.setProperty("_lvgl_source_tab", source)
                obj.setTabText(index, tr(source))
        if isinstance(obj, QTreeWidget):
            item = obj.headerItem()
            sources = obj.property("_lvgl_source_headers")
            if sources is None:
                sources = [item.text(index) for index in range(obj.columnCount())]
                obj.setProperty("_lvgl_source_headers", sources)
            for index, source in enumerate(sources):
                item.setText(index, tr(source))


_qt_translator = None


def install_qt_translation(language):
    """Qt's own texts in the language: the standard buttons (Save, Cancel, Close) and Qt's dialogs.
    PySide carries them; English needs none."""
    global _qt_translator
    from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator

    app = QCoreApplication.instance()
    if app is None:
        return False
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if language == "en":
        return True
    translator = QTranslator(app)
    if not translator.load(f"qtbase_{language}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        return False
    app.installTranslator(translator)
    _qt_translator = translator
    return True


def apply_language(root, language):
    selected = set_language(language)
    QSettings("CopperAndCode", "LVGL MPY Studio").setValue("language", selected)
    install_qt_translation(selected)
    retranslate_widget(root)
    return selected
