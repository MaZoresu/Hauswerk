"""Panel komprimieren: hauswerk-panel.js.gz neben die Datei legen (Home Assistant liefert sie aus, wenn der Browser gzip kann).

Aufruf vor jedem Commit, der das Panel ändert:  python3 dev/pack.py
Der Test tests/test_panel.py::test_panel_gz_aktuell prüft, dass die .gz-Datei zum Panel passt.
"""
from __future__ import annotations

import gzip
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "custom_components" / "hauswerk" / "frontend" / "hauswerk-panel.js"


def pack() -> Path:
    data = SRC.read_bytes()
    out = SRC.with_suffix(".js.gz")
    # mtime=0: gleiche Eingabe → gleiche Datei (keine unnötigen Änderungen im Repo)
    out.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    return out


if __name__ == "__main__":
    out = pack()
    print(f"{out.name}: {SRC.stat().st_size // 1024} KB → {out.stat().st_size // 1024} KB")
