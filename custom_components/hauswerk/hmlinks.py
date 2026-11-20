"""Direktverknüpfungen der Homematic-CCU lesen (Integration „Homematic(IP) Local“).

Die CCU verknüpft Geräte direkt miteinander – z. B. Wandthermostat → Heizkörper-Thermostat,
Fensterkontakt → Wandthermostat oder Wandthermostat → Kanal eines Fußbodenheizungs-Aktors. Solche
Verknüpfungen arbeiten ohne Home Assistant. Heizwerk liest sie über die Aktion
``homematicip_local.get_link_peers`` (nur lesen, ändert nichts an der CCU) und nutzt sie für:

- die Kopplung Wandthermostat/Heizkörper (statt sie am Modell zu raten),
- die Fensterpause (macht die CCU sie schon, schickt Hauswerk keine eigenen Befehle),
- Hinweise: Wandthermostat ohne Verknüpfung, Heizkörper ohne Wandthermostat, unbenutzte Aktor-Kanäle.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

HM_DOMAIN = "homematicip_local"


def peer_kind(model: str | None) -> str:
    """Art eines Geräts nach dem Modell: trv, wall, window, fal (Fußbodenheizungs-Aktor) oder other."""
    m = (model or "").upper()
    if "TRV" in m:
        return "trv"
    if any(x in m for x in ("WTH", "STH", "BWTH")):
        return "wall"
    if any(x in m for x in ("SWDO", "SRH", "SCI", "SWDM", "FCI")):
        return "window"
    if any(x in m for x in ("FAL", "FALMOT", "WGC", "MOD-HO")):
        return "fal"
    return "other"


def sensor_kind(model: str | None) -> str:
    """Art eines Senders für Licht: motion (Bewegungs-/Anwesenheitsmelder), button (Taster, Fernbedienung) oder other."""
    m = (model or "").upper()
    if any(x in m for x in ("SMI", "SPI", "SMO", "SPDR", "MDIR", "SEN-MDIR", "PIR")):
        return "motion"
    if any(x in m for x in ("WRC", "BRC", "RC", "PB", "PBI", "DBB", "KRC", "STI", "MOD-RC", "-BSM", "BSL")):
        return "button"
    return "other"


def fal_channels(model: str | None) -> int | None:
    """Anzahl Heizkreise eines Fußbodenheizungs-Aktors aus dem Modell (HmIP-FAL230-C6 → 6)."""
    m = re.search(r"-C(\d+)", str(model or "").upper())
    return int(m.group(1)) if m else None


def split_peer(peer: str) -> tuple[str, int | None]:
    addr, _, ch = str(peer).partition(":")
    try:
        return addr, int(ch)
    except ValueError:
        return addr, None


def analyze_room(room: dict, kind_of, addr_of, peers: dict[str, list[str]], devices: dict[str, dict]) -> dict | None:
    """Verknüpfungen eines Raums: Wandthermostate mit Gegenstellen, verknüpfte Heizkörper und Fensterkontakte.

    kind_of(entity) → "wall"/"trv"/None, addr_of(entity) → Geräteadresse oder None.
    Rückgabe None, wenn für keinen Wandthermostat des Raums Daten vorliegen.
    """
    climates = room.get("climates") or []
    walls = [c for c in climates if kind_of(c) == "wall"]
    trvs = [c for c in climates if kind_of(c) == "trv"]
    windows = room.get("windows") or []
    addr = {e: addr_of(e) for e in climates + windows}
    known = [w for w in walls if addr.get(w) and addr[w] in peers]
    if not known:
        return None
    in_room = {a: e for e, a in addr.items() if a}
    wall_out, linked_trvs, linked_windows, fal = [], set(), set(), []
    for w in known:
        items = []
        for p in peers.get(addr[w]) or []:
            a, ch = split_peer(p)
            dev = devices.get(a) or {}
            k = peer_kind(dev.get("model"))
            ent = in_room.get(a)
            items.append({"address": a, "channel": ch, "name": dev.get("name") or a, "model": dev.get("model"), "kind": k,
                          "entity": ent, "in_room": ent is not None})
            if ent in trvs:
                linked_trvs.add(ent)
            if ent in windows:
                linked_windows.add(ent)
            if k == "fal":
                fal.append({"address": a, "channel": ch, "name": dev.get("name") or a})
        # gleiche Gegenstelle mit mehreren Kanälen nur einmal zeigen (Kanäle zusammengefasst)
        merged: dict[str, dict] = {}
        for it in items:
            key = it["address"] if it["kind"] != "fal" else f"{it['address']}:{it['channel']}"
            if key in merged:
                merged[key]["channels"] = sorted({*merged[key]["channels"], it["channel"]} - {None})
            else:
                merged[key] = {**it, "channels": [it["channel"]] if it["channel"] is not None else []}
        wall_out.append({"entity": w, "address": addr[w], "peers": list(merged.values())})
    # Fensterkontakte können auch selbst als Sender verknüpft sein (Gegenstelle = Thermostat im Raum)
    for win in windows:
        a = addr.get(win)
        if a and any(split_peer(p)[0] in {addr.get(c) for c in climates} for p in peers.get(a) or []):
            linked_windows.add(win)
    return {"walls": wall_out, "linked_trvs": sorted(linked_trvs), "unlinked_trvs": sorted(set(trvs) - linked_trvs),
            "windows_ccu": sorted(linked_windows), "fal": fal}


def findings(rooms: dict[str, dict], analysis: dict[str, dict], name_of, devices: dict[str, dict],
             all_fal_peers: list[tuple[str, int | None]]) -> list[dict]:
    """Hinweise aus den Verknüpfungen: Wandthermostat ohne Verknüpfung, Heizkörper ohne Wandthermostat,
    unbenutzte Kanäle eines Fußbodenheizungs-Aktors."""
    out: list[dict] = []
    for room_id, info in analysis.items():
        room = rooms.get(room_id) or {}
        assist = set(room.get("assist_entities") or []) | set(room.get("pair_exclude") or [])
        for w in info["walls"]:
            if not w["peers"]:
                others = [e for e in (room.get("climates") or []) if e != w["entity"]] + list(room.get("show_entities") or [])
                out.append({"level": "warn" if others else "info", "room": room_id, "entity": w["entity"],
                            "text": f"{name_of(w['entity'])} ist in der CCU mit keinem Gerät verknüpft"
                                    + (" – Heizkörper bzw. Fußbodenheizung folgen ihm nicht" if others else " – steuert es dort etwas?")})
        for t in info["unlinked_trvs"]:
            if t not in assist and info["walls"]:
                out.append({"level": "info", "room": room_id, "entity": t,
                            "text": f"{name_of(t)} ist nicht mit dem Wandthermostat verknüpft – Hauswerk stellt ihn selbst"})
    # Aktor-Kanäle, die kein Wandthermostat nutzt
    by_fal: dict[str, set[int]] = {}
    for a, ch in all_fal_peers:
        if ch is not None:
            by_fal.setdefault(a, set()).add(ch)
    for a, used in by_fal.items():
        dev = devices.get(a) or {}
        n = fal_channels(dev.get("model"))
        if not n:
            continue
        free = [c for c in range(1, n + 1) if c not in used]
        if free:
            out.append({"level": "info", "room": None, "entity": None,
                        "text": f"{dev.get('name') or a}: Kanal {', '.join(map(str, free))} ist keinem Wandthermostat zugeordnet"
                                + (" – Heizkreis ohne Regelung?" if len(free) < n else "")})
    return out


# HmIP-Zeitbasis (TIME_BASE 0–7) in Sekunden; Basis 7 mit Faktor 31 = unendlich
_HMIP_BASE = [0.1, 1, 5, 10, 60, 300, 600, 3600]


def on_time(paramset: dict | None, kind: str = "SHORT") -> float | None:
    """Einschaltdauer einer Verknüpfung in Sekunden aus dem Link-Paramset (HmIP: Basis × Faktor, BidCos: Sekunden).
    None = unendlich bzw. unbekannt."""
    p = paramset or {}
    if f"{kind}_ON_TIME_BASE" in p and f"{kind}_ON_TIME_FACTOR" in p:
        base, fac = int(p[f"{kind}_ON_TIME_BASE"]), int(p[f"{kind}_ON_TIME_FACTOR"])
        if (base == 7 and fac == 31) or not 0 <= base < len(_HMIP_BASE):
            return None
        return _HMIP_BASE[base] * fac
    if f"{kind}_ON_TIME" in p:
        v = float(p[f"{kind}_ON_TIME"])
        return None if v >= 111600 or v <= 0 else v
    return None


def entity_channel(unique_id: str | None, addr: str) -> int | None:
    """Kanal einer Homematic-Entität aus ihrer unique_id (…<adresse>_<kanal>_…)."""
    m = re.search(re.escape(addr.lower()) + r"[_:](\d+)", (unique_id or "").lower())
    return int(m.group(1)) if m else None


class HmLinks:
    """Liest und merkt die Direktverknüpfungen der CCU."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.peers: dict[str, list[str]] = {}
        self.devices: dict[str, dict[str, Any]] = {}
        self.at: str | None = None
        self.error: str | None = None
        self.on_times: dict[tuple[str, str], float | None] = {}

    @property
    def available(self) -> bool:
        has = getattr(self.hass.services, "has_service", None)
        return bool(has and has(HM_DOMAIN, "get_link_peers"))

    def _index(self) -> None:
        """Alle Homematic-Geräte: Adresse → Name, Modell."""
        out: dict[str, dict[str, Any]] = {}
        reg = dr.async_get(self.hass)
        for dev in list(getattr(reg, "devices", {}).values()):
            for dom, ident in getattr(dev, "identifiers", set()) or set():
                if dom == HM_DOMAIN:
                    out[str(ident).split("@")[0]] = {"name": getattr(dev, "name_by_user", None) or getattr(dev, "name", None),
                                                     "model": getattr(dev, "model", None)}
        self.devices = out

    def addr(self, entity_id: str) -> str | None:
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None or not getattr(entry, "device_id", None):
            return None
        dev = dr.async_get(self.hass).async_get(entry.device_id)
        for dom, ident in getattr(dev, "identifiers", set()) or set():
            if dom == HM_DOMAIN:
                return str(ident).split("@")[0]
        return None

    async def _peers(self, a: str) -> list[str]:
        """Gegenstellen eines Geräts. Ältere BidCos-Geräte antworten nur je Kanal: dann Kanal 1–4 nacheinander."""
        try:
            res = await self.hass.services.async_call(HM_DOMAIN, "get_link_peers", {"device_address": a},
                                                      blocking=True, return_response=True)
            return list((res or {}).get(a) or [])
        except Exception:  # noqa: BLE001
            out: list[str] = []
            ok = False
            for ch in (1, 2, 3, 4):
                try:
                    res = await self.hass.services.async_call(HM_DOMAIN, "get_link_peers", {"device_address": a, "channel": ch},
                                                              blocking=True, return_response=True)
                except Exception:  # noqa: BLE001 - Kanal gibt es nicht
                    continue
                ok = True
                for v in (res or {}).values():
                    out.extend(v or [])
            if not ok:
                raise
            return out

    async def async_on_time(self, sender: str, entity_id: str, addr: str) -> tuple[bool, float | None]:
        """Einschaltdauer der Verknüpfung Sender-Kanal → Leuchte. (gelesen?, Sekunden oder None = dauerhaft)."""
        key = (sender, entity_id)
        if key in self.on_times:
            return True, self.on_times[key]
        entry = er.async_get(self.hass).async_get(entity_id)
        first = entity_channel(getattr(entry, "unique_id", None), addr)
        for ch in ([first] if first is not None else []) + [c for c in range(1, 9) if c != first]:
            try:
                res = await self.hass.services.async_call(HM_DOMAIN, "get_link_paramset",
                                                          {"sender_channel_address": sender, "receiver_channel_address": f"{addr}:{ch}"},
                                                          blocking=True, return_response=True)
            except Exception:  # noqa: BLE001 - kein Link auf diesem Kanal
                continue
            if res:
                self.on_times[key] = on_time(res)
                return True, self.on_times[key]
        return False, None

    def entities_of(self, addr: str) -> list[str]:
        """Entitäten eines Homematic-Geräts (für Sender wie Bewegungsmelder)."""
        reg = er.async_get(self.hass)
        dreg = dr.async_get(self.hass)
        out = []
        for ent in list(getattr(reg, "entities", {}).values()):
            dev = dreg.async_get(getattr(ent, "device_id", None)) if getattr(ent, "device_id", None) else None
            if dev and any(dom == HM_DOMAIN and str(i).split("@")[0] == addr for dom, i in getattr(dev, "identifiers", set()) or set()):
                out.append(ent.entity_id)
        return out

    async def async_refresh(self, entity_ids: list[str]) -> None:
        if not self.available:
            self.error = "Integration „Homematic(IP) Local“ nicht gefunden"
            return
        self._index()
        addrs = sorted({a for e in entity_ids if (a := self.addr(e))})
        peers: dict[str, list[str]] = {}
        errors = []
        for a in addrs:
            try:
                peers[a] = await self._peers(a)
            except Exception as err:  # noqa: BLE001 - Gerät weg, CCU nicht erreichbar: weiter mit den anderen
                errors.append(f"{a}: {err}")
        if peers:
            self.peers = peers
            self.on_times = {}
            self.at = dt_util.utcnow().isoformat()
        self.error = "; ".join(errors[:3]) if errors and not peers else None
        _LOGGER.debug("Homematic-Verknüpfungen: %d Geräte gelesen, %d Fehler", len(peers), len(errors))
