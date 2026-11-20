<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/hauswerk/brand/dark_logo.png">
  <img alt="Hauswerk" src="custom_components/hauswerk/brand/logo.png" height="64">
</picture>

# Hauswerk

Haussteuerung für Home Assistant mit eigenem Seitenmenü-Panel. Die Startseite ist das Dashboard von Hauswerk und fasst die Informationen aller Module zusammen. Einstellungen, die für alle Module gelten (Anwesenheit, Urlaub, Wetter, Startseite, Berechtigungen), stehen zentral unter Hauswerk; alles andere steht im jeweiligen Modul. Hauswerk ist in Module gegliedert:

| Modul | Stand |
|---|---|
| <img src="docs/icons/heizwerk.svg" height="20"> **Heizwerk** | fertig – raumweise Heizungsregelung (früher eine eigene Integration) |
| <img src="docs/icons/rollwerk.svg" height="20"> **Rollwerk** | Rollläden mit Profilen wie die Cover Control Automation: Zeiten, Sonne, Helligkeit, Beschattung, Lüften, Bewohner, Sturm |
| <img src="docs/icons/kraftwerk.svg" height="20"> **Kraftwerk** | Energiefluss live – Solar, Netz, Batterie, Hausverbrauch und Verbraucher; Tageswerte, Autarkie und Kosten aus dem Energie-Dashboard; **lernende Fertigerkennung** für Waschmaschine, Trockner & Co. |
| Licht | geplant |
| Garten | geplant |

## Installation

1. Ordner `custom_components/hauswerk` nach `config/custom_components/hauswerk` kopieren (oder dieses Repo in HACS als benutzerdefiniertes Repository vom Typ „Integration“ hinzufügen).
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Hauswerk**.
4. Im Seitenmenü **Hauswerk** öffnen und **„Hauswerk einrichten“** auf der Startseite antippen: Personen, Wetter, Räume, Rollläden und Energie in einem Durchgang (später unter Einstellungen › Einrichtung).

Voraussetzung: Home Assistant 2024.11 oder neuer. Das eigene Logo unter Geräte & Dienste und in HACS zeigt Home Assistant ab 2026.3 (Ordner `brand/` der Integration); ältere Versionen zeigen dort einen Platzhalter. Räume, Heizpläne und Einstellungen ändern dürfen Admins – oder alle Benutzer, wenn ein Admin das unter Einstellungen › Berechtigungen freigibt (z. B. für ein Wand-Tablet). Die Temperatur ±0,5 °C und Boost dürfen immer alle.

### Umstieg von Heizwerk

Hauswerk ersetzt die frühere Integration „Heizwerk“. Räume, Heizpläne, Einstellungen, Statistik und gelernte Aufheizzeiten werden beim ersten Start automatisch aus `config/.storage/heizwerk.data` übernommen.

1. Hauswerk wie oben installieren und einrichten.
2. Die alte Integration **Heizwerk** unter Geräte & Dienste löschen und den Ordner `config/custom_components/heizwerk` entfernen – sonst regeln beide gleichzeitig dieselben Thermostate.
3. Home Assistant neu starten.
4. Automationen und Dashboards auf die neuen Entitäten umstellen: aus `switch.heizwerk_…` wird `switch.hauswerk_…`, aus `sensor.heizwerk_…` wird `sensor.hauswerk_…`.

> **Prüfung:** Bei jedem Push laufen auf GitHub die Tests, hassfest und die HACS-Prüfung (Workflow „Prüfen“).

# Modul Heizwerk

Raumweise Heizungsregelung.

- **Heizkörper und Flächenheizung** werden unterschiedlich geregelt (siehe unten)
- **Fensterpause**: Thermostat auf Frostschutz oder aus, solange ein Fenster offen ist
- **Heizpläne**: gemeinsame Pläne für mehrere Räume oder ein eigener Plan je Raum, Komfortzeiten je Wochentag (auch über Mitternacht), Import aus einem Home-Assistant-Kalender
- **Anwesenheit & Urlaub** (für das ganze Haus): Absenken, wenn alle weg sind; Urlaub per Schalter, Zeitraum oder aus einem Kalender mit Stichworten
- **Raumsensor & Bericht**: externer Temperatur-/Feuchtesensor je Raum, Heizdauer, Komfortzeit, Fensterpausen und Ø-Temperatur der letzten 7/14/30 Tage

## Aufbau des Panels

```
Start                       Hauswerk-Dashboard: Widgets aller Module
Heizwerk                    Modul Heizen
  ├─ Räume                  /hauswerk/heizen/raeume  (Raumseite: /hauswerk/heizen/raum/<id>)
  ├─ Bericht                /hauswerk/heizen/bericht
  └─ Einstellungen          /hauswerk/heizen/einstellungen  (nur Heizwerk, Heizpläne darunter)
Rollwerk                    Modul Rollläden
  ├─ Rollläden              /hauswerk/rollwerk/rolllaeden
  └─ Einstellungen          /hauswerk/rollwerk/einstellungen
Kraftwerk                   Modul Energie
  ├─ Energiefluss           /hauswerk/kraftwerk/energiefluss
  ├─ Verlauf                /hauswerk/kraftwerk/verlauf
  └─ Einstellungen          /hauswerk/kraftwerk/einstellungen
Licht · Garten              geplant, ausgegraut
⚙ Einstellungen            /hauswerk/einstellungen  (zentral, für alle Module)
  └─ Protokoll              /hauswerk/protokoll  (was wann warum entschieden wurde)
🔔 Hinweise                 Pop-up mit allem, was zu beheben oder gut zu wissen ist
```

- **Start (Dashboard von Hauswerk):** Zustand des Hauses und frei wählbare **Widgets** aus allen Modulen: Heizwerk, Anwesenheit (mit Personen, Ort und Entfernung nach Hause), Wetter, Räume, Shortcuts (Szenen, Skripte, Schalter, Lichter), Fenster, Komfortzeiten, Heizdauer, Werte (beliebige Sensoren) und Wetterprognose (nächste Stunden oder Tage, Frost-Hinweis). Über „Anpassen“ hinzufügen (mit Vorschau in allen Größen), am Griff ziehen zum Verschieben, umbenennen, entfernen und in drei Größen stellen: **klein** (nur das Wichtigste), **mittel** (Kennzahlen bzw. Liste) und **groß** (volle Breite mit allen Einzelheiten) – gilt für alle Benutzer.
- **Zentrale Einstellungen (Zahnrad oben rechts):** gelten für ganz Hauswerk und alle Module – **Anwesenheit** (Personen per Tipp wählen mit Status „da“ oder Abstand in Metern; weitere Personen oder Handys/Tracker hinzufügen oder eine neue Person direkt in Home Assistant anlegen; Wohnungs-Zone, Wartezeiten beim Gehen und Heimkommen, Urlaub, Gäste, Heimweg-Grenze in Metern, Entfernungs-Sensoren), **Urlaub** (von Hand, Zeitraum oder Kalender mit Stichworten), **Wetter**, **Darstellung**, **Widgets** der Startseite, **Module** im Überblick, **Funk-Auslastung** (Duty Cycle), **Protokoll** und **Berechtigungen**.
- **Benachrichtigungen:** Nachrichten aufs Handy über die Home-Assistant-App (`notify.mobile_app_…`, mehrere Geräte wählbar, mit Testnachricht): **Fenster lange offen** (ab X Min., einmal je Öffnen), **Thermostat nicht erreichbar** (seit X Min.), **Frost erwartet** (Tiefstwert der Vorhersage der nächsten 3 Tage unter der Grenze „Kälteeinbruch“) und **Batterie schwach**. Je Anlass wählbar: **Aus**, **Protokoll** (kein Push), **Normal** oder **Wichtig** (sofort auch in der Ruhezeit, durchbricht „Nicht stören“ auf dem iPhone, hohe Priorität auf Android). Auf Wunsch zusätzlich als **Mitteilung in Home Assistant**, die von selbst verschwindet, wenn der Anlass erledigt ist. **Ruhezeit** (z. B. 22:00–07:00): Nachrichten werden zurückgehalten und danach gesendet, falls der Anlass noch besteht. Jede Nachricht steht auch im Protokoll unter „Nachrichten“.
- **Wetter:** Wetterquelle, Außentemperatur (eigene Wetterstation statt Wetterdienst) und **Sonnenstand** (Entität der Integration „Sonne“, Standard `sun.sun`) wählen; dazu die aktuellen Werte (Wetterlage, gefühlte Temperatur, Feuchte, Wind, Sonne, Sonnenauf- und -untergang) und Grenzwerte: **Heizgrenze** (aus Heizwerk › Saison), **Kälteeinbruch** (Tiefstwert der nächsten 3 Tage) und **Sturm** (Böen der nächsten 24 Stunden). Wird eine Grenze erreicht, erscheint ein Hinweis unter der Glocke. Jede Zeile erklärt sich per „?“.
- **Protokoll:** was wann warum entschieden wurde, 14 Tage lang und live – Nachrichten (gesendet oder in der Ruhezeit zurückgehalten), Anwesenheit, Saison (Sommerpause, Entkalken), Ziel & Heizung je Raum mit Begründung, Fenster, Von Hand (Thermostat, Home Assistant, Panel, Boost), Geräte (nicht/wieder erreichbar), Thermostat-Befehle und Einstellungen (mit Benutzer). Filter nach Raum und Kategorie (je Gerät gemerkt, Thermostat-Befehle standardmäßig aus) und Suche.
- **Darstellung:** Design (wie Home Assistant, hell oder dunkel), Akzentfarbe (Auswahl oder eigene Farbe, auch fürs Logo), Hintergrund (Muster, **Tageszeit** – die Kopfzeile zeigt Nacht, Sonnenaufgang, Tag oder Sonnenuntergang nach `sun.sun` – oder schlicht) sowie Wetter und Uhrzeit oben rechts. Änderungen sind im Pop-up sofort als Vorschau zu sehen und gelten nach dem Speichern für alle. Die **Größe** (kompakt, normal, groß) merkt sich jedes Gerät selbst, z. B. groß auf dem Wand-Tablet.
- **Heizwerk › Einstellungen:** nur was das Heizen betrifft – **Abwesenheit & Urlaub** (welche Temperatur, wenn niemand da ist oder Urlaub ist; Frostschutz nach langer Abwesenheit), **Saison**, **Heizpläne**, **Vorheizen** (auch nach Wetter), **Lüften & Schimmelschutz**, **Frostschutz**, **Boost**, **Entkalkungsschutz**, **Kalibrierung** und die **Räume**. Ganz oben führt ein Eintrag zu den zentralen Einstellungen.
- Beide Einstellungsseiten sind Listen mit Suche; ein Tipp öffnet die Einzelheiten als Pop-up.
- **Entitätssuche** (überall, wo Geräte gewählt werden): gewählte Entitäten als Karten mit aktuellem Wert und Raum; darunter **Vorschläge** mit Trefferquote und Begründung (Geräteklasse, Name, Raum aus Home Assistant, erreichbar), **Nach Raum** gruppiert und **Filter** nach Art und Erreichbarkeit. Temperaturunterschiede zeigt Hauswerk überall in °C.
- **Kopfzeile:** schrumpft beim Scrollen auf eine Zeile mit Logo, Reitern, Glocke und Zahnrad. Auf dem Handy gibt es stattdessen unten eine Leiste **Start · Heizwerk · Rollwerk · Kraftwerk · Einstellungen**; im Modul Heizwerk bleibt dessen Unterleiste **Räume · Bericht · Einstellungen** sichtbar.
- **Raumseite:** Ein Tipp auf den Raumnamen öffnet eine eigene Seite mit Raumkarte, Verlauf der letzten 24 Stunden (Raumtemperatur, Soll, Heizzeiten, offene Fenster), Geräten mit Live-Werten, Einstellungen im Überblick und den letzten 7 Tagen.
- **Suche über alles:** Lupe oben (am Computer `/` oder Strg+K) – Seiten, Räume, Geräte, Heizpläne, Rollläden, Profile, Verbraucher, alle Einstellungen und das Protokoll.
- **Hinweise:** Glocke oben rechts mit Zahl. Ein Tipp listet alles, was zu beheben ist (z. B. Thermostat nicht erreichbar, **zweite Regelung** am selben Thermostat, **Funk ausgelastet**, **Batterie schwach** an Thermostat, Fensterkontakt oder Sensor, Raum ohne Thermostat, Kalender nicht lesbar) und was gut zu wissen ist (z. B. Fenster lange offen, **Jetzt lüften**, Fenster vermutlich offen) – jeweils mit Sprung an die richtige Stelle.
- **Räume:** schmales Banner mit Ø-Temperatur, Kurzurteil (z. B. „2 Räume unter Soll“), Wetter und Kennzahlen (heizende Räume, Fenster, Außen, Luftfeuchte, heute geheizt). Raumkacheln **detailliert** (Boost und „⋯“-Menü für Heizplan, Bearbeiten und Automatik; heutiger Zeitplan; nur der wichtigste Hinweis) oder **kompakt** (Übersicht vieler Räume); die Wahl merkt sich jedes Gerät. Symbole an der Kachel: Fenster offen, Präsenz, Ventilöffnung in %, Fußbodenheizung (nur solange sie heizt) und Luftfeuchte – Details als Quickinfo. **Ein Tipp auf die Kachel** öffnet das Schnellmenü für manuelle Änderungen: Wunschtemperatur (± oder Komfort/Eco), Dauer (bis Planwechsel, 1/2/4/8 h), Boost, zurück zum Plan, Raumseite, Heizplan und Automatik.
- Hell oder dunkel folgt dem Design von Home Assistant.

## Tabletmodus (Wand-Tablet)

Unter *Einstellungen › Darstellung › Tabletmodus* je Gerät einschalten – oder als Start-Adresse `…/hauswerk?tablet` eintragen (z. B. in Fully Kiosk; `?tablet=0` schaltet ihn wieder aus).

- **Unterleiste unten:** Die Modul-Tasten bleiben oben; die Unterleiste des Moduls (z. B. Räume · Bericht · Einstellungen) steht groß am unteren Rand.
- **Kein Scrollen:** Jede Seite passt sich der Auflösung an – so groß wie gut lesbar, bei Listen zwei Spalten. Passt es nicht auf eine Seite, gibt es eine zweite zum Wischen (Punkte unten).
- **Hell/Dunkel nach Sonnenstand** (Standard am Tablet, je Gerät umstellbar) – Fully meldet den Dunkelmodus des Geräts meist nicht.
- **Bildschirmschoner** nach 1–10 Minuten ohne Berührung: abgedunkelt mit großer Uhr, Datum, Wetter, Hausstand und Hinweisen; nachts noch dunkler, der Inhalt wandert gegen Einbrennen; neue Hinweise leuchten auf. Dabei geht es zurück zur Startseite. Antippen weckt auf, ohne etwas zu schalten.
- **Seitenleiste:** Die Seitenleiste von Home Assistant wird im Tabletmodus ausgeblendet (☰ öffnet sie kurz); ohne Tabletmodus kommt sie wie vorher zurück.
- **Eigene Startseite:** Im Anpassen-Modus am Tablet „Eigene“ wählen – Handy und PC bleiben unverändert.
- **Aufwecken bei Bewegung** über Bewegungsmelder aus Home Assistant oder die Kamera in Fully; **nachts** abgedunkelt, schwarz mit kleiner Uhr oder Display aus (Fully).
- **Im Bildschirmschoner** zusätzlich: Vorhersage, nächste Rollladen-Fahrten, Termine (z. B. Müllabfuhr); Warnungen groß, neue machen den Schoner hell.
- **Tablet sperren:** nur bedienen, nichts einstellen – 3 Sekunden auf das Logo drücken entsperrt für 10 Minuten.
- **Fully Kiosk:** „Bildschirm anlassen“ einschalten; mit eingeschalteter JavaScript-Schnittstelle dunkelt Hauswerk das Display im Bildschirmschoner zusätzlich ab.

## Heizkörper oder Flächenheizung

| Einstellung | Heizkörper | Flächenheizung | Warum |
|---|---|---|---|
| Fensterpause nach | 60 s | 15 min | Kurzes Stoßlüften kühlt einen Estrich kaum aus, Abschalten bringt dort nichts |
| Vorheizen vor Komfortbeginn | 15 min | 120 min | Fußbodenheizungen brauchen Stunden zum Aufheizen |
| Max. Absenkung unter Komfort | unbegrenzt | 2 °C | Tiefes Absenken kostet bei trägen Systemen beim Wiederaufheizen mehr, als es spart |
| Thermostat nachführen | wählbar | aus | Heizkörper-Thermostate messen am Heizkörper zu warm |

Alle Werte lassen sich je Raum ändern; seltene Feinheiten (Absenkgrenze, Fenster-Temperatur, Ausgleich, Kalibrierung, Ventil, Übersteuern, Helfer) zeigt der Raum-Dialog erst mit dem Schalter **Experte** (gemerkt je Gerät). Leere Felder nutzen die Werte der Heizungsart.

## Weitere Funktionen

| Funktion | Wo | Was sie tut |
|---|---|---|
| Raum-Assistent | Heizwerk › Räume › „Raum anlegen“ | Schritt für Schritt: Bereich aus Home Assistant, Nutzung (Temperatur-Vorschläge), Heizungsart inkl. Mischbetrieb, Geräte automatisch aus dem Bereich, Komfort/Eco und Heizzeiten. „Ohne Assistent“ öffnet den vollen Dialog |
| Wartezeit beim Heimkommen | Hauswerk › Einstellungen › Anwesenheit | Erst nach X Minuten zu Hause wird wieder normal geheizt |
| Vorheizen: Lernen, feste Zeit oder aus | Heizwerk › Einstellungen › Vorheizen, je Raum unter Vorheizen & Fenster änderbar | Feste Zeit getrennt für Heizkörper und Flächenheizung. Lernend: misst je Raum, wie schnell er warm wird (°C pro Stunde), und startet so früh, dass die Komforttemperatur pünktlich erreicht ist (höchstens X Minuten vorher) |
| Gemeinsame Heizpläne | Heizpläne, im Raum unter „Heizplan“ auswählen | Ein Plan für mehrere Räume; Komfort/Eco bleiben je Raum. Beim Löschen behalten die Räume die Zeiten als eigenen Plan |
| Gemeinsamer Plan live aus Kalender | Heizpläne › Plan › „HA-Kalender (live)“ | Läuft ein Termin (optional mit Stichwort), heizen alle Räume mit diesem Plan auf Komfort; Vorheizen vor dem nächsten Termin. Termine werden alle 5 Minuten gelesen, ganztägige zählen nicht |
| Heizplan aus Kalender importieren | Heizpläne › „Aus Kalender importieren“ | Termine der nächsten 7 Tage (optional nach Stichwort) werden Zeitfenster, gleiche Uhrzeiten an mehreren Tagen zusammengefasst |
| Zeitplan oder Kalender aus Home Assistant | Raum › Heizplan › Aus Home Assistant | `schedule.*` oder `calendar.*` statt eines Heizplans (an bzw. Termin = Komfort), Vorheizen vor dem nächsten Schaltpunkt bzw. Termin |
| Urlaub aus Kalender | Hauswerk › Einstellungen › Urlaub | Läuft ein Termin mit einem der Stichworte (z. B. „Urlaub, Ferien“), ist Urlaub; Abfrage alle 5 Minuten, die nächsten Termine stehen im Pop-up |
| Abwesend: Temperatur oder Absenkung | Heizwerk › Einstellungen › Abwesenheit & Urlaub | „höchstens X °C“ oder „um X °C absenken“; wahlweise Thermostate ganz aus |
| Lange Abwesenheit | Heizwerk › Einstellungen › Abwesenheit & Urlaub | Nach X Tagen ohne Personen auf Frostschutz |
| Eco erzwingen | Übersicht, `switch.hauswerk_eco_erzwingen` | Alle Räume auf Eco (Boost und manuelle Änderungen gehen vor) |
| Fenster-Temperatur je Raum | Raum › Vorheizen & Fenster | Eigene Temperatur bei offenem Fenster statt Frostschutz |
| Heizperiode aus Entität | Heizwerk › Einstellungen › Saison | `input_boolean` o. Ä.: an = Heizperiode; Ersatzverhalten, wenn der Außensensor ausfällt |
| Manuelle Änderungen je Herkunft | Raum › Regelung | Am Gerät gedreht und in Home Assistant geändert getrennt übernehmen |
| Zeitfenster für Präsenzmelder | Raum › Geräte | Präsenzmelder zählt nur, solange ein `schedule.*` an ist |
| Fester Ausgleich, eigene Entitäten | Raum › Regelung | Sollwert-Ausgleich ±X °C; Kalibrier- und Ventil-Entität selbst wählen; Kalibrier-Intervall in den Einstellungen |
| Auf dem Heimweg vorheizen | Hauswerk › Einstellungen › Anwesenheit | Entfernungs-Sensoren (z. B. Integration „Nähe“): näher als X Meter gilt als zu Hause |
| Gäste | Übersicht, `switch.hauswerk_gaste` | Nie auf Abwesend absenken |
| Party | Übersicht, `switch.hauswerk_party` | Alle Räume mindestens auf Komfort, auch im Urlaub oder bei Abwesenheit |
| Boost | Raumkarte | Thermostate eines Raums für X Minuten ganz auf |
| Sommerpause | Heizwerk › Einstellungen › Saison | Thermostate aus (oder Frostschutz) ab einer Außentemperatur, 1 °C Hysterese, oder von Hand |
| Entkalkungsschutz | Heizwerk › Einstellungen, `switch.hauswerk_entkalken` | Einmal pro Woche alle Ventile für X Minuten ganz öffnen |
| Präsenzmelder | Raum › Geräte | Komfortzeit nur, wenn jemand im Raum ist – oder Komfort, sobald jemand da ist |
| Komfort/Eco aus Helfern | Raum › Regelung | `input_number` ersetzt den festen Wert |
| Kleinste Temperatur statt Aus | Raum › Erweitert | Für Thermostate, die „aus“ schlecht vertragen |
| Aus, wenn warm genug | Raum › Erweitert | Thermostat aus ab Soll + X °C, wieder an unter Soll |
| Übersteuern | Raum › Erweitert | Bei großer Abweichung höheren/tieferen Sollwert senden, damit träge Thermostate schneller reagieren |
| Kalibrieren | Raum › Erweitert | Offset-Entität des Thermostats (`number.*calibration*`/`*offset*`) auf den Raumsensor einstellen |
| Ventil direkt steuern | Raum › Erweitert | Ventil-Entität (`number.*valve*`/`*position*`) proportional zum Abstand zum Soll |
| Vorheizen nach Wetter | Heizwerk › Einstellungen › Vorheizen | Bezug 5 °C außen: je Grad kälter 4 % mehr Vorlauf, je Grad wärmer 4 % weniger (0,6- bis 1,8-fach). Lernende Räume rechnen ihre Aufheizgeschwindigkeit auf 5 °C um |
| Feiertage wie Wochenende | Hauswerk › Einstellungen › Kalender | Kalender der Integration „Arbeitstag“ (workday, ersatzweise ihr Sensor): fehlt an einem Werktag der Arbeitstag, gelten die Zeiten von Samstag oder Sonntag – in Heizwerk für alle Heizpläne (auch in der Vorschau), in Rollwerk fürs Öffnen und Schließen |
| Lüften & Schimmelschutz | Heizwerk › Einstellungen › Lüften | Hinweis „Jetzt lüften“, wenn drinnen ab X % Luftfeuchte und die Luft draußen trockener ist (absolute Feuchte, Taupunkt) |
| Nach dem Duschen nachheizen | Raum › Geräte (mit Feuchtesensor) | Steigt die Luftfeuchte in 15 Min. um X Prozentpunkte, heizt der Raum für X Min. auf Komfort (höchstens einmal pro Stunde) |
| Fenster ohne Kontakt erkennen | Raum › Vorheizen & Fenster | Fällt die Raumtemperatur in 5 Min. um X °C (Standard 1 °C), Fensterpause für X Min. (Standard 15) |
| Weitere Geräte nur anzeigen | Raum › Geräte | Z. B. Heizkörper-Thermostat, Stellantrieb oder Schalter der Fußbodenheizung neben dem Wandthermostat, das Heizwerk einstellt: Symbole an Raumkarte und kompakter Kachel – Ventil mit Öffnung in % (höchster Wert; gelesen aus dem Thermostat oder automatisch aus einem %-Sensor wie „Ventilöffnungsgrad“ am selben Gerät), Fußbodenheizung an/aus – und alle Werte auf der Raumseite |
| Zweite Regelung erkennen | automatisch, Hinweis unter der Glocke | Nennt eine andere Integration ein Thermostat in ihren Attributen (z. B. Better Thermostat, ein anderes Heizungsprogramm) oder stellen Automationen, Skripte oder Integrationen es 3-mal in 2 Stunden um, warnt Hauswerk mit deren Namen. Solche Änderungen stehen im Protokoll als „von …“ |
| Wandthermostat und Heizkörper gekoppelt | Raum › Geräte | Wandthermostat und Heizkörper-Thermostate im Raum (erkannt am Modell, z. B. HmIP-WTH und HmIP-eTRV, sonst am Namen): Hauswerk stellt nur das Wandthermostat, die Heizkörper folgen über die CCU. Weicht ein Heizkörper länger als 15 Min. ab, stellt Hauswerk ihn wieder selbst. „Alle selbst stellen“ schaltet das ab |
| Mischbetrieb (Fußbodenheizung + Heizkörper) | Raum › Geräte | Gewählte Heizkörper-Thermostate (in der CCU aus der Heizgruppe genommen, auf manuell) sind Zusatzheizung: zu (Frostschutz), solange die Fußbodenheizung über das Wandthermostat reicht; Raum-Soll (um den Messfehler am Heizkörper erhöht), wenn der Raum X °C (Standard 0,5) unter Soll liegt, beim Vorheizen und Boost – bis 0,1 °C unter Soll. Nicht gewählte Heizkörper folgen weiter dem Wandthermostat |
| Funk-Auslastung (Duty Cycle) | Hauswerk › Einstellungen › Funk-Auslastung | Duty-Cycle-Sensoren (automatisch alle %-Sensoren mit „duty_cycle“, z. B. CCU, Access Point, Router): ab X % (Standard 70) nur Betriebsart-Wechsel und Änderungen ab 1 °C, höchstens alle 15 Min. je Thermostat, keine Ventil- und Kalibrier-Befehle. Geräte mit „Duty Cycle erreicht“ bekommen keine Befehle |
| Heizkörper bleibt kalt | automatisch, Glocke und Nachricht | Ventil eine Stunde ≥ 90 % offen, Raum ≥ 0,5 °C unter Soll und kaum wärmer (< 0,3 °C): Hinweis auf Luft im Heizkörper, hängenden Ventilstift oder fehlende Wärme; bei mehreren Räumen gleichzeitig: Heizung prüfen |
| Wärmeanforderung | Heizwerk › Einstellungen › Wärmeanforderung | Wärmeerzeuger (z. B. Zone der Vaillant-Anlage) absenken oder ausschalten, wenn X Min. kein Raum Wärme braucht (Ventil unter X %, kein Vorheizen/Boost); sofort zurück, sobald ein Raum Wärme braucht; beim Vorheizen optional anheben. Gemerkte Werte werden wiederhergestellt |
| Heizleistung je Raum | Heizwerk › Bericht | Urteil (Passt, Reserve, Knapp, Reicht nicht, Messung prüfen) aus „Komfort erreicht“, Ø Abweichung, Ø Ventil und „ganz auf“, Aufheizgeschwindigkeit, überheizt und kalten/milden Tagen – mit Ursachen und Tipps (Heizkörper/Vorlauf, Thermostat misst falsch, Heizkurve bei Frost, Reserve für niedrigere Vorlauftemperatur) |
| Ventilverlauf | Heizwerk › Bericht | Ø Ventilöffnung je Raum und Stunde als Wärmekarte (inkl. Fußbodenheizung an/aus) |
| Diagnose | Geräte & Dienste › Hauswerk › ⋮ › Diagnose herunterladen | Einstellungen, Räume, Zustände aller beteiligten Entitäten (mit Gerätemodell) und die letzten 1500 Protokolleinträge als Datei |
| Batterie-Warnung | Hauswerk › Einstellungen › Benachrichtigungen | Batterie-Sensoren an den Geräten von Thermostaten, Fensterkontakten und Raumsensoren; unter X % Hinweis unter der Glocke und auf Wunsch Nachricht |

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

# Modul Rollwerk

Rollläden mit **Profilen** nach dem Vorbild der [Cover Control Automation (CCA)](https://github.com/hvorragend/ha-blueprints) – ohne Blueprint und YAML, alles im Panel (Rollwerk › Rollläden und Rollwerk › Einstellungen).

- **Rollläden-Seite:** nach Räumen aus Home Assistant, je Rollladen Stellung, was die Automatik gerade will und warum, ↑ ■ ↓ und Schieberegler; Hinweise für Beschattung, gekippt/offen, Bewohner schläft, von Hand – mit „Automatik übernimmt“.
- **Profile:** jeder Rollladen nutzt ein Profil (z. B. „Standard“, „Süd mit Hitze“, „Schlafzimmer“) mit fünf Abschnitten; Profile lassen sich anlegen, kopieren, umbenennen (Name oben im Profil-Dialog) und löschen (die Rollläden bekommen dann ein gewähltes Ersatzprofil). Zuerst nur das Wichtige, mit **Experte** alle Einstellungen der Cover Control Automation:
  - **Tagesablauf:** nach Uhrzeit oder mit der Sonne (früheste/späteste Zeit, Werktag und frei getrennt, Sonnenhöhe), Stellungen in % für öffnen und schließen; abends wahlweise **in zwei Stufen** (Stufe 1 auf X % ab Sonnenrichtung, -höhe oder Uhrzeit, Stufe 2 zur spätesten Zeit ganz zu – beide schaltbar); Experte: Kalender, Helligkeit, „Arbeitstag morgen“.
  - **Sonnenschutz:** Fensterrichtung per Kompass mit **Empfehlung je Himmelsrichtung** (übernehmbar) und ein Satz mit − / + für Sonnenhöhe, Außentemperatur und Stellung; Experte: Bedingungen mit und/oder, Sonnenhöhe, Innen-/Außentemperatur, Helligkeit, Vorhersage, Wetterlage, Wartezeiten.
  - **Fenster & Lüften:** Tür offen = nicht herunterfahren (oder höchstens bis X %) – auch beim Erzwingen; gekippt = Lüftungsstellung (in jedem Profil standardmäßig an).
  - **Ausnahmen:** niemand zu Hause (wie immer, tagsüber zu, beschattet) und Urlaub mit zufälligen Zeiten – beides aus Hauswerk › Anwesenheit/Urlaub; von Hand verstellt; Schlafzimmer-Schalter; Experte: Erzwingen.
  - **Feinheiten:** alle Stellungen; Experte: Toleranz, Fahrzeit, Verzögerung, Regeln im Detail.
- **Assistent „Rollladen hinzufügen“:** Rollläden wählen, Richtung am Kompass, Kontakte (im Bereich gefunden), Raum-Art und Sonnenschutz – passendes Profil wird vorgeschlagen oder neu angelegt (Name frei wählbar).
- **Tagesleiste:** je Profil und Rollladen – heute öffnen, Beschattung möglich, schließen – und „Als Nächstes“.
- **Je Rollladen:** Profil, Raum aus Heizwerk (automatisch über den Bereich), Kontakte (aus dem Heizwerk-Raum: Türen = ganz offen, Fenster = gekippt – oder eigene), Automatik und Sturmschutz an/aus. Die Raumtemperatur aus Heizwerk zählt beim Sonnenschutz als Innentemperatur.
- **Sturmschutz:** ab der Sturmgrenze aus Hauswerk › Wetter hoch, Ende nach 15 Min. unter 80 %; Böen vom Wetterdienst oder dem Böen-Sensor unter Hauswerk › Wetter.
- **Nach Neustart:** nichts, verpasste Wechsel nachholen oder immer auf Sollstellung.

**Protokoll:** jede Fahrt (Kategorie „Rollläden“, mit Grund und vorheriger Stellung), Übersteuerungen von Hand, Sturmschutz sowie Änderungen an Profilen und Rollläden mit Vorher → Nachher; Filter „Rollwerk“.

Einstellungen aus Version 0.24 werden beim ersten Start übernommen (je Fassade ein Profil). Anwesenheit, Urlaub, Feiertage, Sonnenstand, Wetter und Sturmgrenze stellt man nur einmal unter Hauswerk ein. Alles steht im Protokoll.

# Modul Kraftwerk

Zeigt, woher der Strom kommt und wohin er fließt (Kraftwerk › Energiefluss):

- **Energiefluss live:** Solar, Netz (Bezug oder Einspeisung), Batterie (lädt/entlädt, Ladestand) und Haus als Kreise; animierte Linien zeigen, wer wen versorgt – Solar zuerst ins Haus, dann in die Batterie, der Rest ins Netz. Am Haus steht, wie viel Prozent gerade selbst gedeckt sind.
- **Verbraucher jetzt:** einzelne Geräte mit Leistungsmessung (Wärmepumpe, Wallbox …) mit eigenem Namen, passendem Symbol (nach dem Namen gewählt) und Anteil am Hausverbrauch; der Rest erscheint als „Sonstiges“.
- **Heute und Verlauf** (Heute, 7 Tage, 30 Tage, 12 Monate): erzeugt, verbraucht, Netzbezug, eingespeist, Batterie, **Eigenverbrauch** und **Autarkie** in %, Kosten bzw. Ertrag. Balken je Stunde, Tag oder Monat: Verbrauch aus Solar, Batterie und Netz, darunter die Einspeisung.
- **Einstellungen:** nur die Leistungs-Sensoren (W/kW) für Solar, Netz (mit Vorzeichen oder Bezug/Einspeisung getrennt, Vorzeichen umkehrbar), Batterie (+ Ladestand), Hausverbrauch (sonst errechnet) und Verbraucher. **Automatisch erkennen** schlägt sie vor – aus dem Energie-Dashboard, von denselben Geräten wie die dort eingetragenen Zähler oder nach Namen.
- **Nichts doppelt:** Zähler (kWh) und Preise kommen aus dem **Energie-Dashboard von Home Assistant** und dessen Statistik.
- **Widget „Energie“** für die Startseite: klein Solar und Netz, mittel vier Werte und Autarkie heute, groß mit Energiefluss und Tageswerten.

# Aufbau des Projekts

```
custom_components/hauswerk/
  __init__.py       Einstieg, Panel, Module (hass.data["hauswerk"]: "log", "haus", "heizen", "rollwerk", "kraftwerk")
  core.py           Hauswerk-Kern für alle Module: Anwesenheit, Urlaub (auch Kalender), Wetter (Frost-Vorhersage),
                    Benachrichtigungen mit Ruhezeit, Darstellung, Widgets, Berechtigungen (config/.storage/hauswerk.haus)
  logic.py          Modul Heizwerk: Regel-Logik ohne Home-Assistant-Abhängigkeit (getestet)
  controller.py     Modul Heizwerk: Speicher, Zustandsüberwachung, Ansteuerung der Thermostate, Statistik
  log.py            Protokoll für alle Module (config/.storage/hauswerk.protokoll, 14 Tage)
  rollwerk.py       Modul Rollwerk: Rollläden (config/.storage/hauswerk.rollwerk)
  kraftwerk.py      Modul Kraftwerk: Sensoren für den Energiefluss (config/.storage/hauswerk.kraftwerk)
  diagnostics.py    Diagnose-Download (Geräte & Dienste › Hauswerk › Diagnose herunterladen)
  api.py            WebSocket-Befehle fürs Panel (hauswerk/heizen/get, /subscribe, /room/save …, hauswerk/log/get, /subscribe, hauswerk/notify/test)
  sensor.py, switch.py, entity.py
  brand/            Logo und Symbol für Home Assistant (icon.png, logo.png, dark_logo.png, je mit @2x)
  frontend/hauswerk-panel.js   Panel als Web-Komponente, ohne Build-Schritt
tests/test_logic.py             Regel-Logik
tests/test_smoke.py             Kern, Heizwerk und Protokoll mit nachgebautem Home Assistant
tests/test_panel.py             Panel und Backend passen zusammen (Widget-Typen)
tests/test_panel_ui.py          Klicktests im Browser (Playwright): alle Seiten, Fenster, Widgets; gesendete Befehle gegen api.py
dev/vorschau.html               Panel mit simuliertem Home Assistant im Browser ansehen
.github/workflows/ci.yml        Prüfen bei jedem Push: pytest, hassfest, HACS
.github/workflows/release.yml   Release, sobald sich die Version in manifest.json ändert; Text aus CHANGELOG.md
CHANGELOG.md                    Änderungen je Version – erscheinen als Update-Notizen in Home Assistant (HACS)
```

Nach jeder Änderung am Panel `python3 dev/pack.py` ausführen – das legt die komprimierte `hauswerk-panel.js.gz` daneben (ein Test prüft, dass sie passt).

Tests: `pip install pytest`, dann im Projektordner `python -m pytest tests` (Home Assistant wird nicht gebraucht). Für die Klicktests zusätzlich `pip install playwright voluptuous` und `python -m playwright install chromium`.

Vorschau: `dev/vorschau.html` direkt im Browser öffnen. Alle Daten sind erfunden, Speichern wirkt nur bis zum Neuladen.

Speicher: zentrale Einstellungen in `config/.storage/hauswerk.haus`, Daten des Moduls Heizwerk in `config/.storage/hauswerk.heizen`. Beim ersten Start mit 0.18 übernimmt der Kern Anwesenheit, Urlaub, Wetter, Darstellung, Widgets und Berechtigungen automatisch aus den bisherigen Heizwerk-Einstellungen.
