"""Where the IDE keeps its settings (QSettings), and the copy of those saved under an old name."""
from PySide6.QtCore import QSettings

ORGANIZATION = "CopperAndCode"
APPLICATION = "Copper and Code Studio"
# the names up to 0.7 and up to 0.4, newest first
OLD_APPLICATIONS = ("LVGL MPY Studio", "LVGL IDE")


def app_settings():
    return QSettings(ORGANIZATION, APPLICATION)


def adopt_old_settings():
    """The settings of the IDE. On the first start under this name, those saved under the newest
    old name are copied, once; the old ones are left for an earlier version of the IDE."""
    settings = app_settings()
    if settings.allKeys():
        return settings
    for name in OLD_APPLICATIONS:
        old = QSettings(ORGANIZATION, name)
        keys = old.allKeys()
        if keys:
            for key in keys:
                settings.setValue(key, old.value(key))
            settings.sync()
            break
    return settings
