"""Leistung messen: wie lange Berechnungen dauern, wie oft sie laufen und wie groß die Meldungen ans Panel sind.

Je Messpunkt die letzten Messungen der vergangenen 15 Minuten (Anzahl je Minute, Mittel, 95-%-Wert, Höchstwert) plus
Summen seit dem Start. Dazu die Berichte der Panels (je Gerät: Ladezeit, Zeichnen, Meldungen). Kostet selbst kaum etwas.
"""
from __future__ import annotations

import functools
import inspect
import json
import time
from collections import deque
from typing import Any

WINDOW = 900          # Sekunden für Rate und Verteilung
KEEP = 2000           # höchstens so viele Messungen je Messpunkt
SIZE_EVERY = 30       # Größe einer Meldung höchstens alle 30 s messen (json.dumps kostet selbst)

_data: dict[str, deque] = {}
_total: dict[str, list[float]] = {}   # name → [Anzahl, Summe ms, Max ms]
_sizes: dict[str, tuple[float, int]] = {}  # name → (Zeitpunkt, Bytes)
_panels: dict[str, dict] = {}
_started = time.time()


def record(name: str, ms: float) -> None:
    now = time.time()
    d = _data.get(name)
    if d is None:
        d = _data[name] = deque(maxlen=KEEP)
    d.append((now, ms))
    t = _total.setdefault(name, [0, 0.0, 0.0])
    t[0] += 1
    t[1] += ms
    t[2] = max(t[2], ms)


def count(name: str) -> None:
    record(name, 0.0)


class timer:  # noqa: N801 - als Kontextmanager gedacht: with perf.timer("…")
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *_exc) -> None:
        record(self.name, (time.perf_counter() - self.t0) * 1000)


def timed(name: str):
    """Dekorator für Methoden (sync und async); HA-Kennzeichen (@callback) bleiben erhalten."""
    def deco(fn):
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrap(*a, **kw):
                t0 = time.perf_counter()
                try:
                    return await fn(*a, **kw)
                finally:
                    record(name, (time.perf_counter() - t0) * 1000)
            return awrap

        @functools.wraps(fn)
        def wrap(*a, **kw):
            t0 = time.perf_counter()
            try:
                return fn(*a, **kw)
            finally:
                record(name, (time.perf_counter() - t0) * 1000)
        return wrap
    return deco


def size(name: str, payload: Any) -> None:
    """Größe einer Meldung (JSON) – gedrosselt."""
    now = time.time()
    last = _sizes.get(name)
    if last and now - last[0] < SIZE_EVERY:
        return
    try:
        n = len(json.dumps(payload, default=str, separators=(",", ":")).encode())
    except (TypeError, ValueError):
        return
    _sizes[name] = (now, n)


def panel_report(device: str, report: dict) -> None:
    _panels[device[:60]] = {**report, "at": time.time()}
    while len(_panels) > 8:
        _panels.pop(min(_panels, key=lambda k: _panels[k]["at"]))


def _pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(q * (len(vals) - 1) + 0.5))]


def summary() -> dict[str, Any]:
    now = time.time()
    out: dict[str, Any] = {}
    for name, d in _data.items():
        recent = [ms for t, ms in d if now - t <= WINDOW]
        span = min(WINDOW, now - _started) or 1
        tot = _total.get(name, [0, 0.0, 0.0])
        out[name] = {
            "per_min": round(len(recent) / span * 60, 2),
            "avg": round(sum(recent) / len(recent), 2) if recent else 0,
            "p95": round(_pct(recent, 0.95), 2),
            "max": round(max(recent), 2) if recent else 0,
            "load": round(sum(recent) / span / 10, 3),  # Anteil der Zeit in % (ms je s / 10)
            "total_n": int(tot[0]),
            "total_max": round(tot[2], 1),
        }
    return {
        "since": _started,
        "window": WINDOW,
        "points": dict(sorted(out.items())),
        "sizes": {k: v[1] for k, v in sorted(_sizes.items())},
        "panels": {k: v for k, v in sorted(_panels.items(), key=lambda kv: -kv[1]["at"])},
    }


def reset() -> None:
    global _started  # noqa: PLW0603
    _data.clear()
    _total.clear()
    _sizes.clear()
    _started = time.time()
