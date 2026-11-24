"""cac_settings, the WiFi networks that the example apps share on a board (examples/settings)."""
import importlib.util
import json
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parents[1] / "examples"
SOURCE = EXAMPLES / "settings" / "cac_settings.py"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                    # on a PC the file is next to the program
    spec = importlib.util.spec_from_file_location("cac_settings_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.time = FakeTime()
    return module


class FakeTime:
    """MicroPython's ticks, with a clock that moves only when the code sleeps."""

    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, a, b):
        return a - b

    def sleep_ms(self, ms):
        self.now += ms


class FakeStation:
    def __init__(self, visible, working):
        self.visible = visible                     # {ssid: rssi}
        self.working = working                     # {ssid: password} that connect
        self.tried = []
        self.ssid = None

    def scan(self):
        return [(name.encode(), b"", 1, rssi, 3, False) for name, rssi in self.visible.items()]

    def isconnected(self):
        return self.ssid is not None

    def connect(self, ssid, password):
        self.tried.append(ssid)
        if self.working.get(ssid) == password:
            self.ssid = ssid

    def disconnect(self):
        self.ssid = None

    def config(self, key):
        return self.ssid

    def ifconfig(self):
        return ("192.168.1.10", "", "", "")


def test_every_app_has_the_same_cac_settings():
    source = SOURCE.read_text(encoding="utf-8")
    copies = 0
    for path in sorted(EXAMPLES.glob("*/project.json")):
        modules = {m["name"]: m["source"] for m in json.loads(path.read_text(encoding="utf-8")).get("modules", [])}
        if "cac_settings" in modules:
            copies += 1
            assert modules["cac_settings"] == source, f"{path.parent.name} has another copy of cac_settings"
    assert copies >= 12


def test_networks_are_kept_from_the_most_recent_and_five_at_most(settings):
    assert settings.networks() == []
    for n in range(6):
        settings.remember(f"N{n}", f"p{n}")
    assert [n["ssid"] for n in settings.networks()] == ["N5", "N4", "N3", "N2", "N1"]
    settings.remember("N2", "new")
    assert settings.networks()[0] == {"ssid": "N2", "password": "new"}
    assert len(settings.networks()) == 5
    settings.forget("N4")
    assert [n["ssid"] for n in settings.networks()] == ["N2", "N5", "N3", "N1"]
    assert settings.password("N3") == "p3" and settings.password("nowhere") is None


def test_the_file_is_written_whole(settings, tmp_path):
    settings.remember("Home", "secret")
    assert json.loads((tmp_path / "cac_settings.json").read_text()) == {"version": 1, "wifi": [{"ssid": "Home", "password": "secret"}]}
    assert not (tmp_path / "cac_settings.json.new").exists()


def test_a_broken_file_reads_as_empty(settings, tmp_path):
    (tmp_path / "cac_settings.json").write_text("{not json")
    assert settings.networks() == []
    (tmp_path / "cac_settings.json").write_text('{"wifi": [{"ssid": ""}, "x", {"ssid": "Ok", "password": "p"}]}')
    assert settings.networks() == [{"ssid": "Ok", "password": "p"}]


def test_connect_tries_the_most_recent_first_then_the_strongest(settings):
    for name in ("Weak", "Strong", "Absent", "Recent"):
        settings.remember(name, name.lower())
    sta = FakeStation({"Weak": -80, "Strong": -40, "Recent": -90, "Stranger": -30}, {"Weak": "weak"})
    assert settings.connect(sta) == "Weak"
    assert sta.tried == ["Recent", "Strong", "Weak"]            # Absent is not in range: not tried
    assert settings.networks()[0]["ssid"] == "Weak"             # the one that worked is now the most recent


def test_connect_without_saved_networks_or_when_already_connected(settings):
    sta = FakeStation({"Home": -50}, {"Home": "secret"})
    assert settings.connect(sta) is None and sta.tried == []
    sta.ssid = "Elsewhere"
    assert settings.connect(sta) == "Elsewhere" and sta.tried == []


def test_without_wifi_hardware_nothing_connects_and_the_scan_is_a_demo(settings):
    settings.remember("Home", "secret")
    assert settings.station() is None
    assert settings.connect() is None
    assert [name for name, _rssi in settings.scan()] == ["Home", "Office", "Guest"]


def test_a_section_is_kept_apart_from_the_networks(settings):
    assert settings.section("display") == {}
    settings.remember("Home", "secret")
    settings.set_section("display", {"brightness": 60})
    settings.remember("Office", "other")
    assert settings.section("display") == {"brightness": 60}
    assert [n["ssid"] for n in settings.networks()] == ["Office", "Home"]
    settings.set_section("display", "not a dict")
    assert settings.section("display") == {}


def test_the_language_is_english_unless_italian_is_chosen(settings):
    assert settings.language() == "en"
    t = settings.translator({"Save": "Salva"})
    assert t("Save") == "Save"
    settings.set_section("general", {"language": "it"})
    assert settings.language() == "it"
    t = settings.translator({"Save": "Salva"})
    assert t("Save") == "Salva" and t("Other") == "Other"
    settings.set_section("general", {"language": "fr"})   # a language the apps do not speak
    assert settings.language() == "en"
