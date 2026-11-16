"""Klicktests fürs Panel: dev/vorschau.html in einem echten Browser.

Geprüft wird, was Nutzer tun – und was dabei schon schiefging:
- jede Seite über ihre Adresse öffnen (wie in Home Assistant, mit „location-changed“),
- jedes Widget in jeder Größe zeigen und über „Widget hinzufügen“ speichern,
- jedes Einstellungs-Fenster aller Module öffnen, etwas ändern und speichern,
- Rollwerk-Profile, Rollläden, Räume und Kraftwerk speichern,
- und alles, was das Panel dabei an Home Assistant schickt, gegen die echten Schemas aus api.py prüfen.

Läuft, wenn Playwright installiert ist (im CI immer); die Schema-Prüfung braucht voluptuous.
"""
from __future__ import annotations

import functools
import http.server
import importlib
import os
from pathlib import Path
import shutil
import sys
import threading
import types

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "custom_components" / "hauswerk"
EL = "document.querySelector('hauswerk-panel')"
KW = {
    "kw_solar": ["sensor.wechselrichter_pv_leistung"], "kw_grid": "sensor.smartmeter_wirkleistung",
    "kw_battery": "sensor.speicher_leistung", "kw_battery_soc": "sensor.speicher_ladestand",
    "kw_consumers": ["sensor.waermepumpe_leistung", "sensor.wallbox_leistung"],
}


# ------------------------------------------------------------ Umgebung
@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        chrome = os.environ.get("HW_CHROME") or ("/usr/bin/google-chrome" if Path("/usr/bin/google-chrome").exists() else None)
        try:
            b = p.chromium.launch(executable_path=chrome) if chrome else p.chromium.launch()
        except Exception as err:  # noqa: BLE001
            pytest.skip(f"kein Browser für die Klicktests: {err}")
        yield b
        b.close()


class Panel:
    """Eine geöffnete Vorschau mit Hilfen für die Tests."""

    def __init__(self, page):
        self.page = page
        self.errors: list[str] = []
        page.on("pageerror", lambda e: self.errors.append(f"Skriptfehler: {e}"))
        page.on("console", lambda m: m.type == "error" and self.errors.append(f"Konsole: {m.text}"))

    def js(self, code, arg=None):
        return self.page.evaluate(code, arg)

    def wait(self, ms=150):
        self.page.wait_for_timeout(ms)

    def failures(self) -> list[str]:
        """Fehlerkarten im Panel und Skriptfehler im Browser."""
        found = self.js(f"[...{EL}.shadowRoot.querySelectorAll('.hw-fail')].map((x) => x.innerText.replace(/\\s+/g, ' ').slice(0, 300))")
        last = self.js(f"{EL}._lastErr")
        out = list(self.errors) + found
        if last:
            out.append(f"{last['where']}: {last['msg']}\n{last.get('stack', '')}")
        return out

    def ok(self, what: str):
        bad = self.failures()
        assert not bad, f"{what}:\n" + "\n".join(bad)

    def view(self, view: str):
        self.js(f"{EL}._setView('{view}')")
        self.wait()

    def click(self, selector: str):
        """Klick wie ein Nutzer (Ereignis läuft durch den Klick-Handler des Panels)."""
        self.js(f"(s) => {{ const el = {EL}.shadowRoot.querySelector(s); if (!el) throw new Error('nicht gefunden: ' + s); el.click(); }}", selector)
        self.wait(200)

    def has(self, selector: str) -> bool:
        return self.js(f"(s) => !!{EL}.shadowRoot.querySelector(s)", selector)

    def sent(self) -> list[dict]:
        return self.js("window.hwSent || []")


@pytest.fixture
def panel(browser, server):
    page = browser.new_page(viewport={"width": 390, "height": 900})
    page.goto(f"{server}/dev/vorschau.html")
    page.wait_for_function(f"{EL} && {EL}._data")
    p = Panel(page)
    # Adresse wie in Home Assistant, damit Seitenwechsel über die Adresse laufen
    p.js("history.replaceState(null, '', '/hauswerk/start')")
    p.wait(300)
    yield p
    _check_sent(p.sent())
    page.close()


# ------------------------------------------------------------ Schemas aus api.py
def _stub(name, **attrs):
    mod = sys.modules.get(name) or types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


@functools.lru_cache(maxsize=1)
def _schemas() -> dict:
    """Je WebSocket-Befehl das Schema, wie api.py es Home Assistant meldet."""
    vol = pytest.importorskip("voluptuous")
    found: dict[str, dict] = {}

    def websocket_command(schema):
        def deco(func):
            for key, value in schema.items():
                if str(key) == "type":
                    found[value] = schema
            return func
        return deco

    _stub("homeassistant")
    _stub("homeassistant.components")
    ws = _stub("homeassistant.components.websocket_api", websocket_command=websocket_command, async_response=lambda f: f,
               require_admin=lambda f: f, event_message=lambda *a, **k: {}, result_message=lambda *a, **k: {},
               async_register_command=lambda *a, **k: None)
    sys.modules["homeassistant.components"].websocket_api = ws
    core = _stub("homeassistant.core")
    for k, v in {"HomeAssistant": object, "callback": lambda f: f}.items():
        if not hasattr(core, k):
            setattr(core, k, v)
    helpers = _stub("homeassistant.helpers")
    if not hasattr(helpers, "entity_registry"):
        helpers.entity_registry = _stub("homeassistant.helpers.entity_registry", async_get=lambda hass: None)
    pkg = Path(__file__).resolve().parent / ".hwapi_tmp" / "hwapi"
    shutil.rmtree(pkg.parent, ignore_errors=True)
    pkg.mkdir(parents=True)
    for name in ("api.py", "const.py", "logic.py"):
        shutil.copy(SRC / name, pkg / name)
    (pkg / "__init__.py").write_text("")
    sys.path.insert(0, str(pkg.parent))
    try:
        importlib.import_module("hwapi.api")
    finally:
        sys.path.remove(str(pkg.parent))
        shutil.rmtree(pkg.parent, ignore_errors=True)
    return {t: vol.Schema(s) for t, s in found.items()}


def _check_sent(messages: list[dict]):
    """Alles, was das Panel an Hauswerk geschickt hat, muss das Backend annehmen."""
    ours = [m for m in messages if str(m.get("type", "")).startswith("hauswerk/")]
    if os.environ.get("HW_DEBUG"):
        from collections import Counter
        print("\ngesendet:", dict(Counter(m["type"] for m in ours)),
              sorted({k for m in ours if m["type"] == "hauswerk/heizen/settings/save" for k in m["settings"]}))
    if not ours:
        return
    try:
        schemas = _schemas()
    except pytest.skip.Exception:
        return  # ohne voluptuous (lokal) nur die Klicktests
    problems = []
    for msg in ours:
        schema = schemas.get(msg["type"])
        if schema is None:
            problems.append(f"{msg['type']}: diesen Befehl kennt das Backend nicht")
            continue
        try:
            schema({k: v for k, v in msg.items() if k != "id"})
        except Exception as err:  # noqa: BLE001
            problems.append(f"{msg['type']}: {err}\n  gesendet: {str(msg)[:400]}")
    assert not problems, "Das Backend würde ablehnen:\n" + "\n".join(problems)


# ------------------------------------------------------------ Tests
def test_jede_seite_ueber_ihre_adresse(panel):
    """Jede Seite öffnen – die Adresse muss wieder auf dieselbe Seite führen (sonst springt das Panel zurück)."""
    views = panel.js("Object.keys(SLUGS)")
    room = panel.js(f"Object.keys({EL}._data.rooms)[0]")
    for configured in (False, True):
        if configured:
            panel.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
        for view in views:
            if view == "room":
                panel.js(f"{EL}._roomId = '{room}'")
            panel.view(view)
            tab = panel.js(f"{EL}._tab")
            assert tab == view, f"Seite {view} ({panel.js('location.pathname')}) springt zurück auf {tab}"
            assert panel.js(f"{EL}.shadowRoot.getElementById('main').innerHTML.trim().length") > 50, f"Seite {view} ist leer"
            panel.wait(250)  # nachgeladene Berichte und Statistik
            panel.ok(f"Seite {view}")
            assert panel.js(f"(v) => {{ history.replaceState(null, '', location.pathname); return {EL}._viewFromPath(); }}", view) == view


def test_widgets_in_jeder_groesse(panel):
    panel.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    types_ = panel.js("Object.keys(WIDGETS)")
    for size in ("s", "m", "l"):
        widgets = [{"id": f"w{i}", "type": t, "size": size, "title": None, "entities": []} for i, t in enumerate(types_)]
        panel.js(f"(w) => {{ {EL}._data.settings.start_widgets = w; }}", widgets)
        panel.view("start")
        panel.wait(400)
        panel.js(f"{EL}._renderMain()")
        panel.ok(f"Widgets in Größe {size}")
        assert panel.js(f"{EL}.shadowRoot.querySelectorAll('.wdg').length") == len(types_)


def test_jedes_widget_hinzufuegen(panel):
    """Wie im Fehlerbericht: Widget hinzufügen speichert die Startseite – das Backend muss jedes Widget annehmen."""
    panel.view("start")
    types_ = panel.js("Object.keys(WIDGETS)")
    for t in types_:
        panel.js(f"{EL}._openPop('widget-add')")
        panel.wait()
        panel.click(f'[data-action="w-add"][data-type="{t}"]')
        panel.ok(f"Widget {t} hinzufügen")
        panel.js(f"{EL}._closePop()")
    saved = [m for m in panel.sent() if m["type"] == "hauswerk/heizen/settings/save" and "start_widgets" in m["settings"]]
    assert {w["type"] for w in saved[-1]["settings"]["start_widgets"]} >= set(types_)


def _settings_pops(panel, view):
    panel.view(view)
    return panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.srow[data-action=\"pop-open\"]')].map((x) => x.dataset.pop)")


@pytest.mark.parametrize("view", ["house", "settings", "shutset", "kwset"])
def test_einstellungs_fenster(panel, view):
    """Jedes Fenster der Einstellungsliste öffnen, eine Auswahl und einen Schalter ändern, speichern."""
    if view == "kwset":
        panel.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    pops = _settings_pops(panel, view)
    assert pops, f"{view}: keine Einstellungen gefunden"
    for pop in pops:
        panel.js(f"(id) => {EL}._openPop(id)", pop)
        panel.wait()
        panel.ok(f"{view} › Fenster {pop}")
        # etwas ändern, damit beim Speichern wirklich etwas geschickt wird
        panel.js(f"""() => {{
            const r = {EL}.shadowRoot.getElementById('pop');
            r.querySelector('.seg:not(.on)[data-action="set-seg"]:not([disabled])')?.click();
            const box = r.querySelector('input[type=checkbox][data-set]:not([disabled])');
            if (box) {{ box.checked = !box.checked; box.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }})); }}
        }}""")
        panel.wait()
        panel.ok(f"{view} › Fenster {pop} nach Änderung")
        if panel.has('#pop [data-action="pop-save"]'):
            panel.click('#pop [data-action="pop-save"]')
        if panel.js(f"!!{EL}._pop"):
            panel.js(f"{EL}._closePop()")
        panel.ok(f"{view} › Fenster {pop} speichern")


def test_raeume_speichern(panel):
    for room in panel.js(f"Object.keys({EL}._data.rooms)"):
        panel.view("overview")
        panel.js(f"(id) => {EL}._openRoom({EL}._data.rooms[id])", room)
        panel.wait()
        panel.ok(f"Raum {room} öffnen")
        for tab in panel.js(f"[...{EL}.shadowRoot.querySelectorAll('#dialog [data-action=\"dialog-tab\"]')].map((x) => x.dataset.tab)"):
            panel.click(f'#dialog [data-action="dialog-tab"][data-tab="{tab}"]')
            panel.ok(f"Raum {room} › {tab}")
        panel.click('#dialog [data-action="room-save"]')
        panel.ok(f"Raum {room} speichern")


def test_rollwerk_profile_und_rolllaeden(panel):
    panel.view("shutset")
    profiles = panel.js(f"Object.keys({EL}._data.rollwerk.profiles)")
    sections = panel.js("RW_SECTIONS.map((x) => x[0])")
    for expert in (False, True):
        panel.js(f"{EL}._expert = {str(expert).lower()}; localStorage.setItem('hauswerk.experte', '{int(expert)}')")
        for pid in profiles:
            for sec in sections:
                panel.js(f"(id) => {EL}._openPop(id)", f"rwp:{pid}:{sec}")
                panel.wait()
                panel.ok(f"Profil {pid} › {sec} (Experte {expert})")
            panel.click('#pop [data-action="rwp-save"]')
            panel.ok(f"Profil {pid} speichern")
    for cover in panel.js(f"{EL}._data.settings.rw_covers"):
        panel.js(f"(id) => {EL}._openPop(id)", f"rwc:{cover}")
        panel.wait()
        panel.ok(f"Rollladen {cover}")
        if panel.has('#pop [data-action="rwc-save"]'):
            panel.click('#pop [data-action="rwc-save"]')
        panel.js(f"{EL}._pop && {EL}._closePop()")
        panel.ok(f"Rollladen {cover} speichern")


def test_rollwerk_assistent(panel):
    panel.view("shutset")
    panel.js(f"{EL}._cwizOpen()")
    panel.wait()
    panel.js(f"{EL}._pop.draft.covers = ['cover.ra_bad']")
    for step in range(1, 6):
        panel.js(f"(i) => {{ {EL}._pop.draft.step = i; {EL}._renderPop(); }}", step)
        panel.wait()
        panel.ok(f"Assistent Schritt {step + 1}")
    panel.click('#pop [data-action="cwiz-save"]')
    panel.ok("Assistent speichern")


def test_kraftwerk_erkennen_und_speichern(panel):
    panel.view("kwflow")
    panel.js(f"{EL}._kwPrefs()")
    panel.wait(300)
    panel.js(f"{EL}._openPop('kwdetect')")
    panel.wait()
    panel.click('#pop [data-action="kw-take"][data-k="all"]')
    panel.click('#pop [data-action="pop-save"]')
    panel.ok("Kraftwerk erkennen")
    panel.view("kwflow")
    assert panel.has(".kwd"), "Energiefluss fehlt nach dem Einrichten"
    for rng in ("today", "7", "30", "365"):
        panel.js(f"(r) => {{ {EL}._kwRange = r; }}", rng)
        panel.view("kwrep")
        panel.wait(300)
        panel.js(f"{EL}._renderMain()")
        panel.ok(f"Kraftwerk Verlauf {rng}")


def test_fehler_wird_angezeigt(panel):
    """Bricht eine Seite ab, erscheint eine Fehlerkarte mit „Diagnose kopieren“ statt einer leeren Seite."""
    panel.js(f"() => {{ {EL}._viewReport = () => {{ throw new Error('Testfehler'); }}; }}")
    panel.view("report")
    assert panel.has(".hw-fail [data-action='err-copy']")
    assert "Testfehler" in panel.js(f"{EL}._failText()")
    assert any(m["type"] == "system_log/write" for m in panel.sent())
    panel.js(f"{EL}._lastErr = null")
    panel.errors.clear()
    panel.js(f"(() => {{ const r = {EL}.shadowRoot; r.querySelectorAll('.hw-fail').forEach((x) => x.remove()); }})()")
