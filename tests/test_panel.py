"""Panel und Backend passen zusammen (ohne Home Assistant, nur Quelltext)."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "hauswerk"


def test_widget_typen_im_backend_erlaubt():
    """Jedes Widget des Panels muss beim Speichern der Startseite erlaubt sein."""
    js = (ROOT / "frontend" / "hauswerk-panel.js").read_text(encoding="utf-8")
    block = js[js.index("const WIDGETS = {"):js.index("const DEFAULT_WIDGETS")]
    panel = set(re.findall(r"^  (\w+): \{ name:", block, re.M))
    api = (ROOT / "api.py").read_text(encoding="utf-8")
    allowed = set(re.findall(r'"(\w+)"', api[api.index("WIDGET_TYPES = ["):api.index("WIDGET_SCHEMA")]))
    assert panel and panel <= allowed, f"im Backend nicht erlaubt: {sorted(panel - allowed)}"


def test_bedienen_ohne_admin():
    """Einstellungen speichern: Bedienen (Anwesenheit & Co.) für alle, alles andere nur mit Recht zum Ändern."""
    api = (ROOT / "api.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'"(\w+)"', api[api.index("OPERATE_KEYS = {"):].split("}", 1)[0]))
    assert keys == {"vacation", "presence_force", "guest", "party", "eco_force"}
    save = api[api.index("async def ws_settings_save"):api.index("connection.send_result", api.index("async def ws_settings_save"))]
    assert "_may_edit(hass, connection)" in save and "OPERATE_KEYS" in save
    head = api[api.rindex("@websocket_api.websocket_command", 0, api.index("async def ws_settings_save")):api.index("async def ws_settings_save")]
    assert "require_editor" not in head


def test_panel_gz_aktuell():
    """Die komprimierte Panel-Datei muss zum Panel passen (sonst lädt der Browser eine alte Version): python3 dev/pack.py"""
    import gzip
    js = ROOT / "frontend" / "hauswerk-panel.js"
    gz = js.with_suffix(".js.gz")
    assert gz.exists(), "hauswerk-panel.js.gz fehlt – python3 dev/pack.py ausführen"
    assert gzip.decompress(gz.read_bytes()) == js.read_bytes(), "hauswerk-panel.js.gz veraltet – python3 dev/pack.py ausführen"
