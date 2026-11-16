# Änderungen

Neueste Version oben. Der Abschnitt einer Version erscheint automatisch als Release-Text auf GitHub und damit im Update-Dialog von Home Assistant (HACS).

## 0.34.1 – 2026-11-16

### Behoben
- **Widgets hinzufügen schlug fehl** („Ungültiger Wert bei start_widgets…type“): Die neuen Widgets Rollläden, Nächste Fahrten, Heizleistung, Hinweise und Energie wurden beim Speichern der Startseite abgelehnt. Ein Test prüft jetzt, dass jedes Widget des Panels gespeichert werden darf.

## 0.34.0 – 2026-11-16

### Neu
- **Modul Kraftwerk** – Energie im Haus, neben Heizwerk und Rollwerk (eigener Reiter, eigenes Symbol):
  - **Energiefluss live:** Solar, Netz, Batterie und Haus mit animierten Linien – wer wen gerade versorgt, Bezug oder Einspeisung, Laden oder Entladen mit Ladestand, Anteil selbst gedeckt.
  - **Verbraucher jetzt:** z. B. Wärmepumpe, Wallbox, Waschmaschine mit Anteil am Hausverbrauch, Rest als „Sonstiges“.
  - **Heute und Verlauf** (Heute, 7 Tage, 30 Tage, 12 Monate): erzeugt, verbraucht, Netzbezug, eingespeist, Batterie, Eigenverbrauch, Autarkie und Kosten; Balken je Stunde/Tag/Monat.
  - **Nichts doppelt:** Zähler (kWh) und Preise kommen aus dem Energie-Dashboard von Home Assistant. In Kraftwerk werden nur die Leistungs-Sensoren (W/kW) gewählt – **„Automatisch erkennen“** schlägt sie vor.
  - Vorzeichen von Netz und Batterie umkehrbar; Einspeisung auch als eigener Sensor.
- **Widget „Energie“** für die Startseite (klein, mittel, groß mit Energiefluss).
- Kraftwerk im Protokoll (Filter „Kraftwerk“), unter Einstellungen › Module, in der unteren Leiste am Handy und als Hinweis, wenn ein Sensor nicht erreichbar ist.

## 0.33.0 – 2026-11-16

### Neu
Vier neue Widgets für die Startseite (Startseite › Anpassen › „+“), je in klein, mittel und groß:
- **Rollläden:** wie viele offen, zu und beschattet; „Alle hoch“ / „Alle runter“; von Hand verstellte Rollläden mit „Automatik“ zum Zurückgeben. Groß: alle Rollläden mit Stellung und Grund.
- **Nächste Fahrten:** die nächsten Fahrten heute mit Uhrzeit und betroffenen Rollläden, darüber die Tagesleiste. Groß: eine Tagesleiste je Profil.
- **Heizleistung:** Räume mit „Reicht nicht“, „Messung prüfen“ oder „Knapp“ aus dem Bericht (14 Tage). Groß: alle Räume mit Urteil und wichtigstem Hinweis.
- **Hinweise:** der Inhalt der Glocke, jeder Hinweis führt zur passenden Stelle. Steht das Widget auf der Startseite, entfällt der gelbe Hinweis-Streifen darüber.

## 0.32.1 – 2026-11-16

- Heizwerk: Die Statusleiste (heizen, Fenster, Anwesenheit, Außen, Hinweise) über Bericht, Heizplänen und Einstellungen entfällt. Hinweise bleiben über die Glocke oben erreichbar.

## 0.32.0 – 2026-11-16

### Neu
- **Bericht: Heizleistung je Raum.** Für jeden Raum gibt es ein Urteil – **Passt**, **Reserve**, **Knapp**, **Reicht nicht**, **Messung prüfen** oder **Zu wenig Daten**.
  - **Kennzahlen:** Komfort erreicht (Anteil der Komfortzeit höchstens 0,5 °C unter Soll), Ø Abweichung vom Soll, Ø Ventilöffnung und Anteil „ganz auf“, gelernte Aufheizgeschwindigkeit, überheizt sowie kalte gegen milde Tage.
  - **Hinweise mit Ursachen und Tipps:**
    - Heizkörper zu klein / Vorlauf zu niedrig / Luft / hydraulischer Abgleich
    - Thermostat misst zu warm (Raumsensor, Kalibrierung)
    - Heizkurve bei Frost zu flach
    - Reserve für niedrigere Vorlauftemperatur
    - oft überheizt, heizt langsam auf, viel gelüftet
  - Räume mit Handlungsbedarf stehen oben, mit Sprung zu „Raum einstellen“.
- Für die Analyse sammelt Heizwerk ab jetzt zusätzlich je Minute: Komfort erreicht, Abweichung vom Soll, überheizt, Ventil ganz offen und Außentemperatur. Die Einschätzung wird nach einigen Tagen aussagekräftig.

### Behoben
- Lange Raumnamen in der Ventil-Wärmekarte wurden abgeschnitten.

## 0.31.1 – 2026-11-16

### Behoben
- **Rollläden fuhren nach einem Neustart von Home Assistant hoch.** Zwei Ursachen:
  - War ein Rollladen beim Start noch nicht erreichbar (die Integration lädt später), fuhr Rollwerk ihn beim ersten Wert sofort.
  - Wartezeiten wie „Sonne mindestens 30 s unter …“ begannen nach dem Neustart neu – in der Zwischenzeit galt abends „noch Tag“, also offen.
  
  Jetzt übernimmt Rollwerk nach dem Start bei jedem Rollladen zuerst nur den Stand, sobald er erreichbar ist. In den ersten 3 Minuten gelten Wartezeiten sofort. Der Tagesstand (heute schon geöffnet/geschlossen, Stufe 1, Beschattung) übersteht den Neustart. Gefahren wird erst beim nächsten echten Wechsel – oder wie unter „Nach Neustart“ eingestellt.

## 0.31.0 – 2026-11-16

### Neu
- **Sonnenschutz-Empfehlung je Himmelsrichtung:** Sobald die Fensterrichtung gewählt ist, zeigt das Profil eine Empfehlung mit Begründung – Sonnenbereich, Sonnenhöhe von/bis, ab welcher Außentemperatur und auf wie viel % (z. B. West: ab 3° Höhe, ab 20 °C, auf 15 %; Süd: 25–65°, ab 21 °C, auf 25 %; Nord: meist nicht nötig). „Empfehlung übernehmen“ setzt alle Werte; im Satz steht neben abweichenden Werten „empfohlen …“. Bei der ersten Wahl der Richtung und im Assistenten werden die Werte gleich übernommen.
- **Rollwerk im Protokoll:**
  - Jede Fahrt steht unter der neuen Kategorie **„Rollläden“** – mit Grund und vorheriger Stellung.
  - Ebenso: Übersteuerungen von Hand, „Automatik wartet“ und der Sturmschutz.
  - **Profil-Änderungen** stehen mit Vorher → Nachher (z. B. „Beschatten ab außen 22 °C → 24 °C“) und Benutzer.
  - **Rollladen-Änderungen** (Profil, Kontakte, Automatik, Raum) ebenso.
  - Einträge sind dem Heizwerk-Raum des Rollladens zugeordnet.
  - Neuer Filter **Alles · Heizwerk & Haus · Rollwerk**; Rollwerk › Einstellungen › Protokoll öffnet direkt die Rollwerk-Einträge.

## 0.30.1 – 2026-11-16

### Geändert
- **„Verhalten“ heißt wieder „Profil“** – in Einstellungen, Rollladen-Dialog, Assistent und Tagesleiste. Die Auswahl der CCA-Regeln unter Feinheiten heißt jetzt „Regeln im Detail“.
- **Profile löschen:** Jedes Profil lässt sich löschen – auch „Standard“, solange ein anderes bleibt. Der Papierkorb steht unten im Profil-Dialog; vor dem Löschen wählst du, welches Profil die betroffenen Rollläden bekommen.

## 0.30.0 – 2026-11-16

### Neu
- **Abends in zwei Stufen schließen** (Verhalten › Tagesablauf › Abends schließen › „In zwei Stufen“):
  - **Stufe 1** fährt auf eine eigene Stellung (z. B. 50 %), sobald die Sonne eine Himmelsrichtung erreicht (z. B. ab 250° = West), unter eine Höhe sinkt oder zu einer Uhrzeit.
  - **Stufe 2** fährt zur spätesten Zeit (Werktag / vor freiem Tag getrennt) ganz zu. Stufe 2 lässt sich abschalten – dann bleibt der Rollladen nachts auf Stufe 1.
  - Die Tagesleiste zeigt Stufe 1 mit Uhrzeit und Prozent, „Als Nächstes“ nennt sie ebenfalls.
- **Prozent direkt im Tagesablauf:** „Morgens öffnen auf … %“ und „Abends schließen auf … %“ lassen sich jetzt dort mit − / + einstellen (vorher nur unter Feinheiten). Unter Feinheiten stehen alle Stellungen (offen, zu, Stufe 1, Lüften, Beschattung) beisammen.

## 0.29.0 – 2026-11-16

### Neu
- **Rollladen kennt seinen Heizwerk-Raum:** Rollwerk findet den Raum über den Bereich in Home Assistant (Thermostat oder Fensterkontakt im selben Bereich, sonst gleicher Name); im Rollladen-Dialog lässt er sich auch fest wählen oder abschalten.
- **Kontakte aus Heizwerk:** Die Fensterkontakte des Raums gelten automatisch auch für den Rollladen – Türen als „ganz offen“ (nicht herunterfahren), Fenster als „gekippt“ (Lüftungsstellung). Eigene Kontakte am Rollladen sind nur noch nötig, wenn ein Kontakt fürs Heizen keine Rolle spielt; „Keine“ schaltet es ab.
- **Raumtemperatur aus Heizwerk** für den Sonnenschutz („innen wärmer als“), wenn kein eigener Sensor gewählt ist.
- Der Assistent „Rollladen hinzufügen“ übernimmt Kontakte und Raum aus Heizwerk, statt sie neu abzufragen.

## 0.28.0 – 2026-11-16

### Neu
- **Assistent „Rollladen hinzufügen“** (Rollwerk › Rollläden „+“ oder Einstellungen) in sechs Schritten:
  1. **Rollladen:** einen oder mehrere Rollläden wählen, nach Bereichen sortiert.
  2. **Richtung:** am Kompass antippen, wohin das Fenster zeigt.
  3. **Fenster:** Kontakte „ganz offen“ und „gekippt“; Kontakte im selben Bereich werden gefunden und vorausgewählt.
  4. **Raum:** Wohnraum, Schlafzimmer, Kinderzimmer oder Nebenraum; mit der Sonne oder nach Uhrzeit; Sonnenschutz ab °C.
  5. **Verhalten:** ein passendes vorhandenes wird vorgeschlagen, sonst ein neues aus den Antworten.
  6. **Fertig:** Zusammenfassung und hinzufügen.
- **Sonnenschutz in einem Satz:** „Beschatten, wenn die Sonne aufs Fenster nach Süd scheint, mindestens 25° hoch steht und es draußen wärmer als 24 °C ist. Der Rollladen fährt dann auf 25 % …“ – die Werte im Satz lassen sich direkt mit − und + ändern.

## 0.27.0 – 2026-11-16

### Neu
- **Rollwerk einfacher:** Ein „Profil“ heißt jetzt **Verhalten** und hat nur noch fünf Abschnitte:
  - **Tagesablauf:** nach Uhrzeit oder mit der Sonne
  - **Sonnenschutz**
  - **Fenster & Lüften**
  - **Ausnahmen**
  - **Feinheiten**
  
  Zu sehen sind zuerst nur die wichtigen Einstellungen. Alles Weitere wie bei der Cover Control Automation (und/oder-Bedingungen, Helligkeit, Wartezeiten, Erzwingen, Verhalten im Detail) erscheint mit **Experte**.
- **Kompass:** Beim Sonnenschutz tippst du an, wohin das Fenster zeigt. Der Bereich, in dem die Sonne zählt, und die Sonne jetzt sind eingezeichnet.
- **Tagesleiste:** Für jedes Verhalten und an jedem Rollladen zeigt eine Leiste, wann heute geöffnet wird, wann Beschattung möglich ist und wann geschlossen wird. Dazu steht „Als Nächstes: …“ am Rollladen.
- **Anwesenheit und Urlaub aus Hauswerk:** Je Verhalten wählbar, was passiert, wenn niemand zu Hause ist (wie immer, tagsüber zu, beschattet). Im Urlaub lassen sich die Zeiten zufällig verschieben. Eigene Sensoren dafür braucht Rollwerk nicht.
- **Böen-Sensor unter Hauswerk › Wetter:** gilt für alle Module. Ein in Rollwerk gewählter Sensor wird übernommen.

### Geändert
- Die Einstellungsliste von Rollwerk zeigt je Verhalten eine Zeile statt zwölf; Feiertage, Sonnenstand, Wetter und Sturmgrenze kommen nur noch aus Hauswerk.

### Behoben
- **Raumnamen abgeschnitten:** Auf den Raumkacheln (kompakt und detailliert) stehen lange Namen jetzt vollständig, bei Bedarf in zwei Zeilen; die Symbole stehen darunter.

## 0.26.0 – 2026-11-16

### Neu
- **Assistent „Raum anlegen“** in Heizwerk, in sechs Schritten:
  1. **Raum:** Bereich aus Home Assistant wählen; der Name wird übernommen. Bereiche, die schon angelegt sind, erscheinen ausgegraut.
  2. **Nutzung:** Wohnzimmer, Schlafzimmer, Kinderzimmer, Bad, Küche, Büro oder Flur. Daraus kommen Vorschläge für Komfort/Eco und Heizzeiten; am Raumnamen wird die Nutzung vorausgewählt.
  3. **Heizung:** Heizkörper, Fußbodenheizung oder beides (Mischbetrieb).
  4. **Geräte:** Thermostate, Fenster-/Türkontakte, Temperatur- und Feuchtesensor sowie der Schalter der Fußbodenheizung werden im Bereich gefunden und vorausgewählt; andere lassen sich hinzufügen. Im Mischbetrieb wird je Heizkörper „Zusatz“ oder „folgt Wand“ gewählt.
  5. **Zeiten:** Komfort und Eco; dazu ein gemeinsamer Heizplan oder eine Vorlage.
  6. **Fertig:** Zusammenfassung, wahlweise danach alle Einstellungen des Raums öffnen.
- „Ohne Assistent“ öffnet wie bisher den vollständigen Raum-Dialog.

## 0.25.1 – 2026-11-16

### Geändert
- **Geräte wählen:** Nach einem Tipp auf „Passt“ bzw. „Wählen“ schließt sich die Auswahl sofort – auch dort, wo mehrere Geräte möglich sind. Mit „Weitere hinzufügen“ öffnet sie sich wieder.

## 0.25.0 – 2026-11-16

### Neu
- **Rollwerk-Profile nach dem Vorbild der Cover Control Automation (CCA):** Einstellungen stehen jetzt in Profilen, die du Rollläden zuordnest. Abschnitte: Funktionen, Positionen, Zeiten (früh/spät, Werktag/frei, Arbeitstag morgen, Kalender), Helligkeit, Sonnenhöhe, Lüften, Beschattung (Bedingungen mit und/oder aus Richtung, Höhe, Helligkeit, Temperatur innen/außen, Vorhersage, Wetterlage, eigenem Schalter; Wartezeiten), Bewohner, Von Hand (Übersteuerung halten und zurücksetzen), Verzögerung, Erzwingen und Verhalten.
- **Je Rollladen zwei Kontakte:** „ganz offen“ (Aussperrschutz) und „gekippt“ (Lüftungsstellung).
- **„Automatik übernimmt“** auf der Rollläden-Seite beendet eine Übersteuerung von Hand.
- **Nach Neustart:** wahlweise verpasste Wechsel nachholen.

### Geändert
- Die bisherigen Einstellungen (Öffnen, Schließen, Sonnenschutz, Fassade, Tür) werden beim ersten Start in Profile übernommen – je Fassade eins mit passender Himmelsrichtung.
- Der Urlaubs-Zufall entfällt; dafür gibt es je Profil eine zufällige Verzögerung.

## 0.24.1 – 2026-11-16

### Neu
- **Eigene Symbole für Heizwerk und Rollwerk:** gleiche Hausform wie das Hauswerk-Logo – Heizwerk in Orange mit Heizkörper, Rollwerk in Blau mit Rollladen. Sie stehen in den Modul-Reitern, in der unteren Leiste am Handy und unter *Einstellungen › Module*. Das Hauswerk-Logo bleibt unverändert.

## 0.24.0 – 2026-11-16

### Neu
- **Modul Rollwerk:** Rollläden morgens auf (Sonnenaufgang mit „frühestens“ für Werktag und Wochenende, oder feste Uhrzeit), abends zu (Sonnenuntergang mit „spätestens“, oder feste Uhrzeit), **Sonnenschutz** nach Fassade, Sonnenstand und Außentemperatur, **Sturmschutz** (hoch ab der Sturmgrenze aus Hauswerk › Wetter) und **Aussperrschutz** (bei offener Tür nicht herunterfahren). Von Hand verstellte Rollläden bleiben bis zum nächsten Wechsel so. Eigene Seite mit allen Rollläden nach Räumen, ↑ ■ ↓, Schieberegler und „Alle hoch/runter“; Einstellungen je Rollladen (Fassade, Nachtstellung, Tür, Automatik). Im Urlaub auf Wunsch zufällige Zeiten.
- **Heizkörper bleibt kalt:** Steht ein Ventil eine Stunde lang auf 90 % oder mehr und der Raum wird nicht wärmer, erscheint ein Hinweis (Luft im Heizkörper, Ventilstift, Heizung?) und auf Wunsch eine Nachricht. Bei mehreren Räumen gleichzeitig: Hinweis, die Heizung zu prüfen.
- **Wärmeanforderung:** Heizwerk kann den Wärmeerzeuger (z. B. die Zone der Vaillant-Anlage) absenken oder ausschalten, wenn kein Raum Wärme braucht, und beim Vorheizen anheben. Sobald ein Raum Wärme braucht, kommt der alte Wert sofort zurück. Standardmäßig aus – unter *Heizwerk › Einstellungen › Wärmeanforderung* einschalten.
- **Ventilverlauf im Bericht:** Ø Ventilöffnung je Raum und Stunde als Wärmekarte – zeigt, welche Räume viel Wärme brauchen und ob Komfortzeiten zu früh oder zu spät beginnen.
- **Diagnose herunterladen:** unter *Geräte & Dienste › Hauswerk › ⋮* – Einstellungen, Zustände aller beteiligten Geräte und das Protokoll als Datei, zur Fehlersuche.

### Geändert
- Die Ventilöffnung liest jetzt auch Hauswerk selbst (nicht nur das Panel) – aus dem Thermostat, aus %-Sensoren am selben Gerät und aus den Anzeige-Geräten (Fußbodenheizung an = 100 %).

## 0.23.3 – 2026-11-16

### Neu
- **Thermostate anderer Hersteller erkennen:** Wandthermostat oder Heizkörper-Thermostat erkennt Hauswerk jetzt auch bei Bosch (Smart Home, Zigbee BTH-RA/BTH-RM, EasyControl), tado, Netatmo, Danfoss Ally, Aqara, AVM FRITZ!DECT, Honeywell evohome, Drayton Wiser, Eurotronic, Eve, Sonoff, Hive, Shelly, Viessmann, Homematic (klassisch) u. a. – am Modell aus dem Geräte-Register, sonst am Namen. Das gilt für die Überschriften, die Rollen und die Kopplung.
- **Ventilöffnung weiterer Hersteller:** auch Bosch „Ventilstößel“, tado „Heizleistung“ und Netatmo „heating_power_request“ werden als Ventilöffnung bzw. Heizleistung angezeigt.

## 0.23.2 – 2026-11-16

### Geändert
- **Geräte mit Art als Überschrift:** Gewählte Geräte, die Rollen der Thermostate und die Geräteliste der Raumseite zeigen jetzt oben die Art des Geräts (z. B. Wandthermostat, Heizkörper-Thermostat, Fußbodenheizung, Fensterkontakt, Temperatursensor, Ventilöffnung) und darunter den Namen der Entität mit Zustand. Die Art erkennt Hauswerk am Gerätemodell, an der Geräteklasse oder am Namen.

## 0.23.1 – 2026-11-16

### Geändert
- **Rolle der Thermostate:** Kopplung und Mischbetrieb unter *Raum › Geräte* sind zu einer übersichtlichen Liste zusammengefasst. Jedes Thermostat steht mit Art, Zustand und Ventilöffnung da; das Wandthermostat „stellt ein“, jeder Heizkörper bekommt per Tipp eine Rolle: **Folgt Wand** (Heizgruppe der CCU), **Selbst** (Hauswerk stellt ihn auf das Raum-Soll) oder **Zusatz** (Mischbetrieb). Die Erklärung steht aufklappbar unter „Was bedeuten die Rollen?“. Die Rolle „Selbst“ gibt es jetzt je Heizkörper statt nur für den ganzen Raum.

## 0.23.0 – 2026-11-16

### Neu
- **Mischbetrieb – Heizkörper als Zusatzheizung:** Für Räume mit Fußbodenheizung und Heizkörper. Unter *Raum › Geräte* einzelne Heizkörper-Thermostate als Zusatzheizung wählen. Die Fußbodenheizung über das Wandthermostat trägt die Grundlast; die gewählten Heizkörper bleiben zu (Frostschutz) und heizen nur mit, wenn der Raum zu weit unter Soll liegt (Standard 0,5 °C), beim Vorheizen und beim Boost – bis das Soll fast erreicht ist. Ihr Messfehler am Heizkörper wird mit der Temperatur des Wandthermostats ausgeglichen. Heizkörper, die nicht gewählt sind, bleiben in der Heizgruppe und folgen weiter dem Wandthermostat. An Kachel, Schnellmenü und Raumseite zeigt ein Heizkörper-Symbol, wenn er nachhilft; Wechsel stehen im Protokoll.

### Geändert
- **Raumtemperatur ohne Raumsensor:** Sind im Raum Wandthermostat und Heizkörper-Thermostate eingetragen, zählt nur noch der Messwert des Wandthermostats (Heizkörper-Thermostate messen am Heizkörper zu warm).

## 0.22.1 – 2026-11-16

### Behoben
- **Kacheln unten abgeschnitten (Handy):** Die untere Navigationsleiste verdeckte das Ende der letzten Kachel bzw. des letzten Widgets – auch ganz nach unten gescrollt. Die Seite lässt unten jetzt genug Platz.

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
