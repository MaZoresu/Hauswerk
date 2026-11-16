# Änderungen

Neueste Version oben. Der Abschnitt einer Version erscheint automatisch als Release-Text auf GitHub und damit im Update-Dialog von Home Assistant (HACS).

## 0.22.0 – 2026-11-16

### Neu
- **Zweite Regelung erkennen:** Nennt eine andere Integration (z. B. ein anderes Heizungs- oder Raumklima-Programm, Better Thermostat) eines deiner Thermostate, oder stellen Automationen, Skripte oder Integrationen es wiederholt um (3-mal in 2 Stunden), erscheint unter der Glocke „Zweite Regelung stellt dasselbe Thermostat“ – mit Namen der Automation bzw. Integration. Solche Änderungen stehen im Protokoll als „von …“ statt „am Thermostat gedreht“.
- **Wandthermostat und Heizkörper gekoppelt:** Sind in einem Raum ein Wandthermostat und Heizkörper-Thermostate eingetragen (z. B. Homematic IP HmIP-WTH und HmIP-eTRV), stellt Hauswerk nur noch das Wandthermostat – es gibt den Wert in der CCU selbst an die Heizkörper weiter. Hauswerk prüft das laufend: weicht ein Heizkörper länger als 15 Minuten ab, stellt es ihn wieder selbst und meldet das. Abschaltbar je Raum unter *Geräte*.
- **Funk-Auslastung (Duty Cycle):** Hauswerk liest die Duty-Cycle-Sensoren der Homematic-CCU, des Access Points bzw. Routers. Ab 70 % (einstellbar) sendet es nur noch Wechsel der Betriebsart und Änderungen ab 1 °C, höchstens alle 15 Minuten je Thermostat, und lässt Ventil- und Kalibrier-Befehle weg. Meldet ein Gerät „Duty Cycle erreicht“, bekommt es solange keine Befehle. Neu unter *Hauswerk › Einstellungen › Funk-Auslastung* mit Befehlen pro Stunde.

## 0.21.1 – 2026-11-16

### Behoben
- **Ventilöffnung wurde nicht angezeigt** bei Thermostaten, die sie als eigenen Sensor melden (z. B. Homematic IP „Ventilöffnungsgrad“, Zigbee „pi_heating_demand“). Hauswerk sucht diesen %-Sensor jetzt automatisch am selben Gerät wie das Thermostat – an der Raumkachel, im Schnellmenü und auf der Raumseite.

## 0.21.0 – 2026-11-16

### Neu
- **Schnellmenü per Tipp auf die Raumkachel:** Ein Tipp auf eine Kachel (detailliert oder kompakt) öffnet ein Menü für manuelle Änderungen – Wunschtemperatur mit ± oder Komfort/Eco, Dauer (bis zum nächsten Planwechsel, 1, 2, 4 oder 8 Stunden), Boost, zurück zum Plan sowie Sprung zu Raumseite, Heizplan und Automatik. Oben stehen Betriebsart, Ist- und Sollwert, Luftfeuchte, Ventilöffnung und Fußbodenheizung auf einen Blick. Manuelle Änderungen dürfen alle Benutzer.

### Geändert
- Die Raumkacheln zeigen nicht mehr „Heizkörper“ oder „Flächenheizung“.
- Die **Fußbodenheizung** erscheint nur noch als Symbol, solange sie heizt; Name und Zustand stehen im Quickinfo. Die **Ventilöffnung** steht weiter mit % an der Kachel.

## 0.20.3 – 2026-11-16

### Behoben
- **Heizpläne am Handy:** Beim Einstellen einer Uhrzeit sprang die Seite heraus und der Uhrzeit-Wähler schloss sich. Jetzt bleibt er offen; Vorschau, Dauer und Speicherleiste passen sich trotzdem sofort an.
- **Speichern verdeckt:** Die Speicherleiste von Heizplänen und Einstellungen liegt am Handy jetzt über der unteren Navigationsleiste. Dialoge nutzen die tatsächlich sichtbare Bildschirmhöhe, damit „Speichern“ in der App nicht unter den Leisten verschwindet.

## 0.20.2 – 2026-11-16

### Neu
- **Fußbodenheizung als Schalter:** Unter *Raum › Geräte › Weitere Geräte – nur anzeigen* lassen sich jetzt auch Schalter wählen (`switch.*`, `input_boolean.*`), z. B. der Heizkreis oder Stellantrieb einer Fußbodenheizung.
- **Symbole für Ventil und Fußbodenheizung** an der Raumkarte und der kompakten Kachel: Ventil mit Öffnung in %, Fußbodenheizung mit an/aus (orange, solange sie heizt). Auf der Raumseite stehen beide mit ihren Werten in der Geräteliste.

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
