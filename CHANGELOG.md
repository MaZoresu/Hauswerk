# Änderungen

Neueste Version oben. Der Abschnitt einer Version erscheint automatisch als Release-Text auf GitHub und damit im Update-Dialog von Home Assistant (HACS).

## 0.109.0 – 2026-11-28

### Neu – Wartung aus den Geräten
- **Hauswerk durchsucht Home Assistant** (alle 10 Min.) nach Verschleißteilen und Verbrauchsmaterial in den Geräten und legt je Gerät und Teil eine Aufgabe an:
  - **Saugroboter** (z. B. Roborock): Restzeit von Haupt- und Seitenbürste, Filter, Sensoren, Wischtuch – „Robiboter: Filter · seit 35 Std. überfällig“.
  - **Mähroboter:** Messerqualität bzw. Restzeit, dazu die Betriebsstunden der Messer.
  - **Geschirrspüler, Kaffeemaschine, Luftreiniger …:** Salz, Klarspüler, Entkalken, Filter, Staubbeutel.
  - **Batterien je Gerät:** „Batterie fast leer“ (Battery Notes) bzw. Ladestand unter der Grenze – mit Batterie-Typ, z. B. „Batterie wechseln: S_Klingeltaster · 2× AAA“. Handys, Tablets, Akku-Geräte (Saug-/Mähroboter) und Stromspeicher sind ausgenommen.
- **Erledigt setzt im Gerät zurück:** Gibt es einen Knopf (z. B. „Messer zurücksetzen“, „Batterie ersetzt“ von Battery Notes), drückt Hauswerk ihn. Ohne Knopf (z. B. Roborock – dort in der App zurücksetzen) bleibt die Aufgabe ausgeblendet, bis das Gerät den neuen Wert meldet.
- **Prognose:** Aus dem Verlauf der Restzeit schätzt Hauswerk, wann es so weit ist („noch 130 Std. · etwa in 12 Tagen“); Teile, die in 30 Tagen fällig werden, stehen unter „Demnächst“, alle übrigen unter „Aus den Geräten“ mit Balken.
- Fällige Geräte-Wartung kommt als „Wartung fällig“ mit Knopf „Erledigt“.
- **Einstellbar** unter Wartung › Zahnrad: an/aus, fällig ab 5–25 % bzw. ab einer Restzeit, was gefunden wurde, ausgeblendete Funde wieder anzeigen. Einzelne Funde lassen sich in der Zeile ausblenden (Auge).

## 0.108.1 – 2026-11-28

### Geändert – Tablet-Startseite
- **Kachel „Wartung“ statt „Anwesenheit“:** zeigt, wie viele Aufgaben fällig sind (bzw. in den nächsten 14 Tagen anstehen) und welche – rot bei mehr als 14 Tagen überfällig, orange bei fällig, türkis wenn bald etwas ansteht, grün wenn alles erledigt ist. Antippen öffnet den Bereich Wartung. Die Anwesenheit steht oben in der Kopfzeile.

## 0.108.0 – 2026-11-28

### Neu – Wartung ausgebaut
- **Nach Saison:** Aufgaben nur in bestimmten Monaten, z. B. „Gartenwasser abstellen“ (Okt–Nov), „Bewässerung in Betrieb nehmen“ (April), „Dachrinne reinigen“ (November) – fällig zu Beginn der Saison, einmal je Saison. Mit Intervall: frühestens nach dem Intervall, aber nur in der Saison.
- **Nach Nutzung:** fällig nach Durchläufen eines Geräts der Fertigerkennung (z. B. Waschmaschine reinigen nach 30 Wäschen), nach Betriebsstunden (z. B. Lüftungsfilter nach 2000 Std. Lüftung an) oder nach einem Zähler (z. B. Mähermesser nach 300 Betriebsstunden). Die Zeile zeigt „24 von 30 Durchläufe“ und schätzt, wann es so weit ist.
- **Aus Meldungen abgeleitet:** „Heizkörper bleibt kalt“ wird zur Aufgabe „Heizkörper entlüften: Bad“, „Kühlschrank braucht mehr Strom“ zu „abtauen, Dichtung prüfen“ – bis quittiert.
- **Zuständige Person:** Die Erinnerung geht dann nur an das Handy dieser Person (Home-Assistant-App).
- **Gerätedaten:** Modell, Kaufdatum, Garantie bis, Ersatzteil/Nummer und Link zur Anleitung. 30 Tage vor Ende der Garantie erscheint ein Hinweis.
- **Fachbetrieb und Termin:** Firma und Telefon; rechtzeitig vor der Fälligkeit (2 Wochen bis 3 Monate) „Termin vereinbaren“ mit Anruf-Knopf. Der Termin steht an der Aufgabe, kommt auf Wunsch einmal in einen Kalender (Wartung › Zahnrad) und am Tag gibt es eine Erinnerung.
- **Beim Erledigen:** optional Notiz, Kosten, Messwert (z. B. Anlagendruck in bar oder Zählerstand – frühere Werte werden angezeigt) und ein Foto (wird verkleinert gespeichert, die letzten 40). Alles steht im Verlauf.
- **Kosten:** je Jahr und je Aufgabe im laufenden Jahr.
- **In Home Assistant:** Aufgabenliste „Hauswerk Wartung“ (`todo.hauswerk_wartung`) mit allem, was in 30 Tagen fällig ist – abhaken = erledigt, neue Einträge werden einmalige Aufgaben, auch per Assist. Kalender „Hauswerk Wartung“ (`calendar.hauswerk_wartung`) mit allen Fälligkeiten und Terminen.
- **Neue Vorlagen:** Schornsteinfeger, Zähler ablesen (Wasser, Gas, Strom), Anlagendruck prüfen, Mähroboter einwintern, Regentonne entleeren, Klimagerät reinigen u. a.

## 0.107.0 – 2026-11-28

### Neu: Wartung im Haus
- Eigener Bereich „Wartung“ (Seite, Start-Widget, Kachel unter „Mehr“, Link aus der Glocke): alle Aufgaben nach Fälligkeit – überfällig, bald fällig, später.
- Aufgaben mit einem Tipp quittieren, um eine Woche verschieben, Raum und Notiz hinterlegen; Verlauf der letzten Erledigungen.
- Neue Vorlagen (u. a. Rauchmelder testen, Filter wechseln, Dachrinne, Heizung entlüften).
- Automatische Aufgaben: Verschleißteile aus Beetwerk und schwache Batterien der Heizwerk-Thermostate (mit Raum) – quittierbar.

### Kopfzeile: Anwesenheit
- Oben rechts zeigen Bilder bzw. Anfangsbuchstaben, wer zu Hause ist (grüner Punkt) und wer unterwegs; dazu Urlaub/Abwesend sowie Gäste, Party und Eco. Antippen öffnet die Anwesenheitsauswahl.
- Auf dem Handy kompakt als Zähler. Abschaltbar unter Darstellung.

## 0.106.2 – 2026-11-28

### Behoben (Kraftwerk › Stromfresser)
- **Falsche Meldung „Waschmaschine braucht mehr Strom … 98 kWh am Tag (+8093 %)“:** Messsteckdosen melden ihren Zähler oft in Wh – die Werte wurden als kWh gelesen. Jetzt rechnet der Wächter immer in kWh (auch Grundlast und Akku).
- **Nur noch Dauerläufer:** Geräte, die nur bei Bedarf laufen (Waschmaschine, Trockner, Spülmaschine …), schwanken von Tag zu Tag stark – ein Anstieg heißt dort nur, dass mehr gewaschen wurde. Gemeldet werden nur Geräte mit gleichmäßigem Tagesverbrauch (Kühlschrank, Gefriertruhe, Router, Pumpe …). Der Tipp „Dichtung, Eis …“ steht nur noch bei Kühl- und Gefriergeräten.
- Die falsche Meldung verschwindet bei der nächsten Prüfung (etwa 3 Min. nach dem Update).

## 0.106.1 – 2026-11-27

### Geändert – Heizwerk › Lüften im Tabletmodus
- **Alle Räume auf einer Seite:** flachere Kacheln zu dritt bzw. viert (ab 7 Räumen) statt großer Wand-Kacheln auf zwei Seiten; die Seite scrollt bei Bedarf, statt zu blättern.
- **Kachel:** Raum, Feuchte groß mit Wasser in g/m³, Aussage in der Farbe des Zustands und eine Zeile darunter – beim Lüften Ring und Restzeit, sonst der Grund bzw. „zuletzt vor 3 Std.“. Räume ohne Bedarf zurückhaltend, „jetzt lüften“ kräftig.
- **Kopfkarte in einer Zeile:** Titel, beste Lüftzeiten rechts daneben, darunter die 24-Stunden-Leiste schmal (Legende unter ⓘ).
- **Kein Widerspruch mehr:** Statt „Alles gut – nirgends lüften nötig“ bei Räumen mit „Bald lüften“ steht „Gerade nichts zu tun · 2 Räume bald lüften“ (orange). Ab 3 Räumen heißt es „4 Räume jetzt lüften“ statt einer langen Namensliste.

## 0.106.0 – 2026-11-27

### Neu – Kraftwerk
- **Stromfresser erkennen:** Braucht ein Gerät aus dem Energie-Dashboard („Einzelne Geräte“) in den letzten 5 Tagen deutlich mehr als sonst (+30 %, mind. 0,15 kWh am Tag), kommt z. B. „Kühlschrank braucht mehr Strom – seit 5 Tagen 1,3 kWh am Tag statt 0,8 kWh (+62 %)“. Ebenso **„Grundlast gestiegen“**, wenn der Verbrauch nachts (1–5 Uhr) deutlich über dem der Wochen davor liegt. Täglich um 7:40 Uhr geprüft.
- **Standby je Gerät** (Bericht): niedrigste übliche Leistung jeder Messsteckdose bzw. jedes Geräts aus dem Energie-Dashboard über 7 Tage, mit Kosten im Jahr – z. B. „Fernseher 8 W – ca. 22 € im Jahr“; unterscheidet Ruhezustand und Dauerläufer (Kühlschrank, Router).
- **Abschlag prüfen** (Bericht): Kosten seit Beginn des Abrechnungsjahrs (Netzbezug − Einspeisung, auf Wunsch + Grundpreis), der Rest mit den Vorjahresmonaten hochgerechnet – „Guthaben ca. 120 €“ bzw. „Nachzahlung ca. …“, mit Monatsbalken und Abschlag-Linie. Abschlag, Beginn und Grundpreis unter Kraftwerk › Einstellungen › Abschlag.
- **Tablet-Wand:** großer Energiefluss, daneben in einem Satz, was gerade gilt („1,7 kW Überschuss – jetzt ist eine gute Zeit für Waschmaschine, Trockner“), heute Autarkie und selbst genutzt als Ringe, Solar-Prognose und Auffälliges.
- **Störungen melden:** Solar liefert trotz Sonne nichts bzw. der Wechselrichter meldet sich nicht (je 30 Min.), Akku wird an Tagen mit Einspeisung nicht mehr voll, Stromzähler sendet seit 30 Min. keinen Wert.
- Alles erscheint oben unter Kraftwerk › Energiefluss („Auffällig“), unter der Glocke und als Nachricht – neuer Anlass „Auffälliger Stromverbrauch & Störungen“ unter Benachrichtigungen › Kraftwerk (Knopf „Gesehen“).

## 0.105.0 – 2026-11-27

### Geändert – Handy
- **Anwesenheit in einer Zeile:** Das Widget zeigt nur noch „Zu Hause · Jens · Julia (460 m)“ mit dem Modus-Symbol und aktiven Schaltern (Gäste, Party, Eco). Antippen öffnet die Auswahl mit Zu Hause / Abwesend / Urlaub, Gäste / Party / Eco und den Personen; das Zahnrad führt zu den Einstellungen.
- **Untere Leiste entlastet:** Start, die vier Module, die du auf diesem Gerät am häufigsten öffnest (das gerade offene ist immer dabei), und **Mehr** – dort die übrigen Module, Einstellungen und Protokoll. Keine abgeschnittenen Namen mehr.
- **Nach unten ziehen zum Aktualisieren:** ganz oben auf einer Seite nach unten ziehen lädt alle Werte neu.
- **Scroll-Position bleibt:** Beim Zurückkehren in die App (oder nach dem Neuladen, bis 30 Min.) steht die Seite wieder dort, wo du warst.

## 0.104.0 – 2026-11-27

### Neu – Wachwerk › Wetter-Schutz
- **Bei amtlicher Unwetterwarnung** (NINA, DWD – Sturm/Orkan ab Stufe 2, Gewitter, Hagel, Starkregen):
  - **Markisen fahren ein** (Geräteklasse „Markise“ bzw. „Markise“ im Namen oder selbst gewählt),
  - **Rollläden auf Sturmstellung** bei Sturm- bzw. Orkanwarnung – der Rollwerk-Sturmschutz greift schon mit der Warnung, nicht erst bei Böen über der Sturmgrenze; endet 30 Min. nach der Warnung,
  - **Mähroboter in die Station** (Beetwerk-Pause „Unwetterwarnung“, danach mäht er weiter wie nach Regen),
  - eine Nachricht „Unwetterschutz: STURMBÖEN – Markisen eingefahren · Rollläden auf Sturmstellung · Mäher fährt in die Station · noch offen: …“.
- **Offene Fenster vor dem Unwetter:** Kommt laut Stunden-Vorhersage Gewitter oder Sturmböen über der Sturmgrenze (Standard: in den nächsten 3 Std.) oder gilt eine Warnung, meldet Wachwerk offene Fenster aus Heizwerk – z. B. „Gewitter ab 18:00 Uhr – 2 Fenster offen“ mit „In 30 Min.“ und „Gesehen“.
- **DWD-Warnungen** (Sensor „Aktuelle Warnstufe“ der Integration „Deutscher Wetterdienst – Warnungen“) werden jetzt automatisch als Warnquelle erkannt.
- Alles einstellbar unter Wachwerk › Einstellungen › Wetter-Schutz; die Seite Wachwerk zeigt „Unwetterschutz aktiv“ bzw. die Vorhersage.

## 0.103.0 – 2026-11-27

### Geändert – Heizwerk › Bericht › Heizleistung: Fußbodenheizung und Mischbetrieb richtig bewertet
- **Fußbodenheizung nach Einschaltdauer:** Der Stellantrieb kennt nur auf/zu – „Ventil ganz auf“ wurde bisher wie bei einem voll aufgedrehten Heizkörper gewertet und konnte „Zu schwach“ auslösen. Jetzt zählt, wie lange der Stellantrieb in der Komfortzeit an war („Fußbodenheizung an 60 % der Komfortzeit“); am Limit erst ab 80–85 %.
- **Mischbetrieb (Fußbodenheizung + Zusatz-Heizkörper):** neue Kennzahl „Zusatz half“ – Anteil der Komfortzeit, getrennt nach Frost und mild – mit eigenen Aussagen: „Fußbodenheizung reicht allein“, „Zusatz-Heizkörper hilft nur bei Frost“ (so gedacht) oder „Zusatz-Heizkörper oft nötig – auch an milden Tagen“ (Vorlauf/Heizkurve des Fußbodenheizkreises anheben, Abgleich und Stellantrieb prüfen; Urteil dann „Knapp“).
- **Kein falsches „Thermostat prüfen“ mehr im Mischbetrieb:** Die Zusatz-Heizkörper sind absichtlich zu – ohne Werte vom Stellantrieb der Fußbodenheizung heißt es jetzt „Wird nicht warm genug“ mit dem Tipp, den Stellantrieb einzutragen.
- **Aufheizen im Mischraum** ist als „mit Zusatz“ gekennzeichnet; „Heizt schnell auf“ entfällt dort. Die Raumkarte zeigt „Fußbodenheizung + Zusatz“.
- Die neuen Werte werden ab jetzt gesammelt – aussagekräftig nach einigen Tagen.

## 0.102.1 – 2026-11-27

### Geändert – Lichtwerk im Tabletmodus
- **Kleinere Licht-Kacheln:** Eingeschaltete Lichter stehen in flacheren Kacheln (etwa halb so hoch) zu dritt bzw. viert nebeneinander, mit kleinerer Lampe, Helligkeit in % und dezenterem Schein. Bei Leuchten, die nur an/aus können, entfällt das große „an“. Die Stimmungs-Knöpfe sind etwas kleiner.

## 0.102.0 – 2026-11-27

### Geändert – Lichtwerk im Tabletmodus
- **Zeitleiste lesbar:** schmale Leiste mit Punkten (jetzt, Schaltungen, Sonnenunter-/aufgang, Uhrzeiten alle 3 Std.) und darunter die nächsten Schaltungen als Knöpfe – z. B. „16:10 an · 7 Lichter“, „23:00–00:00 aus · MP3 Gong, Flur OG“. Schaltungen binnen 20 Min. werden zusammengefasst, nichts überlappt mehr. Antippen öffnet die Leuchte, den Raum bzw. die Liste der Lichter.
- **Haus-Bild nach Stockwerken:** je Stockwerk eine Fensterreihe (oben DG/OG, unten EG/Keller), Außenbereiche wie der Vorgarten als Laterne neben dem Haus. Das Stockwerk kommt aus Home Assistant (Bereiche › Stockwerke), sonst aus dem Namen („Flur OG“, „Vorgarten“).
- **Räume im Haus anordnen:** „⋯“ am Haus öffnet das Fenster – je Raum Stockwerk wählen und mit ‹ › die Reihenfolge von links nach rechts festlegen; „Automatisch anordnen“ setzt zurück.

## 0.101.0 – 2026-11-27

### Neu – Kraftwerk › Bericht (bisher „Verlauf“)
- **Energie pro Tag eines Monats:** je Tag nach oben Solar (selbst genutzt, eingespeist), nach unten Netzbezug; Stern am besten Solartag; Monate blättern (‹ ›, Kalender = dieser Monat). **Ein Tipp auf einen Balken öffnet den Tag** – je Stunde, mit Kennzahlen und Kosten.
- **Kosten und Vorteil:** Netzbezug, Einspeisung, selbst genutzter Solarstrom und Bilanz als Säulen; „Ohne Solar hättest du gezahlt“ und „Vorteil durch Solar“. Preise aus dem Energie-Dashboard (fest oder Entität, sonst aus den Kosten-Zählern).
- **Geräte aus dem Energie-Dashboard** („Einzelne Geräte“): Verbrauch im Monat, Kosten und Anteil am Hausverbrauch, dazu „Rest (ohne eigene Messung)“.
- **Sparschwein:** Vorteil durch Solar seit Beginn der Aufzeichnung (mit heutigen Preisen). Mit den **Anschaffungskosten** (Kraftwerk › Einstellungen › Anschaffung der Solaranlage): wie viel schon bezahlt ist und wann sich die Anlage etwa bezahlt gemacht hat.

### Geändert
- **Verbraucher jetzt:** Die Geräte aus dem Energie-Dashboard erscheinen automatisch mit ihrem Namen unter dem Energiefluss – mit ihrer Leistung aus dem Dashboard bzw. dem Leistungs-Sensor am selben Gerät.

## 0.100.0 – 2026-11-27

### Geändert – Heizwerk › Lüften übersichtlich (Handy und Tablet)
- **Nach Handlungsbedarf geordnet:** oben „Jetzt lüften“ (stoßlüften, Fenster schließen, lange offen, Schimmelgefahr), darunter „Lüftet gerade“, unten „Alles gut“ als kompakte, aufklappbare Liste mit Ampelpunkt, Feuchte und „zuletzt gelüftet“ (zugeklappt, solange oben etwas zu tun ist).
- **Eine Aussage je Raum** mit einer Farbe, z. B. „Jetzt 10 Min. stoßlüften“; alle Zahlen im Fenster des Raums (Antippen) unter „Alle Werte“.
- **Laufende Lüftung als Ring** mit Restzeit (läuft sekundengenau) und drei Haken: Zeit, Feuchte gesunken, Raum kühler.
- **Kleine Anzeigen statt Zahlenblöcken:** Feuchte als Balken mit Strich an der Grenze, Wasser in der Luft drinnen/draußen als zwei Balken („trocknet“ / „trocknet nicht“), Schimmel als Ampelpunkt, CO₂.
- **Woche als Mini-Leiste:** Lüften je Tag der letzten 7 Tage, Mond = nachts offen.
- **Feste Farben:** Türkis = lüften/Fenster, Orange = bald bzw. lange offen, Rot = Schimmelgefahr, Grau = alles gut.
- **Kopfkarte einfacher:** groß, was zu tun ist, die besten Lüftzeiten als Knöpfe, Richtwert und Tipps hinter ⓘ, Einstellungen am Zahnrad.
- **Lüftzeiten als Tagesleiste:** 24 Stunden mit gut (trockene Luft, kein Regen), Regen, Nacht und den besten Zeiten.
- **Tablet:** Wand-Kacheln je Raum – große Feuchte, eine Statuszeile, Farbe nach Zustand, beim Lüften Ring und Restzeit; Antippen öffnet die Details.

## 0.99.0 – 2026-11-27

### Neu – Lichtwerk im Tabletmodus
- **Haus bei Nacht:** oben eine Hausgrafik mit einem Fenster je Raum – es leuchtet in der Lichtfarbe, wenn dort Licht an ist (heller je Helligkeit). Antippen öffnet den Raum bzw. die Leuchte. Daneben groß „3 von 4 an“ und was auffällt (von Hand, niemand zu Hause, nicht erreichbar).
- **Zeitleiste des Abends:** von jetzt bis zum Sonnenaufgang bzw. der letzten Schaltung – geplante Schaltungen mit Uhrzeit und welche Lichter („23:00 · 2 Lichter“), Sonnenunter- und -aufgang, die Dunkelheit schattiert. Antippen öffnet die betroffenen Lichter.
- **Stimmungen als Knöpfe:** Gemütlich, Fernsehen, Nachtlicht und Alles aus für alle Lichter, die gerade an sind; im Raum-Fenster alle Stimmungen für den ganzen Raum. Jede Leuchte bekommt nur, was sie kann (Farbe, Weißton, Helligkeit).
- **Eingeschaltete Lichter groß:** Lampe mit Schein in der echten Lichtfarbe, Kachel leicht getönt, der Pegel von unten zeigt die Helligkeit. **Hoch/runter wischen dimmt**, Tippen schaltet aus, lange drücken öffnet Helligkeit und Farbe (auch über „…“).
- **Ablauftimer als Ring** um die Lampe (Bewegung bzw. HmIP), dazu „aus in 1:40“.
- **Ausgeschaltete Lichter klein** darunter als Knöpfe: Lampe schaltet ein, Name öffnet das Fenster; mit „an 16:30“ bzw. „von Hand aus“. Nicht erreichbare schraffiert mit Warnzeichen.
- **Spalten nach Anzahl:** 2 bzw. 3 Spalten, ab 7 Lichtern 4; ab 9 eingeschalteten nach Raum gruppiert. Im Hochformat 2 Spalten. Die Seite scrollt, statt zu blättern.
- **Nachts** (Sonne unter dem Horizont) treten ausgeschaltete Lichter zurück, eingeschaltete leuchten.

## 0.98.1 – 2026-11-27

### Behoben (Heizwerk › Lüften)
- **Lüften übersteht einen Neustart von Home Assistant:** Bisher galt ein offenes Fenster nach dem Neustart als „gerade geöffnet“ – Lüft-Timer, „genug gelüftet“, die gewollte Nacht beim Schlafzimmer und „Fenster lange offen“ begannen von vorn, und eine Lüftung über den Neustart hinweg fehlte in der Bilanz. Jetzt merkt sich Heizwerk, seit wann jedes Fenster offen ist, die laufenden Lüftungen und wie oft „Fenster schließen“ heute kam. Ist das Fenster während des Neustarts zugegangen, kommt die Lüftung mit voller Dauer in die Bilanz.

## 0.98.0 – 2026-11-27

### Geändert (Heizwerk › Lüften) – absolute Luftfeuchte
- **„Genug gelüftet“ nach Wasser in der Luft:** Beim Lüften kühlt der Raum ab – die relative Feuchte sinkt dann kaum oder steigt sogar, obwohl viel Wasser hinausgeht. Jetzt zählt die absolute Feuchte (g/m³): genug, wenn so viel Wasser hinaus ist wie 10 %-Punkte bei der Anfangstemperatur (höchstens die Hälfte des Unterschieds zu draußen). Grund z. B. „Feuchte 11,0 → 8,9 g/m³“. Ohne Außenwerte wie bisher.
- **„Feuchte steigt schnell“ (Duschen, Kochen) und Nachheizen nach dem Duschen** aus der absoluten Feuchte: kein Fehlalarm mehr, wenn der Raum abkühlt (Heizung regelt herunter, Fenster). Die Grenze bleibt „%-Punkte in 15 Min.“, umgerechnet bei der Raumtemperatur.
- **Anzeige je Raum** auf der Seite Lüften: „9,1 g/m³ – Wasser in der Luft · draußen 4,2 g/m³ – Lüften trocknet“ (bzw. „trocknet nicht“).
- Ob ein Raum zu feucht ist, sagt weiter die relative Feuchte (Grenze je Raumart) – sie entscheidet über Schimmel und Wohlgefühl.

## 0.97.0 – 2026-11-27

### Geändert
- **Bildschirmschoner nur mit Wichtigem:** Im Tabletmodus zeigt der Bildschirmschoner nur noch Warnungen (z. B. Sturm, Fenster offen bei Regen, amtliche Warnungen) – keine normalen Hinweise mehr. Diese stehen weiter unter der Glocke. Die Müllabfuhr steht dafür wieder bei den Terminen.

### Behoben (Heizwerk › Lüften)
- **Kein „morgens lüften“ nach einer Nacht bei offenem Fenster:** War das Fenster nachts mindestens 30 Min. offen (zwischen „Nachts ab“ und der Erinnerungszeit), entfällt die Erinnerung – in jedem Raum, auch wenn das Fenster vor der Erinnerung schon wieder zu ist. Bisher galt das nur für Räume, in denen das Fenster nachts offen bleiben darf.

## 0.96.0 – 2026-11-24
- Wetter: Antippen der Wetterkachel öffnet Details – jetzt (gefühlt, Wind/Böen, Feuchte, Sonne), Satz zum Tag, amtliche Warnungen, 24-Stunden-Kurve mit 0°-Linie, Regen und Nacht, 7 Tage mit Spannbalken, Regen und Wind, „Fürs Haus“ (Böen, Frost/Mäher, Regen bei offenen Fenstern, Lüften, kälteste Nacht, Sonne, Mähen).
- Handy-Kachel: Regenbalken mit Wahrscheinlichkeit je Stunde und eine „Fürs Haus“-Zeile.
- Tablet: Wetter auf der Startseite mit Satz, 5 Tagen und Hinweisen; Bildschirmschoner zeigt den Satz.
- Fix: „jetzt“ zeigt den gemessenen Wert statt der Vorhersage; „20 Uhr Uhr“ behoben.

## 0.95.0 – 2026-11-24

### Neu (Benachrichtigungen)
- **Modul-Logo in jeder Benachrichtigung:** Man sieht sofort, aus welchem Modul eine Meldung kommt – z. B. das Wachwerk-Logo bei „Niemand zu Hause – noch offen“, das Heizwerk-Logo bei „Fenster lange offen“, das Hauswerk-Logo bei Müll und Wartung.
  - **Mitteilung in Home Assistant:** das Logo vor dem Text.
  - **App auf dem iPhone:** das Logo als kleines Bild rechts in der Mitteilung (nicht, wenn schon ein Kamerabild dabei ist, z. B. bei der Klingel).
  - **App auf Android:** das Logo als großes Symbol, dazu das Modul-Symbol in der Statusleiste.
- Abschaltbar unter Benachrichtigungen › Empfänger › „Modul-Logo in Benachrichtigungen“. Die Vorschau je Anlass zeigt das Logo mit.

## 0.94.1 – 2026-11-23

### Geändert
- **Hausmodi-Knöpfe ausgeblendet:** „Gute Nacht“, „Guten Morgen“, „Wir gehen“ und „Wir sind da“ stehen nicht mehr auf der Startseite und am Tablet. Wieder einblenden unter Einstellungen › Haus › Hausmodi › „Knöpfe auf der Startseite“; die Schritte je Modus bleiben gespeichert.

## 0.94.0 – 2026-11-23

### Neu (Darstellung)
- **Design „Weihnachten“** unter Darstellung › Design: dunkles Tannengrün mit Kerzenrot und Gold, eine leuchtende Lichterkette unter der Kopfzeile (rot, gold, grün, blau, leise funkelnd) und ruhiger Schneefall im Hintergrund. Eine eigene Akzentfarbe gilt weiter. Am Tablet unter Darstellung › Tabletmodus › Hell/Dunkel ebenfalls wählbar („Weihnachten“, oder „Wie Darstellung“). Ist am Gerät „Bewegung reduzieren“ eingestellt, stehen Schnee und Lichter still.

## 0.93.1 – 2026-11-23

### Geändert (Benachrichtigungen › Frost erwartet)
- **Frostwarnung einmal am Tag zu fester Uhrzeit:** Standard jetzt täglich um 07:00 Uhr – solange Frost vorhergesagt ist, kommt die Nachricht genau einmal am Tag, auch wenn die Vorhersage zwischendurch über und unter die Grenze schwankt (das löste bisher immer neue Warnungen aus). Einstellbar unter Benachrichtigungen › Anlässe › Frost erwartet › „Senden“: sofort oder täglich um 6:00 bis 20:00 Uhr.

## 0.93.0 – 2026-11-22

### Neu – Nachrichten mit Knöpfen (Home-Assistant-App)
- Nachrichten an die Home-Assistant-App tragen jetzt passende Knöpfe – erledigen, ohne die App zu öffnen:
  - **Licht an, niemand zu Hause:** Alle aus · Gesehen
  - **Niemand zu Hause – noch offen:** Lichter aus · Gesehen
  - **Fenster lange offen**, **Fenster offen – Regen/Sturm:** In 30 Min. · Gesehen
  - **Fenster schließen (Lüften):** 10 Min. später · Gesehen
  - **Tür/Tor lange offen:** Schließen (bei Toren) · In 30 Min. · Gesehen
  - **Mäher fährt heim:** Garten frei (Melder 1 Std. nicht beachten) · 2 Std. belegt
  - **Wartung fällig:** Erledigt · In 1 Woche
  - **Müllabfuhr**, **Batterie schwach**, **Mähroboter braucht Hilfe:** Erledigt bzw. Gesehen
  - **Wochenbericht:** Hauswerk öffnen · **Es hat geklingelt:** Wachwerk öffnen
- **Gesehen** = derselbe Anlass meldet sich erst wieder, wenn er erledigt war und neu auftritt. **Später** = bis dahin Ruhe, dann erneut, falls noch aktuell.
- Jeder Knopf wirkt einmal und nur 12 Stunden; danach passiert nichts. Im Protokoll steht, wer ihn gedrückt hat („Knopf in der Nachricht · Jens“). Eine neue Nachricht zum selben Anlass ersetzt die alte auf dem Handy.
- Unter Benachrichtigungen zeigt die Vorschau je Anlass die Knöpfe mit. Andere Kanäle (Pushover, Telegram, Ansagen …) bleiben unverändert.

### Geändert – überall dasselbe Muster
- **Zahnrad oben im Fenster** führt zu den Einstellungen des Geräts: Raum (Heizwerk-Schnellmenü), Rollladen, Leuchte, Mähroboter, Bewässerung, Termine.
- **„Warum so?“ mit „Rückgängig“:** Rollladen- und Leuchten-Fenster zeigen oben den Grund, die letzte automatische Änderung („Zuletzt 16:42: 20 % offen · Beschattung“) und – bis 3 Stunden danach – **Rückgängig** (zurück auf die Stellung bzw. den Zustand davor; danach wartet die Automatik wie nach jeder Änderung von Hand). Heizwerk zeigt „Warum“ wie bisher im Schnellmenü.

## 0.92.0 – 2026-11-22

### Neu – Heizwerk › Therme
- **Eigener Reiter „Therme“** zwischen Lüften und Bericht. Heizwerk erkennt die Therme (myVaillant u. Ä.: Vorlauf-Soll, Heizkurve, Raumsoll, Fußpunkt, Heizgrenze, Außenfühler, Anlagendruck, Zustand, Warmwasser, Störung) und die eigenen Fühler: Vorlauf/Rücklauf der Fußbodenheizung am Namen, den Heizkreis-Fühler am selben Gerät (z. B. Shelly mit drei Fühlern). Alles wählbar unter Heizwerk › Einstellungen › Therme & Heizkurve.
- **Thermengrafik:** Therme mit Flamme (bewegt sich beim Heizen), Vorlauf und Rücklauf mit Temperaturen und Soll, Heizkörper, Mischer und Fußbodenheizung mit Vorlauf, Rücklauf und Spreizung, Warmwasserspeicher (Ist/Soll) und Anlagendruck als Anzeige.
- **Heizkurve:** die Kurve der Therme (Steilheit, Raumsoll, Fußpunkt, Heizgrenze) neben einer **Beispiel-Heizkurve** nach Auslegung – Heizkörper (Standard 55 °C bei −12 °C) und Fußbodenheizung (35 °C) – und den **gemessenen Stundenwerten der letzten 14 Tage** (Vorlauf-Soll, Heizkreis, FBH-Vorlauf) aus den Statistiken. Tabelle bei −10, 0 und 10 °C außen.
- **Abgleich in Worten,** je mit dem, was zu tun ist: Raumsoll der Therme höher als die Räume brauchen (hebt die ganze Kurve an), Kurve steiler oder flacher als das Beispiel – abgestimmt mit dem Bericht › Heizleistung (nicht flacher stellen, solange ein Raum knapp ist), Abweichung der Therme von der Formel, Heizkreis unter Soll, Fußbodenheizung zu heiß bzw. Spreizung, Anlagendruck, Störung.

## 0.91.0 – 2026-11-22

### Neu (Heizwerk › Bericht)
Jeder neue Bericht endet mit einer Zeile, was zu tun ist.
- **Verbrauch nach Wetter:** Gasverbrauch je Tag mit Gradtagen (wie kalt es war) und **kWh je Gradtag** im Vergleich zum Zeitraum davor – z. B. „Wetterbereinigt 7 % sparsamer“. Kosten, wenn im Energie-Dashboard ein Preis eingetragen ist. Der Zähler kommt aus dem Energie-Dashboard (Gas) bzw. dem ersten Gaszähler; m³ werden mit dem Faktor von der Gasrechnung umgerechnet (Heizwerk › Einstellungen › Gaszähler für den Bericht, Standard 10,3 kWh/m³).
- **Anteil je Raum:** wohin die Wärme geht – geschätzt aus der Ventilöffnung, mit kWh und Kosten je Raum.
- **Pünktlich warm:** je Raum, ob er zu Beginn der Komfortzeit warm genug ist bzw. wie viele Minuten später, ob er gar nicht warm wurde oder unnötig früh – mit Tipp „früher“ bzw. „kürzer vorheizen“. Zählt ab jetzt; erste Aussage nach zwei Komfort-Beginnen.
- **Was das Absenken bringt:** Stunden und geschätzte kWh für Eco laut Heizplan, niemand zu Hause, Urlaub und Fensterpause. Gezählt wird, wie viel kühler der Raum wirklich war, nicht der eingestellte Wert. Zählt ab jetzt.
- **Geräte:** was jetzt Aufmerksamkeit braucht (Batterie, nicht erreichbar) und was in den letzten Tagen auffiel (z. B. „übernimmt den Sollwert nicht“, 3×).

### Geändert
- **Raum hinter dem Gerät:** Leuchten heißen in Lichtwerk-Bericht, Kopfkachel, Tablet-Kachel, „Licht an, niemand zu Hause“ und im Check beim Gehen jetzt z. B. „Fenster · Wohnzimmer“ – außer der Raum steckt schon im Namen. Ebenso die Geräte im neuen Heizwerk-Bericht.

## 0.90.0 – 2026-11-22

### Behoben (Heizwerk › Bericht › Heizleistung)
- **„Überheizt“ war fast immer zu hoch:** Gezählt wurde auch die Eco-Zeit – nach dem Absenken ist ein Raum aber natürlich noch Stunden wärmer als sein Eco-Wert. Jetzt zählt „zu warm“ nur in der Komfortzeit. Ältere Tage, die das noch nicht unterscheiden, bleiben dafür außen vor (der Wert erscheint wieder, sobald genug neue Tage da sind).
- **Nach dem Lüften kein „zu kalt“ mehr:** Die Aufheizzeit nach dem Schließen des Fensters (Heizkörper 30 Min., Fußbodenheizung 3 Std.) zählt nicht mehr gegen „warm genug“.
- **Keine widersprüchlichen Aussagen mehr:** kein „Reserve“ (Vorlauf senken) zusammen mit „bei Frost zu kalt“ (Heizkurve anheben); kein „heizt schnell auf“ bei „zu schwach“; „braucht lange zum Aufheizen“ bei einem Raum, der trotzdem warm wird, nur als Hinweis statt Warnung; zu kalt und zu warm zugleich heißt jetzt „Mal zu kalt, mal zu warm“ (Temperatur schwankt). „Bei Frost zu kalt“ erst, wenn es dort unter 85 % liegt. Fehlen Ventilwerte, behauptet der Bericht keine Ursache mehr (vorher „Ventil im Schnitt ? %“).
- „Ventil ganz auf“ kann nicht mehr über 100 % liegen.

### Geändert – klarere Sprache
- Urteile: **Passt**, **Passt · Reserve**, **Knapp**, **Zu schwach** (statt „Reicht nicht“), **Thermostat prüfen** (statt „Messung prüfen“).
- Kennzahlen: **Warm genug** (statt „Komfort erreicht“) und **Zu warm** (statt „Überheizt“), jeweils „der Komfortzeit“; **Ventil offen Ø …** mit „… % der Heizzeit ganz auf“; „Warm genug bei Frost / mild“.
- Hinweise sagen, was es bedeutet und was hilft, z. B. „Zu kalt, aber das Ventil bleibt fast zu – das Thermostat regelt zu früh ab, vermutlich misst es am Heizkörper zu warm“. Zahlen mit deutschem Komma.

## 0.89.0 – 2026-11-22

### Neu (Termine)
- **Übersicht der Termine:** Ein Tipp auf die Kachel „Termine“ (Tablet-Startseite) bzw. „Alle“ im Widget „Termine“ öffnet die nächsten 14 Tage aus allen Kalendern – nach Tagen gruppiert (Heute, Morgen, Wochentag mit Datum), mit Uhrzeit von–bis bzw. „ganztägig“, Ort und Kalender; Müll mit Symbol je Abfallart, laufende Termine markiert.
- **Zahnrad** oben im Fenster führt zu den Kalender-Einstellungen (vorher öffnete die Kachel direkt die Einstellungen).

## 0.88.0 – 2026-11-22

### Neu (Hauswerk › Wochenbericht)
- **Wochenbericht mit KI formulieren** (optional, Einstellungen › Haus › Wochenbericht): Über die Home-Assistant-Schnittstelle „AI Task“ (z. B. OpenAI, Google, Ollama) wird aus dem Bericht ein kurzer Text mit Zusammenhängen und einem Tipp – z. B. „Das Kinderzimmer war 23× offen und hat dadurch gut 20 % mehr geheizt als in der Vorwoche. Tipp: lieber 5 Min. stoßlüften statt kippen.“
- **Die Zahlen rechnet weiter Hauswerk:** je Raum Heizstunden, Fensteröffnungen und Fensterpause mit Vorwoche, Ø Temperatur, Heizleistung und Auffälligkeiten, Außentemperatur mit Vorwoche, Licht je Leuchte mit „von Hand“ und Vorschlägen, dazu Energie, Mähen, Klingel und Wartung. Die KI bekommt nur diese Fakten und die Vorgabe, nichts zu erfinden.
- **Sicher im Alltag:** Antwortet die KI nicht (Netz, Kontingent, 90 s Zeitlimit), kommt der normale Bericht; im Protokoll steht „Wochenbericht ohne KI“. An den KI-Dienst gehen Raum- und Gerätenamen und Wochenwerte, keine Personen.
- **Vorschau: normal und mit KI** nebeneinander im Fenster; die KI-Entität ist wählbar (leer = erste gefundene).

## 0.87.0 – 2026-11-22

### Neu (Lichtwerk › Leuchte antippen)
- **Farbe und Weißton von Hand:** Kann eine Leuchte Farbe bzw. Farbtemperatur, zeigt ihr Fenster neben der Helligkeit jetzt
  - **Vorschläge** – Stimmungen mit passender Helligkeit: Gemütlich, Abendessen, Lesen, Konzentriert (Weißtöne) sowie Fernsehen, Kaminfeuer, Sonnenuntergang, Weihnachten und Party (Farbe),
  - **Weißton:** Kerze, Warmweiß, Hellweiß, Neutral, Tageslicht – im Bereich, den die Leuchte kann,
  - **Farbe:** zehn Farbtupfer (Kaminfeuer, Bernstein, Rot, Rosa, Lila, Blau, Eisblau, Türkis, Grün, Gelb) und „Eigene“ mit Farbwähler.
- Ein Tipp schaltet sofort, das Fenster bleibt offen zum Ausprobieren; die aktuelle Farbe ist markiert. Gilt als „von Hand“ (Automatik wartet wie beim Dimmen) und steht mit Farbe im Protokoll. Leuchten, die nur an/aus können, zeigen wie bisher nur die Knöpfe.

## 0.86.1 – 2026-11-22

### Behoben
- Prüfung von Home Assistant (hassfest): Der Wochenbericht liest das Energie-Dashboard – „energy“ ist jetzt als optionale Abhängigkeit eingetragen. Bitte direkt 0.86.1 installieren; alles Neue aus 0.86.0 steht unten.

## 0.86.0 – 2026-11-22

### Neu: Modul Wachwerk (Sicherheit)
- Findet **Rauch-, CO- und Wassermelder**, **amtliche Warnungen** (NINA, DWD), **Türen & Tore**, die **Alarmanlage** (z. B. Alarmo) und die **Klingel** automatisch.
- **Rauch oder CO:** wichtige Nachricht (auch in der Ruhezeit), alle Rollläden fahren hoch und alle Lichter gehen auf 100 % – als Fluchtweg (beides abschaltbar). **Wasser:** wichtige Nachricht.
- Warnungen mit Überschrift und Text, Tür bzw. Tor lange offen, **Check beim Verlassen** (Türen, Fenster, Lichter), Klingel mit Kamerabild.
- Eigene Seite, Wand-Kacheln im Tabletmodus, Kachel auf der Tablet-Startseite, Zeile im Bildschirmschoner, Hinweise unter der Glocke, Protokoll-Filter und Einstellungen im Reiter Wachwerk.

### Neu: Hausdienste (ohne eigenes Modul)
- **Hausmodi** als Knöpfe auf der Startseite: „Gute Nacht“, „Guten Morgen“, „Wir gehen“, „Wir sind da“ – Lichter, Rollläden, Heizung (Eco), Anwesenheit, Mähroboter und Alarmanlage mit einem Tipp; danach steht da, was noch offen ist. Schritte je Modus unter Einstellungen › Haus › Hausmodi.
- **Wartung:** Aufgaben mit Intervall (Vorlagen wie Rauchmelder testen, Heizkörper entlüften, Filter …) mit „Erledigt“; automatisch dabei sind schwache Batterien, Melder am Lebensende und die Mähermesser. Fälliges steht unter der Glocke.
- **Wochenbericht:** einmal pro Woche (Standard Sonntag 18:00) je Modul eine Zeile – Heizen und Lüften, Energie, Licht, Mähen, Klingel und Warnungen, fällige Wartung. Mit Vorschau und „Jetzt senden“.
- Neue Benachrichtigungs-Anlässe unter Wachwerk und Hauswerk.

## 0.85.0 – 2026-11-22

### Neu (Beetwerk › Mähplan)
- **Feiertage aus dem Arbeitstage-Kalender:** Der Mähplan kennt jetzt Feiertage und Brückentage (Werktag, aber laut Workday-Kalender kein Arbeitstag – wie in Heizwerk und Rollwerk). Neue Auswahl **„An Feiertagen“**: *wie Sonntag* (Standard – ist Sonntag kein Mähtag, wird auch am Feiertag nicht gemäht), *nicht mähen (Feiertagsruhe)* oder *wie der Wochentag*.
- Im Mähplan der Mäher-Karte ist der Tag mit „*“ markiert und zeigt „Feiertag“; was dort ausfällt, holt Beetwerk an den nächsten Mähtagen nach. Ohne gewählten Arbeitstage-Kalender verweist das Fenster auf Einstellungen › Kalender.

## 0.84.0 – 2026-11-22

### Geändert (Tabletmodus, Beetwerk)
- **Beetwerk wie die anderen Module:** Die Seite Garten zeigt im Tablet Wand-Kacheln – je Kachel Name, eine große Zahl und eine Statuszeile, darunter große Knöpfe:
  - **Mähroboter:** Bild im Zustand, Akku in %, „Mäht · seit 42 Min.“ bzw. „In der Station · wartet – es regnet“ oder „Winterpause“; Knöpfe Mähen/Pause und Zur Station.
  - **Garten:** „frei“ oder „belegt“ (Kamera bzw. „Garten belegt“), Knöpfe 2 Std. belegt / Bis heute Abend bzw. Wieder frei.
  - **Je Bewässerungs-Zone:** Bedarf in Min. bzw. Restzeit beim Gießen, Bilanz; Knopf Gießen bzw. Stopp.
- Antippen öffnet die Details im Fenster: die Karte des Mähroboters mit Zeitplan/Mähplan und Mähzeiten bzw. die Bewässerung mit allen Zonen. Wie bei den anderen Modulen gilt Darstellung › Tabletmodus › Kacheln (Automatisch: Details nach dem ersten Antippen).

## 0.83.3 – 2026-11-22

### Behoben (Heizwerk › Fensterpause)
- **Wandthermostat wurde bei offenem Fenster nicht abgesenkt:** War ein Fensterkontakt in der CCU nur mit einem Heizkörper-Thermostat verknüpft (nicht mit dem Wandthermostat), überließ Heizwerk die Fensterpause des ganzen Raums der CCU – das Wandthermostat blieb auf dem alten Sollwert. Jetzt überlässt Heizwerk der CCU nur die Thermostate, mit denen der Fensterkontakt wirklich direkt verknüpft ist (ein verknüpftes Wandthermostat nimmt seine verknüpften Heizkörper mit). Alle anderen – ohne Verknüpfung also alle – senkt Heizwerk selbst auf die Fenstertemperatur. Die Ursache am Raum nennt beides („die CCU senkt … ab, Hauswerk senkt WTH Wohnzimmer“).
- Im Protokoll heißt eine Sollwert-Änderung bei offenem Fenster ohne Verknüpfung „Sollwert bei offenem Fenster“ statt „Fensterfunktion HmIP“; „HmIP“ an der Wand-Kachel nur, wenn die CCU das Wandthermostat selbst absenkt.

## 0.83.2 – 2026-11-22

### Geändert (Bildschirmschoner)
- **Beetwerk in der Winterpause:** nur noch die Schneeflocke – ohne Akku und ohne „winterpause“.

## 0.83.1 – 2026-11-22

### Behoben (Heizwerk)
- **Fensterfunktion der CCU galt als „von Hand“:** Ist der Fensterkontakt in der CCU direkt mit dem Thermostat verknüpft, senkt die CCU beim Öffnen sofort ab (z. B. auf 12 °C) – noch bevor Heizwerks Fensterpause beginnt. Heizwerk hielt das für eine Änderung von Hand („Manuell 12,0°“), die bis zum nächsten Planwechsel gegolten hätte, und stellte in der Wartezeit sogar zurück. Jetzt gilt: Ändert sich der Sollwert, während ein Fenster offen ist oder bis 3 Min. nach dem Öffnen/Schließen, ist das die Fensterfunktion („Fensterfunktion HmIP: 12,0 °C“ im Protokoll), kein „von Hand“. Den verknüpften Thermostaten sendet Heizwerk in dieser Zeit nichts.

### Geändert (Tabletmodus)
- **Fenster offen auf jeder Raumkachel:** oben rechts das Fenster-Symbol mit der Dauer („4 Min.“), die Kachel in Türkis. Senkt die CCU über die Direktverknüpfung ab, steht „Fenster offen · HmIP 12,0°“ (der Sollwert am Thermostat), sonst „Fenster offen“ mit Heizwerks Wert.

## 0.83.0 – 2026-11-22

### Neu (Heizwerk › Lüften)
- **Schlafzimmer: Fenster darf nachts offen bleiben.** Zwischen 21:00 und 07:30 (einstellbar unter Lüften & Schimmelschutz) gilt ein offenes Fenster im Schlafzimmer als gewollt: kein „Fenster schließen“, kein „Fenster lange offen“ und kein „Kippen kostet Wärme“. Die Heizung bleibt solange in der Fensterpause.
- Ist das Fenster am Morgen noch offen, kommt einmal „Fenster schließen – Nacht vorbei“. „Morgens lüften“ entfällt nach einer Nacht bei offenem Fenster.
- Raumkachel und Seite Lüften zeigen „Nachts bei offenem Fenster – gewollt“ mit Mond-Symbol. Die Nacht zählt in der Bilanz extra („2× nachts offen“) und verfälscht weder Lüftdauer, Wärme noch die gelernte Lüftdauer.
- Automatisch für Räume mit Raumart Schlafzimmer (bzw. „Schlaf“ im Namen); je Raum unter Raum › Lüften „Nachts bei offenem Fenster schlafen“ (Automatisch / Ja / Nein) – z. B. auch fürs Kinderzimmer.

## 0.82.1 – 2026-11-21

### Behoben (Lichtwerk)
- **Licht ging nach einem Neustart von Home Assistant an:** Bei Profilen mit dem Auslöser „Rollläden schließen“ meldeten sich die Rollläden nach dem Neustart zuerst als „nicht verfügbar“ – Lichtwerk wertete das als „offen“. Ihr erstes „geschlossen“ danach galt als Schließen: Das Licht ging an, auch wenn es vorher von Hand ausgeschaltet war. Jetzt zählt nur ein Schließen aus einem bekannten Stand (offen → geschlossen).

## 0.82.0 – 2026-11-21

### Neu – Beetwerk plant die Mähzeiten nach Wetter (Mähplan)
- **Wochenziel statt fester Zeiten** (Einstellungen › Beetwerk › Mähplan): z. B. 12 Std. je Woche, Mähtage Mo–Sa, erlaubt 9–19 Uhr. Nach Wachstum passt Beetwerk das Ziel an die vorhergesagte Temperatur an (unter 5 °C 20 %, ab 15 °C voll, über 26 °C etwas weniger).
- **Mähen in den trockenen Stunden:** Aus der Stunden-Vorhersage legt Beetwerk die Mähzeiten so, dass nicht bei Regen und 2 Std. danach, nicht bei Frost oder Hitze, nicht im Dunkeln (Igelschutz) und nicht nach dem Gießen gemäht wird. Stündlich neu gerechnet.
- **Nachholen:** Was an den letzten Tagen ausgefallen ist (Regen, Kinder im Garten …), legt Beetwerk auf die nächsten guten Stunden – höchstens zwei Tagesmengen.
- **Robust:** Der Plan wird in die Zeitpläne des Mähers geschrieben (Robonect: je Wochentag zwei, Zeitplan 1–14) – nur was sich ändert. Der Mäher fährt danach auch, wenn Home Assistant gerade nicht läuft. Deine bisherigen Zeitpläne merkt sich Beetwerk und stellt sie beim Ausschalten wieder her. Mäher ohne Zeitpläne startet Beetwerk selbst und holt sie am Ende heim.
- **In der Karte des Mähroboters:** Mähplan der nächsten 7 Tage als Leisten mit Mähzeiten, Regen, Nässe, Hitze und Igelschutz; Ziel, geplant, gemäht und was nachgeholt wird.
- Pausen bleiben als Sicherheitsnetz: Danach schaltet Beetwerk den Mäher mit Mähplan in den Automatik-Modus (statt „Mähen“), damit er wieder seinen Zeitplänen folgt.

## 0.81.1 – 2026-11-21

### Geändert (Beetwerk › Garten)
- **Zeitplan und Mähzeiten gehören zum Mähroboter:** Sie stehen jetzt unten in der Karte des Mähroboters statt als eigene Kacheln – Zeitplan (Wochenleiste, an/aus, ändern) und Mähzeiten (Stunden je Tag, Ladevorgänge, Fehler). Die Seite Garten hat damit nur noch zwei Karten: Mähroboter und Bewässerung.

## 0.81.0 – 2026-11-21

### Neu – Benachrichtigungen mit Emoji
- Vor jedem Titel steht dezent ein passendes Emoji – auf einen Blick erkennbar: 🪟 Fenster lange offen / Fenster schließen, 🌧️ Fenster offen – Regen, 💨 Sturm, ❄️ Frost, 🪫 Batterie schwach, 📡 nicht erreichbar, 🌡️ Heizkörper bleibt kalt, 🌬️ Lüften empfohlen, 💡 Licht an, niemand zu Hause, 🆘 Mähroboter braucht Hilfe, 🧒 Mäher fährt heim, 🌙 nachts nicht in der Station, 🔧 Wartung, 🌱 Saison starten, 🗑️ Müllabfuhr, 🧺 Waschmaschine fertig, 👕 Trockner, 🍽️ Spülmaschine, ✅ andere Geräte fertig, 📬 gebündelte Meldungen, 👋 Testnachricht.
- Nur im Titel, der Text bleibt sachlich; Ansagen über Lautsprecher bleiben ohne. Abschaltbar unter Benachrichtigungen › Empfänger › „Emojis in Benachrichtigungen“. Die Vorschau je Anlass zeigt es mit.

## 0.80.1 – 2026-11-21

### Behoben
- **Hauswerk startete mit 0.80.0 nicht:** Ein Befehl für die Mäher-Zeitpläne war vor seiner Rechteprüfung eingetragen – Home Assistant konnte die Integration nicht laden. Bitte direkt auf 0.80.1 aktualisieren. Alles Neue aus 0.80.0 steht unten.

## 0.80.0 – 2026-11-21

### Neu – Beetwerk: mehr für den Mähroboter
- **Mäher mit Bild:** Die Karte auf der Seite Garten zeigt einen gezeichneten Mähroboter, der seinen Zustand zeigt – fährt (Räder und Messer drehen), lädt (Blitz), in der Station, Regen-, Hitze- oder Igelpause (Symbol des Grundes), Fehler (rot), Winterpause. Dazu „Mäht seit 42 Min.“, Akku als Balken und der nächste Start laut Zeitplan.
- **Garten frei – Kinder und Tiere:** Meldet ein Person- oder Haustier-Sensor im Garten (z. B. die Kamera) etwas, während der Mäher fährt, schickt Beetwerk ihn in die Station. Ist 30 Min. (einstellbar) niemand mehr zu sehen, startet er wieder. Wahlweise Nachricht „Mäher fährt heim“ mit Kamerabild in der Home-Assistant-App (Benachrichtigungen › Beetwerk, Standard: nur Protokoll). Auf der Seite Garten „2 Std. belegt“ und „Bis heute Abend“, z. B. zum Grillen.
- **Igelschutz:** Zwischen Sonnenuntergang und Sonnenaufgang (Puffer einstellbar) wird nie gemäht – mäht der Roboter im Dunkeln, schickt Beetwerk ihn in den Feierabend; am nächsten Tag mäht er nach seinem Zeitplan weiter.
- **Hitzepause** ab 30 °C draußen (weiter ab 2 °C kühler) und **Saison-Hinweise:** „Winterpause einlegen?“ nach 3 kalten Tagen im Herbst, „Saison starten?“ nach 5 milden Nächten im Frühjahr.
- **Zeitpläne:** Die Zeitpläne des Mähers (Robonect, 14 Stück) als Wochenleiste mit der Igelschutz-Zeit; je Zeitplan an/aus und ändern (Uhrzeit, Wochentage) – gespeichert am Mäher.
- **Verschleiß:** Hinweise unter der Glocke bei stumpfen Messern (Messerqualität bzw. Messer-Drehzahl deutlich unter dem Üblichen), alterndem Akku (Kapazität unter 70 % der besten), schwachem Signal des Begrenzungsdrahts, schwachem WLAN und Feuchte im Gehäuse.
- **Wächter:** Nachricht mit Kamerabild, wenn der Mäher außerhalb der Station keine Verbindung mehr hat, 20 Min. im Garten steht oder nachts ab 22 Uhr nicht in der Station ist.
- **Statistik:** Mähstunden je Tag (14 Tage), Ladevorgänge, Fehler und die häufigsten Fehler mit Uhrzeit („3× Mäher steckt fest, meist 14–16 Uhr“).
- **Widget „Mähroboter“** für die Startseite und eine Zeile im Bildschirmschoner („wartet – jemand im Garten“).
- Einstellungen › Beetwerk: neu „Garten frei & Igelschutz“ und „Hitze, Saison & Wächter“.

## 0.79.0 – 2026-11-21

### Neu – Wer treibt den Duty Cycle hoch?
- **Wer funkt am meisten** (Einstellungen › System › Funk-Auslastung): die Homematic-Geräte mit den meisten Befehlen in der letzten Stunde und den letzten 24 Stunden – mit Herkunft je Befehl: Heizwerk, Rollwerk, Lichtwerk, Beetwerk, Automation „…“ bzw. Skript „…“, von Hand (App) oder andere Integration. Gezählt wird jeder Befehl aus Home Assistant an ein Homematic-Gerät, seit dem letzten Neustart; Programme und Direktverknüpfungen in der CCU selbst sieht Home Assistant nicht.
- **Verlauf der Auslastung** der letzten 24 Stunden (alle 5 Min.) mit der Drossel-Grenze als Linie.
- In der Einstellungsliste steht das Gerät, das gerade am meisten funkt.

### Behoben – Heizwerk sendet nicht mehr im Kreis
- Übernimmt ein Thermostat einen Sollwert nicht – das Gerät antwortet nicht oder eine Verknüpfung in der CCU stellt ihn zurück –, sendete Heizwerk jede Minute erneut (und nach dem Zurückfallen sogar sofort). Das trieb den Duty Cycle der CCU bis 99 %. Jetzt wartet Heizwerk nach jedem Befehl die Bestätigung ab, sendet denselben Wert höchstens zweimal, dann erst nach 15 Min. und danach stündlich.
- Hinweis unter der Glocke und in der Funk-Auslastung: „Thermostat übernimmt den Sollwert nicht – 7,0 °C 3× gesendet, bleibt bei 12,0 °C · nächster Versuch 21:40“; im Protokoll „… übernimmt den Sollwert nicht“ bzw. „… wieder“. Sobald der Wert steht, geht es normal weiter.
- **Warnung bei widersprüchlicher Rolle:** Ein Heizkörper, der als Zusatzheizung (oder „Selbst“) gewählt ist, in der CCU aber mit dem Wandthermostat verknüpft ist, wird gemeldet – beide stellen sonst gegeneinander. Abhilfe: Rolle „Folgt Wand“ oder die Verknüpfung in der CCU lösen.

## 0.78.1 – 2026-11-21

### Neu (Beetwerk › Bewässerung)
- **Mehrere Ventile je Zone** (z. B. bei zu wenig Wasserdruck): Unter Einstellungen › Beetwerk › Bewässerung je Zone „Weiteres Ventil“. Die Ventile gehen nacheinander an, jedes für die berechnete Zeit; die Wasserbilanz wird erst zurückgesetzt, wenn das letzte fertig ist. Das Protokoll nennt Ventil 1/2, 2/2.
- **Ablauftimer:** Während gegossen wird, zeigt die Seite Garten groß „Fertig in 19:59“ (alle Ventile), je Zone „gießt Ventil 1/2 (Garten Links) noch 9:59 · Zone fertig in 19:59“, wartende Zonen „kommt gleich dran“; in der Kopfkachel „fertig um 05:40 Uhr“.

## 0.78.0 – 2026-11-21

### Neu – Beetwerk gießt mit Smart Irrigation
- **Zonen aus Smart Irrigation** stehen auf der Seite Garten: je Zone der berechnete Bedarf („braucht 12 Min. Wasser“), die Wasserbilanz in mm, das Ventil und – während gegossen wird – ein Countdown.
- **Bedienen je Zone:** „12 Min. gießen“ (berechnete Dauer, sonst 10 Min.), Multiplikator − / +, „Berechnen“ und „Bilanz 0“. Dazu „Alle mit Bedarf gießen“ und „Gießen stoppen“.
- **Gießplan (Einstellungen › Beetwerk › Bewässerung):** Beetwerk gießt täglich zur Startzeit (Standard 05:00) alle Zonen mit Bedarf nacheinander – Ventil auf für die berechnete Dauer, danach zu und Wasserbilanz zurück auf 0. Bei Regen jetzt oder in den nächsten 6 Stunden wird ausgelassen (abschaltbar). Der Mäher fährt solange in die Station und wartet danach. Alles im Protokoll (Filter Beetwerk). Übersteht Neustarts: eine laufende Zone wird beendet und das Ventil geschlossen.
- **Ventil je Zone:** Die Ventile von Smart Irrigation selbst sind nur Platzhalter – Beetwerk ordnet das echte Ventil (valve oder Schalter) über den Namen zu (z. B. Zone „Beet Links“ ↔ „Beet_Links“) oder du wählst es je Zone aus. Je Zone abwählbar aus dem Gießplan.
- **Bisherige Bewässerungs-Automationen** werden aufgelistet und lassen sich mit einem Tipp abschalten, damit nicht doppelt gegossen wird.
- Wetterquellen, Berechnung, Fläche, Durchfluss und Bodenart bleiben in Smart Irrigation (Link im Fenster).

## 0.77.0 – 2026-11-21

### Neu – Modul Beetwerk (Garten)
- **Eigenes Modul** mit grünem Logo in der Leiste (Handy, Tablet, PC), Seite **Garten** und Reiter **Beetwerk** unter Einstellungen. Ersetzt den Platzhalter „Garten – geplant“.
- **Mähroboter** (lawn_mower, z. B. Gardena/Husqvarna mit Robonect): Zustand (mäht, in der Station, pausiert, fährt zurück, Fehler), Akku, Status-Text, Messer-Tage, Betriebsstunden. Knöpfe **Mähen**, **Pause**, **Zur Station** – mit Robonect zusätzlich **Feierabend** und **Winterpause / Saison starten**. Mäher und Geräte-Entitäten werden automatisch gefunden.
- **Mähpause:** Mäht der Roboter bei **Regen**, **nassem Boden** (Bodenfeuchte ab 85 %), **Frost** (unter 3 °C) oder **während/nach dem Bewässern** (60 Min.), schickt Beetwerk ihn in die Station. Ist der Grund 60 Min. vorbei, startet er wieder (bis 19 Uhr, nur wenn Beetwerk pausiert hat). Alles einstellbar unter Einstellungen › Beetwerk › Mähpause; jede Pause steht im Protokoll (Filter Beetwerk).
- **Bewässerung:** Ventil (valve oder Schalter) auf/zu, Bodenfeuchte, „Gießen nötig“ und „gießt gerade“ (z. B. Smart Irrigation), Wasserbilanz.
- **Benachrichtigungen:** „Mähroboter braucht Hilfe“ bei Fehlern (Standard: wichtig) und „Messer wechseln“ nach 60 Tagen (Standard: nur Glocke) – unter Benachrichtigungen › Beetwerk.

## 0.76.1 – 2026-11-21

### Behoben (Kraftwerk › Verbraucher)
- **Name sofort vergeben:** Ein neu hinzugefügter Verbraucher bekommt gleich sein Namensfeld unter „Namen und Symbole“ – nicht erst nach Speichern und erneutem Öffnen.

### Neu
- **Geräte der Fertigerkennung sind automatisch Verbraucher:** Waschmaschine, Trockner & Co. aus Kraftwerk › Geräte erscheinen mit ihrem Namen und Symbol unter „Verbraucher jetzt“, in der Grundlast und in der Suche – ohne sie zusätzlich als Verbraucher einzutragen. Im Fenster Verbraucher stehen sie unter „Aus der Fertigerkennung – automatisch dabei“.

## 0.76.0 – 2026-11-21

### Neu – Lüften mit Rollwerk
- **Beim Lüften ganz öffnen:** Neue Option im Rollwerk-Profil unter Fenster & Lüften: Ist ein Fenster des Raums offen (Kontakt aus Heizwerk oder eigener „gekippt“-Kontakt), fährt der Rollladen ganz auf statt auf die Lüftungsstellung. Nach dem Schließen des Fensters fährt er zurück auf die Sollstellung (z. B. wieder zu). Ohne die Option wie bisher Lüftungsstellung.
- **Fenster offen bei Sturm oder Regen:** Nachricht „Fenster offen – Sturm“ bzw. „Fenster offen – Regen“ je Fenster (Anlass Sturm unter Benachrichtigungen) – für Fenster in Räumen mit Rollläden. Bei Sturm fahren die Rollläden wie bisher hoch, bei Regen bleibt der Rollladen auf Lüftungsstellung und fährt nicht herunter.

### Entfernt
- **Kosten je Lüftung** (aus 0.75.0) samt Einstellung Wärmepreis – die Wärmemenge (kWh) beim Dauerkippen und im Bericht bleibt.

## 0.75.0 – 2026-11-21

### Neu – Lüften in Heizwerk
- **Lüftdauer lernen statt Tabelle:** Aus jeder Lüftung misst Heizwerk je Raum, wie schnell die Feuchte zur Außenluft hin fällt (Luftwechsel). Ab drei Messungen gilt die gelernte Dauer – bis die Feuchte 10 % unter der Grenze liegt (ohne Feuchte-Anlass etwa 85 % Luftaustausch), 3–30 Min. Empfehlung und Lüft-Timer nutzen sie („gelernt“), die Raumkarte zeigt „gelernte Lüftdauer“; im Protokoll steht „Lüften gelernt“. Ohne Feuchtesensor bleiben die Richtwerte.
- **Nur lüften, wenn es hilft:** Ist es drinnen feucht, die Luft draußen aber nicht trockener (schwül, Nebel), kommt keine Empfehlung wegen Feuchte. Die Raumkarte sagt „Feucht – aber Lüften trocknet gerade nicht“ und, aus der Stunden-Vorhersage, „ab 21:00 Uhr trockener“. CO₂ und morgens lüften gelten weiter.
- **Beste Lüftzeit:** Aus der Stunden-Vorhersage des Wetterdienstes (Temperatur, Feuchte, Regen) die besten Zeiten der nächsten 24 Stunden – je eine am Vormittag und am Nachmittag/Abend: kein Regen, trockene Luft, möglichst wenig Wärmeverlust. Steht in der Kopfkachel der Seite Lüften („Am besten lüften: 9:00 (8°, 0,5 ct) · 14:00 …“). In der Sommerpause aus.
- **Kosten je Lüftung:** Wärmepreis unter Lüften & Schimmelschutz (Standard 12 ct/kWh). Laufende Lüftung „bisher ca. 0,05 kWh, 0,6 ct“, zuletzt gelüftet mit Kosten, 7 Tage in €, beim Dauerkippen „gekippt kostet ca. … je Stunde“; Bericht › Lüften · 7 Tage mit Spalte Kosten.

## 0.74.3 – 2026-11-21

### Geändert (Lichtwerk › Einstellungen)
- **Lichter-Liste:** Leuchten ohne Profil werden nicht mehr ausgegraut und tragen keine Marke. Leuchten mit Profil tragen den Profilnamen als Etikett neben dem Namen (z. B. „Abendlicht“); darunter steht der Raum.

## 0.74.2 – 2026-11-21

### Neu (Lichtwerk)
- **Vorschläge beim eigenen Symbol:** Beim Eintippen erscheinen passende Symbole zum Antippen – nach englischem Namen („lamp“, „ceiling“) oder deutschem Stichwort („Lampe“, „Kerze“, „Decke“, „Gong“, „Steckdose“, „Weihnacht“ …), aus rund 200 Symbolen für Licht, Haus und Geräte. Ein beliebiger anderer mdi-Name lässt sich weiter direkt eintragen.

### Geändert (Lichtwerk)
- **„Kein Profil“ je Leuchte:** In der Profil-Auswahl der Leuchte (und „Profil für alle“ im Raum) gibt es oben „Kein Profil“ – Lichtwerk zeigt die Leuchte dann nur an und schaltet sie nicht; HmIP-Direktverknüpfungen schalten weiter. Ersetzt den Schalter „Profil aktiv“; das bisherige Profil bleibt gemerkt. In der Liste steht „Kein Profil – nur anzeigen“ mit der Marke KEIN PROFIL.

## 0.74.0 – 2026-11-21

### Neu (Lichtwerk)
- **Eigenes Symbol je Leuchte:** Unter Einstellungen › Lichtwerk › Leuchte › **Symbol** aus 24 Symbolen wählen (Deckenleuchte, Kronleuchter, Stehlampe, Schreibtischlampe, Wandleuchte, LED-Streifen, Lichterkette, Kerze, Außenleuchte, Steckdose, Gong …) oder ein eigenes `mdi:`-Symbol eintragen. „Auto“ = Glühbirne wie bisher.
- Das Symbol erscheint überall: Einstellungsliste, Kacheln (detailliert, kompakt, Räume, Wand-Kacheln am Tablet), Helligkeitsfenster, Widget „Licht“, Homematic-Übersicht und Suche. Nicht erreichbare Leuchten zeigen weiter das Warnzeichen.

## 0.73.2 – 2026-11-21

### Geändert
- **Einstellungen:** Der Reiter „Haus“ trägt das Hauswerk-Logo, „System“ ein gut sichtbares Zahnrad.

## 0.73.1 – 2026-11-21

### Geändert
- **Einstellungen nur noch an einer Stelle:** Die Reiter „Einstellungen“ in Heizwerk, Rollwerk, Kraftwerk und Lichtwerk entfallen. Alle Einstellungen stehen unter dem Zahnrad (bzw. „Einstellungen“ in der Leiste) mit den Reitern Haus · Heizwerk · Rollwerk · Kraftwerk · Lichtwerk · System; dort ist dann das Zahnrad markiert. Alte Adressen wie `/hauswerk/rollwerk/einstellungen` funktionieren weiter.

### Behoben (Tabletmodus)
- **Einstellungen abgeschnitten:** Die Einstellungsseiten wurden auf eine Bildschirmseite gezwängt – Gruppen wurden zwischen den Spalten geteilt und unten abgeschnitten. Jetzt stehen sie vollständig in zwei Spalten (keine Gruppe geteilt) und lassen sich innen scrollen; ist rechts eine Einstellung geöffnet, in einer Spalte.

## 0.73.0 – 2026-11-21

### Neu – Einstellungen übersichtlicher
- **Ein Einstieg:** Oben in jeden Einstellungen die Reiter Haus · Heizwerk · Rollwerk · Kraftwerk · Lichtwerk · System. Zahnrad und die Reiter „Einstellungen“ der Module landen auf derselben Seite, nur im passenden Reiter. Die Zeilen „Module“ und „Zentrale Einstellungen“ entfallen.
- **Nach Häufigkeit geordnet:** oben „Oft gebraucht“ (Anwesenheit, Urlaub & Abwesenheit, Benachrichtigungen, Heizpläne, Tablet), darunter die Bereiche (Einrichten, Darstellung, Heizen, Räume …), ganz unten zugeklappt „Feinheiten“ (Frostschutz, Boost, Entkalken, Kalibrierung, Wärmeanforderung, Funk, Nach Neustart, Protokoll …).
- **Prüfen:** Was Aufmerksamkeit braucht (z. B. keine Personen gewählt, Homematic-Hinweise, Sensor nicht erreichbar), steht oben in einem eigenen Block.
- **Wert rechts:** jede Zeile mit ihrem Wert rechtsbündig – „2 Personen“, „5,0 °C“, „30 Min.“, „lernend“, „Mo 10:00“ –, die Beschreibung einzeilig darunter.
- **Doppeltes zusammengelegt:**
  - **Urlaub & Abwesenheit** ist ein Fenster: wann Urlaub ist (Zeitraum/Kalender) und darunter, was Heizwerk tut (absenken, Thermostate aus, Urlaubstemperatur, Frostschutz) – mit Verweis auf die Profile von Rollwerk und Lichtwerk. Erreichbar unter Haus und unter Heizwerk.
  - **Homematic-Verknüpfungen** von Heizwerk und Lichtwerk in einem Fenster unter System (umschaltbar).
  - **Lüften & Schimmelschutz** steht nur noch im Reiter Lüften („Einstellen“); die Suche findet es weiter.
- **Dieses Tablet:** eigene Zeile bzw. eigenes Fenster für Startseite, Kacheln, Bildschirmschoner, Nacht, Sperre und „Zurück zur Startseite“ – auf anderen Geräten „Als Tablet verwenden“. Darstellung verweist darauf.
- **Sofort gespeichert:** Schalter, Auswahllisten und Umschalter in den Einstellungs-Fenstern speichern ohne „Speichern“ – mit Meldung „Gespeichert · Rückgängig“. Zahlen- und Textfelder weiter mit „Speichern“.
- **Lange Fenster mit Sprungmarken** (z. B. Darstellung, Benachrichtigungen, Urlaub & Abwesenheit); auf breiten Bildschirmen stehen die Abschnitte zweispaltig.
- **PC und Tablet quer (ab 1100 px):** Das Fenster einer Einstellung öffnet rechts neben der Liste statt darüber – die Liste bleibt sichtbar.
- **Experte** als kleiner Schalter neben der Suche statt der großen Karte; Experten-Zeilen tragen ein kleines Symbol.
- **Suche findet auch Werte** („17 °C“, „lernend“), ein Treffer öffnet das Fenster direkt an der passenden Stelle und hebt sie kurz hervor. Ohne Suche steht oben „Zuletzt geändert“ mit den letzten drei Einstellungen dieses Bereichs.

## 0.72.6 – 2026-11-21

### Geändert (Tabletmodus, Heizwerk)
- **Soll-Temperatur in der Raumkachel:** hinter der Betriebsart steht die eingestellte Soll-Temperatur – „Komfort 21,0° · bis 21:00“, „Eco 18,0° · Komfort ab 18:00“.

## 0.72.5 – 2026-11-21

### Geändert (Tabletmodus, Heizwerk)
- **Betriebsart mit Symbol in der Raumkachel:** Die Statuszeile zeigt jetzt zuerst, ob der Raum gerade auf Komfort (Sofa) oder Eco (Blatt) steht – bzw. Vorheizen, Fenster, Von Hand, Abwesend … –, dahinter den nächsten Wechsel: „Komfort · bis 21:00“, „Eco · Komfort ab 18:00“.

## 0.72.4 – 2026-11-21

### Geändert
- **Tagesleiste in den Fenstern besser lesbar:** Uhrzeiten unter der Leiste (z. B. Rollwerk › Raum, „Höhe einstellen“) mit mehr Abstand zur Leiste und größerer Schrift (15 px); Stufe 1 rutscht in eine eigene Zeile, damit sich nichts überlappt. Profilnamen über der Leiste ebenfalls größer.

## 0.72.3 – 2026-11-21

### Geändert (Heizwerk, kompakte Raumkacheln)
- **Feste Plätze in jeder Kachel:** Der Name hat immer Platz für zwei Zeilen, die Zeile für Symbole (Ventil, Lüften, Fenster, Feuer) ist auch ohne Symbole reserviert. Temperatur, Soll, Betriebsart und Tagesleiste stehen dadurch in allen Kacheln einer Reihe auf derselben Höhe – auch ohne Heizplan bleibt der Platz der Leiste frei.

## 0.72.2 – 2026-11-21

### Geändert (Rollwerk)
- **Größere Knöpfe im Fenster „Höhe einstellen“:** ↑ ■ ↓ nebeneinander als große Tasten (64 px hoch, Symbol 32 px), die Behanghöhen (Offen, Halb offen …) als deutlich sichtbare Knöpfe mit 60 px Höhe und größerer Schrift.
- Im Raum-Fenster (mehrere Rollläden) haben ↑ ■ ↓ je Rollladen 56 px große Tasten.

## 0.72.1 – 2026-11-21

### Neu – Tagesleiste in den Fenstern hinter den Kacheln
- **Heizwerk:** Das Fenster eines Raums („Manuell ändern“) zeigt den Tagesplan mit Vorheizen und „Komfort bis …“.
- **Rollwerk:** „Höhe einstellen“ zeigt die Tagesleiste des Profils mit Öffnet/Schließt-Zeiten; das Raum-Fenster eine Leiste je Profil der Rollläden (mit Profilname, wenn mehrere).
- **Lichtwerk:** Das Fenster einer Leuchte und das Raum-Fenster zeigen die Tagesleiste des Profils (mit Szenen), im Raum eine je Profil.
- Nur bei eingeschalteter Automatik bzw. aktivem Profil.

## 0.72.0 – 2026-11-21

### Geändert – Tabletmodus: Wand-Kacheln nach festem Muster
- **Wieder Standard im Tablet:** Heizwerk, Rollwerk und Lichtwerk zeigen große Wand-Kacheln. Die Detailkacheln gibt es unter Darstellung › Tabletmodus › Kacheln („Details“ oder „Automatisch“).
- **Jede Kachel:** Name, eine große Zahl (48 px) und genau eine Statuszeile (16 px). Zeitleisten, Ursachen und Ventilwerte erst beim Antippen im Fenster.
  - **Heizwerk:** „21,4°“ und „Komfort bis 21:00“ (bei Abweichung z. B. „Fenster offen“, „Von Hand“).
  - **Rollwerk:** Fenster-Grafik, „50 %“ groß, darunter nur ↑ und ↓ als große Knöpfe. Fährt der Rollladen, wird der Knopf seiner Richtung zu Stopp. Räume mit mehreren Rollläden: Mittel in % und „2 von 3 offen“.
  - **Lichtwerk:** Raumkachel mit „2 von 3 an“ und großem Schalter (64 px) für alle Lichter des Raums; Statuszeile Ablauftimer, sonst welche Lichter an sind.

## 0.71.1 – 2026-11-21

### Geändert
- **Tablet: wieder die gewohnten Modul-Kacheln.** Heizwerk, Rollwerk, Kraftwerk und Lichtwerk zeigen im Tabletmodus standardmäßig wieder die Kacheln mit allen Details. Die großen Wand-Kacheln gibt es weiter unter Darstellung › Tabletmodus › Kacheln (*Automatisch* oder *Immer groß*).

## 0.71.0 – 2026-11-21

### Neu – Tabletmodus, zweiter Teil
- **Wand-Startseite:** links große Uhr, Datum, Wetter und „Jetzt wichtig“ (bzw. „Alles in Ordnung“), rechts je eine große Kachel für Heizwerk (Ø-Temperatur, heizen, offen), Rollwerk (offen/zu, nächste Fahrt), Kraftwerk (Solar, Bezug/Einspeisung), Lichtwerk (wie viele an), Termine (Müll zuerst) und Anwesenheit. Eine Seite, kein Scrollen; Tipp öffnet das Modul. Die Widget-Startseite gibt es weiter („Widgets anzeigen“ bzw. Darstellung › Tabletmodus › Startseite).
- **Zwei Stufen – Wand und Details:** Unter Darstellung › Tabletmodus › Kacheln: *Automatisch* zeigt große Wand-Kacheln, bis jemand das Tablet berührt – dann die Kacheln mit allen Details bis zum Bildschirmschoner. Oder fest *Immer groß* bzw. *Immer Details*.
- **Rollläden und Lichter je Raum:** In der Wand-Ansicht eine Kachel je Raum – „2 / 3 offen“ mit ↑ ■ ↓ für alle Rollläden des Raums bzw. „2 / 3 an“ mit einer Lampe für alle Lichter. Antippen öffnet die einzelnen Rollläden bzw. Lichter. Räume mit nur einem Gerät zeigen dieses direkt.
- **Kraftwerk in zwei Spalten:** links der Energiefluss (und „Verbraucher jetzt“, nur wenn einer über 50 W zieht), rechts „Heute“ und die Solar-Prognose.
- **Größere Tippflächen:** Unterseiten-Umschalter 48 px hoch, beim Blättern Pfeile ‹ › neben den Seitenpunkten und „Seite 1 von 2“.
- **Zurück zur Startseite** nach 2 Minuten ohne Berührung (einstellbar: nie, 1, 2, 5 Min.), offene Fenster schließen sich – der Bildschirmschoner kommt erst danach.

## 0.70.0 – 2026-11-21

### Neu – Tabletmodus neu aufgeteilt
- **Modul-Leiste links:** Start, Heizwerk, Rollwerk, Kraftwerk, Lichtwerk und unten Einstellungen als große Tasten (mindestens 64 px) am linken Rand, mit Zahl bei heizenden Räumen bzw. offenen Fenstern. Die Reiter oben entfallen.
- **Unterseiten oben** als Umschalter (z. B. Räume · Lüften · Bericht · Einstellungen) statt der Leiste am unteren Rand – mehr Höhe für die Kacheln.
- **Festes Seitenraster:** Räume, Rollläden und Lichter stehen in 2–4 Spalten × 1–3 Reihen, passend zur Bildschirmgröße. Keine Kachel wird angeschnitten; die Kacheln werden gleichmäßig auf die Seiten verteilt (5 → 3 + 2 statt 4 + 1). Seiten blättern seitwärts, unten steht „Seite 1 von 2“.
- **Wand-Kacheln, lesbar aus Abstand:** je Kachel Name (19 px), eine große Zahl (48 px) und genau eine Statuszeile (16 px); die ganze Kachel ist in der Farbe des Zustands leicht eingefärbt. Einzelheiten (Zeitplan, Ursache, Ventil …) beim Antippen.
  - **Heizwerk:** Raumtemperatur, „Soll 21,0 °C · Komfort bis 22:00“, Symbole für heizt, Fenster/Lüften, Kamin.
  - **Rollwerk:** Fenster-Grafik, „55 %“ bzw. offen/zu, Grund (Beschattung, von Hand, Tür offen …) oder die nächste Fahrt; ↑ ■ ↓ als große Knöpfe.
  - **Lichtwerk:** große Lampe zum Schalten (mit Melder-Symbol), „an“/„80 %“/„aus“, HmIP, von Hand oder Ursache und Ablauftimer.
- Detailliert/Kompakt gibt es im Tablet nicht mehr – Handy und PC bleiben unverändert.

## 0.69.0 – 2026-11-21

### Neu – Startseite und Tablet
- **„Jetzt wichtig“** oben auf der Startseite statt des Hinweis-Streifens: höchstens drei Punkte zum Erledigen, je mit Sprung an die richtige Stelle und „Erledigt“ (für heute ausgeblendet – unter der Glocke steht es weiter). Bei fertigen Geräten heißt der Knopf „Gesehen“ und quittiert direkt in Kraftwerk. „alle x“ öffnet die Glocke.
- **Bildschirmschoner:**
  - Hinweis **lange drücken** (0,7 s) blendet ihn für heute aus, ohne den Schoner zu beenden.
  - **„und x weitere Hinweise“** ist ein Knopf und öffnet direkt die Glocke.
  - **Müll nicht doppelt:** Steht die Abholung schon als Hinweis da („Heute Müllabfuhr · Biotonne“), fehlt derselbe Termin in der Terminliste.

### Neu – Lüften
- **Lüft-Bilanz je Raum als Ampel** (Heizwerk › Lüften): „gut gelüftet“, „bald lüften“ (2 Tage nicht gelüftet oder morgens über der Grenze) oder „zu selten gelüftet“ (3 Tage nicht gelüftet und morgens feucht, bzw. Schimmel-Ampel rot). Dazu die Feuchte morgens (5–9 Uhr, Mittel 3 Tage). Hinweis unter der Glocke wie „Schlafzimmer: 3 Tage nicht gelüftet, Feuchte morgens 68 %“. Nur für Räume mit Fensterkontakt.

### Behoben – Heizwerk
- **„Heizkörper bleibt kalt“ ohne Fehlalarm nach dem Lüften:** bis 30 Min. nach dem Schließen des Fensters wird nicht gemessen (die ausgekühlten Wände ziehen erst Wärme). Räume mit Fußbodenheizung oder Zusatz-Heizkörpern melden erst nach 3 Std. statt 1 Std.

### Neu – Kraftwerk
- **Solar-Prognose** (aus der Prognose im Energie-Dashboard, z. B. Forecast.Solar): Stundenbalken unter Energiefluss mit Grundlast-Linie; in der Kopfkachel „Heute ab 11 Uhr ca. 1,8 kW Überschuss – Waschmaschine & Co. dann starten“ bzw. „Heute noch ca. 1,1 kWh Solar, Spitze gegen 13 Uhr – kaum Überschuss“ (abends für morgen).
- **Grundlast** (Kraftwerk › Verlauf): niedrigster Verbrauch nachts (Median aus 7 Nächten), kWh und Kosten im Jahr mit dem Preis aus dem Energie-Dashboard; welche gemessenen Verbraucher dazu beitragen und wie viel ohne eigene Messung bleibt.
- **Akku-Rest:** gespeicherte Energie (Sensor am Gerät, z. B. „Akkuenergie“ der Solarbank – automatisch gefunden – oder Kapazität × Ladestand) und „reicht bei 300 W bis ca. 04:30“; rot mit „leer vor Sonnenaufgang“, wenn er vorher leer ist. Reserve (Standard 10 %) und Kapazität unter Einstellungen › Batterie.

## 0.68.5 – 2026-11-21

### Geändert (Lüften)
- **„Fenster schließen“ höchstens zweimal am Tag senden – je Raum.** Danach kommt die Meldung nur noch als Hinweis unter der Hauswerk-Glocke (und im Bildschirmschoner); im Protokoll steht „nur Glocke – heute schon 2× gesendet“. Ab Mitternacht zählt es neu.

## 0.68.4 – 2026-11-21

### Behoben (Benachrichtigungen)
- **„Waschmaschine fertig“ / „Trockner fertig“ abwählbar:** In der Empfänger-Karte waren die Fertigmeldungen der Geräte nur Anzeige. Jetzt lassen sie sich wie die anderen Anlässe je Empfänger an- und abwählen; gespeichert wird mit „Speichern“ direkt am Gerät (Kraftwerk › Geräte zeigt dieselbe Auswahl).

## 0.68.3 – 2026-11-21

### Geändert (Bildschirmschoner)
- **Heizwerk wieder wie vorher:** heizende Räume, offene Fenster und „niemand zu Hause“ (statt „ok“). Rollwerk, Kraftwerk und Lichtwerk bleiben schlank wie in 0.68.2.

## 0.68.2 – 2026-11-21

### Geändert (Bildschirmschoner)
- **Module schlanker:** je Modul nur noch das Wichtigste –
  - **Heizwerk:** „ok“ mit grünem Haken; nur wenn die Kopfkachel etwas zu beheben hat, „prüfen“ in deren Farbe.
  - **Rollwerk:** wie viele offen und wie viele zu (ohne Beschattung und nächste Fahrt).
  - **Kraftwerk:** Solar und Netz, ohne Akku.
  - **Lichtwerk:** wie viele Lichter an (ohne nächste Schaltung).

## 0.68.1 – 2026-11-20

### Behoben (Lichtwerk)
- **Ansicht „Räume“ ohne Melder-Symbol:** Die Leuchten-Zeilen zeigen jetzt wie die Kacheln das kleine Melder-Symbol an der Lampe. Schaltet ein HmIP-Bewegungsmelder, steht „HmIP“ mit Melder-Symbol statt des Verknüpfungs-Symbols; Bewegung aus dem Profil zeigt ebenfalls das Melder-Symbol.

## 0.68.0 – 2026-11-20

### Neu (Lichtwerk)
- **Bericht** – neuer Reiter Lichtwerk › Bericht:
  - **Letzte 7 Tage je Leuchte:** Brenndauer mit Tagesbalken, heute, Energie in kWh und wie oft von Hand geschaltet; oben die Summen.
  - **Energie:** aus einer Leistungsmessung am Gerät (automatisch erkannt) oder einer eingetragenen Leistung (Leuchte › Einstellungen › Leistung in W). Ohne beides nur die Brenndauer.
  - **Vorschläge aus dem Alltag:** Wird ein Profil an mindestens drei Tagen in 14 Tagen deutlich vor dem Plan von Hand ein- bzw. ausgeschaltet, schlägt Lichtwerk vor, es entsprechend früher zu tun („Profil „Abendlicht“: 4× von Hand eingeschaltet, im Mittel 20 Min. vor dem Plan – 20 Min. früher einschalten?“) – mit „Profil öffnen“. Brennt eine Leuchte ohne Bewegungsmelder im Mittel 5 Std. und mehr am Tag, kommt der Hinweis auf Bewegungsmelder oder früheres Ausschalten. HmIP-Schaltungen zählen nicht als von Hand.
- **Gerätezustand:**
  - **Schaltet nicht:** 30 s nach jedem Befehl prüft Lichtwerk, ob die Leuchte geschaltet hat. Wenn nicht: Hinweis an der Kachel, unter der Glocke und im Protokoll („Funk, Strom oder Schalter prüfen“); verschwindet, sobald sie wieder schaltet.
  - **Batterie schwach** (z. B. Smartkerze, ab 20 % oder Meldung „Batterie schwach“) und **Funk schwach** (unter −85 dBm) an der Kachel und im Bericht; Batterie auch unter der Glocke.

## 0.67.0 – 2026-11-20

### Neu (Lichtwerk)
- **Ausschaltzeit lernen:** Lichtwerk misst bei HmIP-Direktverknüpfungen, wie lange nach dem letzten Melden die CCU die Leuchte wirklich ausschaltet (je Leuchte und Melder, die letzten 10 Mal). Ab drei Messungen nutzt der Ablauftimer den Median statt der Einschaltdauer aus der CCU – bis dahin steht „aus in ~0:42“, danach ohne „~“. Übersteht Neustarts.
- **Szenen je Tageszeit** (Profil › Tageszeiten): ab einer Uhrzeit eigene Helligkeit und Farbtemperatur, z. B. 06:00 Morgen 60 % kühl, 09:00 Tag 100 %, 18:00 Abend 50 % warm, 22:00 Nacht 15 % – als Vorlage mit einem Tipp. Die Szene gilt bis zur nächsten, auch über Mitternacht; brennt das Licht beim Wechsel, wird übergeblendet. Nachtlicht hat Vorrang, „Licht“ und „Dynamisch“ treten zurück. Die Tagesleiste der Kachel zeigt die Szenen in ihrer Lichtfarbe und Helligkeit.
- **Ansicht „Räume“** (neben Detailliert und Kompakt): je Raum eine Kachel – Lampe schaltet alle Leuchten des Raums an bzw. aus, Melder-Symbol, „x von y an“, Profil und der nächste Ablauf. Darunter jede Leuchte als Zeile mit Zustand, HmIP bzw. von Hand, Countdown und Ein/Aus. Über das Zahnrad bekommt der ganze Raum ein Profil (und „Profil aktiv“) auf einmal – z. B. Windfang Wand und Decke gemeinsam.

## 0.66.0 – 2026-11-20

### Neu (Lichtwerk)
- **Ablauftimer bis die Leuchte wieder ausgeht** – für Licht über Bewegungsmelder:
  - **HmIP-Direktverknüpfung:** Lichtwerk liest die Einschaltdauer der Verknüpfung aus der CCU (nur lesen, z. B. 1 Min.). Solange der Melder Bewegung bzw. Anwesenheit meldet, steht „aus 1 Min. nach der letzten Bewegung“; ist er ruhig, läuft „aus in 0:42“ sekundengenau herunter.
  - **Bewegung im Profil:** genauso mit der Nachlaufzeit des Profils („Aus nach x Min. ohne Bewegung“).
  - In der kompakten Ansicht steht der Countdown neben dem Namen.

### Geändert
- **Kein Melder-Name mehr in der Kachel:** Die Markierung heißt nur noch „HmIP“, die Zeile mit dem Bewegungsmelder entfällt (das Symbol an der Lampe bleibt; der Name steht beim Antippen bzw. Darüberfahren). Auch die Kopfkachel sagt nur „… HmIP an“.

## 0.65.5 – 2026-11-20

### Geändert
- **Symbol-Erklärung zieht um:** Das „?“ oben in der Kopfzeile entfällt (mehr Platz, besonders am Handy). Die Erklärung aller Symbole und Farben steht jetzt unter **Hauswerk › Einstellungen › Darstellung › Symbole & Farben** – auch über die Suche („Symbole“, „Legende“) zu finden. Am Computer öffnet die Taste `?` sie weiterhin, mit dem aktuellen Modul zuerst.

## 0.65.4 – 2026-11-20


### Geändert (Lichtwerk)
- **HmIP auch bei abgeschaltetem Profil:** Eine Direktverknüpfung in der CCU schaltet unabhängig von Lichtwerk. Deshalb zeigen auch Leuchten ohne aktives Profil das Melder-Symbol ihrer HmIP-Bewegungsmelder und „HmIP · …“, wenn die CCU sie geschaltet hat (Kachel, kompakte Ansicht, Kopfkachel, Helligkeitsfenster). Melder aus dem Profil, „von Hand“ und Ursachen bleiben bei Profil aus weiter weg.

## 0.65.3 – 2026-11-20

### Neu (Lichtwerk)
- **Bewegungsmelder-Symbol:** Leuchten, die über einen Bewegungsmelder schalten – im Profil eingetragen oder per HmIP-Direktverknüpfung in der CCU –, tragen ein kleines Melder-Symbol an der Lampe. In der Info-Zeile steht der Melder (bei mehreren „2 Melder“, Namen beim Antippen bzw. Darüberfahren), in der kompakten Ansicht ein Melder-Symbol neben dem Namen.
- Hat ein HmIP-Bewegungsmelder die Leuchte eingeschaltet, zeigt die Markierung „HmIP · …“ das Melder-Symbol statt des Verknüpfungs-Symbols.
- Bei abgeschaltetem Profil erscheint kein Symbol.

## 0.65.2 – 2026-11-20


### Geändert (Lichtwerk)
- **„HmIP“ statt „von Hand“:** Schaltet eine Homematic-Direktverknüpfung (Bewegungsmelder, Taster) eine Leuchte, steht an Kachel, Kopfkachel, Helligkeitsfenster und im Protokoll „HmIP · S_Bewegung:Windfang“ bzw. „Windfang Wand: HmIP an/aus“ – nicht mehr „von Hand“. „Automatik übernimmt“ entfällt dann.
- Auch das **Ausschalten nach der Nachlaufzeit** der CCU wird erkannt (Melder seit höchstens 30 Min. ruhig) – selbst wenn Lichtwerk das Einschalten nicht mitbekommen hat.
- Bei abgeschaltetem Profil zeigt die Kachel auch „von Hand“ bzw. „HmIP“ nicht mehr an.

## 0.65.1 – 2026-11-20


### Geändert (Lichtwerk)
- **Profil aus = keine Angaben an der Kachel:** Ist das Profil an einer Leuchte abgeschaltet, zeigt die Kachel nur noch Name, Zustand und Helligkeit – kein „Profil … aus“, kein „Profil einschalten“, keine Ursache. Auch das Helligkeitsfenster zeigt dann weder Ursache noch Profil-Schalter.
- **Ein- und ausschalten nur noch in den Einstellungen** der Leuchte (Lichtwerk › Einstellungen › Leuchte › „Profil aktiv“); dort steht weiter „PROFIL AUS“.

## 0.65.0 – 2026-11-20

### Neu – Lichtwerk liest die Direktverknüpfungen der Homematic-CCU
- Wie in Heizwerk (nur lesen, alle 6 Stunden und auf Wunsch): Lichtwerk weiß, welche Leuchten in der CCU direkt von einem Bewegungsmelder oder Taster geschaltet werden. Eigene Taster der Leuchte (z. B. Unterputz-Aktor) werden ausgeblendet.
- **Kein „von Hand“ mehr durch die CCU:** Schaltet ein verknüpfter Melder die Leuchte ein, zeigt die Kachel „über CCU-Verknüpfung · Melder“; Lichtwerk schaltet sie nicht wieder aus, sondern wartet, bis die CCU nach ihrer Nachlaufzeit ausschaltet – dann übernimmt das Profil. Meldet die Leuchte vor dem Melder, prüft Lichtwerk nach 3 s nach und korrigiert.
- **Hinweise** unter der Glocke und im Protokoll: Leuchte wird zusätzlich zum Profil direkt in der CCU geschaltet; steht derselbe Bewegungsmelder auch im Profil, schaltet Lichtwerk doppelt (Warnung).
- **Leuchte › Einstellungen:** Abschnitt „Direktverknüpfungen in der CCU“. **Übersicht** unter Lichtwerk › Einstellungen › Homematic-Verknüpfungen mit „Neu lesen“.
- Ältere BidCos-Geräte (z. B. HM-LC-Sw1PBU-FM) antworten der CCU nur je Kanal – Hauswerk fragt sie jetzt kanalweise ab (gilt auch für Heizwerk).

## 0.64.0 – 2026-11-20

### Neu – Heizwerk liest die Direktverknüpfungen der Homematic-CCU
- Über die Integration „Homematic(IP) Local“ (Aktion „Get link peers“, **nur lesen**, alle 6 Stunden und auf Wunsch) kennt Heizwerk jetzt, welche Geräte in der CCU direkt verknüpft sind: Wandthermostat → Heizkörper, Fensterkontakt, Kanal des Fußbodenheizungs-Aktors.
- **Raum › Geräte:** Abschnitt „Direktverknüpfungen in der CCU“ mit allen Gegenstellen (Aktor mit Kanal) und welche Heizkörper nicht verknüpft sind.
- **Kopplung aus der CCU statt geraten:** Nur Heizkörper, die wirklich mit dem Wandthermostat verknüpft sind, folgen ihm – Hauswerk stellt dann nur das Wandthermostat. Nicht verknüpfte stellt Hauswerk selbst.
- **Fensterpause der CCU überlassen:** Ist jeder offene Fensterkontakt direkt mit dem Thermostat verknüpft, senkt die CCU selbst ab; Hauswerk zeigt die Pause nur an („Fenster offen – die CCU senkt über die Direktverknüpfung ab“) und sendet nichts – spart Funk. Je Raum abschaltbar.
- **Hinweise unter der Glocke** und im Protokoll: Wandthermostat ohne Verknüpfung, Heizkörper nicht mit dem Wandthermostat verknüpft (außer Zusatzheizung im Mischbetrieb), Kanäle eines Fußbodenheizungs-Aktors, die kein Wandthermostat nutzt.
- **Übersicht** unter Heizwerk › Einstellungen › Homematic-Verknüpfungen: je Raum Wandthermostat → Gegenstellen, Hinweise und „Neu lesen“.

## 0.63.2 – 2026-11-20

### Geändert (Benachrichtigungen)
- **Empfänger aktivieren und deaktivieren:** Jede Empfänger-Karte hat oben einen Schalter. Pausiert bekommt der Empfänger nichts mehr – für alle Anlässe, auch die Fertigmeldung der Geräte –, Anlässe, Zeiten und Bündeln bleiben erhalten. Oben steht „x aktiv · y pausiert“; in Anlässen und Tabelle sind pausierte Empfänger gekennzeichnet; sind alle Empfänger eines Anlasses pausiert, steht im Protokoll „alle Empfänger pausiert“. Die Testnachricht geht auch an pausierte Empfänger.
- **„Kanal hinzufügen“** steht jetzt oben im Reiter Empfänger und springt direkt zur Auswahl (die sich dabei öffnet) – kein Scrollen mehr. Die Auswahl-Chips stehen linksbündig.

## 0.63.1 – 2026-11-20


### Geändert (Lichtwerk)
- **Profil an einer Leuchte abschalten** – direkt im Helligkeitsfenster (Tipp auf den Namen), im Einstellungsfenster der Leuchte („Profil aktiv“) und wieder einschalten mit „Profil einschalten“ an der Kachel. Die Leuchte bleibt in Lichtwerk und lässt sich schalten, Lichtwerk schaltet sie nur nicht mehr; Profil und Einstellungen bleiben erhalten, andere Leuchten mit demselben Profil laufen weiter.
- Kachel zeigt „Profil „…“ aus“ statt „Automatik aus“, die Einstellungsliste „PROFIL AUS“; jede Änderung steht im Protokoll.

## 0.63.0 – 2026-11-20

### Neu – Modul Lichtwerk
- **Licht nach dem Vorbild des Blueprints „🔆 Smart Light“ (Blackshome)** – ohne Blueprint und YAML, aufgebaut wie Rollwerk: Reiter **Licht** und **Einstellungen**, eigenes Logo (Indigo), Kopfkachel, Kacheln nach Raum (detailliert/kompakt), Tabletmodus.
- **Profile = Smart-Light-Automationen** mit den Abschnitten Einschalten (Sonne sinkt, Helligkeit fällt, Uhrzeit, Entität an, Rollläden schließen), Ausschalten (spätestens um, Sonne steigt, Helligkeit steigt, Entität aus), **Bewegung** (optional, nur wenn dunkel, aus nach x Min.), Tage (auch Arbeitstage-Kalender), Licht (Helligkeit, Übergang, Farbtemperatur/Farbe), **Dynamisch** (nach Sonne oder Helligkeit), **Nachtlicht** und Ausnahmen (von Hand, Pause-Schalter, niemand zu Hause, Urlaubs-Simulation).
- **Wechsel statt Zustand** wie im Blueprint (an bei Sonnenuntergang, aus um 23:00 – um 5 Uhr nicht wieder an). Sonne und Uhrzeit werden vorausberechnet: Tagesleiste je Licht, „als Nächstes … um …“, richtiger Stand nach einem Neustart.
- **Von Hand hat Vorrang:** wer schaltet (Schalter, App, andere Automation), wird erkannt; die Automatik wartet bis zum nächsten Wechsel (oder eine Zeit) – „Automatik übernimmt“ an der Kachel.
- **Eine Vorrang-Logik mit Ursache an jeder Kachel:** Automatik aus › Pause-Schalter › von Hand › niemand zu Hause › Bewegung › Profil, z. B. „Sonne unter 2° · Nachtlicht“.
- **Assistent „Licht hinzufügen“** mit Vorlagen: Abendlicht, Außenlicht, Flur mit Bewegung, Fernsehlicht, Deko/Weihnachten, Morgenlicht.
- **Helligkeit-Fenster** mit Regler und Stufen (Aus, Nachtlicht, Normal, Hell), Lampensymbol in der echten Lichtfarbe.
- **Hauswerk-Anbindung:** Anwesenheit (niemand da → aus), Urlaub mit Anwesenheits-Simulation (Zeiten zufällig ±30 Min.), Sonnenstand, Arbeitstage; Benachrichtigungen „Licht an, niemand zu Hause“ und „Leuchte nicht erreichbar“; Widget „Licht“, Zeile in „Lage“ und im Bildschirmschoner, Suche, Legende, Protokoll mit Filter „Lichtwerk“, Diagnose, umbenannte Entitäten.
- **Bestehende Licht-Automationen** (z. B. Nachtlicht) werden unter Lichtwerk › Einstellungen aufgelistet und lassen sich nach der Übernahme mit einem Tipp abschalten.

## 0.62.0 – 2026-11-20

### Geändert – Heizpläne: klares Modell
- **Eco ist der Standard.** Wo kein Zeitfenster steht, gilt der Eco-Wert – Lücken muss niemand mit Eco füllen.
- **Komfort-Zeitfenster:** Sollwert = Komfortwert des Raums oder – optional – eine **eigene Temperatur nur für dieses Zeitfenster** (Komfort- und Eco-Wert bleiben unverändert). Beispiel: 06:00–08:00 Komfort, 17:00–21:00 Komfort mit 22 °C, sonst automatisch Eco.
- **Eco-Zeitfenster** (neu, optional): ausdrücklich Eco, z. B. mittags in einem langen Komfort-Tag.
- Ein Komfort-Zeitfenster legt nur den Sollwert fest – geheizt wird nur, wenn es kälter ist.
- **Eindeutige Zeiten:** Ende gehört nicht mehr dazu (06:00–08:00 heißt bis 07:59). Endet ein Zeitfenster vor seinem Beginn (22:00–06:00), läuft es bis zum Folgetag – auch von Sonntag auf Montag. „24:00“ = Mitternacht. Beginn = Ende ist nicht erlaubt (außer 00:00–24:00).
- **Keine Überschneidungen mehr:** Der Editor zeigt sie sofort am Zeitfenster („Zeitfenster 2 und 4 überschneiden sich am Mo 20:00–21:00“) und sperrt Speichern. Mit **„Zeitfenster X hat Vorrang“** wird das andere dort gekürzt bzw. geteilt. Auch Home Assistant lehnt überschneidende Pläne ab. „Zeitfenster hinzufügen“ schlägt eine freie Zeit vor.
- **Bestehende Pläne werden überführt:** Überschneidende Zeitfenster werden beim Start so aufgeteilt, dass wie bisher der höhere Wert gilt – jetzt eindeutig. Steht im Protokoll („Heizpläne bereinigt“). Pläne ohne Überschneidung bleiben unverändert.

### Neu – ein Sollwert, eine Ursache
- **Zentrale Vorrang-Logik:** Automatik aus › Fenster offen › Entkalken/Sommerpause › Boost/von Hand › Eco erzwungen/Party/Urlaub/abwesend/Präsenzmelder › Heizplan (mit Vorheizen); danach „höchstens x °C absenken“ und „warm genug“.
- **Ursache überall gleich:** Kachel („Heizplan: Komfort 17:00–21:00 (eigene 22,0 °C)“, „Niemand zu Hause – höchstens 17,0 °C (Plan: 22,0 °C)“, „Von Hand bis 19:30“), Schnellmenü („Warum 22 °C?“ mit Planwert) und Zeitleiste. Der Tagesbalken der Kachel kommt direkt aus der Steuerung; der Plan-Editor rechnet nach denselben Regeln (per Test abgeglichen).

## 0.61.0 – 2026-11-20

### Neu – Benachrichtigungen neu aufgebaut
- **Drei Reiter:** *Anlässe* (was löst aus) · *Empfänger* (wer bekommt was) · *Ruhezeit & Verlauf*.
- **Anlässe nach Modul** mit Modulfarbe: Heizwerk, Lüften, Rollwerk, Kraftwerk, Hauswerk. Je Anlass **eine Zeile** – „Fenster lange offen · ab 30 Min. → Pixel 8“ – mit Schalter an/aus und rotem Glöckchen bei „Wichtig“. Antippen klappt Art, Grenze, eigene Kanäle und eine **Vorschau** der Mitteilung auf.
- **„So senden“ und „Probehören“:** schickt die Beispielmeldung an die Kanäle des Anlasses bzw. spielt sie als Ansage ab.
- **Tabelle Anlass × Kanal** auf breiten Bildschirmen (PC, Tablet quer): Haken setzen, Art je Zeile wählen. Am Handy die Liste.
- **Vorlagen:** „Nur Wichtiges aufs Handy“, „Ansagen tagsüber“ (Fenster, Lüften, Müll als Ansage am Tablet 8–21 Uhr), „Ruhig“ (nur Frost und Sturm).
- **Neue Anlässe aus Rollwerk:** Sturm (Rollläden fahren hoch) und Rollladen nicht erreichbar. Kraftwerk zeigt die Fertigmeldung je Gerät mit Sprung zu den Geräten.
- **Empfänger als Karten:** je Kanal Zustand (grün = zuletzt zugestellt mit Zeit, rot = Fehler mit Meldung), welche Anlässe er bekommt (antippen schaltet), Testen, Entfernen. Fehlerhafte Kanäle stehen oben mit „Testen“.
- **Zeiten je Kanal:** z. B. Ansagen nur 8–21 Uhr – außerhalb bekommt der Kanal nur Wichtiges. **Ansagen nur, wenn jemand zu Hause ist** (Standard an).
- **Bündeln je Kanal:** Kommen binnen 5 Min. mehrere Meldungen, geht die erste sofort, die weiteren zusammen als „Hauswerk: 3 Meldungen“. Wichtiges nie gebündelt.
- **Verlauf:** heute gesendet · zurückgehalten · nur Protokoll · nicht zugestellt, die letzten 10 Nachrichten mit Ergebnis und Sprung ins Protokoll. Zustand und Verlauf überstehen Neustarts.

## 0.60.0 – 2026-11-20

### Neu
- **„?“ oben rechts erklärt alle Symbole und Farben** (am Computer auch mit der Taste `?`): die Farbsprache und alle Zeichen aus Heizwerk, Lüften, Rollwerk und Kraftwerk mit kurzer Erklärung – z. B. Kamin an / „?“ / Nachwärme, Lüften läuft, Fenster schließen, Sturm, Tür offen, von Hand, Ende wird geprüft. Das Modul, in dem du gerade bist, steht zuerst; mit Suchfeld.

### Geändert – einheitliche Farbsprache
- Grün = läuft wie gewollt · Orange = Wärme (heizt, Beschattung, Kamin) · Gelb = Sonne und Hinweise · Türkis = Fenster und Lüften · Hellblau = kühl, Frost, Gerät läuft · Violett = von Hand · Rot = Achtung · Grau = Ruhe/aus.
- Angeglichen: „von Hand“ überall im selben Violett (Heizwerk, Rollwerk, Protokoll), gekippte Fenster in Rollwerk und „Jetzt lüften“ türkis wie die Fenster in Heizwerk, „Gerät läuft“ hellblau.

## 0.59.0 – 2026-11-20

### Neu – Heizwerk: Kamin im Raum
- **„Kamin im Raum vorhanden“** (Raum › Geräte › Kamin). Vorhanden heißt nicht in Betrieb: Wird ein solcher Raum in 30 Min. um mindestens 0,4 °C wärmer, **ohne dass geheizt wird** (auch keine Restwärme – Heizkörper 20 Min., Fußbodenheizung 3 Std.), zeigt die Raumkachel ein Kamin-Symbol mit „?“: „Wärmer ohne Heizung – vielleicht der Kamin, die Sonne oder Kochen. Sicher ist das nicht.“
- **Signal „Kamin in Betrieb“ (optional):** Schalter, Binärsensor oder Steckdose (an = brennt), Temperaturfühler am Ofen/Rohr (ab 50 °C) oder Leistung eines Gebläses. Dann ist die Aussage sicher („Kamin an laut Signal“); meldet das Signal „aus“, gilt ein Anstieg als andere Wärmequelle.
- **Von Hand:** „Kamin an / aus“ im Schnellmenü der Raumkachel – endet spätestens nach 8 Stunden von selbst. Darf jeder (wie Temperatur von Hand).
- **Bewertung unverfälscht:** Solange der Kamin an ist, die Temperatur ohne Heizung steigt oder der Raum danach noch wärmer als gewollt ist (Nachwärme, bis höchstens 0,3 °C über Soll bzw. 3 Std.), zählt die Zeit weder für „Komfort erreicht“ noch „überheizt“ oder „Ventil ganz offen“. Aufheizmessungen in dieser Zeit – oder in Kamin-Räumen deutlich schneller als gelernt – werden verworfen und nicht ins Vorheizen übernommen (steht im Protokoll).
- **Bericht › Heizleistung:** „Kamin u. Ä. – x h herausgerechnet“ je Raum.

## 0.58.0 – 2026-11-20

### Neu
- **Benachrichtigungen über mehrere Kanäle – gemeinsam für Heizwerk, Rollwerk und Kraftwerk** (Hauswerk › Benachrichtigungen). Angeboten wird, was in Home Assistant eingerichtet ist, nach Art sortiert: Home-Assistant-App, Pushover, Telegram, E-Mail, Benachrichtigungs-Entitäten (z. B. Anzeige am Tablet), Sprachassistenten, **Ansagen über Lautsprecher** (Sprachdienst + Lautsprecher frei kombinierbar), Mitteilung in Home Assistant und weitere Dienste. Nicht erreichbare Kanäle sind nicht wählbar und werden beim Senden übersprungen (Protokoll).
- **Je Anlass eigene Kanäle**: z. B. „Fenster schließen“ als Ansage im Wohnzimmer, Frost nur aufs Handy. Ohne eigene Auswahl gelten die Standard-Kanäle. Aus / Protokoll / Normal / Wichtig je Anlass wie bisher.
- **Testnachricht an die Auswahl** – mit Ergebnis je Kanal („nicht zugestellt: …“).
- **Fertigmeldung von Waschmaschine & Trockner** nutzt dieselbe Kanalauswahl (inkl. Ansage). Weiterhin je Durchlauf und Kanal höchstens einmal, auch nach Neustart.

### Geändert
- **Schutz vor doppelten Meldungen**: dieselbe Nachricht an denselben Kanal kommt innerhalb von 2 Minuten nur einmal (z. B. nach Neuladen). Ansagen in der Ruhezeit nur bei „Wichtig“.
- Bisherige Auswahl (Apps und „Auch in Home Assistant“, auch je Gerät) wird automatisch übernommen.

## 0.57.1 – 2026-11-20

### Geändert
- **Rollwerk: Beschattung in der Tagesleiste nur, wenn sie heute wirklich zu erwarten ist** – sie läuft gerade, oder Außentemperatur (wie bei „Beschattung ab“) und Wetter passen: Wetterlage der Tagesvorhersage (sonst die aktuelle) sonnig oder teils bewölkt bzw. die Wetter-Bedingung des Profils. Bei Regen oder Bewölkung bleibt der orange Abschnitt weg, ebenso „Beschattung ab“ und „Als Nächstes: Beschattung“. In den Profil-Einstellungen zeigt die Leiste weiter, wann Beschattung möglich wäre.

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
