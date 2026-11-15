# Hauswerk

Haussteuerung für Home Assistant mit eigenem Seitenmenü-Panel. Hauswerk ist in Module gegliedert:

| Modul | Stand |
|---|---|
| **Heizen** | fertig – raumweise Heizungsregelung (früher eigenständig als „Heizwerk“) |
| Rollladen | geplant |
| Licht | geplant |
| Garten | geplant |

## Installation

1. Ordner `custom_components/hauswerk` nach `config/custom_components/hauswerk` kopieren (oder dieses Repo in HACS als benutzerdefiniertes Repository vom Typ „Integration“ hinzufügen).
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Hauswerk**.
4. Im Seitenmenü **Hauswerk** öffnen und Räume anlegen.

Voraussetzung: Home Assistant 2024.11 oder neuer. Räume, Heizpläne und Einstellungen ändern dürfen Admins – oder alle Benutzer, wenn ein Admin das unter Einstellungen › Berechtigungen freigibt (z. B. für ein Wand-Tablet). Die Temperatur ±0,5 °C und Boost dürfen immer alle.

### Umstieg von Heizwerk

Hauswerk ersetzt die frühere Integration „Heizwerk“. Räume, Heizpläne, Einstellungen, Statistik und gelernte Aufheizzeiten werden beim ersten Start automatisch aus `config/.storage/heizwerk.data` übernommen.

1. Hauswerk wie oben installieren und einrichten.
2. Die alte Integration **Heizwerk** unter Geräte & Dienste löschen und den Ordner `config/custom_components/heizwerk` entfernen – sonst regeln beide gleichzeitig dieselben Thermostate.
3. Home Assistant neu starten.
4. Automationen und Dashboards auf die neuen Entitäten umstellen: aus `switch.hauswerk_…` wird `switch.hauswerk_…`, aus `sensor.hauswerk_…` wird `sensor.hauswerk_…`.

> **Hinweis zur Wiederherstellung:** `frontend/hauswerk-panel.js` ist in diesem Stand ein schlichtes Ersatz-Panel (Raumübersicht, ±0,5 °C, Boost). Das vollständige Panel mit Widgets, Raumseite, Hinweisen und Einstellungen war nicht unter den gesicherten Dateien und muss aus dem Original ersetzt werden – dabei die WebSocket-Befehle von `heizwerk/…` auf `hauswerk/heizen/…` und den Elementnamen auf `hauswerk-panel` umstellen. Ebenso fehlen `dev/vorschau.html` und die ursprünglichen Tests.

# Modul Heizen

Raumweise Heizungsregelung.

- **Heizkörper und Flächenheizung** werden unterschiedlich geregelt (siehe unten)
- **Fensterpause**: Thermostat auf Frostschutz oder aus, solange ein Fenster offen ist
- **Heizpläne**: gemeinsame Pläne für mehrere Räume oder ein eigener Plan je Raum, Komfortzeiten je Wochentag (auch über Mitternacht), Import aus einem Home-Assistant-Kalender
- **Anwesenheit & Urlaub** (für das ganze Haus): Absenken, wenn alle weg sind; Urlaub per Schalter, Zeitraum oder aus einem Kalender mit Stichworten
- **Raumsensor & Bericht**: externer Temperatur-/Feuchtesensor je Raum, Heizdauer, Komfortzeit, Fensterpausen und Ø-Temperatur der letzten 7/14/30 Tage

## Aufbau des Panels

- **Start:** Zustand des Hauses und frei wählbare **Widgets** (die Module erreichst du über die Reiter oben): Heizen, Anwesenheit (mit Personen, Ort und Entfernung nach Hause), Wetter, Räume, Shortcuts (Szenen, Skripte, Schalter, Lichter), Fenster, Komfortzeiten, Heizdauer, Werte (beliebige Sensoren) und Wetterprognose (nächste Stunden oder Tage, Frost-Hinweis). Über „Anpassen“ hinzufügen, verschieben, umbenennen, entfernen und in drei Größen stellen: **klein** (nur das Wichtigste), **mittel** (Kennzahlen bzw. Liste) und **groß** (volle Breite mit allen Einzelheiten) – gilt für alle Benutzer.
- **Einstellungen:** eine Liste mit Suche, gegliedert in Haus (Anwesenheit, Urlaub, Saison), Heizen und Räume. Ein Tipp öffnet die Einzelheiten als Pop-up.
- **Kopfzeile:** schrumpft beim Scrollen auf eine Zeile mit Logo, Reitern und Glocke. Auf dem Handy gibt es stattdessen unten eine Leiste **Start · Räume · Bericht · Einstellungen**.
- **Raumseite:** Ein Tipp auf den Raumnamen öffnet eine eigene Seite (`/hauswerk/heizen/raum/<id>`) mit Raumkarte, Verlauf der letzten 24 Stunden (Raumtemperatur, Soll, Heizzeiten, offene Fenster), Geräten mit Live-Werten, Einstellungen im Überblick und den letzten 7 Tagen.
- **Hinweise:** Glocke oben rechts mit Zahl. Ein Tipp listet alles, was zu beheben ist (z. B. Thermostat nicht erreichbar, Raum ohne Thermostat, Kalender nicht lesbar) und was gut zu wissen ist (z. B. Fenster lange offen, Raum feucht) – jeweils mit Sprung an die richtige Stelle.
- **Heizen:** Unterleiste **Räume · Bericht · Einstellungen** (Adressen `/hauswerk/heizen/raeume` usw.). Die Heizpläne erreichst du über Einstellungen › Heizpläne.
- **Räume:** schmales Banner mit Ø-Temperatur, Kurzurteil (z. B. „2 Räume unter Soll“), Wetter und Kennzahlen (heizende Räume, Fenster, Außen, Luftfeuchte, heute geheizt). Raumkacheln **detailliert** (Boost und „⋯“-Menü für Heizplan, Bearbeiten und Automatik; heutiger Zeitplan; nur der wichtigste Hinweis) oder **kompakt** (Übersicht vieler Räume); die Wahl merkt sich jedes Gerät.
- **Rollladen, Licht, Garten:** ausgegraut, als Platzhalter für spätere Module.
- Hell oder dunkel folgt dem Design von Home Assistant.

## Heizkörper oder Flächenheizung

| Einstellung | Heizkörper | Flächenheizung | Warum |
|---|---|---|---|
| Fensterpause nach | 60 s | 15 min | Kurzes Stoßlüften kühlt einen Estrich kaum aus, Abschalten bringt dort nichts |
| Vorheizen vor Komfortbeginn | 15 min | 120 min | Fußbodenheizungen brauchen Stunden zum Aufheizen |
| Max. Absenkung unter Komfort | unbegrenzt | 2 K | Tiefes Absenken kostet bei trägen Systemen beim Wiederaufheizen mehr, als es spart |
| Thermostat nachführen | wählbar | aus | Heizkörper-Thermostate messen am Heizkörper zu warm |

Alle Werte lassen sich je Raum ändern; seltene Feinheiten (Absenkgrenze, Fenster-Temperatur, Ausgleich, Kalibrierung, Ventil, Übersteuern, Helfer) zeigt der Raum-Dialog erst mit dem Schalter **Experte** (gemerkt je Gerät). Leere Felder nutzen die Werte der Heizungsart.

## Weitere Funktionen

| Funktion | Wo | Was sie tut |
|---|---|---|
| Wartezeit beim Heimkommen | Einstellungen › Anwesenheit | Erst nach X Minuten zu Hause wird wieder normal geheizt |
| Vorheizen: Lernen, feste Zeit oder aus | Einstellungen › Vorheizen, je Raum unter Vorheizen & Fenster änderbar | Feste Zeit getrennt für Heizkörper und Flächenheizung. Lernend: misst je Raum, wie schnell er warm wird (K/h), und startet so früh, dass die Komforttemperatur pünktlich erreicht ist (höchstens X Minuten vorher) |
| Gemeinsame Heizpläne | Heizpläne, im Raum unter „Heizplan“ auswählen | Ein Plan für mehrere Räume; Komfort/Eco bleiben je Raum. Beim Löschen behalten die Räume die Zeiten als eigenen Plan |
| Gemeinsamer Plan live aus Kalender | Heizpläne › Plan › „HA-Kalender (live)“ | Läuft ein Termin (optional mit Stichwort), heizen alle Räume mit diesem Plan auf Komfort; Vorheizen vor dem nächsten Termin. Termine werden alle 5 Minuten gelesen, ganztägige zählen nicht |
| Heizplan aus Kalender importieren | Heizpläne › „Aus Kalender importieren“ | Termine der nächsten 7 Tage (optional nach Stichwort) werden Zeitfenster, gleiche Uhrzeiten an mehreren Tagen zusammengefasst |
| Zeitplan oder Kalender aus Home Assistant | Raum › Heizplan › Aus Home Assistant | `schedule.*` oder `calendar.*` statt eines Heizplans (an bzw. Termin = Komfort), Vorheizen vor dem nächsten Schaltpunkt bzw. Termin |
| Urlaub aus Kalender | Einstellungen › Urlaub | Läuft ein Termin mit einem der Stichworte (z. B. „Urlaub, Ferien“), ist Urlaub; Abfrage alle 5 Minuten, die nächsten Termine stehen im Pop-up |
| Abwesend: Temperatur oder Absenkung | Einstellungen › Anwesenheit | „höchstens X °C“ oder „um X K absenken“; wahlweise Thermostate ganz aus |
| Lange Abwesenheit | Einstellungen › Anwesenheit | Nach X Tagen ohne Personen auf Frostschutz |
| Eco erzwingen | Übersicht, `switch.hauswerk_eco_erzwingen` | Alle Räume auf Eco (Boost und manuelle Änderungen gehen vor) |
| Fenster-Temperatur je Raum | Raum › Vorheizen & Fenster | Eigene Temperatur bei offenem Fenster statt Frostschutz |
| Heizperiode aus Entität | Einstellungen › Saison | `input_boolean` o. Ä.: an = Heizperiode; Ersatzverhalten, wenn der Außensensor ausfällt |
| Manuelle Änderungen je Herkunft | Raum › Regelung | Am Gerät gedreht und in Home Assistant geändert getrennt übernehmen |
| Zeitfenster für Präsenzmelder | Raum › Geräte | Präsenzmelder zählt nur, solange ein `schedule.*` an ist |
| Fester Ausgleich, eigene Entitäten | Raum › Regelung | Sollwert-Ausgleich ±X K; Kalibrier- und Ventil-Entität selbst wählen; Kalibrier-Intervall in den Einstellungen |
| Auf dem Heimweg vorheizen | Einstellungen › Anwesenheit | Entfernungs-Sensoren (z. B. Integration „Nähe“): näher als X km gilt als zu Hause |
| Gäste | Übersicht, `switch.hauswerk_gaste` | Nie auf Abwesend absenken |
| Party | Übersicht, `switch.hauswerk_party` | Alle Räume mindestens auf Komfort, auch im Urlaub oder bei Abwesenheit |
| Boost | Raumkarte | Thermostate eines Raums für X Minuten ganz auf |
| Sommerpause | Einstellungen | Thermostate aus (oder Frostschutz) ab einer Außentemperatur, 1 K Hysterese, oder von Hand |
| Entkalkungsschutz | Einstellungen, `switch.hauswerk_entkalken` | Einmal pro Woche alle Ventile für X Minuten ganz öffnen |
| Präsenzmelder | Raum › Geräte | Komfortzeit nur, wenn jemand im Raum ist – oder Komfort, sobald jemand da ist |
| Komfort/Eco aus Helfern | Raum › Regelung | `input_number` ersetzt den festen Wert |
| Kleinste Temperatur statt Aus | Raum › Erweitert | Für Thermostate, die „aus“ schlecht vertragen |
| Aus, wenn warm genug | Raum › Erweitert | Thermostat aus ab Soll + X K, wieder an unter Soll |
| Übersteuern | Raum › Erweitert | Bei großer Abweichung höheren/tieferen Sollwert senden, damit träge Thermostate schneller reagieren |
| Kalibrieren | Raum › Erweitert | Offset-Entität des Thermostats (`number.*calibration*`/`*offset*`) auf den Raumsensor einstellen |
| Ventil direkt steuern | Raum › Erweitert | Ventil-Entität (`number.*valve*`/`*position*`) proportional zum Abstand zum Soll |

## Vorrang der Betriebsarten

`Automatik aus` › `Fenster offen` › `Entkalken` › `Sommerpause` › `Boost` / `Manuell` › `Party` › `Urlaub` › `Abwesend` › `Präsenzmelder` › `Vorheizen` / `Komfort` / `Eco`

Danach kann **Warm genug** einen Raum noch abschalten (außer beim Boost).

- **Manuell**: Wer am Thermostat dreht oder im Panel ± tippt, bekommt den Wert bis zur nächsten Planänderung (abschaltbar je Raum).
- **Abwesend** senkt nur ab und hebt nie an.
- Thermostate, die vom Nutzer ausgeschaltet wurden (`off`), lässt Hauswerk in Ruhe.
- Thermostate, die Hauswerk wegen eines offenen Fensters ausgeschaltet hat, schaltet es danach wieder in den vorherigen Modus, auch nach einem Neustart.

## Entitäten

| Entität | Inhalt |
|---|---|
| `switch.hauswerk_urlaub` | Urlaub an/aus, für Automationen |
| `switch.hauswerk_gaste` / `switch.hauswerk_party` / `switch.hauswerk_entkalken` | Gäste, Party, Entkalkungsschutz |
| `switch.hauswerk_<raum>_automatik` | Automatik des Raums |
| `sensor.hauswerk_<raum>_soll` | Solltemperatur, Attribute: Betriebsart, Raumtemperatur, Luftfeuchte, Fenster offen, heizt |
| `sensor.hauswerk_<raum>_heizdauer_heute` | Heizminuten heute |

# Aufbau des Projekts

```
custom_components/hauswerk/
  __init__.py       Einstieg, Panel, Module (hass.data["hauswerk"]["heizen"])
  logic.py          Modul Heizen: Regel-Logik ohne Home-Assistant-Abhängigkeit (getestet)
  controller.py     Modul Heizen: Speicher, Zustandsüberwachung, Ansteuerung der Thermostate, Statistik
  api.py            WebSocket-Befehle fürs Panel (hauswerk/heizen/get, /subscribe, /room/save …)
  sensor.py, switch.py, entity.py
  frontend/hauswerk-panel.js   Panel als Web-Komponente, ohne Build-Schritt
tests/test_logic.py             python -m pytest tests
dev/vorschau.html               Panel mit simuliertem Home Assistant im Browser ansehen
```

Für die Vorschau den Projektordner mit einem beliebigen Webserver ausliefern (z. B. `python -m http.server`) und `/dev/vorschau.html` öffnen.

Die Daten des Moduls Heizen liegen in `config/.storage/hauswerk.heizen`.
