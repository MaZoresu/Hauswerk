"""Lernende Fertigerkennung (Kraftwerk) – nachgespielte Verläufe wie bei echten Homematic-Steckdosen.

Die Steckdosen melden nur bei Änderung (hier etwa alle 1–3 Minuten); ein Wert gilt bis zum nächsten.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "hauswerk" / "appliance_logic.py"
_spec = importlib.util.spec_from_file_location("hauswerk_appliance_logic", _PATH)
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

MIN = 60


def play(det, t0, segments, step=150):
    """Abschnitte [(Minuten, Watt), …] abspielen: alle `step` Sekunden ein Messwert (Homematic-artig).
    Watt None = Messwert fehlt. Zwischendurch läuft die Uhr (tick) wie im Betrieb alle 30 s."""
    t = t0
    events = []
    for minutes, watt in segments:
        end = t + minutes * MIN
        while t < end:
            det.feed(t, watt)
            for k in range(30, step, 30):
                if t + k < end:
                    det.tick(t + k)
            events += [(t, e) for e in det.events]
            det.events = []
            t += step
    return t, events


# Waschmaschine wie am 19.11.: Heizen, Waschen, 15 Min. Pause bei 3 W, Spülen/Schleudern, danach Anzeige 1,6 W
WASH_A = [(30, 0.05), (35, 1930), (15, 120), (15, 3.0), (43, 180), (27, 1.65), (60, 0.04)]
# zweiter Durchlauf mit 25 Min. Pause bei 1,64 W – genau der Wert, den sie auch nach dem Ende anzeigt
WASH_B = [(10, 1940), (15, 30), (25, 1.64), (5, 44), (15, 2.0), (10, 224), (45, 1.66), (30, 0.04)]


def starts_and_dones(events):
    return [e[0] for _, e in events if e[0] in ("start", "done", "discard")]


def test_waschmaschine_lernt_pausen():
    det = A.Detector("waschmaschine")
    assert det.model["learning"] and det.status(0)["label"] == "Bereit"
    t, ev = play(det, 0, WASH_A)
    assert starts_and_dones(ev) == ["start", "done"]
    run = det.runs[-1]
    assert 85 * MIN <= run["dur"] <= 112 * MIN and run["max_pause"] >= 14 * MIN and run["wh"] > 1000
    # das Ende kommt erst nach der Wartezeit (keine Meldung mitten in der 15-Min.-Pause)
    done_t = [tt for tt, e in ev if e[0] == "done"][0]
    assert done_t >= run["end"] + 29 * MIN
    # Lauf B: 25 Min. Pause bei Anzeige-Leistung – darf nicht als Ende gelten
    t, ev = play(det, t, WASH_B)
    assert starts_and_dones(ev) == ["start", "done"], starts_and_dones(ev)
    assert det.runs[-1]["max_pause"] >= 24 * MIN
    # gelernt: längste Pause ~25 Min. → Wartezeit länger als die Pause
    assert det.model["pause_max"] >= 24 * MIN and det.model["end_wait"] > det.model["pause_max"]
    # aktiv/ruhig aus den beobachteten Ruhe-Leistungen
    assert det.model["active_w"] >= 7.5 and det.model["quiet_w"] <= 3.1


def test_lernphase_und_dauer():
    det = A.Detector("waschmaschine")
    t = 0
    for _ in range(3):
        t, _ = play(det, t, WASH_A)
    m = det.model
    assert m["n"] == 3 and not m["learning"]
    assert m["dur_med"] and 85 * MIN <= m["dur_med"] <= 112 * MIN
    # neuer Lauf: Restzeit-Schätzung
    t, _ = play(det, t, [(20, 1930)])
    st = det.status(t)
    assert st["state"] == "running" and st["run"]["eta"] > t


def test_trockner_knitterschutz_kein_neuer_start():
    det = A.Detector("trockner")
    knitter = []
    for _ in range(12):  # 60 Min. Knitterschutz: kurze Trommeldrehungen
        knitter += [(1, 14.0), (4, 0.5)]
    t, ev = play(det, 0, [(10, 0.0), (100, 480)] + knitter + [(60, 0.4)], step=60)
    assert starts_and_dones(ev) == ["start", "done"]
    done_t = [tt for tt, e in ev if e[0] == "done"][0]
    assert done_t - det.runs[-1]["end"] <= 12 * MIN  # Trockner: zügig fertig, ohne Pausen
    assert det.state in ("done", "idle")


def test_fehlende_messwerte_sind_kein_ende():
    det = A.Detector("waschmaschine")
    t, ev = play(det, 0, [(5, 0.05), (30, 1930), (120, None)])
    assert det.state == "running", "Lücke darf nicht als Ruhe zählen"
    t, ev = play(det, t, [(10, 2.0)])
    assert det.state in ("running", "ending") and not any(e[0] == "done" for _, e in ev)
    t, ev = play(det, t, [(40, 0.05)])
    assert any(e[0] == "done" for _, e in ev)


def test_kurzer_start_ist_kein_durchlauf_und_korrektur():
    det = A.Detector("waschmaschine")
    t, ev = play(det, 0, [(5, 0.05), (3, 40), (40, 0.05)])
    assert "discard" in starts_and_dones(ev) and not det.runs
    # „Kein Durchlauf“ bei einem längeren Fehlstart hebt die Mindestenergie
    t, ev = play(det, t, [(15, 200), (35, 0.05)])
    assert det.state == "done"
    det.correct("no_run", t)
    assert det.state == "idle" and det.model["min_wh"] > 20 and not det.runs


def test_korrektur_laeuft_noch_verlaengert_wartezeit():
    det = A.Detector("trockner")
    # Trockner mit 15 Min. Abkühlpause: wird zu früh als fertig erkannt …
    t, ev = play(det, 0, [(5, 0), (60, 480), (16, 0.5)], step=60)
    assert det.state == "done"
    wait_before = det.model["end_wait"]
    text = det.correct("still_running", t)
    assert det.state == "running" and "Pause" in text and det.run["id"].endswith("-k")
    assert det.model["end_wait"] > wait_before
    # … läuft weiter und endet richtig
    t, ev = play(det, t, [(30, 480), (40, 0.5)], step=60)
    assert starts_and_dones(ev) == ["done"]
    assert det.runs[-1]["max_pause"] >= 10 * MIN


def test_korrektur_ist_schon_fertig_verkuerzt():
    det = A.Detector("waschmaschine")
    t = 0
    for _ in range(3):
        t, _ = play(det, t, WASH_A)
    wait = det.model["end_wait"]
    t, _ = play(det, t, [(60, 1900), (25, 0.05)])
    assert det.state == "ending"
    det.correct("finished", t)
    assert det.state == "done" and det.confirm[-1] >= 20 * MIN
    assert det.model["end_wait"] <= wait


def test_speichern_und_neustart_mitten_im_lauf():
    det = A.Detector("waschmaschine")
    t, _ = play(det, 0, [(5, 0.05), (40, 1930), (10, 2.0)])
    data = det.dump()
    again = A.Detector("waschmaschine", data)
    assert again.state in ("running", "ending") and again.last_w is None
    # Neustart dauerte 2 Std.: zählt nicht als Ruhe
    t2, ev = play(again, t + 2 * 3600, [(5, 2.0)])
    assert not any(e[0] == "done" for _, e in ev)
    t2, ev = play(again, t2, [(40, 0.05)])
    assert any(e[0] == "done" for _, e in ev)


def test_einheiten():
    assert A.to_watt("1.5", "kW") == 1500
    assert A.to_watt("250", "mW") == 0.25
    assert A.to_watt("unavailable", "W") is None
    assert A.to_watt("12", None) == 12
