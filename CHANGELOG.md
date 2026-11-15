# Änderungen

Neueste Version oben. Der Abschnitt einer Version erscheint automatisch als Release-Text auf GitHub und damit im Update-Dialog von Home Assistant (HACS).

## 0.20.1 – 2026-11-15

### Geändert
- **Feiertage** stehen jetzt unter *Hauswerk › Einstellungen › Anwesenheit* statt bei Heizwerk – sie gelten künftig für alle Module. Ein schon gewählter Arbeitstag-Sensor wird beim Start automatisch übernommen.

## 0.20.0 – 2026-11-15

### Neu
- **Personen hinzufügen:** Unter *Anwesenheit › Wer wohnt hier?* weitere Personen oder Handys/Tracker wählen – oder eine neue Person direkt in Home Assistant anlegen (nur Administratoren).
- **Sonnenstand wählbar:** Unter *Wetter* die Entität der Integration „Sonne“ festlegen (Standard `sun.sun`).
- **Benachrichtigungsart je Anlass:** Aus, Protokoll, Normal oder Wichtig. „Wichtig“ kommt sofort, auch in der Ruhezeit, durchbricht „Nicht stören“ auf dem iPhone und hat hohe Priorität auf Android.
- **Mitteilung in Home Assistant:** Nachrichten auf Wunsch zusätzlich in der Seitenleiste von Home Assistant; sie verschwinden von selbst, sobald der Anlass erledigt ist.
- **Geräte nur anzeigen:** Am Raum unter *Geräte* weitere Geräte eintragen, z. B. Heizkörper-Thermostat oder Stellantrieb der Fußbodenheizung neben dem Wandthermostat. Heizwerk zeigt deren Ventilöffnung an Raumkarte und Raumseite, stellt aber nur die Thermostate ein.

### Behoben
- Im Shortcut-Widget (und anderen kleinen/mittleren Widgets) verschwand die letzte Reihe im Ausblend-Verlauf am unteren Rand.

## 0.19.0 – 2026-11-15

### Neu
- **Benachrichtigungen aufs Handy** über die Home-Assistant-App: Fenster lange offen, Thermostat nicht erreichbar, Frost erwartet und Batterie schwach – mit Ruhezeit und Testnachricht. Jede Nachricht steht auch im Protokoll unter „Nachrichten“.
- **Batterie-Warnung:** Batterie-Sensoren an Thermostaten, Fensterkontakten und Raumsensoren werden automatisch gefunden; unter 20 % erscheint ein Hinweis unter der Glocke.
- **Vorheizen nach Wetter:** bei Kälte früher, an milden Tagen später. Lernendes Vorheizen rechnet auf 5 °C außen um.
- **Lüften & Schimmelschutz:** Hinweis „Jetzt lüften“ nach absoluter Feuchte und Taupunkt; nach dem Duschen kurz nachheizen.
- **Fenster ohne Kontakt erkennen:** fällt die Raumtemperatur in 5 Minuten stark, startet die Fensterpause.
- **Feiertage wie Wochenende** über den Sensor der Integration „Arbeitstag“.

## 0.18.2 – 2026-11-15

### Neu
- **Eigenes Logo** für Hauswerk unter *Geräte & Dienste* und in HACS (ab Home Assistant 2026.3) und oben links im Panel.

## 0.18.1 – 2026-11-15

### Geändert
- Die **Entitätssuche** klappt erst nach „Hinzufügen“ auf.
- **Wetter:** Wetterquelle und Außentemperatur über die Entitätssuche wählen.

### Behoben
- Der Dialog **Darstellung** war seit 0.16.0 leer.

## 0.18.0 – 2026-11-15

### Geändert
- **Hauswerk-Kern:** Anwesenheit, Urlaub, Wetter, Darstellung, Widgets und Berechtigungen gehören jetzt zu Hauswerk selbst und gelten für alle Module (eigener Speicher `hauswerk.haus`). Bestehende Einstellungen werden beim ersten Start automatisch übernommen.
- Die Schalter Urlaub und Gäste gehören zum Kern; ihre Entitäts-IDs bleiben gleich.

### Intern
- Automatische Prüfung bei jedem Push (Tests, hassfest, HACS) und eine Panel-Vorschau ohne Home Assistant.

## 0.17.0 – 2026-11-15

### Neu
- **Entitätssuche** mit Vorschlägen, Trefferquote, Gruppierung nach Raum und Filtern.
- **Anwesenheit** neu gestaltet: Personen per Tipp, Abstand nach Hause in Metern, Wohnungs-Zone.

### Geändert
- Temperaturunterschiede überall in °C statt K.

## 0.16.0 – 2026-11-15

### Neu
- **Wetter-Einstellungen** mit aktuellen Werten, Sonnenauf- und -untergang sowie Grenzwerten für Kälteeinbruch und Sturm.
- **Protokoll:** was wann warum entschieden wurde – 14 Tage, live, mit Filtern und Suche.

## 0.15.0 – 2026-11-15

### Neu
- **Darstellung:** Design, Akzentfarbe, Hintergrund nach Tageszeit, Wetter und Uhr in der Kopfzeile, Größe je Gerät.

## 0.14.0 – 2026-11-15

### Neu
- **Menüführung:** Start ist das Hauswerk-Dashboard mit Widgets aller Module, Heizwerk ist ein eigenes Modul, zentrale Einstellungen hinter dem Zahnrad.
- Versionen erscheinen in HACS jetzt als richtige Releases.
