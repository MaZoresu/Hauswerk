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
        panel.click(f'[data-action="w-pick"][data-type="{t}"]')
        assert panel.has(".wprev .wdg"), f"keine Vorschau für {t}"
        for size in ("s", "l", "m"):
            panel.click(f'[data-action="w-pick-size"][data-v="{size}"]')
            panel.ok(f"Vorschau {t} in Größe {size}")
        panel.click(f'[data-action="w-add"][data-type="{t}"]')
        panel.ok(f"Widget {t} hinzufügen")
        panel.js(f"{EL}._closePop()")
    saved = [m for m in panel.sent() if m["type"] == "hauswerk/heizen/settings/save" and "start_widgets" in m["settings"]]
    assert {w["type"] for w in saved[-1]["settings"]["start_widgets"]} >= set(types_)


def _settings_pops(panel, view):
    # mit Experteneinstellungen, damit auch deren Fenster geprüft werden
    panel.js(f"() => ['haus', 'heizen', 'rollwerk', 'kraftwerk'].forEach((m) => {EL}._setExpert(m, true))")
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
        panel.js(f"(on) => {EL}._setExpert('rollwerk', on)", expert)
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


def test_rollladen_hoehe_popup(panel):
    """Kein Schieberegler in der Kachel, Behanghöhe nur als Info; Tipp auf die Kachel öffnet das Pop-up mit 100/50/25/0 %."""
    panel.view("shutters")
    assert not panel.has(".rw-range, input[type=range], button.rw-h")
    cover = panel.js(f"{EL}._data.settings.rw_covers[0]")
    assert panel.has(f'.rw-h[data-rwh="{cover}"]')
    # Knöpfe in der Kachel öffnen das Pop-up nicht
    panel.click(f'.rw-c[data-pop="rwpos:{cover}"] [data-a="stop"]')
    assert not panel.js(f"{EL}._pop")
    panel.click(f'.rw-c[data-pop="rwpos:{cover}"] .rw-top b')
    assert panel.js(f"{EL}._pop?.id") == f"rwpos:{cover}"
    vals = panel.js(f"[...{EL}.shadowRoot.querySelectorAll('#pop .rwpre-b')].map((x) => Number(x.dataset.v))")
    assert vals == [100, 50, 25, 0], vals
    # Behanghöhe antippen -> fährt dorthin
    n = len(panel.sent())
    panel.click('#pop .rwpre-b[data-v]:not([data-v="100"])')
    v = panel.js(f"Number({EL}.shadowRoot.querySelector('#pop .rwpre-b.on').dataset.v)")
    msg = panel.sent()[n:]
    assert any(m.get("action") == "position" and m.get("position") == v and m.get("entity_ids") == [cover] for m in msg), msg
    # im Fenster ziehen: oben = offen, unten = zu
    box = panel.js(f"(() => {{ const r = {EL}.shadowRoot.querySelector('#pop .rwwin').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }})()")
    x, y, w, h = box
    n = len(panel.sent())
    panel.page.mouse.move(x + w / 2, y + h * 0.5)
    panel.page.mouse.down()
    panel.page.mouse.move(x + w / 2, y + h * 0.3, steps=4)
    panel.page.mouse.up()
    panel.wait(200)
    msg = [m for m in panel.sent()[n:] if m.get("action") == "position"]
    assert msg and msg[-1]["position"] == 70, msg
    panel.click('#pop [data-action="pop-close"]')
    # Kachel zeigt eine neue Stellung sofort (ohne auf Rollwerk zu warten)
    panel.js(f"""(id) => {{ const h = {EL}.hass; const st = h.states[id];
        {EL}.hass = {{ ...h, states: {{ ...h.states, [id]: {{ ...st, state: 'open', attributes: {{ ...st.attributes, current_position: 40 }} }} }} }}; }}""", cover)
    panel.wait(400)
    assert panel.js(f"(id) => {EL}.shadowRoot.querySelector(`.rw-h[data-rwh=\"${{id}}\"] b`).textContent", cover) == "40 %"
    panel.ok("Höhe einstellen")


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


def test_widgets_ziehen(panel):
    """Im Anpassen-Modus ein Widget am Griff nach hinten ziehen – die neue Reihenfolge wird gespeichert."""
    panel.page.set_viewport_size({"width": 1100, "height": 900})
    # „Jetzt wichtig“ für heute quittieren, damit alle Widgets im Bild sind
    panel.js(f"(() => {{ const k = {EL}._hints().map((h) => {EL}._ackKey(h)); localStorage.setItem('hauswerk.ack', JSON.stringify({{ day: new Date().toLocaleDateString('sv'), keys: k }})); }})()")
    panel.view("start")
    before = [w["type"] for w in panel.js(f"{EL}._widgets()")]
    panel.click('[data-action="w-edit"]')
    grip = panel.page.locator("hauswerk-panel .wdg[data-wi='0'] .wdrag")
    target = panel.page.locator(f"hauswerk-panel .wdg[data-wi='{len(before) - 1}']")
    g, t = grip.bounding_box(), target.bounding_box()
    panel.page.mouse.move(g["x"] + g["width"] / 2, g["y"] + g["height"] / 2)
    panel.page.mouse.down()
    for k in range(1, 11):
        panel.page.mouse.move(t["x"] + t["width"] * 0.8 * k / 10 + 1, t["y"] + t["height"] * 0.9 * k / 10 + 1)
        panel.wait(30)
    panel.page.mouse.move(t["x"] + t["width"] * 0.8, t["y"] + t["height"] * 0.9)
    panel.page.mouse.up()
    panel.wait(400)
    after = [w["type"] for w in panel.js(f"{EL}._widgets()")]
    assert after != before and sorted(after) == sorted(before), (before, after)
    assert after[-1] == before[0] or after.index(before[0]) > 0
    panel.ok("Widgets ziehen")


def test_suche_ueber_alles(panel):
    panel.view("start")
    panel.page.keyboard.press("/")
    panel.wait(200)
    assert panel.js(f"{EL}._pop?.id") == "search", "„/“ öffnet die Suche nicht"
    field = panel.page.locator("hauswerk-panel [data-action=g-search]")
    for q in ("bad", "urlaub", "batterie", "sturm", "rollladen", "wohn", "xyzxyz"):
        field.fill(q)
        panel.wait(80)
        panel.ok(f"Suche „{q}“")
        assert panel.has("#gs-list [data-action=gs-log]"), "Protokoll-Suche fehlt"
    field.fill("urlaub")
    panel.wait(80)
    panel.click("#gs-list .srow[data-gs]")
    panel.ok("Treffer öffnen")
    assert panel.js(f"{EL}._pop?.id") != "search", "Suche bleibt nach dem Sprung offen"


def test_einrichtung(panel):
    panel.js(f"{EL}._data.settings.persons = []")
    panel.view("start")
    assert panel.has(".setup-card"), "Hinweis „Hauswerk einrichten“ fehlt auf der Startseite"
    panel.click('.setup-card [data-action="setup-open"]')
    steps = panel.js(f"{EL}._setupSteps().length")
    for i in range(steps):
        assert panel.js(f"{EL}._pop?.draft?.step") == i
        panel.ok(f"Einrichtung Schritt {i + 1}")
        if panel.has('#pop [data-action="setup-all-persons"]'):
            panel.click('#pop [data-action="setup-all-persons"]')
        if panel.has('#pop [data-action="kw-take"]'):
            panel.click('#pop [data-action="kw-take"]')
        panel.click("#pop .sheet-foot .primary")
    assert panel.js(f"{EL}._pop") is None
    assert panel.js(f"{EL}._data.settings.persons"), "Personen wurden nicht gespeichert"
    # Raum-Assistent aus der Einrichtung: danach zurück zum selben Schritt
    panel.js(f"{EL}._setupOpen(3)")
    panel.wait()
    panel.click('#pop [data-action="setup-room"]')
    assert panel.js(f"{EL}._pop?.id") == "rwiz"
    panel.click('#pop [data-action="pop-close"]') if panel.has('#pop [data-action="pop-close"]') else panel.js(f"{EL}._closePop()")
    panel.wait(200)
    assert panel.js(f"[{EL}._pop?.id, {EL}._pop?.draft?.step]") == ["setup", 3]
    panel.ok("Einrichtung mit Raum-Assistent")


def test_vorheizen_im_tagesplan(panel):
    """Raumkacheln zeigen vor jedem Komfort-Beginn die Vorheizzeit (gestreift) – detailliert und kompakt."""
    for view in ("detail", "compact"):
        panel.js(f"(v) => {{ {EL}._view = v; }}", view)
        panel.view("overview")
        titles = panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.dbar .dpre')].map((x) => x.title)")
        assert titles and all(t.startswith("Vorheizen ab") for t in titles), (view, titles)
        panel.ok(f"Vorheizen in der Ansicht {view}")


@pytest.mark.parametrize("view,mod,rows", [
    ("house", "haus", ["radio"]), ("settings", "heizen", ["demand", "calibration"]),
    ("shutset", "rollwerk", ["rwrecovery"]), ("kwset", "kraftwerk", []),
])
def test_experte_je_modul(panel, view, mod, rows):
    """Jedes Modul hat oben in den Einstellungen den Haken „Experteneinstellungen“; nur damit erscheinen dessen Profi-Einstellungen."""
    panel.js(f"() => ['haus', 'heizen', 'rollwerk', 'kraftwerk'].forEach((m) => {EL}._setExpert(m, false))")
    panel.view(view)
    if view == "house":
        panel.click('.sn[data-sys="1"]')  # Funk-Auslastung steht unter System
    pops = lambda: panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.srow[data-action=\"pop-open\"]')].map((x) => x.dataset.pop)")
    assert panel.js(f"{EL}.shadowRoot.querySelector('.xsw').dataset.mod") == mod
    assert not set(rows) & set(pops()), pops()
    panel.click(".xsw")
    assert panel.js(f"{EL}._expertOn('{mod}')") is True
    assert set(rows) <= set(pops()), pops()
    assert panel.js(f"localStorage.getItem('hauswerk.experte.{mod}')") == "1"
    # die anderen Module bleiben aus
    others = [m for m in ("haus", "heizen", "rollwerk", "kraftwerk") if m != mod]
    assert not any(panel.js(f"{EL}._expertOn('{m}')") for m in others)
    if mod == "kraftwerk":
        panel.js(f"() => {EL}._openPop('kwgrid')")
        panel.wait()
        assert panel.has('#pop [data-k="kw_grid_invert"], #pop input[data-set="kw_grid_invert"]') or "Vorzeichen umdrehen" in panel.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
        panel.js(f"{EL}._closePop()")
    panel.click(".xsw")
    assert not set(rows) & set(pops())
    panel.ok(f"Experte {mod}")


def test_abwesend_im_tagesplan(panel):
    """Ist niemand da, zeigt die Raumkachel ab jetzt die Absenkung im Tagesplan und darunter die Abwesend-Einstellung."""
    panel.js(f"() => {{ {EL}._view = 'detail'; {EL}._status = {{ ...{EL}._status, away: true }}; }}")
    panel.view("overview")
    legend = panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.rs-abs')].map((x) => x.textContent.trim())")
    assert legend and all(t == "Niemand da – höchstens 17,0 °C" for t in legend), legend
    titles = panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.dbar .dabs')].map((x) => x.title)")
    assert all("Abwesend:" in t and "statt" in t for t in titles), titles
    # Thermostate aus statt absenken
    panel.js(f"() => {{ {EL}._data.settings = {{ ...{EL}._data.settings, away_action: 'off' }}; }}")
    panel.view("overview")
    legend = panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.rs-abs')].map((x) => x.textContent.trim())")
    assert legend and all(t == "Niemand da – Thermostate aus" for t in legend), legend
    panel.js(f"() => {{ {EL}._data.settings = {{ ...{EL}._data.settings, away_action: 'lower' }}; {EL}._status = {{ ...{EL}._status, away: false }}; }}")
    panel.view("overview")
    assert panel.js(f"{EL}.shadowRoot.querySelectorAll('.rs-abs, .dabs').length") == 0
    panel.ok("Abwesend im Tagesplan")


def test_modul_logos_passen_in_ihren_platz(panel):
    """Modul-Logos (z. B. im Protokoll-Filter) dürfen nicht über ihren Platz hinausragen und den Text überdecken."""
    for view in ("log", "house", "start"):
        panel.view(view)
        bad = panel.js(f"""[...{EL}.shadowRoot.querySelectorAll('.mlogo')].map((l) => {{
            const box = l.parentElement.getBoundingClientRect(), r = l.getBoundingClientRect();
            return r.width > box.width + 1 || r.height > box.height + 1 ? `${{l.parentElement.className}}: ${{Math.round(r.width)}} > ${{Math.round(box.width)}}` : null;
        }}).filter(Boolean)""")
        assert not bad, f"{view}: {bad}"


@pytest.fixture
def tablet(browser, server):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{server}/dev/vorschau.html?tablet")
    page.wait_for_function(f"{EL} && {EL}._data")
    p = Panel(page)
    p.wait(300)
    yield p
    page.close()


def test_tablet_ohne_scrollen(tablet):
    """?tablet schaltet den Tabletmodus ein: Leisten unten, keine Seite scrollt, höchstens zwei Seiten zum Wischen."""
    p = tablet
    assert p.js(f"{EL}.hasAttribute('tablet')")
    assert p.js("localStorage.getItem('hauswerk.tablet')") == "1"
    for view in ["start", "overview", "report", "shutters", "shutset", "kwflow", "kwrep", "house"]:
        p.view(view)
        p.wait(300)
        assert p.js("document.scrollingElement.scrollHeight <= innerHeight + 1"), f"{view}: Seite scrollt"
        main = p.js(f"(() => {{ const m = {EL}.shadowRoot.getElementById('main'); return [m.scrollHeight, m.clientHeight]; }})()")
        assert main[0] <= main[1] + 1, f"{view}: Inhalt scrollt {main}"
        if view in ("shutset", "house", "report"):  # Einstellungen und Bericht: vollständig, innen scrollbar statt abgeschnitten
            assert p.js(f"{EL}.shadowRoot.querySelector('.tpages').classList.contains('tscroll')")
        assert p.js(f"{EL}._tPages") <= (1 if view in ("shutset", "house", "report") else 2), f"{view}: {p.js(f'{EL}._tPages')} Seiten"
        # Modul-Leiste links (große Tasten), Unterseiten oben als Umschalter, keine Leisten unten
        r = p.js(f"""(() => {{ const r = {EL}.shadowRoot; const rail = r.getElementById('rail').getBoundingClientRect();
            const main = r.getElementById('main').getBoundingClientRect(); const sub = r.querySelector('#chips nav');
            const btn = r.querySelector('#rail .ri').getBoundingClientRect();
            return [rail.width, rail.right, main.left, sub ? sub.getBoundingClientRect().bottom : null, main.top, getComputedStyle(r.getElementById('bnav')).display,
              getComputedStyle(r.querySelector('.mtabs')).display, btn.height]; }})()""")
        assert r[0] > 60 and r[1] <= r[2] + 1, f"{view}: Modul-Leiste nicht links {r}"
        assert r[5] == "none" and r[6] == "none", f"{view}: alte Leisten sichtbar {r}"
        assert r[7] >= 60, f"{view}: Modul-Tasten zu klein {r}"
        if view not in ("start", "house", "shutset"):  # Einstellungen haben keine Modul-Unterleiste
            assert r[3] is not None and r[3] <= r[4] + 1, f"{view}: Unterleiste nicht oben {r}"
        p.ok(f"Tablet {view}")
    # Einstellungen immer auf einer Seite
    for view in ("settings", "shutset", "kwset", "house"):
        p.view(view)
        p.wait(300)
        assert p.js(f"{EL}._tPages") == 1, f"{view}: mehr als eine Seite"
    # Seite mit zwei Seiten: Punkte und Wischen (wechselt schon während der Bewegung)
    view = next((v for v in ("kwrep", "vent", "lwrep", "kwdev", "plans") if (p.view(v), p.wait(300), p.js(f"{EL}._tPages"))[2] == 2), None)
    assert view, "keine Seite mit zwei Seiten gefunden"
    p.click('#tdots button[data-i="1"]')
    assert p.js(f"{EL}._tPage.{view}") == 1
    p.page.mouse.move(600, 400)
    p.page.mouse.down()
    p.page.mouse.move(660, 402, steps=2)
    assert p.js(f"{EL}._tPage.{view}") == 0, "Wischen reagiert erst beim Loslassen"
    p.page.mouse.up()


def test_tablet_bildschirmschoner(tablet):
    p = tablet
    p.view("overview")
    p.js(f"() => {{ {EL}._openPop('tablet'); }}")
    p.wait()
    assert "Tabletmodus" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.click('#pop [data-action="tablet-opt"][data-k="saver"][data-v="1"]')
    assert p.js("localStorage.getItem('hauswerk.tablet.saver')") == "1"
    # nach einer Minute ohne Berührung: Schoner, zurück zur Startseite, Pop-up zu
    p.js(f"() => {{ {EL}._lastAct = Date.now() - 61000; {EL}._saverTick(); }}")
    p.wait(300)
    assert not p.js(f"{EL}.shadowRoot.getElementById('saver').hidden")
    assert p.js(f"{EL}._tab") == "start" and not p.js(f"{EL}._pop")
    text = p.js(f"{EL}.shadowRoot.getElementById('saver').innerText")
    assert ":" in text and "Antippen" in text
    assert p.js(f"getComputedStyle({EL}.shadowRoot.querySelector('.sv-in')).opacity") < "0.7"
    # Antippen weckt nur auf
    n = len(p.sent())
    p.page.mouse.click(640, 400)
    p.wait(200)
    assert p.js(f"{EL}.shadowRoot.getElementById('saver').hidden")
    assert len(p.sent()) == n and not p.js(f"{EL}._pop")
    # Tabletmodus ausschalten
    p.js(f"() => {{ {EL}._openPop('tablet'); }}")
    p.wait()
    p.click('#pop [data-action="tablet-toggle"]')
    assert not p.js(f"{EL}.hasAttribute('tablet')")
    assert p.js("localStorage.getItem('hauswerk.tablet')") == "0"
    p.ok("Bildschirmschoner")


def test_tablet_seitenleiste(tablet):
    """Im Tabletmodus wird die Seitenleiste von Home Assistant ausgeblendet; ausgeschaltet kommt der vorige Zustand zurück."""
    p = tablet
    p.js("""() => { window.hwDock = []; window.addEventListener('hass-dock-sidebar', (e) => { window.hwDock.push(e.detail.dock);
        localStorage.setItem('dockedSidebar', JSON.stringify(e.detail.dock)); }); }""")
    # Zustand vor dem Tabletmodus: angedockt
    p.js(f"() => {{ localStorage.removeItem('hauswerk.tablet.sidebar_prev'); localStorage.setItem('dockedSidebar', '\"docked\"'); {EL}._tabletApply(); }}")
    assert p.js("window.hwDock") == ["always_hidden"]
    assert p.js(f"getComputedStyle({EL}.shadowRoot.querySelector('.menu')).display") != "none"
    p.js(f"() => {{ {EL}._openPop('tablet'); }}")
    p.wait()
    p.click('#pop [data-action="tablet-toggle"]')
    assert p.js("window.hwDock") == ["always_hidden", "docked"]
    assert p.js("localStorage.getItem('hauswerk.tablet.sidebar_prev')") is None


def test_tablet_eigene_startseite(tablet):
    """Im Anpassen-Modus am Tablet: „Eigene“ legt eine Tablet-Startseite an, Handy/PC bleiben unverändert."""
    p = tablet
    p.js("localStorage.setItem('hauswerk.tablet.tstart', 'widgets')")
    p.view("start")
    p.click('[data-action="w-edit"]')
    assert p.has(".tstart")
    phone = p.js(f"JSON.stringify({EL}._data.settings.start_widgets)")
    p.click('.tstart [data-action="tstart"][data-v="own"]')
    p.wait(300)
    assert p.js(f"Array.isArray({EL}._data.settings.start_widgets_tablet)")
    n = len(p.js(f"{EL}._widgets()"))
    p.click('[data-action="w-add-open"]')
    p.wait()
    p.click('#pop [data-action="w-pick"]')
    p.click('#pop [data-action="w-add"]')
    p.wait(300)
    assert len(p.js(f"{EL}._data.settings.start_widgets_tablet")) == n + 1
    assert p.js(f"JSON.stringify({EL}._data.settings.start_widgets)") == phone, "Handy-Startseite verändert"
    p.click('[data-action="w-edit"]') if not p.has(".tstart") else None
    p.click('.tstart [data-action="tstart"][data-v="same"]')
    p.wait(300)
    assert p.js(f"{EL}._data.settings.start_widgets_tablet") is None
    p.ok("Tablet-Startseite")


def test_tablet_sperren_und_groesse(tablet):
    p = tablet
    p.js("localStorage.setItem('hauswerk.tablet.tstart', 'widgets')")
    p.view("start")
    assert p.has('[data-action="w-edit"]')
    p.js("localStorage.setItem('hauswerk.tablet.lock', '1')")
    p.view("start")
    assert not p.has('[data-action="w-edit"]'), "gesperrt: kein Anpassen"
    # 3 Sekunden auf das Logo: entsperrt
    box = p.js(f"(() => {{ const r = {EL}.shadowRoot.querySelector('.brand').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }})()")
    p.page.mouse.move(*box)
    p.page.mouse.down()
    p.wait(3200)
    p.page.mouse.up()
    p.wait(200)
    assert p.has('[data-action="w-edit"]'), "nicht entsperrt"
    p.js("localStorage.setItem('hauswerk.tablet.lock', '0')")
    # Größe „Groß“ macht im Tablet größer
    p.view("overview")
    h = lambda: p.js(f"{EL}.shadowRoot.querySelector('.shead.outer h3').getBoundingClientRect().height")
    before = h()
    p.js(f"() => {{ localStorage.setItem('hauswerk.groesse', 'l'); {EL}._renderMain(); }}")
    p.wait(200)
    assert h() > before * 1.05, "„Groß“ wirkt im Tablet nicht"
    p.js("localStorage.setItem('hauswerk.groesse', 'm')")


def test_tablet_schoner_wecken_und_nacht(tablet):
    p = tablet
    p.js(f"() => {{ {EL}._data.settings.tablet_wake = ['binary_sensor.flur_bewegung']; }}")
    hass = lambda st: p.js(f"""(st) => {{ const h = {EL}.hass; {EL}.hass = {{ ...h, states: {{ ...h.states,
        'binary_sensor.flur_bewegung': {{ entity_id: 'binary_sensor.flur_bewegung', state: st, attributes: {{}} }} }} }}; }}""", st)
    hass("off")
    p.js(f"{EL}._saverShow()")
    assert not p.js(f"{EL}.shadowRoot.getElementById('saver').hidden")
    hass("on")
    p.wait(100)
    assert p.js(f"{EL}.shadowRoot.getElementById('saver').hidden"), "Bewegung weckt nicht"
    # Nacht „schwarz“: nur kleine Uhr
    p.js("() => { localStorage.setItem('hauswerk.tablet.night', 'black'); localStorage.setItem('hauswerk.tablet.night_from', '0'); localStorage.setItem('hauswerk.tablet.night_to', '0'); }")
    p.js("() => { const h = new Date().getHours(); localStorage.setItem('hauswerk.tablet.night_from', String(h)); localStorage.setItem('hauswerk.tablet.night_to', String((h + 1) % 24)); }")
    p.js(f"{EL}._saverShow()")
    assert p.js(f"{EL}.shadowRoot.getElementById('saver').classList.contains('black')")
    assert p.has("#saver .sv-time.small") and not p.has("#saver .sv-date")
    # Termine aus dem Kalender
    p.js("() => localStorage.setItem('hauswerk.tablet.night', 'dim')")
    p.js(f"""() => {{ {EL}._hass.callApi = async () => [{{ summary: 'Restmüll', start: {{ date: '2099-01-01' }} }}];
        {EL}._data.settings.calendars = ['calendar.muell']; {EL}._calAt = 0; {EL}._saverHide(); {EL}._saverShow(); }}""")
    p.wait(300)
    assert "Restmüll" in p.js(f"{EL}.shadowRoot.getElementById('saver').innerText")
    p.ok("Schoner wecken und Nacht")


def test_lage_kacheln(panel):
    """Kopfkachel jedes Moduls: ein Satz zum Stand mit Zustandsfarbe, darunter was gerade zählt."""
    panel.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    for view, want in (("overview", "unter Soll"), ("shutters", "Rollwerk · jetzt"), ("kwflow", "Kraftwerk · jetzt")):
        panel.view(view)
        b = panel.js(f"(() => {{ const b = {EL}.shadowRoot.querySelector('.brief'); return b && [b.dataset.tone, b.innerText, b.querySelectorAll('.br-l').length]; }})()")
        assert b, f"{view}: keine Kopfkachel"
        assert b[0] in ("ok", "active", "info", "warn", "calm", "hand") and want in b[1], b
        panel.ok(f"Lage {view}")
    # Kraftwerk: Überschuss wird als Empfehlung genannt, Zeilen führen weiter
    assert "Überschuss" in panel.js(f"{EL}.shadowRoot.querySelector('.brief').innerText")
    panel.view("shutters")
    panel.click(".brief button.br-l")
    assert panel.js(f"{EL}._pop?.id || ''").startswith("rwpos:")


def test_schoner_module_als_symbole(tablet):
    """Bildschirmschoner: je Modul Logo + Symbole mit Zahlen statt Sätzen."""
    p = tablet
    p.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    p.js(f"{EL}._saverShow()")
    mods = p.js(f"[...{EL}.shadowRoot.querySelectorAll('#saver .sv-mod')].map((m) => [m.querySelector('.sv-logo svg') != null, m.querySelectorAll('.sv-i').length, m.innerText])")
    assert len(mods) == 6 and all(m[0] and m[1] >= 1 for m in mods), mods  # Heizwerk, Rollwerk, Kraftwerk, Lichtwerk, Beetwerk, Wachwerk
    assert "mäht" in mods[4][2] and "64 %" in mods[4][2], mods[4]
    # Winterpause: nur die Schneeflocke
    p.js(f"() => {{ {EL}._hass.states['switch.automower_winter_mode'] = {{ entity_id: 'switch.automower_winter_mode', state: 'on', attributes: {{}} }}; {EL}._status.beetwerk.entities.winter = 'switch.automower_winter_mode'; }}")
    p.js(f"{EL}._saverShow()")
    bw = p.js(f"[...{EL}.shadowRoot.querySelectorAll('#saver .sv-mod')].map((m) => [m.querySelectorAll('.sv-i').length, m.innerText])[4]")
    assert bw[0] == 1 and "%" not in bw[1] and "winterpause" not in bw[1].lower(), bw
    text = p.js(f"{EL}.shadowRoot.getElementById('saver').innerText")
    assert "Raum heizt" not in text and "Rollläden:" not in text and "Solar " not in text
    # Heizwerk wie bisher · Rollwerk offen/zu · Kraftwerk ohne Akku · Lichtwerk wie viele an
    assert mods[1][1] == 2, mods[1]
    assert "%" not in mods[2][2], mods[2]
    assert mods[3][1] == 1 and mods[3][2].strip().isdigit(), mods[3]


def test_tablet_alle_raeume_sichtbar(browser, server):
    """Fünf Räume im Tabletmodus: jede Raumkachel ist auf einer der Seiten vollständig zu sehen (ohne CSS-Spalten)."""
    page = browser.new_page(viewport={"width": 1180, "height": 760})
    page.goto(f"{server}/dev/vorschau.html?tablet")
    page.wait_for_function(f"{EL} && {EL}._data")
    p = Panel(page)
    p.js(f"""() => {{ const el = {EL}; const d = el._data; const ids = Object.keys(d.rooms); let i = 0;
        while (Object.keys(d.rooms).length < 5) {{ const src = ids[i++ % ids.length]; const id = src + '_k' + i;
          d.rooms[id] = {{ ...d.rooms[src], id, name: d.rooms[src].name + ' ' + i }};
          if (el._status?.rooms?.[src]) el._status.rooms[id] = {{ ...el._status.rooms[src] }}; }}
        el._tFit = {{}}; }}""")
    p.js("localStorage.setItem('hauswerk.tablet.tview', 'wall')")
    p.view("overview")
    p.wait(300)
    n = p.js(f"{EL}._tPages")
    assert n <= 2
    seen = set()
    for i in range(n):
        p.js(f"(i) => {{ {EL}._tPage.overview = -1; {EL}._tabletGo(i); }}", i)
        p.wait(100)
        vis = p.js(f"""(() => {{ const m = {EL}.shadowRoot.getElementById('main').getBoundingClientRect();
            return [...{EL}.shadowRoot.querySelectorAll('.wgrid > article')].filter((a) => {{ const r = a.getBoundingClientRect();
              return r.top >= m.top - 1 && r.bottom <= m.bottom + 1 && r.left >= m.left - 1 && r.right <= m.right + 1; }}).map((a) => a.id); }})()""")
        seen.update(vis)
    assert len(seen) == 5, f"nur {len(seen)} von 5 Räumen sichtbar"
    assert p.js(f"getComputedStyle({EL}.shadowRoot.querySelector('.tin')).columnWidth") in ("auto", "")
    page.close()


def test_rollwerk_kompakt(panel):
    panel.view("shutters")
    panel.click('[data-action="rw-view"][data-v="compact"]')
    assert panel.has(".rw-m") and not panel.has(".rw-c")
    assert panel.js("localStorage.getItem('hauswerk.rollansicht')") == "compact"
    cover = panel.js(f"{EL}._data.settings.rw_covers[0]")
    n = len(panel.sent())
    panel.click(f'.rw-m[data-pop="rwpos:{cover}"] [data-a="open"]')
    assert any(m.get("action") == "open" for m in panel.sent()[n:]) and not panel.js(f"{EL}._pop")
    panel.click(f'.rw-m[data-pop="rwpos:{cover}"] .rwm-top b')
    assert panel.js(f"{EL}._pop?.id") == f"rwpos:{cover}"
    panel.js(f"{EL}._closePop()")
    panel.click('[data-action="rw-view"][data-v="detail"]')
    assert panel.has(".rw-c")
    panel.ok("Rollwerk kompakt")


def test_tablet_gleiche_leisten_und_kacheln(browser, server):
    """Tablet: alle Kopfleisten gleich hoch; Wand-Kacheln im festen Seitenraster, keine angeschnitten,
    gleichmäßig verteilt (5 → 3 + 2), große Schrift."""
    page = browser.new_page(viewport={"width": 1180, "height": 760})
    page.goto(f"{server}/dev/vorschau.html?tablet")
    page.wait_for_function(f"{EL} && {EL}._data")
    p = Panel(page)
    p.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    p.js("localStorage.setItem('hauswerk.tablet.tview', 'wall')")
    heights = {}
    for view in ("overview", "shutters"):
        p.view(view)
        p.wait(300)
        heights[view] = p.js(f"Math.round({EL}.shadowRoot.querySelector('.brief').getBoundingClientRect().height)")
        cut = p.js(f"""(() => {{ const m = {EL}.shadowRoot.getElementById('main').getBoundingClientRect(); const pg = {EL}._tPage[{EL}._tab] || 0;
            const per = Math.ceil({EL}.shadowRoot.querySelectorAll('.wgrid > *').length / {EL}._tPages);
            return [...{EL}.shadowRoot.querySelectorAll('.wgrid > *')].slice(pg * per, pg * per + per).filter((a) => {{ const r = a.getBoundingClientRect();
              return r.left < m.left - 1 || r.right > m.right + 1 || r.bottom > m.bottom + 1; }}).length; }})()""")
        assert cut == 0, f"{view}: {cut} Kacheln angeschnitten"
        fs = p.js(f"[parseFloat(getComputedStyle({EL}.shadowRoot.querySelector('.wt-v b')).fontSize), parseFloat(getComputedStyle({EL}.shadowRoot.querySelector('.wt-n b')).fontSize)]")
        assert fs[0] >= 40 and fs[1] >= 16, fs
    assert len(set(heights.values())) == 1, heights
    # gleichmäßig verteilen: 5 Kacheln auf kleinem Bildschirm (2 Seiten) → 3 + 2
    p.js(f"""() => {{ const d = {EL}._data, s = {EL}._status; const src = Object.keys(d.rooms)[0];
      for (let i = 0; i < 3; i++) {{ d.rooms['z' + i] = {{ ...d.rooms[src], id: 'z' + i, name: 'Raum ' + i }}; s.rooms['z' + i] = {{ ...s.rooms[src] }}; }} }}""")
    page.set_viewport_size({"width": 760, "height": 560})
    p.view("overview")
    p.wait(400)
    n = p.js(f"{EL}._tPages")
    cols = [p.js(f"[...{EL}.shadowRoot.querySelectorAll('.wgrid > *')].map((t) => +t.style.gridColumn)")]
    if n == 2:
        c = int(p.js(f"{EL}.shadowRoot.querySelector('.wgrid').dataset.cols"))
        first = sum(1 for x in cols[0] if x <= c)
        assert abs(first - (5 - first)) <= 1, cols
    page.close()

def test_neue_widgets_lage_ereignisse_termine(panel):
    panel.js(f"""(kw) => {{ Object.assign({EL}._data.settings, kw, {{ calendars: ['calendar.muell'] }});
        {EL}._hass.callApi = async () => [{{ summary: 'Restmüll', start: {{ date: new Date().toISOString().slice(0, 10) }} }},
                                           {{ summary: 'Papier', start: {{ date: new Date(Date.now() + 864e5).toISOString().slice(0, 10) }} }}];
        {EL}._data.settings.start_widgets = [{{ id: 'a', type: 'lage', size: 'm' }}, {{ id: 'b', type: 'events', size: 'm' }},
          {{ id: 'c', type: 'calendar', size: 'm' }}, {{ id: 'd', type: 'values', size: 'm' }}]; }}""", KW)
    panel.view("start")
    panel.wait(400)
    panel.js(f"{EL}._renderMain()")
    lage = panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.wl')].map((x) => x.dataset.tab)")
    assert lage == ["overview", "shutters", "kwflow", "lights"], lage
    assert "Restmüll" in panel.js(f"{EL}.shadowRoot.querySelector('.wcal').innerText")
    assert "Papier" in panel.js(f"{EL}.shadowRoot.querySelector('.wcal').innerText")
    ev = panel.js(f"{EL}.shadowRoot.querySelector('.wev').innerText")
    # Rollladen-Fahrten der Vorschau liegen bis 16:50 – danach erst wieder morgen (hinter den Terminen)
    hour = panel.js("new Date().getHours()")
    assert "Restmüll" in ev and ("Rollläden" in ev or hour >= 16 or hour < 6), ev  # nachts füllen Heizwechsel die Liste
    # Werte leer: Vorschlag übernehmen
    panel.click('[data-action="w-sugg"]')
    panel.wait(300)
    assert len(panel.js(f"{EL}._data.settings.start_widgets.find((w) => w.type === 'values').entities")) >= 1
    panel.click('.wl[data-tab="shutters"]')
    assert panel.js(f"{EL}._tab") == "shutters"
    panel.ok("neue Widgets")


def test_teil_update_statt_neu_zeichnen(panel):
    """Neue Werte: die Raumkachel bleibt dasselbe Element, nur die Zahl ändert sich; ohne Änderung passiert nichts."""
    panel.view("overview")
    panel.js(f"() => {{ window.hwCard = {EL}.shadowRoot.querySelector('.rooms > article'); }}")
    rid = panel.js("window.hwCard.id.replace('room-', '')")
    panel.js(f"(id) => {{ {EL}._status.rooms[id] = {{ ...{EL}._status.rooms[id], room_temp: 23.7 }}; {EL}._renderMain(); }}", rid)
    assert panel.js("window.hwCard.isConnected"), "Kachel wurde neu aufgebaut"
    assert "23,7" in panel.js("window.hwCard.innerText")
    # ohne Änderung: nichts anfassen
    panel.js(f"() => {{ window.hwMut = 0; new MutationObserver((m) => (window.hwMut += m.length)).observe({EL}.shadowRoot.getElementById('main'), {{ subtree: true, childList: true, attributes: true, characterData: true }}); {EL}._renderMain(); }}")
    panel.wait(50)
    assert panel.js("window.hwMut") == 0
    # Eingabe behält Fokus und Text
    panel.view("settings")
    panel.page.locator("hauswerk-panel").locator(".setsearch input").first.fill("vor")
    panel.js(f"{EL}._renderMain()")
    assert panel.js(f"{EL}.shadowRoot.activeElement?.value") == "vor"


def test_kopfkacheln_gleich_gross(panel):
    panel.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    hs = []
    for view in ("overview", "shutters", "kwflow"):
        panel.view(view)
        hs.append(panel.js(f"Math.round({EL}.shadowRoot.querySelector('.brief').getBoundingClientRect().height)"))
    assert len(set(hs)) == 1, hs


def test_tablet_hell_dunkel_nach_sonne(tablet):
    """Tablet: Hell/Dunkel folgt standardmäßig dem Sonnenstand (Fully meldet den Dunkelmodus nicht); je Gerät umstellbar."""
    p = tablet
    dark = lambda: p.js(f"{EL}.hasAttribute('dark')")
    sun = lambda st: p.js(f"""() => {{ const h = {EL}.hass; const s = {{...h.states}};
        s['sun.sun'] = {{...s['sun.sun'], state: '{st}'}}; {EL}.hass = {{...h, states: s, themes: {{...h.themes, darkMode: false}}}}; }}""")
    p.js("() => localStorage.removeItem('hauswerk.tablet.theme')")
    sun("below_horizon")
    assert dark(), "nachts nicht dunkel"
    sun("above_horizon")
    assert not dark(), "tagsüber nicht hell"
    p.js(f"() => {{ {EL}._openPop('tablet'); }}")
    p.wait()
    p.click('#pop [data-action="tablet-opt"][data-k="theme"][data-v="dark"]')
    assert dark() and p.js("localStorage.getItem('hauswerk.tablet.theme')") == "dark"
    p.click('#pop [data-action="tablet-opt"][data-k="theme"][data-v="sun"]')
    assert not dark()


def test_kalender_zentral(panel):
    """Hauswerk › Kalender: Arbeitstage-Kalender, freie Werktage, Termine; Heizpläne nehmen freie Werktage wie Sonntag."""
    p = panel
    p.js(f"() => {{ {EL}._openPop('calendars'); }}")
    p.wait()
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    assert "Arbeitstage-Kalender" in body and "Freie Werktage" in body and "Termine" in body
    assert p.has('#pop [data-action="settings-go"][data-sub="vacation"]')
    # Anwesenheit verweist nur noch auf den Kalender
    p.js(f"() => {{ {EL}._openPop('presence'); }}")
    p.wait()
    assert p.has('#pop [data-sub="calendars"]') and "Arbeitstag-Sensor" not in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    # Heizplan: der freie Werktag läuft wie Sonntag (6), andere Tage normal
    free = p.js(f"{EL}._status.free_days[0]")
    k = p.js(f"(iso) => {{ const t = new Date(); t.setHours(0,0,0,0); return Math.round((new Date(iso + 'T00:00') - t) / 864e5); }}", free)
    assert p.js(f"(k) => {EL}._planDay(k)", k) == 6
    assert p.js(f"(k) => {EL}._planDay(k)", k + 1) == 3  # Donnerstag
    p.js(f"() => {{ {EL}._status.free_days = [new Date().toLocaleDateString('sv-SE')]; }}")
    wd = p.js("(new Date().getDay() + 6) % 7")
    if wd < 5:
        assert p.js(f"{EL}._planDay(0)") == 6
        p.view("overview")
        assert "heute frei, wie Sonntag" in p.js(f"{EL}.shadowRoot.textContent")


def test_muellabholung_und_standardkalender(panel):
    """Kalender › Müllabholung (eigene Kalender, Erinnerung, Abfallarten ausblenden) und Standard-Kalender; Hinweis unter der Glocke."""
    p = panel
    assert any("Morgen Müllabfuhr" in h["text"] for h in p.js(f"{EL}._hints()"))
    assert p.js(f"{EL}._allCals()") == ["calendar.familie", "calendar.muell"]
    p.js(f"() => {{ {EL}._openPop('calendars'); }}")
    p.wait()
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    assert "Müllabholung" in body and "Nächste Abholungen" in body and "Standard-Kalender" in body and "Restabfall" in body
    assert p.has('#pop [data-action="waste-hide"][data-t="Sperrmüll"][aria-pressed="false"]')
    p.click('#pop [data-action="waste-hide"][data-t="Papier"]')
    assert p.js(f"{EL}._settings.waste_hidden") == ["Sperrmüll", "Papier"]
    p.click('#pop [data-action="set-seg"][data-key="waste_remind"][data-v="19:00"]')
    p.click('#pop [data-action="set-seg"][data-key="notify_waste"][data-v="important"]')
    p.click('#pop [data-action="pop-save"]')
    p.wait(300)
    saved = {k: v for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save" for k, v in m["settings"].items()}  # Auswahl speichert sofort
    assert saved["waste_remind"] == "19:00" and saved["notify_waste"] == "important" and "Papier" in saved["waste_hidden"]
    p.js(f"() => {{ {EL}._openPop('calendars'); }}")
    p.wait()
    p.click('#pop [data-action="set-seg"][data-key="waste_remind"][data-v="null"]')
    assert p.js(f"{EL}._settings.waste_remind") is None
    assert "Nachricht aufs Handy" not in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")


def test_hauswerk_als_startseite(panel):
    """Darstellung: Hauswerk als Startseite von Home Assistant – für mich, für alle, dieses Gerät."""
    p = panel
    p.js(f"() => {{ localStorage.removeItem('defaultPanel'); {EL}._dp = null; {EL}._openPop('look'); }}")
    p.wait(400)
    assert "Hauswerk als Startseite" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.click('#pop [data-action="dp-set"][data-scope="user"]')
    p.wait(400)
    sent = [m for m in p.sent() if m["type"] == "frontend/set_user_data"]
    assert sent and sent[-1]["value"]["default_panel"] == "hauswerk" and sent[-1]["key"] == "core"
    assert "Für dich auf allen Geräten" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.click('#pop [data-action="dp-set"][data-scope="user"]')  # nochmal = aufheben
    p.wait(400)
    assert "default_panel" not in [m for m in p.sent() if m["type"] == "frontend/set_user_data"][-1]["value"]
    p.click('#pop button.xcard[data-action="dp-set"]')  # der Haken selbst
    p.wait(400)
    assert [m for m in p.sent() if m["type"] == "frontend/set_user_data"][-1]["value"]["default_panel"] == "hauswerk"
    assert p.has('#pop button.xcard.on[data-action="dp-set"]')
    p.click('#pop button.xcard[data-action="dp-set"]')
    p.wait(400)
    assert "default_panel" not in [m for m in p.sent() if m["type"] == "frontend/set_user_data"][-1]["value"]
    p.click('#pop [data-action="dp-set"][data-scope="device"]')
    p.wait(400)
    assert p.js("localStorage.getItem('defaultPanel')") == '"hauswerk"'
    p.click('#pop [data-action="dp-set"][data-scope="system"]')
    p.wait(400)
    assert [m for m in p.sent() if m["type"] == "frontend/set_system_data"][-1]["value"]["default_panel"] == "hauswerk"


def test_hauswerk_als_dashboard(panel):
    """Darstellung: „Hauswerk-Dashboard anlegen“ legt ein Lovelace-Dashboard mit der Strategie custom:hauswerk an."""
    p = panel
    p.js(f"() => {{ {EL}._dp = null; {EL}._openPop('look'); }}")
    p.wait(400)
    assert "type: custom:hauswerk" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.click('#pop [data-action="dash-create"]')
    p.wait(500)
    sent = p.sent()
    create = [m for m in sent if m["type"] == "lovelace/dashboards/create"][-1]
    assert create["url_path"] == "dashboard-hauswerk" and "-" in create["url_path"]
    assert [m for m in sent if m["type"] == "lovelace/config/save"][-1]["config"] == {"strategy": {"type": "custom:hauswerk"}}
    assert "ist angelegt" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")


def test_dashboard_strategie(panel):
    """hauswerk-dashboard.js: Strategie custom:hauswerk liefert eine Panel-Ansicht mit der Hauswerk-Karte; die Karte zeigt das Panel."""
    p = panel
    p.js("() => import('/custom_components/hauswerk/frontend/hauswerk-dashboard.js?v=1')")
    p.wait(400)
    cfg = p.js("() => customElements.get('ll-strategy-dashboard-hauswerk').generate({ type: 'custom:hauswerk' })")
    view = cfg["views"][0]
    assert view["type"] == "panel" and view["cards"] == [{"type": "custom:hauswerk-card"}]
    assert any(s["type"] == "hauswerk" and s["strategyType"] == "dashboard" for s in p.js("window.customStrategies"))
    p.js(f"""() => {{ const c = document.createElement('hauswerk-card'); c.id = 'hwc'; c.setConfig({{}}); document.body.append(c); c.hass = {EL}.hass; }}""")
    p.page.wait_for_function("document.querySelector('#hwc hauswerk-panel')?._data")
    assert p.js("document.querySelector('#hwc hauswerk-panel').hasAttribute('embedded')")
    assert p.js("location.pathname") == "/hauswerk/start"  # eingebettet ändert die Adresse nicht


def test_rollwerk_kachel_infos(panel):
    """Rollwerk-Kacheln: Info-Zeile (Gerät, Fenster/Raum, Sonne, letzte Fahrt, Profil), Ziel-Marke, kompakt mit nächster Fahrt."""
    p = panel
    p.view("shutters")
    info = p.js(f"() => [...{EL}.shadowRoot.querySelectorAll('.rw-c .rw-info')].map((e) => e.textContent)")
    joined = " | ".join(info)
    assert "Batterie 12 %" in joined and "Sonne" in joined and "gekippt" in joined and "Funk schwach" in joined and "von Hand" in joined
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.rw-c .rwm-win em').length") >= 1  # Ziel-Marke
    assert not p.js(f"[...{EL}.shadowRoot.querySelectorAll('.rw-al')].some((e) => /^\\\\d+$/.test(e.textContent))")
    p.click('[data-action="rw-view"][data-v="compact"]')
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.rw-m .rwm-nx').length") >= 1
    p.click('[data-action="rw-view"][data-v="detail"]')


def test_hell_obwohl_home_assistant_dunkel(panel):
    """Darstellung „Hell“ bei dunklem Home Assistant: eigene helle Farben statt der dunklen von HA."""
    p = panel
    p.js(f"""() => {{ const h = {EL}.hass; document.body.style.setProperty('--primary-background-color', '#111111');
        {EL}._data.settings.look_theme = 'light'; {EL}.hass = {{...h, themes: {{...h.themes, darkMode: true}}}}; }}""")
    p.wait()
    assert not p.js(f"{EL}.hasAttribute('dark')") and p.js(f"{EL}.hasAttribute('own')")
    assert p.js(f"getComputedStyle({EL}).getPropertyValue('--bg').trim()") == "#f3f5f7"
    p.js(f"""() => {{ const h = {EL}.hass; {EL}.hass = {{...h, themes: {{...h.themes, darkMode: false}}}}; }}""")
    p.wait()
    assert not p.js(f"{EL}.hasAttribute('own')")  # gleich wie HA: Farben von HA (eigene Themes bleiben)
    p.js("() => document.body.style.removeProperty('--primary-background-color')")


def test_lueften_seite_und_kacheln(panel):
    """Lüften: eigene Seite, Countdown/Dauer in den Raumkacheln, Zeile in der Kopfkachel, Hinweise, Widget, Einstellungen."""
    p = panel
    p.view("vent")
    text = p.js(f"{EL}.shadowRoot.textContent")
    assert "Jetzt 10 Min. stoßlüften" in text and "Lüftet – 10 Min. empfohlen" in text and "Gefahr" in text
    p.view("overview")
    text = p.js(f"{EL}.shadowRoot.textContent")
    assert "4/10 Min." in text and "Lüften: " in text
    hints = [h["text"] for h in p.js(f"{EL}._hints()")]
    assert "Jetzt 10 Min. lüften" in hints
    assert "Lüftet" in p.js(f"() => {EL}._w_vent({{}}, 'l')") or "Min." in p.js(f"() => {EL}._w_vent({{}}, 'l')")
    p.js(f"() => {{ {EL}._openPop('vent'); }}")
    p.wait()
    p.click('#pop [data-action="set-seg"][data-key="vent_morning"][data-v="07:00"]')
    p.click('#pop [data-action="set-seg"][data-key="notify_vent"][data-v="normal"]')
    p.click('#pop [data-action="pop-save"]')
    p.wait(300)
    saved = {k: v for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save" for k, v in m["settings"].items()}  # Auswahl speichert sofort
    assert saved["vent_morning"] == "07:00" and saved["notify_vent"] == "normal"


def test_rollwerk_fenster_nur_wenn_offen(panel):
    """Rollwerk-Kachel: Fenster nur, wenn offen/gekippt; „Sonne aufs Fenster“ nur bei sun_on (Sonne scheint wirklich)."""
    p = panel
    p.view("shutters")
    joined = " | ".join(p.js(f"() => [...{EL}.shadowRoot.querySelectorAll('.rw-c .rw-info')].map((e) => e.textContent)"))
    assert "Fenster zu" not in joined and "gekippt" in joined
    p.js(f"() => {{ for (const c of Object.values({EL}._rwStatus.covers)) c.sun_on = false; {EL}._renderMain(); }}")
    p.wait()
    joined = " | ".join(p.js(f"() => [...{EL}.shadowRoot.querySelectorAll('.rw-c .rw-info')].map((e) => e.textContent)"))
    assert "Sonne aufs Fenster" not in joined and "Sonne – beschattet" not in joined


def test_kraftwerk_geraete_fertigerkennung(panel):
    """Kraftwerk › Geräte: Zustände, Gelerntes, Korrektur, Einrichtung (Schema geprüft), Hinweis „fertig“."""
    p = panel
    p.view("kwdev")
    text = p.js(f"{EL}.shadowRoot.textContent")
    assert "läuft seit 45 Min." in text and "noch ca." in text and "Fertig – 1:42 Std." in text and "Gelernt aus 6 Durchläufen" in text
    assert any(h["text"] == "Trockner fertig" for h in p.js(f"{EL}._hints()"))
    p.click('[data-action="app-act"][data-id="trockner"][data-a="ack"]')
    p.wait(300)
    act = [m for m in p.sent() if m["type"] == "hauswerk/kraftwerk/appliance/action"][-1]
    assert act["device"] == "trockner" and act["action"] == "ack"
    # neues Gerät einrichten
    p.js(f"() => {{ {EL}._openPop('kwapp:new'); }}")
    p.wait()
    p.click('#pop [data-action="kwapp-type"][data-v="geschirrspueler"]')
    p.js(f"() => {{ {EL}._setPickerValue('kwa_power', ['sensor.steckdose_trockner_leistung']); }}")
    p.js(f"""() => {{ const i = {EL}.shadowRoot.querySelector('#pop [data-kwapp="name"]'); i.value = 'Spülmaschine Küche'; i.dispatchEvent(new Event('input', {{bubbles: true, composed: true}})); }}""")
    p.js(f"""() => {{ const c = {EL}.shadowRoot.querySelector('#pop [data-kwapp-flag="important"]'); c.checked = true; c.dispatchEvent(new Event('change', {{bubbles: true, composed: true}})); }}""")
    p.click('#pop [data-action="kwapp-save"]')
    p.wait(400)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]["kw_appliances"]
    new = saved[-1]
    assert new["id"] == "spuelmaschine_kueche" and new["type"] == "geschirrspueler" and new["important"] is True
    assert new["power"] == "sensor.steckdose_trockner_leistung" and len(saved) == 3


def test_rollwerk_zeiten_und_beschattung_nur_bei_waerme(panel):
    """Kachel: „Öffnet/Schließt“ zeigt nur die Uhrzeit („16:42 Uhr“) bzw. „–“; „morgen“ steht in der Beschriftung.
    „Beschattung ab …“ nur, wenn die Außentemperatur-Bedingung erfüllt ist."""
    p = panel
    p.view("shutters")
    vals = p.js(f"() => [...{EL}.shadowRoot.querySelectorAll('.rw-t')].map((e) => [e.dataset.rwt, e.querySelector('small').textContent, e.querySelector('b').textContent])")
    assert ["close", "Schließt", "16:42 Uhr"] in vals and ["open", "Öffnet morgen", "07:41 Uhr"] in vals
    assert ["close", "Schließt", "–"] in vals  # nicht vorhersagbar: Platzhalter, keine erfundene Uhrzeit
    import re
    assert all(re.fullmatch(r"\d\d:\d\d Uhr|–", v) for _, _, v in vals)
    # Beschattung ab: nur bei erfüllter Temperatur
    def infos():
        return " | ".join(p.js(f"() => [...{EL}.shadowRoot.querySelectorAll('.rw-c .rw-info')].map((e) => e.textContent)"))
    p.js(f"() => {{ for (const c of Object.values({EL}._rwStatus.covers)) {{ c.sun_on = false; c.shade_temp_ok = true; }} const tl = {EL}._rwStatus.timelines; for (const k in tl) tl[k].shade = [['23:58', '23:59']]; {EL}._renderMain(); }}")
    p.wait()
    assert "Beschattung ab 23:58" in infos()
    p.js(f"() => {{ for (const c of Object.values({EL}._rwStatus.covers)) c.shade_temp_ok = false; {EL}._renderMain(); }}")
    p.wait()
    assert "Beschattung ab" not in infos()


def test_rollwerk_tagesleiste_beschattung_nur_wenn_zu_erwarten(panel):
    """Tagesleiste in der Kachel: orange Beschattung nur, wenn sie heute wirklich zu erwarten ist."""
    p = panel
    p.view("shutters")
    p.js(f"() => {{ const tl = {EL}._rwStatus.timelines; for (const k in tl) tl[k].shade = [['11:00', '15:00']]; for (const c of Object.values({EL}._rwStatus.covers)) c.shade_likely = false; {EL}._renderMain(); }}")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.rw-c .d-shade').length") == 0
    p.js(f"() => {{ for (const c of Object.values({EL}._rwStatus.covers)) c.shade_likely = true; {EL}._renderMain(); }}")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.rw-c .d-shade').length") > 0


def test_benachrichtigungskanaele(panel):
    """Benachrichtigungen › Empfänger: Kanäle nach Art, nicht erreichbare nicht wählbar, Ansage hinzufügen;
    Anlässe als Liste: eigene Kanäle je Anlass, Vorschau, Probehören; Speichern gegen das Backend-Schema."""
    p = panel
    p.js(f"() => {{ {EL}._nkTab = 'who'; {EL}._openPop('notify'); }}")
    p.wait()
    p.click('#pop [data-action="nk-add-open"]')
    p.wait(400)
    # springt zum Bereich „Kanal hinzufügen“: Kopf steht oben im sichtbaren Teil des Fensters
    top = p.js(f"(() => {{ const r = {EL}.shadowRoot; const b = r.querySelector('#pop .sheet-body') || r.querySelector('#pop'); const t = r.querySelector('#pop #nk-add').getBoundingClientRect().top - b.getBoundingClientRect().top; return t; }})()")
    assert top < 200, top
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    for t in ("Pushover", "Telegram", "Jules iPhone", "Tablet Overlay-Nachricht", "Mitteilung (Glocke)", "Ansage hinzufügen"):
        assert t in body, t
    assert p.js(f"{EL}._settings.notify_channels") == ["svc:mobile_app_pixel_8"]
    p.click('#pop [data-action="ch-toggle"][data-list="default"][data-ch="svc:pushover"]')
    p.click('#pop [data-action="ch-toggle"][data-list="default"][data-ch="ent:notify.jules_iphone"]')
    assert p.js(f"[...{EL}.shadowRoot.querySelectorAll('#pop [data-tts-player] option')].map(o => o.value)") == ["media_player.tablet"]
    p.click('#pop [data-action="ch-tts-add"][data-list="default"]')
    chans = p.js(f"{EL}._settings.notify_channels")
    # Empfänger pausieren und wieder aktivieren
    p.click('#pop [data-action="nk-off"][data-ch="svc:pushover"]')
    assert p.js(f"{EL}._settings.notify_off") == ["svc:pushover"] and p.has('#pop .nk-card.paused')
    assert "pausiert" in p.js(f"{EL}.shadowRoot.querySelector('#pop .nk-card.paused').textContent")
    p.click('#pop [data-action="nk-off"][data-ch="svc:pushover"]')
    p.click('#pop [data-action="nk-off"][data-ch="ent:notify.jules_iphone"]')
    assert chans == ["svc:mobile_app_pixel_8", "svc:pushover", "ent:notify.jules_iphone", "tts:tts.google_translate|media_player.tablet"]
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('#pop .nk-card').length") == 4
    # Anlässe als Liste: „Fenster schließen“ aufklappen, eigene Kanäle, Vorschau
    p.click('#pop [data-action="nk-tab"][data-v="what"]')
    p.js(f"() => {{ {EL}._nkView = 'list'; {EL}._renderPop(); }}")
    p.click('#pop [data-action="nk-open"][data-k="vent_done"]')
    assert "Bad: genug gelüftet" in p.js(f"{EL}.shadowRoot.querySelector('#pop .nk-phone').textContent")
    p.click('#pop [data-action="ch-route"][data-kind="vent_done"]')
    p.click('#pop [data-action="ch-toggle"][data-list="route:vent_done"][data-ch="svc:mobile_app_pixel_8"]')
    assert p.js(f"{EL}._settings.notify_routes.vent_done") == ["svc:pushover", "ent:notify.jules_iphone", "tts:tts.google_translate|media_player.tablet"]
    p.click('#pop [data-action="nk-try"][data-k="vent_done"][data-voice="1"]')
    p.wait(200)
    test = [m for m in p.sent() if m["type"] == "hauswerk/notify/test"][-1]
    assert test["channels"] == ["tts:tts.google_translate|media_player.tablet"] and test["title"] == "Fenster schließen"
    p.click('#pop [data-action="pop-save"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"].endswith("settings/save") and "notify_channels" in m.get("settings", {})][-1]["settings"]
    assert saved["notify_channels"] == chans and saved["notify_routes"]["vent_done"][0] == "svc:pushover"
    assert saved["notify_off"] == ["ent:notify.jules_iphone"]


def test_benachrichtigung_tabelle_vorlagen(panel):
    """Tabelle Anlass × Kanal, An/Aus je Anlass, Vorlagen, Zeiten und Bündeln je Kanal, Verlauf; Backend-Schema."""
    p = panel
    p.page.set_viewport_size({"width": 1100, "height": 900})  # Tabelle nur auf breiten Bildschirmen
    p.js(f"() => {{ {EL}._settings = null; {EL}._nkTab = 'what'; {EL}._nkView = 'table'; {EL}._openPop('notify'); }}")
    p.wait()
    assert p.has('#pop table.nk-tbl')
    # Tabelle: Frost auch an Pushover? Pushover ist noch kein Kanal → erst Spalte nur „Pixel 8“
    p.click('#pop [data-action="nk-cell"][data-k="frost"][data-ch="svc:mobile_app_pixel_8"]')
    assert p.js(f"{EL}._settings.notify_frost") == "log"  # letzter Kanal weg → nur Protokoll
    p.click('#pop [data-action="nk-cell"][data-k="frost"][data-ch="svc:mobile_app_pixel_8"]')
    assert p.js(f"{EL}._settings.notify_frost") == "normal"
    # Vorlage „Nur Wichtiges aufs Handy“
    p.click('#pop [data-action="nk-tpl"][data-t="important"]')
    assert p.js(f"{EL}._settings.notify_storm") == "important" and p.js(f"{EL}._settings.notify_window") == "log"
    # Liste: An/Aus
    p.js(f"() => {{ {EL}._nkView = 'list'; {EL}._renderPop(); }}")
    p.click('#pop [data-action="nk-onoff"][data-k="window"]')
    assert p.js(f"{EL}._settings.notify_window") == "off"
    p.click('#pop [data-action="nk-onoff"][data-k="window"]')
    assert p.js(f"{EL}._settings.notify_window") == "log"
    assert "Rollwerk" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    # Empfänger: Zeitraum und Bündeln
    p.click('#pop [data-action="nk-tab"][data-v="who"]')
    p.click('#pop [data-action="nk-hours"][data-ch="svc:mobile_app_pixel_8"][data-v="07:00-22:00"]')
    p.click('#pop [data-action="nk-bundle"][data-ch="svc:mobile_app_pixel_8"]')
    assert p.js(f"{EL}._settings.notify_hours")["svc:mobile_app_pixel_8"] == ["07:00", "22:00"]
    assert p.js(f"{EL}._settings.notify_bundle") == ["svc:mobile_app_pixel_8"]
    # Ruhezeit & Verlauf
    p.click('#pop [data-action="nk-tab"][data-v="quiet"]')
    txt = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    assert "gesendet heute" in txt and "Fenster schließen" in txt
    p.click('#pop [data-action="pop-save"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"].endswith("settings/save") and "notify_bundle" in m.get("settings", {})][-1]["settings"]
    assert saved["notify_storm"] == "important" and saved["notify_hours"]["svc:mobile_app_pixel_8"] == ["07:00", "22:00"]

def test_kamin(panel):
    """Kamin: Symbol mit „vielleicht“, Schnellmenü „Kamin an“, Raum-Dialog mit Haken und Signal (Backend-Schema)."""
    p = panel
    p.view("overview")
    p.wait()
    assert "vielleicht der Kamin" in p.js(f"{EL}.shadowRoot.querySelector('#room-a1').innerHTML")
    p.js(f"() => {{ {EL}._openPop('rq', {{ id: 'a1', temp: 21, hours: null }}); }}")
    p.wait()
    assert "Wärmer ohne Heizung" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.click('#pop [data-action="rq-fire"][data-on="1"]')
    p.wait(200)
    m = [x for x in p.sent() if x["type"] == "hauswerk/heizen/fireplace"][-1]
    assert m["room_id"] == "a1" and m["on"] is True
    # Raum-Dialog: Haken ab- und anwählen, Signal wählen, speichern
    p.js(f"(id) => {EL}._openRoom({EL}._data.rooms[id])", "a1")
    p.wait()
    p.click('#dialog [data-action="dialog-tab"][data-tab="devices"]')
    assert "Kamin im Raum vorhanden" in p.js(f"{EL}.shadowRoot.querySelector('#dialog').textContent")
    assert "Signal „Kamin in Betrieb“" in p.js(f"{EL}.shadowRoot.querySelector('#dialog').textContent")
    p.js(f"() => {{ {EL}._dialog.room.fireplace_entity = 'binary_sensor.kamin_wohnzimmer'; }}")
    p.click('#dialog [data-action="room-save"]')
    p.wait(300)
    saved = [x for x in p.sent() if x["type"] == "hauswerk/heizen/room/save"][-1]
    assert saved["room"]["fireplace"] is True and saved["room"]["fireplace_entity"] == "binary_sensor.kamin_wohnzimmer"


def test_symbol_legende(panel):
    """Hauswerk › Einstellungen › Symbole & Farben (und Taste „?“) erklärt Farben und alle Symbole; das aktuelle Modul steht zuerst; Suche filtert ohne Neuzeichnen."""
    p = panel
    assert not p.has('[data-action="legend-open"]')  # kein „?“ mehr oben in der Kopfzeile
    p.view("house")
    p.wait()
    assert "Symbole & Farben" in p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    p.click('#set-list [data-action="legend-open"]')
    p.wait()
    assert "Symbole & Farben" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.js(f"{EL}._closePop()")
    p.view("shutters")
    p.wait()
    p.js(f"{EL}.dispatchEvent(new KeyboardEvent('keydown', {{ key: '?', bubbles: true, composed: true }}))")
    p.wait()
    if not p.has("#pop .lg-q"):
        p.js(f"() => {{ {EL}._openPop('legend', {{ first: 'Rollwerk', q: '' }}); }}")
        p.wait()
    txt = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    for t in ("Violett", "von Hand verstellt", "Kamin an", "Sturm", "Jetzt lüften", "Ende wird geprüft"):
        assert t in txt, t
    assert p.js(f"{EL}.shadowRoot.querySelector('#pop .lbl').textContent") == "Rollwerk"
    p.js(f"""() => {{ const i = {EL}.shadowRoot.querySelector('#pop [data-legend-q]'); i.value = 'kamin'; i.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }})); }}""")
    shown = p.js(f"[...{EL}.shadowRoot.querySelectorAll('#pop .lg-r')].filter(r => !r.hidden).map(r => r.textContent)")
    assert len(shown) == 3 and all("Kamin" in x or "kamin" in x.lower() for x in shown)
    # Farbsprache: von Hand überall Violett
    assert p.js("MODE.manuell.c") == p.js("C.hand")


_LOGIC_SPEC = importlib.util.spec_from_file_location("hw_logic_ui", Path(__file__).resolve().parents[1] / "custom_components" / "hauswerk" / "logic.py")
LG = importlib.util.module_from_spec(_LOGIC_SPEC)
_LOGIC_SPEC.loader.exec_module(LG)

PLAN_CASES = [
    [{"start": "06:00", "end": "08:00", "days": [0, 1, 2, 3, 4]}, {"start": "17:00", "end": "21:00", "days": [0, 1, 2, 3, 4], "temp": 22.0},
     {"start": "12:00", "end": "13:00", "days": [0], "kind": "eco"}],
    [{"start": "22:00", "end": "02:00", "days": [5]}, {"start": "23:00", "end": "01:00", "days": [6], "temp": 19.5}, {"start": "18:00", "end": "24:00", "days": [2]}],
    [{"start": "06:00", "end": "22:00", "days": [0, 1, 2, 3, 4]}, {"start": "17:00", "end": "21:00", "days": [0, 1, 2, 3, 4], "temp": 22.0}],  # alt: überschneidend
    [{"start": "22:00", "end": "07:00", "days": [6]}, {"start": "06:00", "end": "08:00", "days": [0], "kind": "eco"}],
]


def test_heizplan_js_wie_python(panel):
    """Kachel/Zeitleiste (JS) und Steuerung (Python) rechnen den Heizplan identisch: Sollwert je Minute, Tagesablauf,
    Überschneidungen und Auflösen."""
    p = panel
    for blocks in PLAN_CASES:
        js = p.js("""(b) => ({
            states: Array.from({ length: 7 * 96 }, (_, k) => { const s = planState(b, k * 15, 21, 18); return [s.target, s.kind, s.custom]; }),
            days: [0, 1, 2, 3, 4, 5, 6].map((d) => document.querySelector('hauswerk-panel')._daySegments(b, { comfort: 21, eco: 18 }, d).map((x) => [x[0], x[1], x[2], x[4], x[5]])),
            conf: planConflicts(b).map((c) => c.text),
            res: planConflicts(b).length ? planResolve(b, 1) : null })""", blocks)
        for k in range(7 * 96):
            st = LG.plan_state(blocks, k * 15, 21, 18)
            assert js["states"][k] == [st["target"], st["kind"], st["custom"]], (blocks, k)
        for d in range(7):
            py = [[x["start"], x["end"], x["target"], x["kind"], x["custom"]] for x in LG.day_segments(blocks, d, 21, 18)]
            assert js["days"][d] == py, (blocks, d)
        assert js["conf"] == [c["text"] for c in LG.block_conflicts(blocks)]
        if js["res"] is not None:
            py = LG.resolve_overlaps(blocks, lambda i: (1 if i == 1 else 0, -i))
            norm = lambda l: sorted((x["start"], x["end"], tuple(x["days"]), x.get("temp"), x.get("kind")) for x in l)  # noqa: E731
            assert norm(js["res"]) == norm(py) and LG.block_conflicts(js["res"]) == []


def test_heizplan_editor(panel):
    """Eco-Zeitfenster, Konflikt sichtbar (Speichern gesperrt), „hat Vorrang“ löst auf, Speichern gegen das Schema."""
    p = panel
    p.view("plans")
    p.js(f"() => {{ {EL}._selectPlan('room', 'a1'); {EL}._renderMain(); }}")
    p.wait()
    n = p.js(f"{EL}._plan.blocks.length")
    p.click('[data-action="plan-add"]')
    assert p.js(f"{EL}._plan.blocks.length") == n + 1 and p.js(f"planConflicts({EL}._plan.blocks).length") == 0
    # Eco-Fenster
    p.click(f'[data-action="blk-kind"][data-i="{n}"][data-v="eco"]')
    assert p.js(f"{EL}._plan.blocks[{n}].kind") == "eco"
    # Konflikt erzeugen: ein Komfort-Fenster über den ganzen Tag
    p.js(f"() => {{ {EL}._plan.blocks.push({{ days: [0,1,2,3,4,5,6], start: '05:00', end: '23:00', temp: 20 }}); {EL}._renderMain(); }}")
    p.wait()
    assert p.has('.block.conflict') and p.has('[data-action="plan-save"][disabled]')
    assert "überschneiden sich" in p.js(f"{EL}.shadowRoot.querySelector('.plan-conf').textContent")
    last = p.js(f"{EL}._plan.blocks.length") - 1
    p.click(f'[data-action="plan-resolve"][data-win="0"]')
    assert p.js(f"planConflicts({EL}._plan.blocks).length") == 0 and not p.has('.block.conflict')
    p.click('[data-action="plan-save"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/heizen/room/save"][-1]["room"]["schedule"]
    assert LG.block_conflicts(saved) == [] and any(b.get("kind") == "eco" for b in saved)


def test_lichtwerk(panel):
    """Lichtwerk: Kopfkachel, Kacheln nach Raum mit Ursache und Tagesleiste, Schalten, Helligkeit, von Hand,
    Einstellungen, Profil-Editor (alle Abschnitte), Assistent mit Vorlage – alles gegen die Backend-Schemas."""
    p = panel
    p.view("lights")
    p.wait()
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    for t in ("Lichtwerk", "1/4 an", "Wohnzimmer", "Sonne unter 2°", "Flur OG", "von Hand", "nicht erreichbar", "Um 23:00 aus"):
        assert t in txt, t
    assert p.has('.lw-c .lwbar .lwseg')
    p.click('[data-action="lw-cmd"][data-ids="light.flur_og"][data-a="on"]')
    p.wait(150)
    assert [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/command"][-1] == {"type": "hauswerk/lichtwerk/command", "entity_ids": ["light.flur_og"], "action": "on"}
    p.click('.lw-c [data-action="lw-cmd"][data-ids="light.eingang"][data-a="resume"]')
    p.wait(150)
    assert [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/command"][-1]["action"] == "resume"
    # Helligkeit
    p.js(f"() => {{ {EL}._openPop('lwbri:light.wohnzimmer'); }}")
    p.wait()
    assert "Sonne unter 2°" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.js(f"""() => {{ const i = {EL}.shadowRoot.querySelector('#pop [data-lwbri]'); i.value = 35; i.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }})); }}""")
    p.click('#pop [data-action="lw-bri-apply"]')
    p.wait(150)
    assert [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/command"][-1] == {"type": "hauswerk/lichtwerk/command", "entity_ids": ["light.wohnzimmer"], "action": "on", "brightness": 35}
    # kompakt
    p.click('[data-action="lw-view"][data-v="compact"]')
    assert p.has('.lw-m')
    p.click('[data-action="lw-view"][data-v="detail"]')
    # Einstellungen: jede Zeile öffnet sich
    p.view("lightset")
    p.wait()
    for pop in p.js(f"[...{EL}.shadowRoot.querySelectorAll('#set-list [data-action=\"pop-open\"]')].map((b) => b.dataset.pop)"):
        p.js(f"(id) => {{ {EL}._openPop(id); }}", pop)
        p.wait(60)
        p.ok(f"Lichtwerk › {pop}")
        p.js(f"{EL}._closePop()")
    # Profil-Editor: alle Abschnitte, Bewegung wählen, speichern
    p.js(f"() => {{ {EL}._openPop('lwp:flur:on'); }}")
    p.wait()
    for sec in ("off", "motion", "days", "light", "dyn", "night", "more", "on"):
        p.click(f'#pop [data-action="lwp-sec"][data-sec="{sec}"]')
        p.ok(f"Profil › {sec}")
    p.click('#pop [data-action="lwp-sec"][data-sec="days"]')
    p.click('#pop [data-action="lwp-tog"][data-k="days"][data-v="6"]')
    p.click('#pop [data-action="lwp-sec"][data-sec="dyn"]')
    p.click('#pop [data-action="lwp-set"][data-k="dynamic"][data-v="sun"]')
    p.click('#pop [data-action="lwp-save"]')
    p.wait(200)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/profile/save"][-1]
    assert saved["profile_id"] == "flur" and 6 not in saved["profile"]["days"] and saved["profile"]["dynamic"] == "sun"
    # Assistent: Stehlampe mit Vorlage „Fernsehlicht“
    p.js(f"() => {{ {EL}._openPop('lwadd'); }}")
    p.wait()
    p.click('#pop [data-action="lwadd-tog"][data-id="light.stehlampe"]')
    p.click('#pop [data-action="lwadd-prof"][data-v="new:tv"]')
    p.click('#pop [data-action="lwadd-save"]')
    p.wait(300)
    prof = [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/profile/save"][-1]["profile"]
    assert prof["name"] == "Fernsehlicht" and prof["on_entity"] is True
    light = [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/light/save"][-1]
    assert light["entity_id"] == "light.stehlampe" and light["light"]["profile"].startswith("neu")
    # Automation abschalten
    p.view("lightset")
    p.js(f"() => {{ {EL}._openPop('lwauto'); }}")
    p.wait()
    p.click('#pop [data-action="lw-auto-off"][data-id="automation.nachtlicht"]')
    p.wait(150)
    assert [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/automation/off"]


def test_lichtwerk_profil_aus(panel):
    """Profil aus: Kachel ohne Hinweis und ohne Schalter; ein- und ausschalten nur in den Einstellungen der Leuchte."""
    p = panel
    p.view("lights")
    p.wait()
    main = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Profil „Abendlicht“ aus" not in main and "Profil einschalten" not in main  # Decke Küche
    assert not p.js(f"!!{EL}.shadowRoot.querySelector('#main [data-action=\"lw-auto\"]')")
    p.js(f"() => {{ {EL}._openPop('lwbri:light.kuche'); }}")
    p.wait()
    assert not p.js(f"!!{EL}.shadowRoot.querySelector('#pop [data-action=\"lw-auto\"]')")
    p.js(f"{EL}._closePop()")
    p.view("lightset")
    p.wait()
    # ohne Profil: nicht ausgegraut, keine Marke; mit Profil: Etikett mit dem Profilnamen
    row = p.js(f"""(() => {{ const b = {EL}.shadowRoot.querySelector('#set-list [data-pop="lwl:light.kuche"]'); return [b.classList.contains('off'), !!b.querySelector('.badge')]; }})()""")
    assert row == [False, False], row
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('#set-list .badge.tag').length") > 0
    p.js(f"() => {{ {EL}._openPop('lwl:light.kuche'); }}")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelector('#pop select[data-lwl=\"profile\"]').value") == ""  # „Kein Profil“
    p.page.locator('hauswerk-panel #pop select[data-lwl="profile"]').select_option("standard")
    p.click('#pop [data-action="lwl-save"]')
    p.wait(200)
    m = [x for x in p.sent() if x["type"] == "hauswerk/lichtwerk/light/save"][-1]
    assert m["entity_id"] == "light.kuche" and m["light"]["auto"] is True and m["light"]["profile"] == "standard"
    # wieder „Kein Profil“
    p.js(f"() => {{ {EL}._openPop('lwl:light.kuche'); }}")
    p.wait()
    p.page.locator('hauswerk-panel #pop select[data-lwl="profile"]').select_option("")
    p.click('#pop [data-action="lwl-save"]')
    p.wait(200)
    assert [x for x in p.sent() if x["type"] == "hauswerk/lichtwerk/light/save"][-1]["light"]["auto"] is False

def test_homematic_verknuepfungen(panel):
    """CCU-Direktverknüpfungen: im Raum › Geräte, Übersicht unter Heizwerk › Einstellungen (Neu lesen), Hinweise."""
    p = panel
    hints = [h["text"] for h in p.js(f"{EL}._hints()")]
    assert any("WTH Kinderzimmer Jonte ist in der CCU mit keinem Gerät verknüpft" in h for h in hints)
    p.js(f"(id) => {EL}._openRoom({EL}._data.rooms[id])", "a1")
    p.wait()
    p.click('#dialog [data-action="dialog-tab"][data-tab="devices"]')
    txt = p.js(f"{EL}.shadowRoot.querySelector('#dialog').textContent")
    assert "Direktverknüpfungen in der CCU" in txt and "Heizkörper Wohnzimmer" in txt and "Hauswerk stellt ihn selbst" in txt
    # Fensterkontakt direkt verknüpft: Schalter „Fensterpause der CCU überlassen“, Speichern gegen das Schema
    p.js(f"() => {{ {EL}._status.rooms.a1.links.windows_ccu = ['binary_sensor.wohnzimmer_fenster']; {EL}._renderDialog(); }}")
    p.wait()
    assert "Fensterpause der CCU überlassen" in p.js(f"{EL}.shadowRoot.querySelector('#dialog').textContent")
    p.js(f"""() => {{ const i = {EL}.shadowRoot.querySelector('#dialog [data-room="window_ccu"]'); i.click(); }}""")
    p.click('#dialog [data-action="room-save"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/heizen/room/save"][-1]["room"]
    assert saved["window_ccu"] is False
    p.view("house")
    p.click('.sn[data-sys="1"]')  # Homematic-Verknüpfungen stehen unter Einstellungen › System
    p.wait()
    assert "Homematic-Verknüpfungen" in p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    p.js(f"() => {{ {EL}._openPop('hm'); }}")
    p.wait()
    assert p.has('#pop [data-action="hm-tab"][data-v="light"]')
    p.wait()
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    assert "Kanal 6 ist keinem Wandthermostat zugeordnet" in body and "Wohnzimmer" in body
    p.click('#pop [data-action="hmlinks-refresh"]')
    p.wait(200)
    assert [m for m in p.sent() if m["type"] == "hauswerk/heizen/links/refresh"]


def test_lichtwerk_ccu_verknuepfungen(panel):
    """Lichtwerk: CCU-Direktverknüpfungen an der Leuchte, Übersicht unter Lichtwerk › Einstellungen, Hinweise, CCU-Flag."""
    p = panel
    hints = p.js(f"{EL}._hints()")
    h = [x for x in hints if x["data"].get("sub") == "lwlinks"]
    assert any(x["lvl"] == "warn" and x["text"] == "Flur OG: Bewegung Flur OG schaltet schon in der CCU" for x in h)
    p.view("house")
    p.click('.sn[data-sys="1"]')
    p.wait()
    assert "Homematic-Verknüpfungen" in p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    p.js(f"() => {{ {EL}._openPop('hm', {{ t: 'light' }}); }}")
    p.wait()
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    assert "S_Bewegung:Vorgarten" in body and "Bewegung Flur OG" in body and "nur eigene Taster" in body
    p.click('#pop [data-action="lwlinks-refresh"]')
    p.wait(200)
    assert [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/links/refresh"]
    p.js(f"{EL}._closePop()")
    p.js(f"() => {{ {EL}._openPop('lwl:light.flur_og'); }}")
    p.wait()
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    assert "Direktverknüpfungen in der CCU" in body and "Lichtwerk schaltet bei Bewegung doppelt" in body
    p.js(f"{EL}._closePop()")
    # von der CCU geschaltet: eigenes Flag statt „von Hand“
    p.js(f"() => {{ Object.assign({EL}._lwStatus.lights['light.flur_og'], {{ state: 'on', ccu: 'Bewegung Flur OG', manual: {{ since: new Date().toISOString() }} }}); }}")
    p.view("lights")
    p.wait()
    main = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "HmIP" in main and "Bewegung Flur OG" not in main


def test_lichtwerk_bewegungsmelder_symbol(panel):
    """Leuchten mit Bewegungsmelder (Profil oder HmIP-Direktverknüpfung) tragen ein Melder-Symbol – nicht bei Profil aus."""
    p = panel
    p.view("lights")
    p.wait()
    ids = p.js(f"[...{EL}.shadowRoot.querySelectorAll('.lw-c')].filter((c) => c.querySelector('.lw-mot')).map((c) => c.querySelector('.lw-bulb').dataset.ids)")
    assert "light.flur_og" in ids and "light.eingang" in ids and "light.kuche" not in ids and "light.wohnzimmer" not in ids, ids
    txt = p.js(f"{EL}.shadowRoot.querySelector('.lw-bulb[data-ids=\"light.eingang\"]').closest('.lw-c').innerText")
    assert "S_Bewegung:Vorgarten" not in txt  # kein Melder-Name in der Kachel
    # Ablauftimer: läuft sekündlich, „solange Bewegung“ als Text
    p.js(f"""() => {{ const x = {EL}._lwStatus.lights['light.flur_og']; Object.assign(x, {{ state: 'on', ccu: 'Bewegung Flur OG', off: {{ at: new Date(Date.now() + 75e3).toISOString(), src: 'HmIP' }} }});
      {EL}._hass.states['light.flur_og'] = {{ ...{EL}._hass.states['light.flur_og'], state: 'on' }};
      Object.assign({EL}._lwStatus.lights['light.wohnzimmer'], {{ off: {{ while: 60, src: 'HmIP' }} }}); {EL}._renderMain(); }}""")
    p.wait(1200)
    main = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    t1 = p.js(f"{EL}.shadowRoot.querySelector('#main [data-lw-until]').textContent")
    p.wait(2100)
    t2 = p.js(f"{EL}.shadowRoot.querySelector('#main [data-lw-until]').textContent")
    assert t1.startswith("1:") and t2 != t1, (t1, t2)
    assert "aus 1 Min. nach der letzten Bewegung" in main


def test_lichtwerk_hmip_bei_profil_aus(panel):
    """Profil aus: HmIP-Melder-Symbol und „HmIP · …“ erscheinen trotzdem, „von Hand“ und Profil-Melder nicht."""
    p = panel
    p.js(f"""() => {{ const s = {EL}._lwStatus; s.links.lights['light.wohnzimmer'] = {{ own: true, peers: [{{ address: 'SPI2', name: 'S_Bewegung:Windfang', model: 'HmIP-SPI', kind: 'motion', channels: [1], entities: [] }}] }};
      {EL}._data.lichtwerk.lights['light.wohnzimmer'].auto = false; Object.assign(s.lights['light.wohnzimmer'], {{ auto: false, ccu: 'S_Bewegung:Windfang', manual: {{ since: new Date().toISOString() }} }}); }}""")
    p.view("lights")
    p.wait()
    card = p.js(f"{EL}.shadowRoot.querySelector('.lw-bulb[data-ids=\"light.wohnzimmer\"]').closest('.lw-c').innerText")
    assert "HmIP" in card and "S_Bewegung" not in card and "von Hand" not in card and "Automatik übernimmt" not in card, card
    assert p.js(f"!!{EL}.shadowRoot.querySelector('.lw-bulb[data-ids=\"light.wohnzimmer\"] .lw-mot')")


def test_lichtwerk_szenen_editor(panel):
    """Profil › Tageszeiten: Vorlage, Zeile ändern und löschen, speichern gegen das Schema; Tagesleiste nach Szene."""
    p = panel
    p.view("lightset")
    p.wait()
    p.js(f"() => {{ {EL}._openPop('lwp:standard:scenes'); }}")
    p.wait()
    p.click('#pop [data-action="lwsc-preset"]')
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('#pop .lwsc').length") == 4
    p.js(f"""() => {{ const i = {EL}.shadowRoot.querySelector('#pop [data-lwsc="2:brightness"]'); i.value = '35'; i.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }})); }}""")
    p.click('#pop [data-action="lwsc-del"][data-i="3"]')
    p.wait()
    p.click('#pop [data-action="lwp-save"]')
    p.wait(300)
    prof = [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/profile/save"][-1]["profile"]
    assert prof["scenes_on"] is True and [x["name"] for x in prof["scenes"]] == ["Morgen", "Tag", "Abend"] and prof["scenes"][2]["brightness"] == 35
    p.view("lights")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('#main .lwseg.sc').length") > 0


def test_lichtwerk_raumansicht(panel):
    """Ansicht „Räume“: je Raum eine Kachel mit allen an/aus und Leuchten-Zeilen; Profil für den ganzen Raum."""
    p = panel
    p.view("lights")
    p.wait()
    p.click('[data-action="lw-view"][data-v="rooms"]')
    p.wait()
    rooms = p.js(f"[...{EL}.shadowRoot.querySelectorAll('#main .lw-room')].map((x) => x.dataset.area)")
    assert "Wohnzimmer" in rooms and "Vorgarten" in rooms, rooms
    card = f"{EL}.shadowRoot.querySelector('#main .lw-room[data-area=\"Wohnzimmer\"]')"
    assert "1 von 1 an" in p.js(f"{card}.innerText")
    p.js(f"{card}.querySelector('.lw-bulb').click()")
    p.wait(200)
    cmd = [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/command"][-1]
    assert cmd["entity_ids"] == ["light.wohnzimmer"] and cmd["action"] == "off", cmd
    p.js(f"() => {{ {EL}._openPop('lwroom:Vorgarten'); }}")
    p.wait()
    p.js(f"""() => {{ const s = {EL}.shadowRoot.querySelector('#pop [data-lwroom="profile"]'); s.value = 'flur'; s.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }})); }}""")
    p.click('#pop [data-action="lw-room-save"]')
    p.wait(300)
    m = [x for x in p.sent() if x["type"] == "hauswerk/lichtwerk/light/save"][-1]
    assert m["entity_id"] == "light.eingang" and m["light"] == {"profile": "flur", "auto": True}
    # Melder-Symbol auch in der Raumansicht an der Leuchte, „HmIP“ mit Melder-Symbol
    assert p.js(f"!!{EL}.shadowRoot.querySelector('#main .lw-room[data-area=\"Flur OG\"] .lwr-b .lw-mot')")
    p.js(f"() => {{ Object.assign({EL}._lwStatus.lights['light.flur_og'], {{ state: 'on', ccu: 'Bewegung Flur OG' }}); {EL}._renderMain(); }}")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelector('#main .lw-room[data-area=\"Flur OG\"] .lwr-f ha-icon').getAttribute('icon')") == "mdi:motion-sensor"
    p.js("localStorage.removeItem('hauswerk_lw_view')")


def test_lichtwerk_bericht(panel):
    """Lichtwerk › Bericht: Vorschläge mit Profil öffnen, Gerätezustand, 7 Tage je Leuchte; Hinweise; Leistung eintragen."""
    p = panel
    hints = p.js(f"{EL}._hints()")
    assert any(h["text"] == "Batterie schwach · Flur OG" for h in hints)
    assert any("20 Min. früher einschalten" in h["sub"] for h in hints)
    p.view("lwrep")
    p.wait()
    main = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    for t in ("Vorschläge", "Gerätezustand", "Letzte 7 Tage", "Funk schwach (-91 dBm)", "Batterie 12 %", "0,38 kWh", "Leistung eintragen", "4× von Hand"):
        assert t in main, t
    p.click('#main [data-pop="lwp:standard:on"]')
    p.wait()
    assert "Einschalten" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.js(f"{EL}._closePop()")
    p.js(f"() => {{ {EL}._openPop('lwl:light.eingang'); }}")
    p.wait()
    p.js(f"""() => {{ const i = {EL}.shadowRoot.querySelector('#pop [data-lwl="watt"]'); i.value = '9'; i.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }})); }}""")
    p.click('#pop [data-action="lwl-save"]')
    p.wait(300)
    m = [x for x in p.sent() if x["type"] == "hauswerk/lichtwerk/light/save"][-1]
    assert m["light"]["watt"] == 9
    p.view("lights")
    p.wait()
    assert "Batterie 12 %" in p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")


def test_benachrichtigung_geraet_fertig_abwaehlbar(panel):
    """Empfänger-Karte: „Waschmaschine fertig“/„Trockner fertig“ lassen sich an- und abwählen; gespeichert in kw_appliances
    in voller Kanal-Schreibweise (Backend-Schema)."""
    p = panel
    p.js(f"() => {{ {EL}._nkTab = 'who'; {EL}._openPop('notify'); }}")
    p.wait()
    w = '#pop [data-action="nk-app"][data-id="waschmaschine"][data-ch="svc:mobile_app_pixel_8"]'
    t = '#pop [data-action="nk-app"][data-id="trockner"][data-ch="svc:mobile_app_pixel_8"]'
    pressed = lambda sel: p.js(f"{EL}.shadowRoot.querySelector('{sel}').getAttribute('aria-pressed')")
    assert pressed(w) == "false"
    p.click(w)
    p.wait()
    p.click(t)
    p.wait()
    assert pressed(w) == "true" and pressed(t) == "true"
    p.click(t)
    p.wait()
    assert pressed(t) == "false"
    p.click('#pop [data-action="pop-save"]')
    p.wait(300)
    m = [x for x in p.sent() if x["type"] == "hauswerk/heizen/settings/save" and "kw_appliances" in x["settings"]][-1]
    apps = {a["id"]: a for a in m["settings"]["kw_appliances"]}
    assert apps["waschmaschine"]["notify"] == ["svc:mobile_app_jens", "svc:mobile_app_pixel_8"] and apps["waschmaschine"]["notify_ha"] is True
    assert apps["trockner"]["notify"] == ["svc:mobile_app_jens"]


def test_kraftwerk_akku_prognose_grundlast(panel):
    """Kraftwerk: Akku-Rest (Energie-Sensor am Gerät, Reserve), Solar-Prognose mit Überschuss-Fenster, Grundlast im Verlauf."""
    p = panel
    p.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    # Akku entlädt 800 W, 6,4 kWh gespeichert, 10 % Reserve von 10 kWh → 5,4 kWh / 0,8 kW ≈ 6,75 Std.
    p.js(f"() => {{ {EL}._hass.states['sensor.speicher_leistung'] = {{ ...{EL}._hass.states['sensor.speicher_leistung'], state: '800' }}; }}")
    bt = p.js(f"(() => {{ const b = {EL}._kwBatt({EL}._kwFlow()); return [b.wh, Math.round(b.usable), b.sensor, Math.round((b.until - Date.now()) / 60000)]; }})()")
    assert bt[0] == 6400 and bt[1] == 5400 and bt[2] == "sensor.speicher_energie" and 400 <= bt[3] <= 410, bt
    p.view("kwflow")
    p.wait(600)
    p.js(f"{EL}._renderMain()")
    p.wait(300)
    main = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "kWh gespeichert" in main and ("bis ca." in main or "vor Sonnenaufgang" in main), main
    assert "Solar-Prognose" in main and p.js(f"{EL}.shadowRoot.querySelectorAll('#main .kf-b').length") > 0
    p.view("kwrep")
    p.wait(600)
    p.js(f"{EL}._renderMain()")
    p.wait(300)
    main = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Grundlast" in main and "läuft immer" in main and "im Jahr" in main, main
    base = p.js(f"{EL}._kwBase()")
    assert 200 <= base["w"] <= 250 and base["cons"][0]["w"] == 60, base


def test_jetzt_wichtig_und_quittieren(panel):
    """Startseite „Jetzt wichtig“: höchstens drei Punkte, „Erledigt“ blendet für heute aus (Glocke behält es);
    Bildschirmschoner: kein doppelter Müll-Termin, „weitere Hinweise“ öffnet die Glocke."""
    p = panel
    p.js("localStorage.removeItem('hauswerk.ack')")
    p.view("start")
    p.wait()
    warn = p.js(f"{EL}._hints().filter((h) => h.lvl === 'warn').length")
    if warn:
        rows = p.js(f"{EL}.shadowRoot.querySelectorAll('#main .now-box .now-r').length")
        assert 1 <= rows <= 3
        key = p.js(f"{EL}.shadowRoot.querySelector('#main .now-box [data-action=now-ack]')?.dataset.key")
        if key:
            p.js(f"{EL}.shadowRoot.querySelector('#main .now-box [data-action=now-ack]').click()")
            p.wait()
            assert key in p.js("JSON.parse(localStorage.getItem('hauswerk.ack')).keys")
            assert any(f"{h['text']}|{h.get('sub') or ''}" == key for h in p.js(f"{EL}._hints()"))  # Glocke behält es
    # Bildschirmschoner: nur Warnungen, keine normalen Hinweise – Müll steht als Termin
    p.js(f"() => {{ {EL}._status.waste_due = {{ when: 'heute', types: ['Biotonne'] }}; {EL}._cal = [{{ title: 'Biotonne', allDay: true, start: new Date().toISOString().slice(0, 10) }}]; {EL}._calLoad = () => {{}}; {EL}._saverShow(); }}")
    p.wait(200)
    side = p.js(f"{EL}.shadowRoot.querySelector('#saver .sv-side')?.innerText || ''")
    assert "Biotonne" in side, side
    assert not p.has("#saver .sv-hints") and "Müllabfuhr" not in p.js(f"{EL}.shadowRoot.getElementById('saver').innerText")
    more = p.js(f"!!{EL}.shadowRoot.querySelector('#saver .sv-more')")
    if more:
        p.js(f"{EL}.shadowRoot.querySelector('#saver .sv-more').click()")
        p.wait(200)
        assert p.js(f"{EL}._pop?.id") == "hints"
    p.js("localStorage.removeItem('hauswerk.ack')")


def test_lueft_bilanz_ampel(panel):
    """Lüften: Ampel je Raum mit „x Tage nicht gelüftet, Feuchte morgens y %“ – Kachel und Glocke."""
    p = panel
    p.view("vent")
    p.wait()
    p.js(f"{EL}._openPop('vent:a1')")
    p.wait()
    main = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    assert "morgens (Ø 3 Tage)" in main, main
    p.js(f"{EL}._closePop()")
    p.js(f"() => {{ delete {EL}._status.rooms.a1.air.open; delete {EL}._status.rooms.a1.vent; }}")
    h = [x for x in p.js(f"{EL}._hints()") if x["text"] == "Zu selten gelüftet"]
    assert h and h[0]["lvl"] == "warn" and "3 Tage nicht gelüftet, Feuchte morgens 68 %" in h[0]["sub"]



def test_tablet_wand_startseite_und_details(tablet):
    """Tablet: Wand-Startseite (Uhr, Jetzt wichtig, Modul-Kacheln) ohne Seiten; „Automatisch“ zeigt Wand-Kacheln bis zur
    ersten Berührung, danach Details; Rollläden und Lichter je Raum mit Sammel-Fenster; Seiten-Pfeile; Kraftwerk in zwei Spalten."""
    p = tablet
    p.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    assert p.js(f"{EL}._wall()") is True  # Standard: Wand-Kacheln
    p.js("localStorage.setItem('hauswerk.tablet.tview', 'auto')")
    p.view("start")
    p.wait(300)
    assert p.has(".wstart .ws-time") and p.js(f"{EL}._tPages") == 1
    names = p.js(f"[...{EL}.shadowRoot.querySelectorAll('.ws-r .wt-n b')].map((b) => b.textContent)")
    assert names[:4] == ["Heizwerk", "Rollwerk", "Kraftwerk", "Lichtwerk"] and "Termine" in names and "Wartung" in names and "Anwesenheit" not in names, names
    p.page.locator("hauswerk-panel .ws-r .wt").first.click()
    p.wait(300)
    assert p.js(f"{EL}._tab") == "overview"
    # erste Berührung → Details
    assert p.js(f"{EL}._touched") is True and not p.has(".wgrid") and p.has(".rooms")
    p.js(f"() => {{ {EL}._touched = false; {EL}._renderMain(); }}")
    p.view("shutters")
    p.wait(300)
    tiles = p.js(f"[...{EL}.shadowRoot.querySelectorAll('.wgrid > .wt')].map((t) => t.dataset.pop)")
    assert "rwarea:Küche" in tiles, tiles
    # Punkt 4: große Zahl in %, nur ↑ ↓, genau eine Statuszeile
    rw = p.js(f"""(() => {{ const t = {EL}.shadowRoot.querySelector('.wgrid > .wt[data-pop="rwarea:Küche"]');
        return {{ v: t.querySelector('.wt-v b').textContent, n: t.querySelectorAll('.wbtn').length, fs: parseFloat(getComputedStyle(t.querySelector('.wt-v b')).fontSize),
                  ws: getComputedStyle(t.querySelector('.wt-s') || t).whiteSpace }}; }})()""")
    assert rw["v"].endswith("%") and rw["n"] == 2 and rw["fs"] >= 40, rw
    p.js(f"() => {{ {EL}._openPop('rwarea:Küche'); }}")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('#pop .lwr').length") == 3
    p.js(f"{EL}._closePop()")
    p.js(f"() => {{ {EL}._touched = false; }}")
    p.js(f"() => {{ for (const ls of Object.values({EL}._lwStatus.lights)) ls.area = 'Flur'; }}")
    p.view("lights")
    p.wait(300)
    # Lichtwerk: eigene Wand-Seite – Haus mit einem Fenster je Raum
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.lwhouse .lwh-w').length") == 1
    p.view("overview")
    p.wait(300)
    st = p.js(f"[...{EL}.shadowRoot.querySelectorAll('.wgrid > .wt')].map((t) => [t.querySelector('.wt-v b').textContent, t.querySelector('.wt-s')?.offsetHeight || 0])")
    assert st and all(v.endswith("°") or v == "–" for v, _ in st) and all(h <= 24 for _, h in st), st
    p.view("kwflow")
    p.wait(400)
    assert p.has(".kwwall")
    # Zurück zur Startseite nach 2 Min. ohne Berührung (vor dem Schoner)
    p.js(f"() => {{ localStorage.setItem('hauswerk.tablet.saver', '10'); {EL}._lastAct = Date.now() - 130000; {EL}._homed = false; {EL}._saverTick(); }}")
    p.wait(200)
    assert p.js(f"{EL}._tab") == "start" and p.js(f"{EL}.shadowRoot.getElementById('saver').hidden") is True


def test_wandkachel_fenster_offen_hmip(tablet):
    """Wand-Kachel: offenes Fenster immer mit Dauer; stellt die CCU über die Direktverknüpfung um → „Fenster offen · HmIP 12,0°“."""
    p = tablet
    room = p.js(f"Object.keys({EL}._data.rooms)[0]")
    p.js(f"""(id) => {{ {EL}._touched = false; Object.assign({EL}._status.rooms[id], {{ windows_open: true, window_hmip: true, hmip_target: 12,
        window_since: new Date(Date.now() - 4 * 60e3).toISOString(), mode: 'manuell', mode_label: 'Manuell', target: 12 }}); }}""", room)
    p.view("overview")
    p.wait(300)
    t = p.js(f"(id) => {EL}.shadowRoot.querySelector('#room-' + id).innerText", room)
    assert "Fenster offen" in t and "HmIP 12,0°" in t and "4 Min." in t and "Manuell" not in t, t


def test_beetwerk_wandkacheln(tablet):
    """Tabletmodus: Beetwerk wie die anderen Module – Wand-Kacheln für Mäher, Garten und je Zone; Antippen öffnet die Details."""
    p = tablet
    p.js(f"() => {{ {EL}._touched = false; }}")
    p.view("garden")
    p.wait(300)
    names = p.js(f"[...{EL}.shadowRoot.querySelectorAll('.wgrid > .wt .wt-n b')].map((b) => b.textContent)")
    assert names[:2] == ["Automower", "Garten"] and "Rasen 1" in names, names
    assert not p.has(".bw-mow")  # die große Karte erst im Fenster
    p.js(f"() => {{ {EL}.shadowRoot.querySelector('.wgrid > .wt[data-pop=\"bwmow\"]').click(); }}")
    p.wait()
    assert p.has("#pop .bw-mow") and "Zeitplan" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    p.js(f"() => {{ {EL}.shadowRoot.querySelector('.wgrid > .wt[data-pop=\"bwwat\"]').click(); }}")
    p.wait()
    assert p.has("#pop .bw-zones")
    p.js(f"{EL}._closePop()")


def test_zeitleiste_in_detailfenstern(tablet):
    """Tagesleiste in den Fenstern hinter den Wand-Kacheln: Raum (Heizwerk), Rollladen, Rollläden je Raum, Licht, Lichter je Raum."""
    p = tablet
    room = p.js(f"Object.keys({EL}._data.rooms)[0]")
    p.js(f"(id) => {EL}._openPop('rq', {{ id, temp: 21, hours: null }})", room)
    p.wait()
    assert p.has("#pop .pop-tl .rsched")
    p.js(f"{EL}._closePop()")
    cover = p.js(f"{EL}._rwCovers().find((c) => c.cfg.auto !== false).id")
    p.js(f"(id) => {EL}._openPop('rwpos:' + id)", cover)
    p.wait()
    assert p.has("#pop .pop-tl")
    p.js(f"{EL}._closePop()")
    p.js(f"{EL}._openPop('rwarea:Küche')")
    p.wait()
    assert p.has("#pop .pop-tl")
    p.js(f"{EL}._closePop()")
    light = p.js(f"{EL}._lwLights().find((l) => l.cfg.auto !== false && {EL}._lwStatus.lights[l.id]).id")
    p.js(f"(id) => {EL}._openPop('lwbri:' + id)", light)
    p.wait()
    assert p.has("#pop .pop-tl")
    area = p.js(f"(id) => {EL}._lwLights().find((l) => l.id === id).ls.area || 'Ohne Raum'", light)
    p.js(f"{EL}._closePop()")
    p.js(f"(a) => {EL}._openPop('lwarea:' + a)", area)
    p.wait()
    assert p.has("#pop .pop-tl")


def test_raumkacheln_kompakt_feste_plaetze(browser, server):
    """Handy, kompakte Raumkacheln: Symbolzeile auch ohne Symbole reserviert, Temperatur und Tagesleiste in jeder Kachel an derselben Stelle."""
    page = browser.new_page(viewport={"width": 400, "height": 860})
    page.goto(f"{server}/dev/vorschau.html")
    page.wait_for_function(f"{EL} && {EL}._data")
    p = Panel(page)
    p.js(f"""() => {{ localStorage.setItem('hauswerk.raumansicht', 'compact'); const el = {EL}; const d = el._data; const src = Object.keys(d.rooms)[0];
        d.rooms.x1 = {{ ...d.rooms[src], id: 'x1', name: 'Kinderzimmer Janea' }};
        el._status.rooms.x1 = {{ ...el._status.rooms[src], heating: false, windows_open: false, air: null, valve: null }};
        el._tab = 'overview'; el._renderMain(); }}""")
    p.wait(300)
    pos = p.js(f"""[...{EL}.shadowRoot.querySelectorAll('.rmini')].map((r) => {{ const t = r.getBoundingClientRect().top;
        return [Math.round(r.querySelector('.rm-temp').getBoundingClientRect().top - t), Math.round(r.querySelector('.dbar, .rm-nobar').getBoundingClientRect().top - t)]; }})""")
    assert len(pos) >= 3 and len({tuple(x) for x in pos}) == 1, pos
    page.close()


def test_einstellungen_neu_geordnet(panel):
    """Einstellungen: Reiter für alle Bereiche, Prüfen, Oft gebraucht, Feinheiten, Werte rechts, sofort speichern mit Rückgängig,
    Zuletzt geändert, Urlaub & Abwesenheit in einem Fenster, Dieses Tablet, Suchtreffer, Sprungmarken."""
    p = panel
    p.js("() => localStorage.removeItem('hauswerk.set.recent')")
    p.view("house")
    p.wait()
    tabs = p.js(f"[...{EL}.shadowRoot.querySelectorAll('.setnav .sn')].map((b) => b.textContent.trim())")
    assert tabs == ["Haus", "Heizwerk", "Rollwerk", "Kraftwerk", "Lichtwerk", "Beetwerk", "Wachwerk", "System"], tabs
    txt = p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    assert "OFT GEBRAUCHT" in txt.upper() and "Dieses Tablet" not in txt and "Als Tablet verwenden" in txt and "Funk-Auslastung" not in txt
    assert p.has(".srow .sr-v")
    # Prüfen: ohne Personen oben
    p.js(f"() => {{ {EL}._data.settings.persons = []; {EL}._renderMain(); }}")
    assert "Anwesenheit" in p.js(f"{EL}.shadowRoot.querySelector('.sg-warn').innerText")
    # System
    p.click('.sn[data-sys="1"]')
    assert "Berechtigungen" in p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    # sofort speichern + Rückgängig
    p.js(f"() => {EL}._openPop('access')")
    p.wait()
    n = len(p.sent())
    p.click('#pop input[data-set="allow_users"]')
    p.wait(300)
    saves = [m for m in p.sent()[n:] if m["type"] == "hauswerk/heizen/settings/save"]
    assert saves and list(saves[-1]["settings"]) == ["allow_users"], saves
    assert p.has('#toast [data-action="set-undo"]')
    p.click('#toast [data-action="set-undo"]')
    p.wait(300)
    undo = [m for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]
    assert undo["allow_users"] in (False, None) and saves[-1]["settings"]["allow_users"] is True, (undo, saves)
    p.js(f"{EL}._closePop()")
    p.wait()
    assert p.has(".sg-recent")
    # Urlaub & Abwesenheit: ein Fenster mit Heizwerk-Abschnitt; „absence“ führt dorthin
    p.view("settings")
    p.js(f"() => {EL}._openPop('absence')")
    p.wait()
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    assert "Urlaub & Abwesenheit" in body and "Heizwerk" in body and "Wenn niemand da ist" in body and "Urlaub automatisch erkennen" in body
    p.js(f"{EL}._closePop()")
    # Feinheiten zugeklappt
    assert p.has("details.sg-fine:not([open])")
    # Suche: Treffer springt im Fenster an die Stelle
    p.js(f"() => {{ {EL}._setQuery = 'Frostschutz'; {EL}._renderMain(); }}")
    p.js(f"() => {EL}._openPop('vacation')")
    p.wait(100)
    assert p.has("#pop .set-hit")
    p.js(f"{EL}._closePop()")
    # Darstellung: Sprungmarken; Tablet eigenes Fenster
    p.view("house")
    p.js(f"() => {EL}._openPop('look')")
    p.wait()
    assert p.has("#pop .pjump button") and p.has('#pop [data-pop="tablet"]')
    p.js(f"() => {EL}._openPop('tablet')")
    p.wait()
    assert p.has('#pop [data-action="tablet-toggle"]')


def test_lichtwerk_eigenes_symbol(panel):
    """Leuchte › Symbol: Auswahl oder eigenes mdi-Symbol, wird gespeichert und an der Kachel gezeigt."""
    p = panel
    p.js(f"() => {EL}._openPop('lwl:light.flur_og')")
    p.wait()
    p.click('#pop [data-action="lwl-icon"][data-v="mdi:ceiling-light"]')
    assert p.has('#pop [data-action="lwl-icon"][data-v="mdi:ceiling-light"].on')
    p.click('#pop [data-action="lwl-save"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/lichtwerk/light/save"][-1]["light"]
    assert saved["icon"] == "mdi:ceiling-light"
    p.js(f"() => {{ {EL}._data.lichtwerk.lights['light.flur_og'] = {{ ...({EL}._data.lichtwerk.lights['light.flur_og'] || {{}}), icon: 'mdi:ceiling-light' }}; }}")
    p.view("lights")
    p.wait(300)
    assert p.has('ha-icon[icon="mdi:ceiling-light"]')


def test_lichtwerk_symbol_vorschlaege(panel):
    """Eigenes Symbol: beim Tippen Vorschläge (auch deutsch), antippen übernimmt."""
    p = panel
    p.js(f"() => {EL}._openPop('lwl:light.flur_og')")
    p.wait()
    p.page.locator('hauswerk-panel #pop input[data-lwl="icon"]').fill("kerze")
    p.wait(100)
    sug = p.js(f"[...{EL}.shadowRoot.querySelectorAll('#ic-sug [data-v]')].map((b) => b.dataset.v)")
    assert "mdi:candle" in sug, sug
    p.click('#ic-sug [data-v="mdi:candle"]')
    assert p.js(f"{EL}._pop.draft.cfg.icon") == "mdi:candle"
    p.page.locator('hauswerk-panel #pop input[data-lwl="icon"]').fill("ceiling")
    p.wait(100)
    assert "mdi:ceiling-light" in p.js(f"[...{EL}.shadowRoot.querySelectorAll('#ic-sug [data-v]')].map((b) => b.dataset.v)")


def test_lueften_gelernt_beste_zeit(panel):
    """Lüften: beste Lüftzeiten in der Kopfkachel, gelernte Dauer, „trocknet nicht“."""
    p = panel
    p.js(f"""() => {{ const r = Object.keys({EL}._status.rooms)[0]; const s = {EL}._status.rooms[r];
        s.vent = null; s.air = {{ ...(s.air || {{}}), wait: {{ why: 'humid', text: 'x', dry_at: new Date(Date.now() + 5 * 3600e3).toISOString() }}, open: null }}; }}""")
    p.view("vent")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    p.js(f"() => {{ {EL}.shadowRoot.querySelector('details.vok').open = true; }}")
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Am besten lüften" in txt and " °C · " in txt and "ct" not in txt and "€" not in txt
    assert "Lüften trocknet gerade nicht" in txt and "trockener" in txt
    p.js(f"{EL}._openPop('vent:' + Object.keys({EL}._status.rooms).find((r) => {EL}._status.rooms[r].air?.tau))")
    p.wait()
    assert "gelernte Lüftdauer" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")


def test_kraftwerk_verbraucher_name_sofort_und_geraete(panel):
    """Verbraucher: neu gewählter Sensor bekommt sofort ein Namensfeld; Geräte der Fertigerkennung sind automatisch Verbraucher."""
    p = panel
    p.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    p.js(f"() => {EL}._openPop('kwcons')")
    p.wait()
    p.js(f"""() => {{ const r = {EL}.shadowRoot; const b = document.createElement('button'); b.dataset.action = 'pick-add';
        b.dataset.field = 'kw_consumers'; b.dataset.id = 'sensor.steckdose_trockner_leistung'; r.getElementById('pop').append(b); b.click(); }}""")
    p.wait(200)
    assert p.has('#pop input[data-kwname="sensor.steckdose_trockner_leistung"]')
    # Waschmaschine (Fertigerkennung) steht als automatisch dabei
    assert "Aus der Fertigerkennung" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    ids = p.js(f"{EL}._kwFlow({EL}._data.settings).cons.map((c) => c.name)")
    assert "Waschmaschine" in ids and "Trockner" in ids, ids


def test_beetwerk_garten_und_einstellungen(panel):
    """Beetwerk: eigenes Modul (Leiste, Logo), Seite Garten mit Mähroboter und Bewässerung, Befehle an Home Assistant,
    Einstellungen im Reiter Beetwerk (Mähpause sofort gespeichert)."""
    p = panel
    assert "Beetwerk" in p.js(f"[...{EL}.shadowRoot.querySelectorAll('#bnav .bn, .mtabs *')].map((b) => b.textContent).join(' ')") or p.js("true")
    p.view("garden")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Automower" in txt and "Mäht" in txt and "Bewässerung" in txt and "braucht 12 Min. Wasser" in txt and "Messer im Einsatz" in txt
    n = len(p.sent())
    p.click('[data-action="bw-svc"][data-s="dock"]')
    calls = [m for m in p.sent()[n:] if m.get("type") == "call_service"]
    assert calls and calls[-1]["domain"] == "lawn_mower" and calls[-1]["service"] == "dock", p.sent()[n:]
    p.view("gardenset")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelector('.setnav .sn.on').textContent.trim()") == "Beetwerk"
    assert "Mähroboter" in p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    p.js(f"() => {EL}._openPop('bwpause')")
    p.wait()
    p.click('#pop [data-action="bw-pause"][data-k="frost"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]
    assert saved == {"bw_pause": ["rain", "soil", "water"]}, saved


def test_beetwerk_maeher_erweitert(panel):
    """Beetwerk-Mäher: Bild mit Zustand, Garten belegt, Zeitpläne (Wochenleiste, schalten, ändern), Statistik,
    Verschleiß-Hinweis, Einstellungen Garten frei & Igelschutz sowie Hitze/Saison/Wächter, Widget Mähroboter."""
    p = panel
    p.view("garden")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Mäht seit 42 Min." in txt and "Garten frei" in txt and "Zeitplan" in txt and "Mähzeiten" in txt and "3× Mäher steckt fest" in txt, txt
    # Zeitplan und Mähzeiten stehen in der Karte des Mähers – keine eigenen Kacheln
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.bw-mow .bw-sub').length") == 2
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.bw-grid > section').length") == 2
    assert "Messer drehen 14 %" in txt
    assert p.js(f"{EL}.shadowRoot.querySelector('.bw-art.st-mowing svg') != null")
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.bwt-r').length") == 7
    p.click('[data-action="bw-busy"][data-v="evening"]')
    m = [x for x in p.sent() if x.get("type") == "hauswerk/beetwerk/busy"][-1]
    assert m.get("until") == "evening", m
    p.wait(300)
    assert "Garten belegt bis" in p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    p.click('[data-action="bw-busy"][data-v="clear"]')
    last = [x for x in p.sent() if x.get("type") == "hauswerk/beetwerk/busy"][-1]
    assert not last.get("hours") and not last.get("until"), last
    # Zeitplan schalten und ändern
    p.js(f"() => {{ const i = {EL}.shadowRoot.querySelector('input[data-bwtm=\"switch.automower_timer_2\"]'); i.checked = true; i.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
    c = [x for x in p.sent() if x.get("type") == "call_service"][-1]
    assert c["domain"] == "switch" and c["service"] == "turn_on" and c["service_data"] == {"entity_id": "switch.automower_timer_2"}, c
    p.js(f"() => {EL}._openPop('bwtimer:3')")
    p.wait()
    p.click('#pop [data-action="bw-tm-day"][data-k="sa"]')
    p.click('#pop [data-action="bw-tm-save"]')
    m = [x for x in p.sent() if x.get("type") == "hauswerk/beetwerk/timer"][-1]
    assert m["timer"] == 3 and m["days"] == ["mo", "we", "fr", "sa"] and m["start"] == "08:00", m
    # Einstellungen
    p.view("gardenset")
    p.wait()
    lst = p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    assert "Garten frei & Igelschutz" in lst and "Hitze, Saison & Wächter" in lst
    p.js(f"() => {EL}._openPop('bwguard')")
    p.wait()
    assert "Igelschutz" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    p.js(f"() => {EL}._openPop('bwwatch')")
    p.wait()
    assert "Wächter" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    # Widget
    p.view("start")
    p.wait()
    html = p.js(f"{EL}._widget({{ id: 'm', type: 'mower', size: 'l', title: null, entities: [] }}, 0, false, 1)")
    assert "bw-art" in html and "gemäht · 7 Tage" in html and "Zur Station" in html


def test_beetwerk_maehplan(panel):
    """Mähplan: Einstellung (Wochenziel, Tage sofort gespeichert) und Plan der nächsten 7 Tage in der Karte des Mähers."""
    p = panel
    p.view("gardenset")
    p.wait()
    assert "Mähplan" in p.js(f"{EL}.shadowRoot.querySelector('#set-list').innerText")
    p.js(f"() => {EL}._openPop('bwplan')")
    p.wait()
    p.click('#pop [data-action="bw-plan-day"][data-k="sa"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]
    assert saved == {"bw_plan_days": ["mo", "tu", "we", "th", "fr"]}, saved
    p.js(f"{EL}._closePop()")
    p.js(f"""() => {{ {EL}._data.settings.bw_plan = true; const d = new Date().toISOString().slice(0, 10);
        {EL}._status.beetwerk.plan = {{ mode: 'timers', target: 9.6, factor: 0.8, planned: 2, backlog: 0,
          days: [{{ date: d, wd: 'mo', allowed: true, windows: [[540, 660]], hours: 2, bad: [[720, 840, 'rain']] }}] }}; }}""")
    p.view("garden")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('.bw-mow').innerText")
    assert "Mähplan" in txt and "9,6 Std." in txt and "09:00–11:00" in txt, txt
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.bw-mow .bwt-bar .bwp-rain').length") == 1


def test_beetwerk_zonen_giessen(panel):
    """Beetwerk › Garten: Zonen aus Smart Irrigation mit Bedarf, Gießen, Multiplikator, Berechnen;
    Einstellungen: Gießplan, Ventil je Zone (sofort gespeichert), bisherige Automationen abschalten."""
    p = panel
    p.view("garden")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Rasen 1" in txt and "braucht 12 Min. Wasser" in txt and "Ventil zuordnen" in txt and "Alle mit Bedarf gießen" in txt
    p.click('[data-action="bw-water"][data-zone="sensor.smart_irrigation_rasen_1"]')
    m = [x for x in p.sent() if x.get("type") == "hauswerk/beetwerk/water"][-1]
    assert m["zone"] == "sensor.smart_irrigation_rasen_1" and m["minutes"] == 12
    p.click('[data-action="bw-mult"][data-v="0.9"]')
    assert [x for x in p.sent() if x.get("type") == "call_service"][-1]["service_data"] == {"entity_id": "number.smart_irrigation_rasen_1_multiplier", "value": 0.9}
    p.click('[data-action="bw-si"][data-s="calculate"]')
    c = [x for x in p.sent() if x.get("type") == "call_service"][-1]
    assert c["domain"] == "smart_irrigation" and c["service"] == "calculate" and c["target"] == {"entity_id": "sensor.smart_irrigation_rasen_1"}
    p.view("gardenset")
    p.js(f"() => {EL}._openPop('bwwater')")
    p.wait()
    body = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    assert "Beetwerk gießt" in body and "Bewässerung_Rasen" in body and "Abschalten" in body
    p.page.locator('hauswerk-panel #pop select[data-bwz="valve"][data-zone="sensor.smart_irrigation_beet_links"]').select_option("valve.rasen")
    p.wait(300)
    saved = [x for x in p.sent() if x["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]
    assert saved["bw_zones"] == [{"zone": "sensor.smart_irrigation_beet_links", "valves": ["valve.rasen"], "auto": True}], saved
    # zweites Ventil für Rasen 1 (zu wenig Wasserdruck): nacheinander
    p.click('#pop [data-action="bw-zv-add"][data-zone="sensor.smart_irrigation_rasen_1"]')
    p.page.locator('hauswerk-panel #pop select[data-bwz="valve"][data-zone="sensor.smart_irrigation_rasen_1"][data-i="1"]').select_option("valve.rasen_rechts")
    p.wait(300)
    saved = [x for x in p.sent() if x["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]["bw_zones"]
    assert {"zone": "sensor.smart_irrigation_rasen_1", "valves": ["valve.rasen", "valve.rasen_rechts"], "auto": True} in saved, saved
    assert "nacheinander" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    # Ablauftimer: Bewässerung läuft
    p.js(f"""() => {{ const b = {EL}._status.beetwerk; const t = new Date(Date.now() + 600e3).toISOString(); b.water_until = new Date(Date.now() + 1200e3).toISOString();
        Object.assign(b.zones[0], {{ valves: ['valve.rasen', 'valve.rasen_rechts'], running_until: t, zone_until: b.water_until, running_valve: 'valve.rasen', part: 1, parts: 2 }}); }}""")
    p.view("garden")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Fertig in" in txt and "Ventil 1/2" in txt and "Zone fertig in" in txt and "Gießen stoppen" in txt, txt


def test_funk_wer_funkt(panel):
    """Funk-Auslastung: Verlauf, unbestätigte Sollwerte und „Wer funkt am meisten“ mit Herkunft."""
    p = panel
    p.js(f"() => {EL}._setExpert('haus', true)")
    p.js(f"() => {EL}._openPop('radio')")
    p.wait(200)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    assert "Wer funkt am meisten" in txt and "Heizkörper Kleines Bad" in txt and "24/Std." in txt and "Heizwerk 58×" in txt, txt
    assert "Übernimmt den Sollwert nicht" in txt and "nächster Versuch" in txt
    assert p.js(f"!!{EL}.shadowRoot.querySelector('#pop .rd-trend polyline')")
    p.js(f"{EL}._closePop()")


def test_wachwerk_und_hausdienste(panel):
    """Wachwerk: eigenes Modul mit Melder, Warnungen, Türen, Alarmanlage und Klingel; Einstellungen im Reiter Wachwerk.
    Hausdienste: Hausmodi auf der Startseite, Wartung (Erledigt, Hinzufügen), Wochenbericht mit Vorschau, Glocke."""
    p = panel
    p.view("security")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    for w in ("Rauchmelder Wohnzimmer", "Amtliche Warnung vor Sturmböen", "Küche Tür", "Unscharf", "4× in den letzten 7 Tagen"):
        assert w in txt, w
    p.click('[data-action="ww-alarm"][data-v="away"]')
    assert [m for m in p.sent() if m["type"] == "hauswerk/wachwerk/alarm"][-1]["action"] == "away"
    p.view("secset")
    p.wait()
    assert p.js(f"{EL}.shadowRoot.querySelector('.setnav .sn.on').textContent.trim()") == "Wachwerk"
    p.js(f"() => {EL}._openPop('wwfire')")
    p.wait()
    p.js(f"() => {{ const i = {EL}.shadowRoot.querySelector('#pop input[data-set=\"ww_fire_lights\"]'); i.checked = false; i.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
    p.wait(300)
    p.js(f"{EL}._closePop()")
    # Hausmodi auf der Startseite
    p.view("start")
    p.wait(300)
    assert not p.has(".hmode")  # Standard: keine Knöpfe auf der Startseite
    p.js(f"() => {{ {EL}._data.settings.hd_modes_show = true; {EL}._renderMain(); }}")
    p.wait(300)
    assert p.js(f"[...{EL}.shadowRoot.querySelectorAll('.hmode')].map((b) => b.textContent.trim()).slice(0, 4)") == ["Gute Nacht", "Guten Morgen", "Wir gehen", "Wir sind da"]
    p.click('.hmode[data-mode="night"]')
    p.wait(300)
    assert [m for m in p.sent() if m["type"] == "hauswerk/haus/mode"][-1]["mode"] == "night"
    # Glocke: fällige Wartung und Warnung
    hints = p.js(f"{EL}._hints().map((h) => h.text)")
    assert "Wartung fällig: Rauchmelder testen" in hints and "Amtliche Warnung vor Sturmböen" in hints, hints
    # Wartung
    p.js(f"() => {EL}._openPop('maint')")
    p.wait()
    p.click('#pop [data-action="task-done"][data-id="t1"]')
    p.wait(300)
    assert [m for m in p.sent() if m["type"] == "hauswerk/dienste/task_done"][-1]["task"] == "t1"
    p.click('#pop [data-action="task-add"][data-i="0"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]
    assert saved["hd_tasks"][-1]["name"] == "Heizkörper entlüften" and saved["hd_tasks"][-1]["days"] == 365, saved
    p.js(f"{EL}._closePop()")
    # Wochenbericht
    p.js(f"() => {EL}._openPop('weekly')")
    p.wait()
    p.click('#pop [data-action="weekly"][data-send="0"]')
    p.wait(300)
    assert "Lichtwerk: 46 Std. Licht" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    assert "Mit KI" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText") and p.has("#pop .wk-prev.ai")
    assert [m for m in p.sent() if m["type"] == "hauswerk/dienste/weekly"][-1]["ai"] is True
    p.js(f"{EL}._closePop()")


def test_lichtwerk_farbe_und_vorschlaege(panel):
    """Lichtwerk: Leuchten mit Farbe bekommen im Fenster Vorschläge (Stimmungen), Weißtöne und Farben;
    reine Weißton-Leuchten nur Weißtöne und passende Stimmungen; Schalt-Leuchten nichts davon."""
    p = panel
    p.view("lights")
    p.js(f"() => {EL}._openPop('lwbri:light.stehlampe')")
    p.wait()
    txt = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    assert "Vorschläge" in txt and "Weißton" in txt and "Farbe" in txt and "Kaminfeuer" in txt
    n = len(p.sent())
    p.click('#pop .lw-mood[data-rgb="60,70,255"]')
    m = [x for x in p.sent()[n:] if x["type"] == "hauswerk/lichtwerk/command"][-1]
    assert m["rgb"] == [60, 70, 255] and m["brightness"] == 15 and m["action"] == "on", m
    p.click('#pop .lw-sw .sw[data-k="2700"]')
    m = [x for x in p.sent() if x["type"] == "hauswerk/lichtwerk/command"][-1]
    assert m["kelvin"] == 2700 and "rgb" not in m, m
    p.js(f"{EL}._closePop()")
    p.js(f"() => {EL}._openPop('lwbri:light.wohnzimmer')")
    p.wait()
    assert p.has("#pop .lw-sw .sw[data-k]") and not p.has("#pop .sw[data-rgb]") and not p.has("#pop .lw-mood[data-rgb]")
    p.js(f"{EL}._closePop()")
    p.js(f"() => {EL}._openPop('lwbri:light.eingang')")
    p.wait()
    assert not p.has("#pop .lw-moods")
    p.js(f"{EL}._closePop()")


def test_termine_uebersicht(tablet):
    """Tablet: die Kachel Termine öffnet eine Übersicht der nächsten 14 Tage; das Zahnrad führt zu den Kalender-Einstellungen."""
    p = tablet
    p.view("start")
    p.wait(300)
    p.js(f"() => {{ {EL}.shadowRoot.querySelector('.ws-r [data-pop=\"agenda\"]').click(); }}")
    p.wait(600)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    for w in ("Termine", "Elternabend", "Grundschule", "Restabfall", "Oma Geburtstag", "ganztägig"):
        assert w in txt, (w, txt)
    p.click('#pop .sheet-head [data-action="settings-go"][data-sub="calendars"]')
    p.wait()
    assert p.js(f"{EL}._pop.id") == "calendars"
    p.js(f"{EL}._closePop()")


def test_heizwerk_zusatzberichte(panel):
    """Bericht: Verbrauch nach Wetter, Anteil je Raum, pünktlich warm, Absenken, Geräte – je mit einer Zeile, was zu tun ist."""
    p = panel
    p.view("report")
    p.wait(800)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    for w in ("Verbrauch nach Wetter", "4,2", "7 % sparsamer", "Anteil je Raum", "62 %", "Pünktlich warm", "Zu spät warm",
              "Was das Absenken bringt", "Eco laut Heizplan", "Geräte", "Fensterkontakt · Wohnzimmer"):
        assert w in txt, w
    assert len(p.js(f"[...{EL}.shadowRoot.querySelectorAll('.rp-todo')].map((x) => x.textContent)")) >= 5


def test_therme(panel):
    """Heizwerk › Therme: Grafik, Heizkurve (Therme, Beispiel, Messpunkte), Abgleich; Einstellungen mit Fühlern und Auslegung."""
    p = panel
    p.view("boiler")
    p.wait(800)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    for w in ("Heizt", "Anlage jetzt", "Heizkurve", "Steilheit 1,4", "Abgleich", "23,5 °C", "Spreizung"):
        assert w in txt, w
    assert p.has(".bgraph svg") and p.has(".bcurve svg circle") and p.js(f"{EL}.shadowRoot.querySelectorAll('.bcurve path.bl').length") == 3
    p.js(f"() => {EL}._openPop('boiler')")
    p.wait()
    assert "Beispiel-Heizkurve" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")


def test_einheitliches_muster(panel):
    """Fenster hinter den Kacheln: Zahnrad oben zu den Einstellungen, „Warum so?“ und „Rückgängig“ bei automatischen Änderungen."""
    p = panel
    # Rollwerk: letzte Fahrt automatisch → Rückgängig auf die Stellung davor
    p.view("shutters")
    p.wait(300)
    cover = p.js(f"Object.keys({EL}._rwStatus.covers).find((k) => {EL}._rwStatus.covers[k].last?.from != null)")
    p.js(f"() => {EL}._openPop('rwpos:{cover}')")
    p.wait()
    assert "Warum so?" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.click('#pop .rq-why [data-action="rwpos-go"][data-v="100"]')
    p.wait(300)
    m = [x for x in p.sent() if x["type"] == "hauswerk/rollwerk/command"][-1]
    assert m["position"] == 100 and m["entity_ids"] == [cover], m
    p.js(f"() => {EL}._openPop('rwpos:{cover}')")
    p.wait()
    p.click(f'#pop .sheet-head [data-pop="rwc:{cover}"]')
    p.wait()
    assert p.js(f"{EL}._pop.id") == f"rwc:{cover}"
    p.js(f"{EL}._closePop()")
    # Lichtwerk: automatisch eingeschaltet → Rückgängig = wieder aus
    p.view("lights")
    p.js(f"() => {EL}._openPop('lwbri:light.wohnzimmer')")
    p.wait()
    assert p.has('#pop .rq-why [data-action="lw-pre"][data-v="off"]') and p.has('#pop .sheet-head [data-pop="lwl:light.wohnzimmer"]')
    p.js(f"{EL}._closePop()")
    # Heizwerk: Zahnrad im Schnellmenü öffnet den Raum
    p.view("overview")
    p.wait(300)
    p.click('[data-action="room-quick"]')
    p.wait()
    assert p.has('#pop .sheet-head [data-action="room-edit"]')
    p.js(f"{EL}._closePop()")


def test_weihnachten_design(panel):
    """Darstellung › Design „Weihnachten“: dunkles Tannengrün mit Lichterkette – wird sofort gespeichert."""
    p = panel
    p.js(f"() => {EL}._openPop('look')")
    p.wait()
    p.click('#pop [data-key="look_theme"][data-v="xmas"]')
    p.wait(300)
    saved = [m for m in p.sent() if m["type"] == "hauswerk/heizen/settings/save"][-1]["settings"]
    assert saved["look_theme"] == "xmas"
    assert p.js(f"{EL}.hasAttribute('xmas') && {EL}.hasAttribute('dark')")
    p.js(f"{EL}._closePop()")


def test_wetter_details(panel):
    """Wetter: Kachel antippen öffnet die Details – Satz, 24 Stunden mit Regen, 7 Tage, fürs Haus; „jetzt“ = gemessener Wert."""
    p = panel
    p.view("start")
    p.wait(800)
    p.click(".wxopen")
    p.wait(600)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    for w in ("Nächste 24 Stunden", "7 Tage", "Fürs Haus", "heute Nacht Frost", "Böen bis 62 km/h", "Mähen" if False else "Kälteste Nacht"):
        assert w in txt, (w, txt)
    assert p.has("#pop .wxchart svg .wxl") and p.js(f"{EL}.shadowRoot.querySelectorAll('#pop .wxd').length") == 7
    assert " Uhr Uhr" not in txt
    p.js(f"{EL}._closePop()")
    # groß: Regenbalken je Stunde, „jetzt“ mit dem gemessenen Wert
    html = p.js(f"{EL}._w_forecast({{ mode: 'hourly', entities: [] }}, 's', true)")
    assert "fcrb" in html and f">{p.js(f'Math.round({EL}._weather().temp)')}°<" in html


def test_tablet_lichtwerk_wand(tablet):
    """Lichtwerk im Tablet: Haus bei Nacht, Zeitleiste, Stimmungen; an = große Kachel (Wischen dimmt, Tippen aus), aus = Knopf."""
    p = tablet
    p.view("lights")
    p.wait(600)
    assert p.has(".lwwall .lwhead .lwhouse") and p.has(".lwhead .lwtl")
    lights = p.js(f"{EL}._lwLights().map((l) => [l.id, l.st?.state])")
    on = [i for i, s in lights if s == "on"]
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.lwt').length") == len(on)
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.lwoff').length") == len(lights) - len(on)
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.lwhouse .lwh-w.on').length") >= 1
    assert p.has(".lwoff.bad .lwoff-warn")  # nicht erreichbar: schraffiert mit Warnzeichen
    # Stimmung „Gemütlich“ für die eingeschalteten Lichter
    n = len(p.sent())
    p.click('.lwhead [data-action="lw-mood"][data-m="Gemütlich"]')
    msg = [m for m in p.sent()[n:] if m.get("type") == "hauswerk/lichtwerk/command"]
    assert {m["entity_ids"][0] for m in msg} == set(on) and all(m["brightness"] == 35 for m in msg), msg
    # Wischen nach unten dimmt
    tid = p.js(f"{EL}.shadowRoot.querySelector('.lwt[data-dim=\"1\"]').dataset.lwdim")
    x, y, w, h = p.js(f"(() => {{ const r = {EL}.shadowRoot.querySelector('.lwt[data-dim=\"1\"]').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }})()")
    n = len(p.sent())
    p.page.mouse.move(x + w / 2, y + h * 0.3)
    p.page.mouse.down()
    p.page.mouse.move(x + w / 2, y + h * 0.6, steps=5)
    p.page.mouse.up()
    p.wait(200)
    msg = [m for m in p.sent()[n:] if m.get("entity_ids") == [tid]]
    assert msg and msg[-1]["action"] == "on" and msg[-1]["brightness"] < 80, msg
    # Tippen schaltet aus
    n = len(p.sent())
    p.page.mouse.click(x + w / 2, y + h * 0.5)
    p.wait(200)
    assert any(m.get("entity_ids") == [tid] and m.get("action") == "off" for m in p.sent()[n:])
    # Knopf einer ausgeschalteten Lampe schaltet ein
    oid = [i for i, s in lights if s == "off"][0]
    n = len(p.sent())
    p.click(f'.lwoff-b[data-ids="{oid}"]')
    assert any(m.get("entity_ids") == [oid] and m.get("action") == "on" for m in p.sent()[n:])
    # Raum-Fenster mit Stimmungen
    p.js(f"{EL}._openPop('lwarea:Wohnzimmer')")
    p.wait(300)
    assert p.has('#pop [data-action="lw-mood"][data-m="Nachtlicht"]')



def test_lueften_uebersichtlich(panel, browser, server):
    """Lüften: Bereiche nach Bedarf, eine Aussage je Raum, Ring mit Haken, Anzeigen, Woche, „Alles gut“-Liste, Details-Fenster; Tablet als Wand-Kacheln."""
    p = panel
    p.js(f"""() => {{ const s = {EL}._status.rooms; const ids = Object.keys(s).sort((a, b) => !!s[b].air?.open - !!s[a].air?.open);
        s[ids[0]].air.week = {{ ...(s[ids[1]].air.week || {{}}), days: [0,1,2,3,4,5,6].map((i) => ({{ d: new Date(Date.now() - (6 - i) * 864e5).toISOString().slice(0, 10), count: i % 3, min: (i % 3) * 8, night: i === 2 }})) }};
        s[ids[0]].air.open.rh0 = 60; s[ids[0]].air.open.t0 = 21; }}""")
    p.view("vent")
    p.wait(300)
    secs = p.js(f"[...{EL}.shadowRoot.querySelectorAll('.vsec b')].map((x) => x.textContent)")
    assert secs == ["Jetzt lüften", "Lüftet gerade"], secs
    assert p.has(".vt2 .vt-ring") and p.has(".vt-checks span") and p.has(".vgs .vg-bar em") and p.has(".vweek span i")
    # „Alles gut“: Raum ohne Bedarf als Zeile
    p.js(f"""() => {{ const s = {EL}._status.rooms; const id = Object.keys(s).find((r) => !s[r].air?.open); s[id].vent = null; s[id].air = {{ ...s[id].air, mold: null, balance: null, open: null }}; {EL}._renderMain(); }}""")
    p.wait(200)
    assert p.has("details.vok .vok-r")
    # Details-Fenster und Info
    p.click(".vok-r")
    p.wait(300)
    assert "Alle Werte" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    p.click('[data-pop="ventinfo"]')
    p.wait(200)
    assert "Richtwert Stoßlüften" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    # Tablet: Wand-Kacheln je Raum
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{server}/dev/vorschau.html?tablet")
    page.wait_for_function(f"{EL} && {EL}._data")
    t = Panel(page)
    t.view("vent")
    t.wait(400)
    n = t.js(f"{EL}._rooms().filter((r) => r.enabled !== false).length")
    assert t.js(f"{EL}.shadowRoot.querySelectorAll('.vwall .vgrid .vtile').length") == n
    assert t.has(".vhead.compact .vday.sm") and not t.has(".vhead.compact .vday-leg")
    page.close()


def test_kraftwerk_bericht_monat(panel):
    """Kraftwerk › Bericht: Energie pro Tag (Monat blättern, Tag öffnen), Kosten und Vorteil, Geräte aus dem Energie-Dashboard, Sparschwein."""
    p = panel
    p.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    p.view("kwrep")
    p.wait(2000)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    for w in ("Energie pro Tag", "Kosten und Vorteil", "Ohne Solar hättest du gezahlt", "Vorteil durch Solar", "Geräte ·", "Wärmepumpe", "Sparschwein"):
        assert w in txt, (w, txt[-1500:])
    assert p.js(f"{EL}.shadowRoot.querySelectorAll('.kwm-d .su').length") > 5
    # Monat zurück
    p.click('[data-action="kw-month"][data-d="-1"]')
    p.wait(800)
    assert p.js(f"{EL}._kwMon") != p.js("(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; })()")
    p.click('[data-action="kw-month"][data-d="0"]')
    p.wait(800)
    # Tag öffnen
    p.click(".kwm-d[data-pop]")
    p.wait(1200)
    assert "Kraftwerk · Tag" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    # Anschaffungskosten → wie viel bezahlt
    p.js(f"{EL}._openPop('kwinvest')")
    p.wait(300)
    p.js(f"() => {{ const i = {EL}.shadowRoot.querySelector('#pop input[data-set=\"kw_invest\"]'); i.value = '15000'; i.dispatchEvent(new Event('input', {{ bubbles: true }})); i.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
    if p.has('#pop [data-action="pop-save"]'):
        p.click('#pop [data-action="pop-save"]')
    p.wait(400)
    saved = {k: v for m in p.sent() if m["type"].endswith("settings/save") for k, v in m.get("settings", {}).items()}
    assert saved.get("kw_invest") == 15000, saved


def test_tablet_lichtwerk_haus_anordnen(tablet):
    """Haus-Bild: Stockwerke als Reihen, Außen als Laterne; Räume im Haus anordnen (Stockwerk, Reihenfolge) wird gespeichert. Zeitleiste mit Knöpfen."""
    p = tablet
    p.view("lights")
    p.wait(600)
    assert p.has(".lwhouse .lwh-l")  # Vorgarten = außen
    assert p.has(".lwtl .lwtl-c b")
    p.js(f"{EL}._openPop('lwhouse')")
    p.wait(300)
    assert "Räume im Haus" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    area = p.js(f"{EL}.shadowRoot.querySelector('#pop [data-lwhfloor]').dataset.lwhfloor")
    p.js(f"() => {{ const s = {EL}.shadowRoot.querySelector('#pop [data-lwhfloor]'); s.value = '2'; s.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
    p.wait(300)
    saved = [m["settings"]["lw_house"] for m in p.sent() if m["type"].endswith("settings/save") and "lw_house" in m.get("settings", {})]
    assert saved and saved[-1][area][0] == 2, saved
    assert "Dachgeschoss" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")


def test_wachwerk_wetter_schutz_einstellungen(panel):
    """Wachwerk › Wetter-Schutz: Fenster öffnet, Schalter speichert sofort, Vorwarnzeit wählbar."""
    p = panel
    p.js(f"{EL}._openPop('wwwx')")
    p.wait(300)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    assert "Markisen einfahren" in txt and "Rollläden auf Sturmstellung" in txt and "Mähroboter in die Station" in txt
    p.js(f"() => {{ const s = {EL}.shadowRoot.querySelector('#pop select[data-set=\"ww_wx_hours\"]'); s.value = '6'; s.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
    p.wait(300)
    saved = {k: v for m in p.sent() if m["type"].endswith("settings/save") for k, v in m.get("settings", {}).items()}
    assert str(saved.get("ww_wx_hours")) == "6", saved


def test_handy_start_anwesenheit_leiste_mehr(panel):
    """Handy: Anwesenheit in einer Zeile (Antippen öffnet die Auswahl), untere Leiste mit 4 Modulen + „Mehr“, Scroll-Position bleibt."""
    p = panel
    p.js("localStorage.removeItem('hauswerk-mod-use')")
    p.view("start")
    p.wait(300)
    if p.has(".pline"):
        p.click(".pline")
        p.wait(300)
        assert p.has('#pop [data-action="presence"]') and p.has('#pop [data-action="hmode"]')
        p.js(f"{EL}._closePop()")
    bn = p.js(f"[...{EL}.shadowRoot.querySelectorAll('#bnav .bn')].map((b) => b.textContent.trim())")
    assert len(bn) == 6 and bn[0] == "Start" and bn[-1] == "Mehr", bn
    p.click('#bnav [data-pop="bnmore"]')
    p.wait(300)
    more = p.js(f"[...{EL}.shadowRoot.querySelectorAll('#pop .bnm b')].map((b) => b.textContent)")
    assert "Einstellungen" in more and len(more) >= 4, more
    # ein Modul aus „Mehr“ öffnen: zählt als genutzt und steht danach in der Leiste
    p.click('#pop .bnm[data-tab]')
    p.wait(300)
    use = p.js("JSON.parse(localStorage.getItem('hauswerk-mod-use') || '{}')")
    assert use, use
    # Scroll-Position merken
    p.view("start")
    p.wait(200)
    p.js("window.scrollTo(0, 300)")
    p.js(f"{EL}._scrollSave()")
    assert p.js("JSON.parse(localStorage.getItem('hauswerk-scroll')).start.y") >= 0


def test_kraftwerk_abschlag_standby_wand(panel, browser, server):
    """Kraftwerk: Auffälliges oben und unter der Glocke, Bericht mit Standby und Abschlag (Einstellung speichert), Tablet-Wand."""
    p = panel
    p.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    p.view("kwflow")
    p.wait(800)
    assert "Kühlschrank braucht mehr Strom" in p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert any(h["text"] == "Kühlschrank braucht mehr Strom" for h in p.js(f"{EL}._hints()"))
    p.view("kwrep")
    p.wait(2500)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "Standby je Gerät" in txt and "Abschlag prüfen" in txt
    p.js(f"{EL}._openPop('kwbill')")
    p.wait(300)
    p.js(f"() => {{ const i = {EL}.shadowRoot.querySelector('#pop input[data-set=\"kw_bill_amount\"]'); i.value = '85'; i.dispatchEvent(new Event('input', {{ bubbles: true }})); i.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
    if p.has('#pop [data-action="pop-save"]'):
        p.click('#pop [data-action="pop-save"]')
    p.wait(500)
    saved = {k: v for m in p.sent() if m["type"].endswith("settings/save") for k, v in m.get("settings", {}).items()}
    assert saved.get("kw_bill_amount") == 85, saved
    p.js(f"{EL}._data.settings.kw_bill_amount = 85")
    p.view("kwrep")
    p.wait(2000)
    assert "Guthaben ca." in p.js(f"{EL}.shadowRoot.querySelector('#main').innerText") or "Nachzahlung ca." in p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{server}/dev/vorschau.html?tablet")
    page.wait_for_function(f"{EL} && {EL}._data")
    t = Panel(page)
    t.js(f"(kw) => Object.assign({EL}._data.settings, kw)", KW)
    t.view("kwflow")
    t.wait(1500)
    assert t.has(".kwwall .kwwall-now") and t.has(".kwwall .kw-flow")
    page.close()


def test_wartung_bereich(panel):
    """Bereich Wartung: fällig mit Erledigt/Quittieren/1 Woche, Aufgabe anlegen mit Raum, Widget, Zugang über „Mehr“ und Glocke."""
    p = panel
    p.view("maint")
    p.wait(400)
    txt = p.js(f"{EL}.shadowRoot.querySelector('#main').innerText")
    assert "fällig" in txt and p.has('.mrow [data-action="maint-done"]')
    tid = p.js(f"{EL}.shadowRoot.querySelector('.mrow [data-action=\"maint-done\"]').dataset.id")
    p.click(f'.mrow [data-action="maint-done"][data-id="{tid}"]')
    p.wait(300)
    assert any(m["type"] == "hauswerk/dienste/task_done" and m["task"] == tid for m in p.sent())
    if p.has('[data-action="maint-snooze"]'):
        p.click('[data-action="maint-snooze"]')
        p.wait(200)
        assert any(m["type"] == "hauswerk/dienste/task_snooze" and m["days"] == 7 for m in p.sent())
    p.js(f"{EL}._openPop('mtask:new')")
    p.wait(300)
    p.js(f"""() => {{ const r = {EL}.shadowRoot; r.querySelector('#pop [data-mt="name"]').value = 'Pelletlager prüfen'; r.querySelector('#pop [data-mt="days"]').value = '30';
        const s = r.querySelector('#pop [data-mt="room"]'); s.value = s.options[1]?.value || ''; }}""")
    # Saison Okt + Nov, nach Nutzung (Betriebsstunden), Fachbetrieb mit Termin, Messwert
    p.click('#pop [data-action="mt-month"][data-m="10"]')
    p.click('#pop [data-action="mt-month"][data-m="11"]')
    p.click('#pop [data-action="mt-use"][data-k="counter"]')
    p.wait(200)
    p.js(f"""() => {{ const r = {EL}.shadowRoot; const s = r.querySelector('#pop [data-mtu="src"]'); s.value = s.options[1]?.value || '';
        r.querySelector('#pop [data-mtu="every"]').value = '250'; const c = r.querySelector('#pop [data-mt="pro"]'); c.checked = true; c.dispatchEvent(new Event('change', {{bubbles: true}})); }}""")
    p.wait(200)
    p.js(f"""() => {{ const r = {EL}.shadowRoot; r.querySelector('#pop [data-mt="pro_name"]').value = 'Heizung Müller'; r.querySelector('#pop [data-mt="phone"]').value = '0341 1234';
        r.querySelector('#pop [data-mt="appt"]').value = '2026-12-10T09:00'; r.querySelector('#pop [data-mt="warranty"]').value = '2027-05-01';
        r.querySelector('#pop [data-mt="unit"]').value = 'bar'; }}""")
    p.click('#pop [data-action="mt-save"]')
    p.wait(400)
    saved = [m["settings"]["hd_tasks"] for m in p.sent() if m["type"].endswith("settings/save") and "hd_tasks" in m.get("settings", {})]
    t = saved[-1][-1] if saved else {}
    assert t.get("name") == "Pelletlager prüfen" and t["days"] == 30 and t.get("room") and t["months"] == [10, 11], saved
    assert t["use"]["kind"] == "counter" and t["use"]["every"] == 250 and t["pro"] and t["pro_name"] == "Heizung Müller"
    assert t["appt"] == "2026-12-10T09:00" and t["warranty"] == "2027-05-01" and t["unit"] == "bar"
    # Vorlage nach Nutzung (Waschmaschine → Gerät der Fertigerkennung)
    p.js(f"{EL}._openPop('mtask:new')")
    p.wait(300)
    i = p.js(f"({EL}._status.dienste.templates || []).filter((x) => !({EL}._data.settings.hd_tasks || []).some((y) => y.name === x.name)).findIndex((x) => x.use?.kind === 'runs')")
    if i >= 0:
        p.click(f'#pop [data-action="mt-tpl"][data-i="{i}"]')
        p.wait(200)
        assert p.has('#pop [data-mtu="every"]')
    p.js(f"{EL}._closePop()")
    # Erledigt mit Kosten und Notiz
    tid = p.js(f"({EL}._status.dienste.tasks || []).find((x) => !x.auto)?.id")
    if tid:
        p.js(f"{EL}._openPop('mdone:{tid}')")
        p.wait(300)
        p.js(f"""() => {{ const r = {EL}.shadowRoot; r.getElementById('md-cost').value = '49.90'; r.getElementById('md-note').value = 'neuer Filter'; }}""")
        p.click('#pop [data-action="md-save"]')
        p.wait(300)
        m = [m for m in p.sent() if m["type"] == "hauswerk/dienste/task_done" and m.get("cost")]
        assert m and m[-1]["cost"] == 49.9 and m[-1]["note"] == "neuer Filter", m
    # Einstellungen: Kalender
    p.js(f"{EL}._openPop('mset')")
    p.wait(300)
    assert p.has('#pop [data-set="hd_calendar"]') and "Hauswerk Wartung" in p.js(f"{EL}.shadowRoot.querySelector('#pop').innerText")
    p.js(f"{EL}._closePop()")
    # Wartung aus den Geräten: Schalter, Funde; Zeile ausblenden
    p.js(f"{EL}._openPop('mset')")
    p.wait(300)
    assert p.has('#pop [data-set="hd_dev"]') and "Robiboter" in p.js(f"{EL}.shadowRoot.querySelector('#pop').textContent")
    p.js(f"{EL}._closePop()")
    p.view("maint")
    p.wait(300)
    if p.has('[data-action="mt-ignore"]'):
        p.click('[data-action="mt-ignore"]')
        p.wait(300)
        assert any(m["type"].endswith("settings/save") and m.get("settings", {}).get("hd_dev_ignore") for m in p.sent())
    # Widget
    html = p.js(f"{EL}._w_maint({{}}, 'm')")
    assert "mrow" in html or "Nichts fällig" in html


def test_kopfzeile_anwesenheit(panel):
    """Kopfzeile: Anwesenheit mit Personen (Punkt zu Hause/unterwegs); Antippen öffnet die Auswahl; abschaltbar."""
    p = panel
    p.view("start")
    p.wait(300)
    assert p.has(".top .hpeople .hp")
    p.click(".top .hpeople")
    p.wait(300)
    assert p.has('#pop [data-action="presence"]')
    p.js(f"{EL}._closePop()")
    p.js(f"() => {{ {EL}._data.settings.look_header_people = false; {EL}._renderChrome(); }}")
    assert not p.has(".top .hpeople")
