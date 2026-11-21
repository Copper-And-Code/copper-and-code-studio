# cac_settings: the settings that every Copper and Code app on a board shares.
#
# One file, cac_settings.json, in the flash: /flash/cac_settings.json on boards with a /flash
# folder (STM32), /cac_settings.json on the others (ESP32, RP2350). The Settings app writes it;
# boot.py and the other apps read it. Today it holds up to five WiFi networks:
#
#     {"version": 1, "wifi": [{"ssid": "Home", "password": "..."}, ...]}
#
# The networks are kept from the most recently used. Passwords are in clear text, like in
# MicroPython's own examples: whoever can read the flash can read them.
#
# Copy the same file into every app that uses it (in the IDE: a Python module of the project).
import json
import os
import sys
import time

try:
    import network
except ImportError:                        # the simulator and the PC have no WiFi
    network = None

VERSION = 1
MAX_NETWORKS = 5
TIMEOUT_S = 10                             # for each network tried
DEMO_SCAN = (("Home", -48), ("Office", -61), ("Guest", -75))


def path():
    """Where the file is: in the flash of a board; next to the program on a PC or in the simulator."""
    if sys.platform in ("linux", "darwin", "win32"):
        return "cac_settings.json"
    try:
        if "flash" in os.listdir("/"):
            return "/flash/cac_settings.json"
    except OSError:
        pass
    return "/cac_settings.json"


def load():
    """The settings, or empty ones when the file is missing or broken."""
    try:
        with open(path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    networks = [n for n in data.get("wifi", []) if isinstance(n, dict) and n.get("ssid")]
    data["wifi"] = networks[:MAX_NETWORKS]
    data["version"] = VERSION
    return data


def save(data):
    """Write the settings whole: first a new file, then the rename, so a reset never leaves half."""
    name = path()
    temporary = name + ".new"
    with open(temporary, "w") as f:
        json.dump(data, f)
    try:
        os.remove(name)
    except OSError:
        pass
    os.rename(temporary, name)


def networks():
    """The saved networks, from the most recently used: a list of {"ssid", "password"}."""
    return load()["wifi"]


def password(ssid):
    for item in networks():
        if item["ssid"] == ssid:
            return item["password"]
    return None


def remember(ssid, password):
    """Save a network, or its new password, as the most recently used; the oldest goes when full."""
    data = load()
    others = [n for n in data["wifi"] if n["ssid"] != ssid]
    data["wifi"] = ([{"ssid": ssid, "password": password}] + others)[:MAX_NETWORKS]
    save(data)


def forget(ssid):
    data = load()
    data["wifi"] = [n for n in data["wifi"] if n["ssid"] != ssid]
    save(data)


def station():
    """The WiFi station interface, active, or None without WiFi hardware."""
    if network is None:
        return None
    try:
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        return sta
    except (AttributeError, OSError):
        return None


def scan(sta=None):
    """The networks in range, strongest first, as (ssid, rssi); demo names without WiFi hardware."""
    sta = sta or station()
    if sta is None:
        return list(DEMO_SCAN)
    best = {}
    for entry in sta.scan():
        try:
            name = entry[0].decode()
        except ValueError:
            continue
        if name and (name not in best or entry[3] > best[name]):
            best[name] = entry[3]
    return sorted(best.items(), key=lambda item: -item[1])


def connected_ssid(sta=None):
    sta = sta or station()
    if sta is None or not sta.isconnected():
        return None
    try:
        return sta.config("essid")
    except (OSError, ValueError):
        return "?"


def join(ssid, password, sta=None, timeout_s=TIMEOUT_S):
    """Connect to one network; True when connected within timeout_s."""
    sta = sta or station()
    if sta is None:
        return False
    try:
        sta.disconnect()
    except OSError:
        pass
    try:
        sta.connect(ssid, password)
    except OSError as e:
        print("cac_settings: connect", ssid, repr(e))
        return False
    start = time.ticks_ms()
    while not sta.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > timeout_s * 1000:
            try:
                sta.disconnect()
            except OSError:
                pass
            return False
        time.sleep_ms(100)
    return True


def connect(sta=None, timeout_s=TIMEOUT_S):
    """Connect to the best saved network in range and return its name, or None.

    Already connected: nothing to do. Otherwise the saved networks found by a scan are tried, the
    most recently used first and then by signal; the one that works becomes the most recent.
    Networks that do not answer the scan are not tried: hidden networks are not supported."""
    sta = sta or station()
    if sta is None:
        return None
    current = connected_ssid(sta)
    if current:
        return current
    saved = networks()
    if not saved:
        return None
    try:
        visible = dict(scan(sta))
    except OSError as e:
        print("cac_settings: scan", repr(e))
        return None
    candidates = [n for n in saved if n["ssid"] in visible]
    if len(candidates) > 1:
        first, rest = candidates[0], candidates[1:]
        candidates = [first] + sorted(rest, key=lambda n: -visible[n["ssid"]])
    for item in candidates:
        if join(item["ssid"], item["password"], sta, timeout_s):
            if item is not saved[0]:
                remember(item["ssid"], item["password"])
            print("cac_settings: connected to", item["ssid"], sta.ifconfig()[0])
            return item["ssid"]
    return None
