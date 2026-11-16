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
