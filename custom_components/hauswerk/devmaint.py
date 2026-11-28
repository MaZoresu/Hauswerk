"""Wartung aus den Geräten: Home Assistant nach Verschleißteilen, Verbrauchsmaterial und Batterien durchsuchen.

Gefunden werden z. B.
- Saugroboter (Roborock, Dreame, Ecovacs …): Restzeit bzw. Lebensdauer von Haupt- und Seitenbürste, Filter, Sensoren, Wischtuch,
- Mähroboter: Messerqualität bzw. Restzeit, mit dem Knopf „Messer zurücksetzen“,
- Luftreiniger, Kaffeemaschinen, Geschirrspüler: Filter, Entkalken, Salz, Klarspüler,
- Batterien: „Batterie fast leer“ bzw. Ladestand unter der Grenze – mit „Batterie ersetzt“ (Battery Notes), wenn vorhanden.

Je Fund: der Wert (Rest in % oder Stunden, Zustand), ob er fällig ist, und der Knopf, der ihn im Gerät zurücksetzt.
"""
from __future__ import annotations

import re
from typing import Any

# Gruppe → (Muster, Bezeichnung, Symbol). Reihenfolge = Vorrang (spezielle vor allgemeinen).
GROUPS: list[tuple[str, str, str, str]] = [
    ("main_brush", r"main[_ ]?brush|haupt[_ ]?b(?:u|ü|ue)rste|roller[_ ]?brush|rollb(?:u|ü|ue)rste", "Hauptbürste", "mdi:brush"),
    ("side_brush", r"side[_ ]?brush|seiten[_ ]?b(?:u|ü|ue)rste", "Seitenbürste", "mdi:broom"),
    ("sensor", r"sensor[_ ]?dirty|sensorzeit|sensor[_ ]?time|clean[_ ]?sensor|sensoren[_ ]?reinig", "Sensoren reinigen", "mdi:eye-outline"),
    ("mop", r"mop[_ ]?pad|wischtuch|wischpad|mop[_ ]?(?:left|life|time|rest)|mopp?[_ ]?(?:rest|restzeit|lebensdauer)", "Wischtuch", "mdi:texture-box"),
    ("dust_bag", r"dust[_ ]?bag|staubbeutel", "Staubbeutel", "mdi:delete-variant"),
    ("blades", r"blade|messer(?:qualit|alter|[_ ]?rest|[_ ]?life|$|[_ ]?zur)|cutting", "Messer", "mdi:saw-blade"),
    ("descale", r"descal|entkalk|limescale|kalk", "Entkalken", "mdi:water-sync"),
    ("salt", r"\bsalt|_salt|salz", "Salz nachfüllen", "mdi:shaker-outline"),
    ("rinse", r"rinse|klarsp(?:u|ü|ue)l", "Klarspüler nachfüllen", "mdi:water-plus-outline"),
    ("filter", r"filter", "Filter", "mdi:air-filter"),
    ("brush", r"brush|b(?:u|ü|ue)rste", "Bürste", "mdi:brush"),
    ("maint", r"consumable|verbrauchsmaterial|lifespan|lebensdauer|wartung|maintenance|service[_ ]?(?:due|interval|left)", "Wartung", "mdi:wrench-outline"),
]
_GROUP_RE = [(g, re.compile(p), label, icon) for g, p, label, icon in GROUPS]
# kein Verschleiß: Batterie, Funk, Fehler, Zähler fürs Gießen, Anwesenheit, Lebensende der Melder (eigene Aufgabe) …
EXCLUDE = re.compile(r"batter|rssi|signal|error|fehler|bucket|wasserbilanz|wasserverbrauch|anwesenheit|presence|is_life_end|life_end|"
                     r"servicemeldung|service_call|weather|wetter|motor|rpm|angebracht|attached|installed|spitzenwert|peak|"
                     r"total|gesamt|reinigungszeit|reinigungsbereich|area|count|anzahl")
USED = re.compile(r"used|usage|nutzung|benutzt|since|seit|betriebsstunden|working|elapsed|alter\b|alter$|_age|days$")
REMAIN = re.compile(r"left|remain|rest|verbleib|qualit|life|lebensdauer|lifespan")
DUE_STATES = {"present", "on", "low", "empty", "nearly_empty", "needed", "required", "due", "yes", "true", "replace", "dirty", "problem",
              "fast leer", "leer", "nötig"}
OK_STATES = {"off", "absent", "ok", "no", "false", "confirmed", "normal", "full", "none", "clean"}
DUR_H = {"s": 1 / 3600, "min": 1 / 60, "h": 1.0, "d": 24.0}
POWER_DEV = re.compile(r"solarbank|wallbox|elektroauto|wechselrichter|inverter|powerstation|ladestation|e3dc|anker|ecoflow|bms")
SKIP_PLATFORMS = {"mobile_app", "ios", "battery_notes_skip"}


def norm(text: str) -> str:
    return (text or "").lower()


def group_of(text: str) -> tuple[str, str, str] | None:
    t = norm(text)
    if EXCLUDE.search(t):
        return None
    for g, rx, label, icon in _GROUP_RE:
        if rx.search(t):
            return g, label, icon
    return None


def _num(state) -> float | None:
    try:
        return float(state)
    except (TypeError, ValueError):
        return None


def scan(hass, ignore: set[str] | None = None) -> list[dict[str, Any]]:
    """Alle Geräte durchsuchen. Ergebnis: Kandidaten (Verschleiß und Batterien) – die Werte liest evaluate() live."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er  # noqa: PLC0415
    try:
        from homeassistant.helpers import area_registry as ar  # noqa: PLC0415
        areas = ar.async_get(hass)
    except Exception:  # noqa: BLE001
        areas = None
    ents = er.async_get(hass)
    devs = dr.async_get(hass)
    by_dev: dict[str, list] = {}
    for e in list(getattr(ents, "entities", {}).values()):
        if getattr(e, "disabled_by", None) or not getattr(e, "device_id", None):
            continue
        by_dev.setdefault(e.device_id, []).append(e)
    out: list[dict[str, Any]] = []
    for dev_id, lst in by_dev.items():
        dev = devs.async_get(dev_id)
        dname = (getattr(dev, "name_by_user", None) or getattr(dev, "name", None) or "") if dev else ""
        model = str(getattr(dev, "model", "") or "") if dev else ""
        area = None
        if dev is not None and getattr(dev, "area_id", None) and areas is not None:
            a = areas.async_get_area(dev.area_id)
            area = getattr(a, "name", None)
        ids = [e.entity_id for e in lst]
        platforms = {getattr(e, "platform", "") for e in lst}
        st = {eid: hass.states.get(eid) for eid in ids}

        def text(eid: str) -> str:
            s = st.get(eid)
            e = next((x for x in lst if x.entity_id == eid), None)
            return " ".join(x for x in (eid, getattr(e, "original_name", None) or "", getattr(s, "name", "") if s is not None else "") if x)

        buttons = [eid for eid in ids if eid.startswith("button.")]
        resets = [b for b in buttons if re.search(r"reset|zur(?:u|ü|ue)ck|replaced|ersetzt|gewechselt", norm(text(b)))
                  and not re.search(r"error|fehler|anwesenheit|bucket|wasser|usage|spitzenwert|peak|home|hause|map|karte", norm(text(b)))]
        # ---- Verschleiß und Verbrauchsmaterial
        if not (platforms & SKIP_PLATFORMS):
            for eid in ids:
                dom = eid.split(".", 1)[0]
                if dom not in ("sensor", "binary_sensor") or (ignore and f"auto:dev:{eid}" in ignore):
                    continue
                s = st.get(eid)
                if s is None:
                    continue
                attrs = getattr(s, "attributes", {}) or {}
                if attrs.get("device_class") in ("battery", "connectivity", "running", "timestamp", "signal_strength", "power", "energy"):
                    continue
                t = text(eid)
                g = group_of(t)
                if g is None:
                    continue
                unit = attrs.get("unit_of_measurement")
                if dom == "binary_sensor":
                    kind = "bin"
                elif unit == "%":
                    kind = "pct"
                elif attrs.get("device_class") == "duration" or unit in DUR_H:
                    kind = "dur"
                elif _num(s.state) is None and (attrs.get("device_class") == "enum" or str(s.state).lower() in DUE_STATES | OK_STATES):
                    kind = "state"
                else:
                    continue
                low = norm(t)
                mode = "used" if kind in ("pct", "dur") and USED.search(low) and not REMAIN.search(low) else "remain"
                # Knopf dazu: gleiche Gruppe im Namen, sonst der einzige Reset-Knopf des Geräts
                btn = next((b for b in resets if (group_of(text(b)) or ("",))[0] == g[0]), None)
                if btn is None and len([x for x in resets if not re.search(r"replaced|ersetzt", x)]) == 1 and g[0] in ("filter", "maint"):
                    btn = next(x for x in resets if not re.search(r"replaced|ersetzt", x))
                out.append({"id": f"auto:dev:{eid}", "type": "dev", "eid": eid, "group": g[0], "label": g[1], "icon": g[2], "kind": kind,
                            "mode": mode, "button": btn, "device": dname or model, "area": area})
        # ---- Batterie (Battery Notes: „Batterie fast leer“, „Batterie ersetzt“, Batterie-Typ; sonst Ladestand)
        btype_eid = next((eid for eid in ids if eid.endswith("_battery_type")), None)
        btype = getattr(st.get(btype_eid), "state", None) if btype_eid else None
        if ("mobile_app" in platforms or "ios" in platforms or POWER_DEV.search(norm(f"{dname} {model}"))
                or any(eid.split(".", 1)[0] in ("vacuum", "lawn_mower") for eid in ids)
                or (btype and re.search(r"recharge|akku|li-?ion|built[- ]?in|fest verbaut", norm(btype)))
                or any((getattr(st.get(eid), "attributes", {}) or {}).get("device_class") in ("power",) for eid in ids)):
            continue
        low_bin = next((eid for eid in ids if eid.startswith("binary_sensor.") and eid.endswith("_battery_plus_low")), None)
        if low_bin is None:
            low_bin = next((eid for eid in ids if eid.startswith("binary_sensor.")
                            and (getattr(st.get(eid), "attributes", {}) or {}).get("device_class") == "battery"), None)
        level = next((eid for eid in ids if eid.startswith("sensor.") and eid.endswith("_battery_plus")), None) or next(
            (eid for eid in ids if eid.startswith("sensor.") and (getattr(st.get(eid), "attributes", {}) or {}).get("device_class") == "battery"
             and (getattr(st.get(eid), "attributes", {}) or {}).get("unit_of_measurement") == "%"), None)
        if not (low_bin or level) or (ignore and f"auto:bat:{dev_id}" in ignore):
            continue
        btn = next((b for b in buttons if re.search(r"battery_replaced|batterie[_ ]?ersetzt|batterie gewechselt", norm(text(b)))), None)
        out.append({"id": f"auto:bat:{dev_id}", "type": "bat", "low": low_bin, "level": level, "button": btn, "battery_type": btype,
                    "device": dname or model, "area": area, "entities": ids})
    return out


def evaluate(c: dict, hass, pct: float, hours: float, bat_pct: float) -> dict[str, Any] | None:
    """Wert und Fälligkeit eines Kandidaten jetzt. None = nicht lesbar."""
    if c["type"] == "bat":
        lvl = None
        if c.get("level"):
            s = hass.states.get(c["level"])
            lvl = _num(getattr(s, "state", None))
        low = None
        if c.get("low"):
            s = hass.states.get(c["low"])
            if s is not None and s.state in ("on", "off"):
                low = s.state == "on"
        if low is None and lvl is None:
            return None
        due = bool(low) if low is not None and c["low"].endswith("_battery_plus_low") else bool(low) or (lvl is not None and lvl <= bat_pct)
        return {"due": due, "value": lvl, "text": f"noch {round(lvl)} %" if lvl is not None else ("fast leer" if low else "ok"),
                "frac": (lvl / 100) if lvl is not None else None}
    s = hass.states.get(c["eid"])
    if s is None or s.state in ("unavailable", "unknown"):
        return None
    attrs = getattr(s, "attributes", {}) or {}
    if c["kind"] == "bin":
        return {"due": s.state == "on", "value": s.state, "text": "jetzt" if s.state == "on" else "ok", "frac": None}
    if c["kind"] == "state":
        st = str(s.state).lower()
        return {"due": st in DUE_STATES, "value": st, "text": "jetzt" if st in DUE_STATES else "ok", "frac": None}
    v = _num(s.state)
    if v is None:
        return None
    if c["kind"] == "pct":
        if c["mode"] == "used":
            return {"due": v >= 100 - pct, "value": v, "text": f"{round(v)} % verbraucht", "frac": max(0.0, min(1.0, 1 - v / 100))}
        return {"due": v <= pct, "value": v, "text": f"noch {round(v)} %" if v > 0 else "verbraucht", "frac": max(0.0, min(1.0, v / 100))}
    h = v * DUR_H.get(attrs.get("unit_of_measurement") or "h", 1.0)
    if c["mode"] == "used":
        txt = f"{round(h / 24)} Tage" if h >= 72 and (attrs.get("unit_of_measurement") == "d") else f"{round(h)} Std."
        return {"due": False, "value": h, "text": f"{txt} in Gebrauch", "frac": None, "info": True}
    if h <= 0:
        txt = f"seit {round(-h)} Std. überfällig" if h < -1 else "verbraucht"
    else:
        txt = f"noch {round(h)} Std." if h < 72 else f"noch {round(h)} Std. (≈ {round(h / 24)} Tage Betrieb)"
    return {"due": h <= hours, "value": h, "text": txt, "frac": None}
