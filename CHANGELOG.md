# Änderungen

Neueste Version oben. Der Abschnitt einer Version erscheint automatisch als Release-Text auf GitHub und damit im Update-Dialog von Home Assistant (HACS).

## 0.57.0 – 2026-11-20

### Neu (Rollwerk-Kacheln)
- **Öffnet / Schließt (und Stufe 1) je Rollladen mit Uhrzeit**, z. B. „Schließt 16:42 Uhr“. Berechnet aus dem Standort und der Zeitzone von Home Assistant und dem Sonnenstand des Tages – auf die Minute genau (Sonnenbahn mit Halbierungssuche statt 10-Minuten-Raster). Es gilt dieselbe Entscheidung wie in der Steuerung:
  - eingestellte Sonnenhöhe: Öffnen bei **aufsteigender**, Schließen bei **absteigender** Sonne, inklusive „Sonnenhöhe Dauer“,
  - Zeitfenster früheste/späteste Zeit (Werktag/frei – auch für morgen über den Arbeitstage-Kalender), zwei Stufen, ohne Zeitsteuerung nur die Sonne,
  - Sperren: Automatik aus, Pause-Schalter, Sturm, Erzwingen; heute zusätzlich „niemand zu Hause – bleibt zu“ und „Bewohner schläft“.
- Ist die Fahrt heute schon passiert oder die Zeit vorbei, steht der Zeitpunkt von morgen da („Öffnet morgen“). Hängt der Zeitpunkt (auch) von der Helligkeit ab oder ist er nicht berechenbar (z. B. Sonne erreicht die Höhe nie, Kalender-Zeiten für morgen), steht „–“ statt einer erfundenen Uhrzeit. Neu berechnet bei Tageswechsel und jeder Profil-Änderung. Tagesleiste und „Als Nächstes“ nutzen dieselben Zeiten.

### Geändert
- **„Beschattung ab …“ nur bei passender Außentemperatur:** erscheint nur, wenn die Temperaturbedingung des Profils (Außentemperatur bzw. Vorhersage, mit Abstand/Hysterese bei laufender Beschattung) gerade erfüllt ist; ohne gültigen Messwert nie. Das abendliche Schließen hängt davon nicht ab.

## 0.56.1 – 2026-11-20

### Behoben
- Korrektur-Knöpfe der Fertigerkennung („Gesehen“, „Läuft noch“ …) hätten in Home Assistant einen Fehler gemeldet (Feldname kollidierte mit der Nachrichtennummer).
- „Aus dem Verlauf lernen“: Recorder als Abhängigkeit eingetragen (hassfest).

## 0.56.0 – 2026-11-20

### Neu – Kraftwerk: lernende Fertigerkennung
- **Kraftwerk › Geräte:** Waschmaschine, Trockner, Geschirrspüler oder ein anderes Gerät melden, wenn sie fertig sind – erkannt am Stromverbrauch einer Mess-Steckdose, direkt in Home Assistant (das Dashboard muss nicht offen sein).
- **Einrichtung je Gerät:** Name, Gerätetyp, Leistungssensor (W, kW oder mW; passende Steckdosen werden vorgeschlagen), optional Türkontakt und ein Status-Sensor des Geräts (z. B. „fertig“), Kanäle für die Meldung (Apps, Mitteilung in Home Assistant, „Wichtig“).
- **Zustände:** Lernphase · Bereit · Läuft (mit Restzeit aus den gelernten Durchläufen) · Ende wird geprüft (mit „x von y Min. Ruhe“) · Fertig. Dazu Zeile in der Kopfkachel, Hinweis unter der Glocke und im Bildschirmschoner.
- **Lernen aus beobachteten Durchläufen, je Gerät getrennt und dauerhaft gespeichert:** typische Dauer, alle Ruhephasen mitten im Programm (Einweichen, Pumpenpausen), Leistung „aktiv“ gegenüber Ruhe/Anzeige, Nachlauf (Knitterschutz-Spitzen, Anzeige, Standby) und Messabstand. Die Wartezeit bis „fertig“ richtet sich nach der längsten gelernten Pause; deutlich vor der üblichen Dauer wird länger geprüft. Unter „Was Kraftwerk gelernt hat“ steht alles nachvollziehbar mit den letzten Durchläufen.
- **Korrektur:** „Läuft noch“ (die Ruhe war eine Pause – künftig länger prüfen), „Ist schon fertig“ (so viel Ruhe reicht – künftig kürzer), „Kein Durchlauf“ (höhere Mindestenergie), „Gesehen“. Dazu „Aus dem Verlauf lernen“ (spielt die letzten 10 Tage nach, ohne Meldungen) und „Neu lernen“.
- **Fertigmeldung:** je Durchlauf und Kanal höchstens einmal – vor dem Senden gespeichert, damit Neustarts, Neuladen oder Verbindungsabbrüche keine Doppel auslösen. Fehlende Messwerte (nicht erreichbar, Neustart) zählen weder als Ruhe noch als Ende. Kurze Spitzen im Nachlauf starten keinen neuen Durchlauf.

## 0.55.1 – 2026-11-20

### Geändert (Rollwerk-Kacheln)
- **„Sonne aufs Fenster“ nur, wenn die Sonne wirklich scheint:** Neben der Richtung zählt jetzt der Helligkeitssensor des Profils (ab der Grenze „Beschattung endet“) bzw. ohne Sensor die Wetterlage (sonnig oder teils bewölkt).
- Fenster erscheinen in der Info-Zeile nur noch, wenn sie offen bzw. gekippt sind („Fenster zu“ entfällt).
- Die Tagesleiste in den Kacheln ist dicker.

## 0.55.0 – 2026-11-18

### Neu – Lüften in Heizwerk
- **Seite „Lüften“** (Heizwerk › Lüften): je Raum Empfehlung oder laufende Lüftung, Luftfeuchte mit Grenze, Schimmel-Ampel, CO₂, zuletzt gelüftet und die Bilanz der letzten 7 Tage. Oben der Richtwert fürs Stoßlüften bei der aktuellen Außentemperatur.
- **Lüftdauer nach Wetter:** „Jetzt 10 Min. stoßlüften“ – unter 0 °C 5 Min., bis 10 °C 10 Min., bis 15 °C 15 Min., darüber 25 Min.
- **Lüft-Timer mit Ende:** Bei offenem Fenster zeigt die Raumkachel einen Countdown („4/10 Min.“). Ist genug gelüftet – Zeit um, Feuchte deutlich gesunken oder Raum 3 °C kühler –, kommt **„Fenster schließen“** unter der Glocke, groß im Bildschirmschoner und auf Wunsch aufs Handy (Standard: an).
- **Schimmel-Ampel:** schätzt die Feuchte an der kühlsten Stelle der Außenwand (Temperaturfaktor 0,7 nach DIN 4108-2) – ab 70 % gelb, ab 80 % rot mit Hinweis.
- **Anlässe:** feucht, Schimmelgefahr, Feuchte steigt schnell (Duschen, Kochen), CO₂ über der Grenze (Räume mit CO₂-Sensor, Standard 1000 ppm), **morgens lüften** in Schlaf- und Kinderzimmern (Uhrzeit wählbar, Standard aus).
- **Dauerkippen erkennen:** In der Heizzeit nach 30 Min. offen: „Kippen kostet Wärme“ mit geschätztem Wärmeverlust in kWh.
- **Sommer: kühlen** – in der Sommerpause „Fenster auf“, wenn es draußen mindestens 2 °C kühler ist (ab 23 °C drinnen), und „Fenster schließen“, sobald es draußen wärmer ist.
- **Grenzen je Raumart:** Bad 70 %, Schlaf- und Kinderzimmer 60 %, sonst der allgemeine Wert – je Raum änderbar (Raum › Geräte › Lüften: Raumart, Grenze, morgens lüften, CO₂-Sensor). Der Raum-Assistent merkt sich die Raumart.
- **Anzeige:** Symbol mit Dauer bzw. Countdown in der Raumkachel (detailliert und kompakt), Zeile in der Kopfkachel, **Bericht › Lüften · 7 Tage** (wie oft, wie lange, Feuchte-Rückgang, Wärme), neues **Widget „Lüften“**.
- Nachrichten „Lüften empfohlen“ (Standard aus) und „Fenster schließen“ unter Benachrichtigungen bzw. Lüften & Schimmelschutz.

## 0.54.1 – 2026-11-18

### Behoben
- **„Hell“ blieb dunkel** (bzw. „Dunkel“ hell), wenn Home Assistant auf dem Gerät anders eingestellt ist – z. B. ein Tablet im Dunkelmodus. Hauswerk nahm die Farben von Home Assistant. Weicht die Wahl unter Darstellung bzw. Tabletmodus von Home Assistant ab, gelten jetzt Hauswerks eigene helle bzw. dunkle Farben.

## 0.54.0 – 2026-11-18

### Neu (Rollwerk-Kacheln)
- **Fenster-Grafik mit Ziel:** Die Kachel zeigt die Stellung als kleines Fenster; weicht die Automatik ab (z. B. von Hand verstellt), markiert eine gestrichelte Linie, wohin sie fahren würde.
- **Info-Zeile**, wichtigstes zuerst:
  - Gerät – nur wenn auffällig: Batterie schwach, Funk schwach,
  - Fenster und Raum aus Heizwerk: „gekippt seit 12 Min. · 20,2 °C“, „Fenster zu · 21,4 °C“,
  - Sonne: „Sonne aufs Fenster“ (Fensterrichtung des Profils) bzw. „Beschattung ab 14:20“,
  - letzte Fahrt mit Grund: „07:15 ↑ · Morgens öffnen“, „09:40 → 40 % · von Hand“ (übersteht Neustarts),
  - Lamellen bei Raffstores,
  - Profil.
- **Tabletmodus:** Die Info-Zeile steht in der Zeile der Knöpfe statt „Behanghöhe“ – die Kacheln bleiben gleich groß; was nicht passt, blendet aus.
- **Kompakte Kachel:** zusätzlich die nächste Fahrt („16:50 ↓“) in derselben Zeile.

### Behoben
- Über Rollladen-Kacheln stand teils eine Zahl („1“, „2“) statt nichts.
- **„Hauswerk als Startseite“ ließ sich nicht anhaken** – der Haken war nur Anzeige. Jetzt setzt ein Tipp Hauswerk als Startseite für dich (alle deine Geräte), ein weiterer hebt es auf.

## 0.53.0 – 2026-11-18

### Neu
- **Hauswerk als Dashboard** – wie andere Integrationen (z. B. Raumklima) mit einem kurzen Code: In einem Dashboard im Rohkonfigurations-Editor
  ```yaml
  strategy:
    type: custom:hauswerk
  ```
  eintragen – dann zeigt das Dashboard Hauswerk ganzseitig. So steht Hauswerk unter Einstellungen › Dashboards in der Liste und lässt sich dort wie jedes Dashboard **als Standard festlegen** oder im Profil wählen.
- **„Hauswerk-Dashboard anlegen“** unter Darstellung › Startseite von Home Assistant erledigt das mit einem Tipp (Admin).
- Zusätzlich gibt es die Karte `custom:hauswerk-card` für eigene Dashboards (am besten in einer Ansicht vom Typ „Panel“).

## 0.52.1 – 2026-11-18

### Geändert
- **Bildschirmschoner:** Hinweise (z. B. „Fenster offen – es regnet“) und Termine in kleinerer Schrift. Termine zeigen ihr Symbol (Müll je Abfallart in eigener Farbe).
- Heißen Fensterkontakt und Raum gleich, steht der Name nur einmal da (statt „Großes Bad · Großes Bad“).

## 0.52.0 – 2026-11-18

### Neu
- **Hauswerk als Startseite von Home Assistant** (Darstellung › Startseite von Home Assistant): Home Assistant bietet beim Standard-Dashboard nur eigene Dashboards an, Hauswerk ist ein eigenes Panel. Jetzt lässt es sich trotzdem festlegen – **für mich** (alle meine Geräte), **für alle Benutzer** (Admin) oder **nur dieses Gerät**. Nochmal tippen hebt es auf.
- **Müllabholung** als eigener Bereich unter Hauswerk › Kalender:
  - eigene Abfuhr-Kalender (z. B. Waste Collection Schedule) – werden beim Update erkannt und aus den Terminen genommen,
  - **Erinnerung am Vorabend** ab 17, 18, 19 oder 20 Uhr: „Morgen Müllabfuhr: Restabfall“ unter der Glocke und groß im Bildschirmschoner, bis zur Abholung am Vormittag,
  - **Nachricht aufs Handy** am Vorabend (Aus · Protokoll · Normal · Wichtig), einmal je Abholtag,
  - **Abfallarten ab- und anwählen** (z. B. Sperrmüll nur auf Anmeldung),
  - die nächsten Abholungen mit Symbol und Farbe je Abfallart.
- **Standard-Kalender** (z. B. Familie) unter Termine: steht in Bildschirmschoner und Widgets zuerst; darunter weitere Kalender.

## 0.51.0 – 2026-11-18

### Neu
- **Kalender zentral** unter Hauswerk › Einstellungen › **Kalender** – für alle Module:
  - **Arbeitstage-Kalender** der Integration „Arbeitstag“ (Workday): Jeder Arbeitstag ist dort ein Termin. Fehlt er an einem Werktag (Feiertag, Brückentag), gelten die Zeiten von Samstag bzw. Sonntag. Anders als der Sensor kennt der Kalender auch die **nächsten Tage**. Ist bisher nur der Arbeitstag-Sensor gewählt, übernimmt Hauswerk den Kalender derselben Integration automatisch (steht im Protokoll). Das Fenster zeigt die freien Werktage der nächsten zwei Wochen.
  - **Urlaub**: Verweis auf die Urlaub-Einstellungen (Zeitraum oder Kalender).
  - **Termine** (z. B. Müllabfuhr, Familie): für den Bildschirmschoner und die Widgets „Termine“ und „Nächste Ereignisse“. Die bisherigen Bildschirmschoner-Kalender werden übernommen.
- **Heizwerk** richtet sich nach dem Arbeitstage-Kalender: an freien Werktagen Heizpläne wie am Wochenende. Auch die Vorschau („Komfort ab morgen 09:00“), der Tagesplan-Streifen und die Kopfkachel wissen vorher Bescheid; am freien Tag steht „heute frei, wie Sonntag“ am Plan.
- **Rollwerk** nimmt ihn fürs Öffnen (heute frei?) und abends fürs Schließen (morgen frei?) – ohne eigenen Sensor „Arbeitstag morgen“ im Profil. Ein eigener Sensor im Profil hat weiter Vorrang.

### Geändert
- Feiertage stehen nicht mehr unter Anwesenheit, sondern unter Kalender. Der Arbeitstag-Sensor bleibt als Ersatz, wenn kein Kalender gewählt oder er nicht lesbar ist.

## 0.50.1 – 2026-11-18

### Verbessert
- **Kopfkacheln im Modulthema** – Heizwerk orange, Rollwerk blau, Kraftwerk gelb wie die Modul-Logos: zarter Farbverlauf, Beschriftung, große Zahl und Werte in der Modulfarbe; der farbige Rand links zeigt weiter den Zustand. In Hell, Dunkel und im Tabletmodus.

## 0.50.0 – 2026-11-18

### Behoben
- **Tabletmodus erkennt Hell/Dunkel** – „Wie Home Assistant“ fragt das Gerät nach dem Dunkelmodus, und das meldet Fully meist nicht. Im Tabletmodus folgt Hell/Dunkel jetzt standardmäßig dem **Sonnenstand** (sun.sun: dunkel nach Sonnenuntergang, hell nach Sonnenaufgang); umstellbar je Tablet unter Darstellung › Tabletmodus (Nach Sonnenstand / Wie Darstellung / Hell / Dunkel).

### Neu
- Design **„Nach Sonnenstand“** auch für PC und Handy (Darstellung › Design).

## 0.49.1 – 2026-11-18

### Geändert
- **Kopfkacheln überall gleich groß** – auch in der normalen Ansicht (PC und Handy) haben Heizwerk, Rollwerk und Kraftwerk denselben Aufbau und dieselbe Höhe: oben Beschriftung und rechts kompakt Wetter, ↑/↓ „Alle“ bzw. „live“; darunter eine große Zahl (Ø-Temperatur, offene Rollläden, Hausverbrauch) mit dem Satz zum Stand; zwei Hinweiszeilen; eine Zeile mit Werten.

## 0.49.0 – 2026-11-18

### Verbessert
- **Panel lädt schneller:** Home Assistant liefert das Panel jetzt komprimiert aus (≈ 180 statt 715 KB) und der Browser behält es bis zum nächsten Update im Zwischenspeicher – besonders spürbar auf dem Tablet.
- **Nur ändern, was sich ändert:** Neue Werte (Temperaturen, Stellungen, Leistungen …) ändern nur die betroffenen Zahlen und Symbole, statt die ganze Seite neu aufzubauen. Bleibt alles gleich, passiert gar nichts. Weniger Ruckeln auf langsamen Tablets; Scrollstand, geöffnete Bereiche und Eingaben bleiben erhalten.
- **Umbenannte Entitäten werden übernommen:** Wird in Home Assistant die ID eines Thermostats, Sensors, Rollladens o. Ä. geändert, ersetzt Hauswerk sie überall – Räume, Heizpläne, Rollläden und Profile, Kraftwerk, Anwesenheit, Widgets – und lädt sich kurz neu. Im Protokoll steht „Entität umbenannt – übernommen“.
- **Sommerpause nach Tagesmittel:** Bei Saison „Nach Außentemperatur“ entscheidet jetzt standardmäßig das Mittel der letzten 24 Stunden (wählbar: Temperatur jetzt · Tagesmittel · Mittel 3 Tage). Einzelne warme Nachmittage oder kalte Morgen kippen die Saison nicht mehr – damit wird auch das Entkalken im Sommer verlässlich. Die Werte überstehen Neustarts; bis genug gesammelt sind (ca. 6 Stunden), gilt die Temperatur jetzt.

### Sicherheit
- **Einstellungen auch im Backend geschützt, Bedienen für alle:** Anwesenheit, Urlaub, Gäste, Party und Eco darf jetzt jeder angemeldete Benutzer schalten – alle anderen Einstellungen prüft der Server weiterhin auf Admin bzw. die Freigabe „Alle Benutzer dürfen ändern“. Damit ist ein eigener Tablet-Benutzer ohne Admin-Rechte sinnvoll: Er kann bedienen, aber nichts einstellen – auch nicht an Hauswerk vorbei. Unter Darstellung › Tabletmodus steht, ob das Tablet so angemeldet ist.

## 0.48.0 – 2026-11-18

### Neue Widgets
- **Lage:** der Stand jedes Moduls in einem Satz (wie die Kopfkacheln) mit Farbe für den Zustand und dem wichtigsten Hinweis – Tipp öffnet das Modul.
- **Nächste Ereignisse:** eine Zeitleiste aus Heizwechseln („08:00 Eco – Bad“), Rollladen-Fahrten („16:30 Rollläden: schließt – Küche …“) und Terminen.
- **Termine:** heute und morgen (groß: 7 Tage) aus gewählten Kalendern, Müll-Termine mit eigenem Symbol und Farbe (Rest, Bio, Papier, Gelb, Glas, Sperrmüll).
  Kalender je Widget wählbar; leer = die Kalender aus Darstellung › Tabletmodus.

### Verbessert
- **Werte und Shortcuts leer:** Vorschläge (z. B. Außentemperatur, Strom, Solar, Luftfeuchte bzw. Szenen und Skripte) mit „Übernehmen“, daneben „Selbst wählen“.
- **Rollläden:** statt drei Zahlenfeldern je Raum kleine Fenster mit Stellung (Rand farbig bei Beschattung, von Hand, Tür offen) und die nächste Fahrt; Tipp auf ein Fenster öffnet „Höhe einstellen“.
- **Heizwerk:** zeigt den Stand-Satz der Kopfkachel und den nächsten Wechsel statt eines eigenen Kurzurteils.
- **Energie (mittel):** Mini-Fluss Solar → Haus → Netz mit Pfeilen, darunter Akku und Tageswerte.
- **Wetter:** Regen-Hinweis aus der Stunden-Vorhersage, z. B. „ab 14 Uhr Regen“ bzw. „Regen bis etwa 16 Uhr“.
- Leere Widgets zeigen „Einrichten“ statt nur eines Hinweises.

## 0.47.1 – 2026-11-18

### Geändert
- **Widget Anwesenheit kompakter** (mittel und groß): Zu Hause · Abwesend · Urlaub und Gäste · Party · Eco stehen als kleine Symbol-Knöpfe in einer Zeile (am Handy in zwei), der Stand in einer Zeile (ganzer Text beim Antippen bzw. Darüberfahren), die Personen als Chips mit Bild, Name und „zu Hause“ bzw. Entfernung nebeneinander.

## 0.47.0 – 2026-11-18

### Geändert (Tabletmodus)
- **Kopfleisten schmal und überall gleich hoch** – so schmal wie die von Kraftwerk, unabhängig von der Seitengröße gleich groß beschriftet: Stand in einer Zeile, darunter bis zu zwei kurze Hinweise.
- **Kacheln in einem festen Raster mit 2 Reihen je Seite.** Räume (Heizwerk) und Rollläden (Rollwerk, detailliert) haben dieselbe Spaltenzahl und dieselben Proportionen; weitere Kacheln stehen auf Seite 2. Rollläden stehen dafür in einem gemeinsamen Raster, der Raum steht klein über dem Namen.

## 0.46.4 – 2026-11-18

### Geändert
- **Bildschirmschoner:** Die Zeile mit den Modulen (Logos, Symbole, Zahlen) ist kleiner, und die Hinweise darunter haben mehr Abstand.

## 0.46.3 – 2026-11-18

### Neu
- **Rollwerk: Detailliert / Kompakt** wie bei den Heizwerk-Räumen (je Gerät gemerkt). Kompakt: Name, Stellung als kleines Fenster mit Prozent, ein Symbol für Besonderes (Beschattung, von Hand, Tür offen, Sturm …) und ↑ ↓. Tipp auf die Kachel öffnet „Höhe einstellen“.

### Behoben
- **Tabletmodus: Räume fehlten bzw. wurden abgeschnitten** (z. B. Seite 1 leer, Seite 2 nur 3 von 5 Räumen). Ältere Tablet-Browser (Fully) können ein Kachel-Raster nicht auf zwei Seiten aufteilen. Kachel-Seiten (Start, Räume, Rollläden, Energie) werden jetzt reihenweise von Hauswerk selbst aufgeteilt – jede Kachel steht vollständig auf einer Seite.
- Raumnamen brachen in schmalen Kacheln mitten im Wort um („Wohnzimme-r“); jetzt rutscht stattdessen die Betriebsart in die nächste Zeile.

## 0.46.2 – 2026-11-17

### Geändert
- **Bildschirmschoner: Module als Symbole mit Zahlen.** Statt Sätzen („1 Raum heizt“, „Rollläden: 1 offen · 0 zu“, „Solar 0 W“) steht je Modul das Logo, dahinter Symbol + Zahl: Heizwerk (heizt, Fenster offen, niemand da), Rollwerk (offen, zu, beschattet, nächste Fahrt mit Uhrzeit, Richtung und Anzahl), Kraftwerk (Solar, Bezug/Einspeisung, Akku).

## 0.46.1 – 2026-11-17

### Geändert (Tabletmodus)
- **Kopfkacheln dezent:** schlichte Karte ohne Hintergrundbild, eine Zeile mit dem Stand, darunter höchstens zwei kleine Hinweise; Werte-Chips entfallen.
- **Einstellungsseiten auf einer Seite:** Heizwerk-, Rollwerk-, Kraftwerk- und Hauswerk-Einstellungen passen immer auf einen Bildschirm – bis zu drei Spalten, notfalls etwas kleiner.
- **Seitenwechsel reagiert sofort:** Die Seite wechselt schon während der Wischbewegung (nicht erst beim Loslassen) und springt ohne ruckelnde Animation, kurz eingeblendet. Die Punkte unten sind größer zum Antippen.

### Behoben
- Im Tabletmodus machte die Größe „Groß“ die Seiten kleiner statt größer.

## 0.46.0 – 2026-11-17

### Neu
- **Kopfkacheln der Module sagen, was gerade los ist.** Oben steht ein Satz zum Stand, der linke Rand zeigt den Zustand (grün = alles gut, orange = aktiv, türkis = lüftet, violett = von Hand, rot = Achtung, grau = Ruhe). Darunter bis zu drei Zeilen mit dem, was gerade zählt – antippen führt an die passende Stelle –, und nur die Werte, die dazu passen.
  - **Heizwerk:** z. B. „Küche 1,5 °C unter Soll – wird aufgeheizt“, „Alles im Plan – 2 Räume auf Komfort“, „Niemand zu Hause – höchstens 17 °C“. Zeilen: offene Fenster mit Pausendauer, Räume von Hand oder im Boost (bis wann), Kälteeinbruch, und der nächste Wechsel („Um 22:00 Eco in Wohnzimmer“, „morgen 05:30 Komfort in Bad (Vorheizen ab 05:00)“). Luftfeuchte erscheint nur, wenn sie auffällt.
  - **Rollwerk:** z. B. „Um 16:50 schließt – 3 Rollläden (in 25 Min.)“ oder „Sturm – alle Rollläden oben“. Zeilen: Beschattung mit Sonnenstand, von Hand verstellte Rollläden („Automatik wartet bis …“), offene Tür, Böen nahe der Sturmgrenze, Wochenend-Zeitplan.
  - **Kraftwerk (neu):** z. B. „1,7 kW Überschuss – gute Zeit für Waschmaschine & Co.“, „Solar deckt den Verbrauch“, „Bezug 380 W – nur Grundlast“. Zeilen: größter Verbraucher, Akku mit Laden/Entladen, „Heute 72 % selbst gedeckt, 13 kWh eingespeist“. Aktualisiert sich live.

## 0.45.0 – 2026-11-17

### Neu (Tabletmodus)
- **Eigene Startseite fürs Tablet:** Im Anpassen-Modus am Tablet „Eigene“ wählen – dann gelten dort eigene Widgets, Handy und PC bleiben unverändert. „Wie am Handy“ schaltet zurück.
- **Aufwecken bei Bewegung:** Unter Darstellung › Tabletmodus Bewegungsmelder (oder andere Schalter) wählen – sie wecken den Bildschirmschoner und halten den Bildschirm wach. In Fully weckt zusätzlich die Bewegungserkennung der Kamera.
- **Nachts:** abgedunkelt, schwarz mit kleiner Uhr oder Display aus (Fully); Nachtzeit einstellbar (Standard 22–6 Uhr). Nachts erscheinen nur Akutes und Neues.
- **Wichtiges groß im Bildschirmschoner:** Warnungen, Sturm und „Fenster offen – es regnet“ als große orangefarbene Hinweise. Ist eine neu, wird der Schoner hell – in Fully auch das Display, sogar wenn es nachts aus ist.
- **Mehr im Bildschirmschoner:** Wettervorhersage der nächsten Stunden, die nächsten Rollladen-Fahrten (gleiche Zeit zusammengefasst) und Termine von heute und morgen aus gewählten Kalendern (z. B. Müllabfuhr).
- **Tablet sperren:** Nur bedienen – Temperatur, Rollläden, Anwesenheit –, nichts einstellen. 3 Sekunden auf das Hauswerk-Logo drücken entsperrt für 10 Minuten.
- **Größe wirkt im Tablet:** „Kompakt · Normal · Groß“ unter Darstellung macht die Seiten im Tabletmodus spürbar kleiner bzw. größer.

## 0.44.2 – 2026-11-17

### Neu
- **Tabletmodus blendet die Seitenleiste von Home Assistant aus** – für mehr Platz und größere Kacheln. Über ☰ oben links lässt sie sich jederzeit kurz öffnen. Schaltest du den Tabletmodus aus, kommt sie so zurück, wie sie vorher war. Abschaltbar unter Darstellung › Tabletmodus › „Seitenleiste von Home Assistant ausblenden“. Gilt nur für diesen Browser (z. B. Fully), nicht für Handy oder PC.

## 0.44.1 – 2026-11-17

### Geändert
- **Tabletmodus: Kacheln größer und lesbar.** Bisher wurde verkleinert, bis alles auf eine Seite passte – mit vielen Widgets wurde die Schrift winzig, und die Bildschirmhöhe begrenzte die Größe. Jetzt geht Lesbarkeit vor: Eine Seite gibt es nur, wenn sie kaum kleiner ist; sonst wird größer dargestellt und auf eine zweite Seite zum Wischen verteilt. Die Größe richtet sich nach der Breite (bis 140 %).
- **Tabletmodus: Modul-Tasten oben.** Start, Heizwerk, Rollwerk und Kraftwerk bleiben oben wie gewohnt; unten steht nur noch die Unterleiste des Moduls (z. B. Räume · Bericht · Einstellungen) mit größeren Tasten.

## 0.44.0 – 2026-11-17

### Neu
- **Tabletmodus** für Wand-Tablets – je Gerät unter Einstellungen › Darstellung oder über die Adresse `…/hauswerk?tablet` (z. B. Start-Adresse in Fully Kiosk):
  - **Leisten unten:** Start, Heizwerk, Rollwerk, Kraftwerk und Einstellungen als große Tasten am unteren Rand, darüber die Unterleiste (z. B. Räume · Bericht · Einstellungen). Oben bleiben Titel, Wetter, Suche und Glocke.
  - **Kein Scrollen:** Jede Seite wird so groß wie möglich dargestellt und passt auf den Bildschirm; Listen (Einstellungen, Bericht, Protokoll, Heizpläne, Raum) stehen zweispaltig. Passt es nicht auf eine Seite, gibt es höchstens eine zweite – wischen oder die Punkte unten antippen. Rollläden-Räume stehen nebeneinander.
  - **Bildschirmschoner** nach 1, 2 (Standard), 5 oder 10 Minuten ohne Berührung: abgedunkelt mit großer Uhr, Datum, Wetter, kurzem Hausstand (heizt, Fenster offen, Rollläden, Solar, niemand zu Hause) und bis zu drei Hinweisen. Nachts (22–6 Uhr) noch dunkler, der Inhalt wandert jede Minute ein Stück gegen Einbrennen, neue Hinweise leuchten auf. Dabei geht es zurück zur Startseite, offene Fenster schließen sich. Antippen weckt auf, ohne etwas zu schalten.
  - **Fully Kiosk:** Mit eingeschalteter JavaScript-Schnittstelle dunkelt Hauswerk im Bildschirmschoner zusätzlich das Display ab (abschaltbar). Der Bildschirm bleibt an, wo der Browser es erlaubt.

## 0.43.1 – 2026-11-17

### Geändert
- **Rollwerk-Kacheln:** Ein Tipp auf die Kachel öffnet „Höhe einstellen“ (hoch, Stopp, runter und Zahnrad bleiben eigene Knöpfe). Die Behanghöhe steht nur noch als Info in der Kachel.
- **Behanghöhen im Pop-up fest:** Offen 100 %, Halb offen 50 %, Viertel offen 25 %, Geschlossen 0 % – nicht mehr aus den Profilen.

### Behoben
- **Kachel zeigte die Stellung verzögert:** Die Rollläden-Seite wartete auf die nächste Meldung von Rollwerk. Jetzt erscheint jede Stellung sofort, sobald Home Assistant sie meldet.

## 0.43.0 – 2026-11-17

### Neu
- **Rollwerk: Höhe einstellen im Pop-up.** Der Schieberegler in den Rollladen-Kacheln entfällt; dafür gibt es den Knopf **Höhe** (mit aktueller Stellung). Er öffnet ein Fenster mit:
  - einem **Rollladen zum Ziehen** – im Fenster nach oben oder unten ziehen, gefahren wird beim Loslassen (in 5-%-Schritten). Kleine Marken zeigen die Behanghöhen des Profils.
  - den **Behanghöhen aus dem Profil** als Knöpfe: Offen, Beschattung (und Beschattung 2), Abends Stufe 1, Lüften, Tür offen und Geschlossen – je nachdem, was im Profil eingeschaltet ist. Ein Tipp fährt dorthin.
  - hoch, Stopp und runter, der Stellung live sowie „Automatik übernimmt“, wenn von Hand verstellt.
  - einem Sprung zu Profil › Feinheiten, um die Behanghöhen zu ändern.

## 0.42.0 – 2026-11-17

### Neu
- **Experteneinstellungen je Modul:** Oben in den Einstellungen von Hauswerk, Heizwerk, Rollwerk und Kraftwerk gibt es jetzt je einen Haken **Experteneinstellungen**. Ohne Haken bleiben die Profi-Einstellungen dieses Moduls ausgeblendet:
  - **Hauswerk:** Funk-Auslastung
  - **Heizwerk:** Wärmeanforderung, Kalibrierung; im Raum-Dialog Regelung im Detail und Fenster-Feinheiten
  - **Rollwerk:** Nach Neustart; im Profil alle Einstellungen der Cover Control Automation
  - **Kraftwerk:** getrennte Einspeisung und Vorzeichen umdrehen (bleiben sichtbar, solange sie genutzt werden)
  
  Der Schalter „Experte“ im Raum-Dialog bzw. im Rollwerk-Profil ist derselbe wie der Haken des Moduls. Gemerkt wird er je Gerät; der bisherige gemeinsame Schalter gilt beim ersten Öffnen für Heizwerk und Rollwerk.

## 0.41.0 – 2026-11-17

### Neu
- **Abwesend im Tagesplan der Raumkachel:** Ist niemand zu Hause, zeigt der Streifen ab jetzt grau gestreift, wo der Plan abgesenkt wird – Antippen bzw. Darüberfahren nennt „Abwesend: 17 °C statt 23 °C“. Darunter steht die Einstellung, z. B. „Niemand da – höchstens 17 °C“, „… 2 °C kühler als geplant“ oder „… Thermostate aus“. Vorheizen entfällt, solange niemand da ist.

### Behoben
- **Abwesenheit griff nicht, wenn jemand in der Nähe war:** Wer näher als die Heimweg-Grenze war, galt als „auf dem Heimweg“ und damit als zu Hause – auch wenn er dort stand (z. B. Arbeit oder Einkauf um die Ecke). Heizwerk blieb dann auf Komfort. Jetzt zählt nur, wer **näher kommt**: laut Bewegungs-Sensor der Integration „Nähe“ („kommt näher“) oder, ohne ihn, wenn der Abstand in den letzten 15 Minuten kleiner wurde.

### Geändert
- **Heizwerk zeigt bei Abwesenheit immer „Abwesend“** statt Komfort oder Eco. Die Temperatur ist höchstens die Abwesend-Temperatur, aber nie wärmer als der Heizplan.

## 0.40.0 – 2026-11-17

### Verbessert
- **Protokoll sagt genau, was geändert wurde:**
  - Listen zeigen, was dazukam und was wegfiel – z. B. „Funktionen: + Beschattung, − Lüften“ statt „6 gewählt → 5 gewählt“.
  - Sensoren und Schalter erscheinen mit ihrem Namen statt der Entitäts-ID.
  - Jede Profil-Einstellung hat eine Bezeichnung; „N weitere Einstellungen“ gibt es nicht mehr.
  - Profil-Einträge nennen die betroffenen Rollläden („für Küche Tür“) statt „1 Rollläden“.
  - Allgemeine Einstellungen (Haus, Heizwerk, Rollwerk, Kraftwerk) zeigen alt → neu, z. B. „Rollwerk: Nach Neustart nie → immer“.
  - Sturmschutz und Automatik am Rollladen zeigen „an → aus“ statt „– → aus“.
- Speichern ohne Änderung erzeugt keinen Protokoll-Eintrag mehr („ohne Änderung“).

## 0.39.1 – 2026-11-17

### Behoben
- **Protokoll:** Die Modul-Symbole im Filter „Heizwerk & Haus · Rollwerk · Kraftwerk“ waren zu groß und überdeckten den Anfang der Beschriftung. Ein Klicktest prüft jetzt, dass Modul-Symbole nirgends über ihren Platz hinausragen.

## 0.39.0 – 2026-11-17

### Neu
- **Vorheizen im Tagesplan der Raumkachel:** Vor jedem Komfort-Beginn zeigt der Streifen die Vorheizzeit gestreift in der Farbe der Zieltemperatur – in der detaillierten und der kompakten Kachel. Die Länge ist die, mit der Heizwerk gerade rechnet: feste Zeit (mit Wetter-Faktor) oder gelernt aus der Aufheizgeschwindigkeit. Antippen bzw. Darüberfahren zeigt „Vorheizen ab 05:25 (35 Min.) für 21 °C um 06:00“; die detaillierte Kachel nennt darunter „Vorheizen … Min. vorher“.

## 0.38.0 – 2026-11-17

### Neu
- **Hauswerk einrichten** – ein Assistent für alles: Personen, Wetter, Räume (mit dem Raum-Assistenten, Bereiche mit Thermostat werden vorgeschlagen), Rollläden (mit dem Rollladen-Assistenten) und Energie (erkannte Sensoren übernehmen). Nach jedem Unter-Assistenten geht es an derselben Stelle weiter; jeder Schritt lässt sich überspringen. Solange etwas fehlt, zeigt die Startseite „Hauswerk einrichten – x von 5 erledigt“ (ausblendbar); jederzeit unter Hauswerk › Einstellungen › Einrichtung.
- **Suche über alles** (Lupe oben, am Computer auch `/` oder Strg+K): Seiten, Räume, Geräte der Räume, Heizpläne, Rollläden, Profile, Verbraucher und alle Einstellungen aller Module – Umlaute egal, bester Treffer zuerst; dazu „… im Protokoll suchen“.
- **Startseite: Widgets ziehen** – im Anpassen-Modus am Griff ziehen (Maus und Finger), die Reihenfolge wird beim Loslassen gespeichert. Am Handy entfallen dafür die Pfeile.
- **Vorschau beim Hinzufügen:** Ein Tipp auf ein Widget zeigt es mit deinen Daten, in klein, mittel oder groß – erst „Hinzufügen“ legt es an, in der gewählten Größe.

### Geändert
- **Rollwerk: gekippte Fenster lüften jetzt in jedem Profil.** Seit 0.29 kommen die Fensterkontakte automatisch aus Heizwerk, das Lüften war aber standardmäßig aus – ein gekipptes Fenster wurde abends ganz zugefahren. Beim Update wird „Fenster gekippt: lüften“ in allen Profilen eingeschaltet (steht im Protokoll); abschalten je Profil unter Fenster & Lüften.

### Behoben
- **Aussperrschutz auch beim Erzwingen:** „Erzwingen: zu / lüften / Beschattung“ fuhr einen Rollladen trotz offener Tür herunter. Jetzt bleibt er bei offener Tür oben, bis sie zu ist.

## 0.37.0 – 2026-11-16

### Neu
- **Fehler sichtbar statt leerer Seite:** Bricht eine Seite, ein Fenster, der Raum-Dialog oder ein Widget ab, erscheint „Hier ist etwas schiefgelaufen“ mit der Fehlermeldung, **Diagnose kopieren** (Version, Seite, Fehler, Browser – in der App ohne Zwischenablage zum Markieren), **Neu laden** und **Zur Startseite**. Schlägt ein Knopf fehl, sagt eine Meldung „Das hat nicht geklappt: …“. Jeder Panel-Fehler steht zusätzlich im Protokoll von Home Assistant (Einstellungen › System › Protokolle, `custom_components.hauswerk.panel`). Die Regelung läuft davon unberührt weiter.

### Behoben
- **Kraftwerk:** Die Fenster Netz, Batterie und Hausverbrauch ließen sich nicht öffnen, sobald dort ein Sensor gewählt war. Gefunden von den neuen Klicktests.

### Intern
- **Panel-Klicktests bei jeder Version** (GitHub „Prüfen“ › Panel-Klicktests): öffnen im Browser jede Seite über ihre Adresse, jedes Widget in jeder Größe, „Widget hinzufügen“ für jedes Widget, jedes Einstellungs-Fenster aller Module (mit Ändern und Speichern), Räume, Rollwerk-Profile und -Rollläden, den Rollladen-Assistenten und Kraftwerk. Alles, was das Panel dabei an Home Assistant schickt, wird gegen die echten Prüfregeln des Backends getestet – so wären die Fehler aus 0.34.1 und 0.34.2 vor dem Release aufgefallen.

## 0.36.0 – 2026-11-16

### Neu
- **Kraftwerk › Verbraucher mit eigenem Namen:** Unter Einstellungen › Verbraucher lässt sich jedem Verbraucher ein Name geben (leer = Name aus Home Assistant).
- **Symbol nach dem Namen:** Kraftwerk wählt das Symbol passend zum Namen – z. B. Wärmepumpe, Wallbox/E-Auto, Waschmaschine, Trockner, Spülmaschine, Kühlschrank, Herd, Backofen, Heizstab/Boiler, Klima, Pool/Pumpe, Fernseher, Server, Router, Computer, Licht. Das Symbol ändert sich schon beim Tippen und erscheint unter „Verbraucher jetzt“.

## 0.35.0 – 2026-11-16

### Neu
- **Profilname im Assistenten:** Bei „Rollladen hinzufügen“ › Profil › „Neues Profil“ lässt sich der Name direkt eingeben (vorgeschlagen aus Raum und Richtung, z. B. „Schlafzimmer Süd“).
- **Profile umbenennen:** Jedes Profil – auch „Standard“ – hat oben im Profil-Dialog das Feld **Name des Profils**, in jedem Abschnitt sichtbar. Die Umbenennung steht im Protokoll (Name alt → neu); die Rollläden behalten ihr Profil.
- Zwei Profile mit gleichem Namen werden verhindert.

## 0.34.2 – 2026-11-16

### Behoben
- **Kraftwerk ließ sich nicht öffnen:** Ein Tipp auf Kraftwerk (Reiter, untere Leiste oder Widget) sprang sofort zur Startseite zurück, weil die Adresse `/hauswerk/kraftwerk/…` nicht erkannt wurde. Jetzt werden die Unterseiten aller Module über ihre Adresse gefunden.

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
