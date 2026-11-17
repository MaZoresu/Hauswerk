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
    pops = lambda: panel.js(f"[...{EL}.shadowRoot.querySelectorAll('.srow[data-action=\"pop-open\"]')].map((x) => x.dataset.pop)")
    assert panel.js(f"{EL}.shadowRoot.querySelector('.xcard').dataset.mod") == mod
    assert not set(rows) & set(pops()), pops()
    panel.click(".xcard")
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
    panel.click(".xcard")
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
        assert p.js(f"{EL}._tPages") <= 2, f"{view}: {p.js(f'{EL}._tPages')} Seiten"
        # Leisten unten: Unterleiste und Navigation unter dem Inhalt
        bottom = p.js(f"(() => {{ const r = {EL}.shadowRoot; return [r.getElementById('main').getBoundingClientRect().bottom, r.getElementById('bnav').getBoundingClientRect().top]; }})()")
        assert bottom[0] <= bottom[1], f"{view}: Navigation nicht unten"
        p.ok(f"Tablet {view}")
    # Heizwerk-Einstellungen: zwei Seiten, Punkte und Wischen
    p.view("settings")
    p.wait(300)
    if p.js(f"{EL}._tPages") > 1:
        p.click('#tdots button[data-i="1"]')
        p.wait(500)
        assert p.js(f"{EL}._tPage.settings") == 1
        p.page.mouse.move(600, 400)
        p.page.mouse.down()
        p.page.mouse.move(900, 410, steps=5)
        p.page.mouse.up()
        p.wait(500)
        assert p.js(f"{EL}._tPage.settings") == 0


def test_tablet_bildschirmschoner(tablet):
    p = tablet
    p.view("overview")
    p.js(f"() => {{ {EL}._openPop('look'); }}")
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
    p.js(f"() => {{ {EL}._openPop('look'); }}")
    p.wait()
    p.click('#pop [data-action="tablet-toggle"]')
    assert not p.js(f"{EL}.hasAttribute('tablet')")
    assert p.js("localStorage.getItem('hauswerk.tablet')") == "0"
    p.ok("Bildschirmschoner")
