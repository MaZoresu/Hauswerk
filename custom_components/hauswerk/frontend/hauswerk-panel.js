/* Hauswerk – Panel für Home Assistant (Module: Heizwerk, Rollwerk; Licht, Garten geplant). Eigenständige Web-Komponente, kein Build nötig. */

const VERSION = "0.28.0";
const DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const TYPES = {
  heizkoerper: {
    label: "Heizkörper",
    icon: "mdi:radiator",
    text: "Reagiert schnell. Kurze Fensterverzögerung, kurzes Vorheizen, Absenken lohnt sich.",
  },
  flaeche: {
    label: "Flächenheizung",
    icon: "mdi:heating-coil",
    text: "Fußboden- oder Wandheizung, sehr träge. Lange Fensterverzögerung, frühes Vorheizen, nur geringe Absenkung.",
  },
};
const MODE = {
  komfort: { c: "#fbbf24", i: "mdi:sofa-outline" },
  vorheizen: { c: "#fb923c", i: "mdi:clock-fast" },
  eco: { c: "#60a5fa", i: "mdi:leaf" },
  fenster: { c: "#22d3ee", i: "mdi:window-open-variant" },
  manuell: { c: "#a78bfa", i: "mdi:hand-back-right-outline" },
  urlaub: { c: "#34d399", i: "mdi:palm-tree" },
  abwesend: { c: "#94a3b8", i: "mdi:home-export-outline" },
  aus: { c: "#6b7280", i: "mdi:power" },
  entkalken: { c: "#38bdf8", i: "mdi:water-sync" },
  sommer: { c: "#facc15", i: "mdi:weather-sunny" },
  boost: { c: "#f43f5e", i: "mdi:rocket-launch-outline" },
  party: { c: "#e879f9", i: "mdi:party-popper" },
  leer: { c: "#64748b", i: "mdi:account-off-outline" },
  belegt: { c: "#fbbf24", i: "mdi:account-check-outline" },
  warm: { c: "#f97316", i: "mdi:thermometer-check" },
  eco_fix: { c: "#22c55e", i: "mdi:leaf-circle-outline" },
  frost: { c: "#38bdf8", i: "mdi:snowflake-thermometer" },
};
/** Raum-Icon aus dem Namen erraten (reihenfolgeabhängig: spezielle Begriffe zuerst). */
const ROOM_GUESS = [
  [/wc|toilette|klo/, "mdi:toilet"],
  [/bad|dusche/, "mdi:shower-head"],
  [/küche|kueche|kochen/, "mdi:stove"],
  [/wohn|lounge/, "mdi:sofa-outline"],
  [/schlaf|eltern/, "mdi:bed-king-outline"],
  [/kind|baby|jugend/, "mdi:teddy-bear"],
  [/arbeit|büro|buero|office|studio/, "mdi:desk"],
  [/ess/, "mdi:silverware-fork-knife"],
  [/flur|diele|gang|eingang|treppe/, "mdi:door"],
  [/gäste|gaeste|gast/, "mdi:bed-outline"],
  [/keller|hauswirtschaft|wasch/, "mdi:washing-machine"],
  [/dach|speicher|boden/, "mdi:home-roof"],
  [/wintergarten|garten/, "mdi:flower-outline"],
  [/hobby|werkstatt|werk/, "mdi:hammer-wrench"],
  [/ankleide|garderobe/, "mdi:hanger"],
  [/sport|fitness/, "mdi:dumbbell"],
  [/garage/, "mdi:garage"],
];
const ROOM_ICON_CHOICES = [...new Set(ROOM_GUESS.map(([, i]) => i)), "mdi:radiator", "mdi:heating-coil", "mdi:television", "mdi:music", "mdi:book-open-variant", "mdi:paw"];
const roomIcon = (room) => {
  if (room.icon) return room.icon;
  const n = (room.name || "").toLowerCase();
  const hit = ROOM_GUESS.find(([re]) => re.test(n));
  return hit ? hit[1] : (TYPES[room.type] || TYPES.heizkoerper).icon;
};
/** Wie weit ist der Raum vom Soll entfernt? Icon, Farbe und Kurztext. */
const trend = (temp, target) => {
  if (temp == null || target == null) return null;
  const d = temp - target;
  if (Math.abs(d) < 0.3) return { i: "mdi:thermometer-check", c: "#34d399", t: "am Soll" };
  if (d < 0) return { i: "mdi:thermometer-chevron-up", c: "#fb923c", t: `${fmt(-d)} °C unter Soll` };
  return { i: "mdi:thermometer-chevron-down", c: "#60a5fa", t: `${fmt(d)} °C über Soll` };
};
const humidityInfo = (h) =>
  h == null ? null : h >= 65 ? { i: "mdi:water-alert", c: "#f59e0b", t: "feucht – lüften" } : h <= 35 ? { i: "mdi:water-off-outline", c: "#f59e0b", t: "trocken" } : { i: "mdi:water-percent", c: "var(--muted)", t: "" };
/** Wetterlage aus Home Assistant: Symbol und deutscher Text. */
const WEATHER = {
  "clear-night": ["mdi:weather-night", "Klar"],
  cloudy: ["mdi:weather-cloudy", "Bewölkt"],
  exceptional: ["mdi:alert-circle-outline", "Unwetter"],
  fog: ["mdi:weather-fog", "Nebel"],
  hail: ["mdi:weather-hail", "Hagel"],
  lightning: ["mdi:weather-lightning", "Gewitter"],
  "lightning-rainy": ["mdi:weather-lightning-rainy", "Gewitter mit Regen"],
  partlycloudy: ["mdi:weather-partly-cloudy", "Teils bewölkt"],
  pouring: ["mdi:weather-pouring", "Starkregen"],
  rainy: ["mdi:weather-rainy", "Regen"],
  snowy: ["mdi:weather-snowy", "Schnee"],
  "snowy-rainy": ["mdi:weather-snowy-rainy", "Schneeregen"],
  sunny: ["mdi:weather-sunny", "Sonnig"],
  windy: ["mdi:weather-windy", "Windig"],
  "windy-variant": ["mdi:weather-windy-variant", "Windig, bewölkt"],
};
/** Widgets der Startseite: Name, Symbol, Farbe, Beschreibung; go = Ansicht öffnen, pop = Einstellung, config = Entitäten wählen. */
const WIDGETS = {
  heat: { name: "Heizwerk", icon: "mdi:radiator", c: "#fb923c", text: "Ø-Temperatur, Kurzurteil, heizende Räume, offene Fenster und Heizstunden heute", go: "overview" },
  presence: { name: "Anwesenheit", icon: "mdi:home-account", c: "#34d399", text: "Zu Hause, Abwesend, Urlaub sowie Gäste, Party und Eco mit einem Tipp umschalten", pop: "presence" },
  weather: { name: "Wetter", icon: "mdi:weather-partly-cloudy", c: "#60a5fa", text: "Wetterlage, Außentemperatur, Wind und Luftfeuchte", pop: "weather" },
  rooms: { name: "Räume", icon: "mdi:floor-plan", c: "#2dd4bf", text: "Alle Räume als kleine Kacheln mit Temperatur und Betriebsart", size: "l", go: "overview" },
  shortcuts: { name: "Shortcuts", icon: "mdi:gesture-tap-button", c: "#a78bfa", text: "Eigene Knöpfe für Szenen, Skripte, Schalter oder Lichter", config: true },
  windows: { name: "Fenster", icon: "mdi:window-open-variant", c: "#22d3ee", text: "Welche Fenster gerade offen sind und seit wann" },
  schedule: { name: "Komfortzeiten", icon: "mdi:calendar-clock", c: "#f59e0b", text: "Wann welcher Raum als Nächstes warm wird oder absenkt" },
  report: { name: "Heizdauer", icon: "mdi:chart-bar", c: "#a78bfa", text: "Geheizte Stunden der letzten 7 Tage als Balken", go: "report" },
  values: { name: "Werte", icon: "mdi:gauge", c: "#94a3b8", text: "Beliebige Sensoren, z. B. Gaszähler, Strompreis oder Vorlauftemperatur", config: true },
  forecast: { name: "Wetterprognose", icon: "mdi:weather-cloudy-clock", c: "#60a5fa", text: "Die nächsten Stunden oder Tage mit Tiefst- und Höchstwerten, Regen und Frost-Hinweis", size: "l", forecast: true },
};
const DEFAULT_WIDGETS = [{ type: "heat", size: "m" }, { type: "weather", size: "s" }, { type: "windows", size: "s" }, { type: "presence", size: "l" }, { type: "rooms", size: "l" }];
const SC_ICONS = { light: "mdi:lightbulb-outline", switch: "mdi:toggle-switch-outline", input_boolean: "mdi:toggle-switch-outline", script: "mdi:script-text-play-outline", scene: "mdi:palette-outline", button: "mdi:gesture-tap-button", input_button: "mdi:gesture-tap-button", fan: "mdi:fan", cover: "mdi:window-shutter", lock: "mdi:lock-outline", media_player: "mdi:speaker" };
const ROOM_COLORS = ["#2dd4bf", "#f59e0b", "#a78bfa", "#f472b6", "#60a5fa", "#a3e635", "#f87171", "#22d3ee", "#facc15", "#c084fc"];
const PICKERS = {
  climates: { scope: "room", multi: true, domains: ["climate"] },
  windows: { scope: "room", multi: true, domains: ["binary_sensor", "cover"] },
  temp_sensor: { scope: "room", multi: false, domains: ["sensor"], deviceClass: "temperature" },
  humidity_sensor: { scope: "room", multi: false, domains: ["sensor"], deviceClass: "humidity" },
  persons: { scope: "settings", multi: true, domains: ["person", "device_tracker"] },
  presence_sensor: { scope: "room", multi: false, domains: ["binary_sensor"] },
  comfort_entity: { scope: "room", multi: false, domains: ["input_number", "number", "sensor"] },
  eco_entity: { scope: "room", multi: false, domains: ["input_number", "number", "sensor"] },
  proximity_sensors: { scope: "settings", multi: true, domains: ["sensor"] },
  radio_entities: { scope: "settings", multi: true, domains: ["sensor"] },
  demand_entity: { scope: "settings", multi: false, domains: ["climate"] },
  rw_covers: { scope: "settings", multi: true, domains: ["cover"] },
  rw_wind_entity: { scope: "settings", multi: false, domains: ["sensor"] },
  outside_sensor: { scope: "settings", multi: false, domains: ["sensor"], deviceClass: "temperature" },
  season_entity: { scope: "settings", multi: false, domains: ["input_boolean", "switch", "binary_sensor", "schedule"] },
  schedule_entity: { scope: "room", multi: false, domains: ["schedule", "calendar", "input_boolean", "binary_sensor"] },
  vacation_calendar: { scope: "settings", multi: false, domains: ["calendar"] },
  weather_entity: { scope: "settings", multi: false, domains: ["weather"] },
  import_calendar: { scope: "pop", multi: false, domains: ["calendar"] },
  w_weather: { scope: "pop", multi: false, domains: ["weather"] },
  w_entities: { scope: "pop", multi: true, domains: ["sensor", "binary_sensor", "input_number", "input_select", "counter", "switch", "light", "input_boolean", "script", "scene", "button", "input_button", "fan", "cover", "lock", "media_player"] },
  plan_calendar: { scope: "plan", multi: false, domains: ["calendar"] },
  presence_schedule: { scope: "room", multi: false, domains: ["schedule", "input_boolean", "binary_sensor"] },
  calibration_entities: { scope: "room", multi: true, domains: ["number"] },
  valve_entities: { scope: "room", multi: true, domains: ["number"] },
  workday_entity: { scope: "settings", multi: false, domains: ["binary_sensor"] },
  sun_entity: { scope: "settings", multi: false, domains: ["sun"] },
  wind_sensor: { scope: "settings", multi: false, domains: ["sensor"], deviceClass: "wind_speed" },
  // Personen hinzufügen: wählt aus Personen und Trackern, die gewählten stehen schon als Chips da
  person_add: { scope: "settings", multi: true, domains: ["person", "device_tracker"], noCards: true },
  // Weitere Geräte im Raum, nur zur Anzeige (z. B. Ventil eines Heizkörper-Thermostats, Stellantrieb der Fußbodenheizung)
  show_entities: { scope: "room", multi: true, domains: ["climate", "switch", "sensor", "number", "valve", "cover", "binary_sensor", "input_boolean"] },
};
// Entitätssuche: Wörter im Namen, die zum Feld passen, und passende Geräteklassen
const PICK_HINTS = {
  climates: ["thermostat", "heizung", "heizkörper", "heizkoerper", "trv", "climate"],
  windows: ["fenster", "tür", "tuer", "window", "door", "kontakt"],
  temp_sensor: ["temperatur", "temp"],
  humidity_sensor: ["feucht", "humid"],
  presence_sensor: ["präsenz", "praesenz", "bewegung", "motion", "presence", "occupancy"],
  outside_sensor: ["außen", "aussen", "outdoor", "garten", "wetter", "balkon", "terrasse"],
  proximity_sensors: ["entfernung", "distance", "nähe", "proximity", "abstand"],
  radio_entities: ["duty_cycle", "duty cycle", "duty", "funk", "carrier"],
  demand_entity: ["zone", "circuit", "vaillant", "kessel", "therme", "heizkreis", "wärmepumpe", "boiler"],
  rw_covers: ["rollladen", "rolladen", "rollo", "shutter", "jalousie", "raffstore", "blind", "markise", "ra_"],
  rw_wind_entity: ["böe", "boe", "gust", "wind"],
  wind_sensor: ["böe", "boe", "gust", "wind"],
  calibration_entities: ["calibration", "offset", "kalibrier"],
  valve_entities: ["valve", "ventil", "position", "opening"],
  comfort_entity: ["komfort", "comfort"],
  eco_entity: ["eco", "absenk"],
  season_entity: ["heizperiode", "heizsaison", "winter"],
  schedule_entity: ["heiz", "zeitplan", "schedule"],
  vacation_calendar: ["urlaub", "familie", "ferien"],
  workday_entity: ["arbeitstag", "workday", "werktag", "feiertag"],
  person_add: ["person", "handy", "phone", "iphone", "pixel", "galaxy"],
  show_entities: ["ventil", "valve", "stellantrieb", "stellung", "position", "demand", "heizkörper", "heizkoerper", "fußboden", "fussboden", "fbh", "heizkreis", "thermostat"],
};
const PICK_CLASSES = {
  windows: ["window", "door", "opening", "garage_door"],
  presence_sensor: ["occupancy", "motion", "presence"],
  proximity_sensors: ["distance"],
  temp_sensor: ["temperature"],
  humidity_sensor: ["humidity"],
  outside_sensor: ["temperature"],
};
// Gerätemodelle verschiedener Hersteller (wie logic.py TRV_MODELS / WALL_MODELS)
const TRV_MODELS = ["trv", "rt-dn", "bth-ra", "radiator", "va01", "va02", "va04", "nrv", "srts", "spzb", "hr91", "hr92", "ally",
  "dect 300", "dect 301", "dect 302", "comet", "eve thermo", "zk03840", "heizkörper", "heizkorper"];
const WALL_MODELS = ["wth", "bwth", "sth", "tc-it", "bth-rm", "rth", "room thermostat", "raumthermostat", "wall", "wand",
  "ru01", "ru02", "su02", "t87rf", "roomstat", "natherm", "w100", "bht-", "ct100", "ct200", "nest", "ecobee"];

const DC_LABEL = {
  temperature: "Temperatur", humidity: "Feuchte", window: "Fenster", door: "Tür", opening: "Öffnung", garage_door: "Garagentor",
  motion: "Bewegung", occupancy: "Belegung", presence: "Präsenz", distance: "Entfernung", battery: "Batterie", power: "Leistung",
};
const DOMAIN_LABEL = {
  climate: "Thermostat", binary_sensor: "Binärsensor", sensor: "Sensor", cover: "Abdeckung", number: "Zahl", input_number: "Zahl-Helfer",
  input_boolean: "Schalter-Helfer", switch: "Schalter", schedule: "Zeitplan", calendar: "Kalender", person: "Person", device_tracker: "Tracker",
  weather: "Wetter", light: "Licht", script: "Skript", scene: "Szene", button: "Knopf", input_button: "Knopf-Helfer", fan: "Lüfter",
  lock: "Schloss", media_player: "Medienplayer", input_select: "Auswahl", counter: "Zähler",
};
const PLAN_PRESETS = {
  berufstaetig: {
    label: "Werktags früh und abends",
    blocks: [
      { days: [0, 1, 2, 3, 4], start: "06:00", end: "08:00" },
      { days: [0, 1, 2, 3, 4], start: "16:30", end: "22:00" },
      { days: [5, 6], start: "08:00", end: "22:30" },
    ],
  },
  homeoffice: {
    label: "Homeoffice",
    blocks: [
      { days: [0, 1, 2, 3, 4], start: "07:00", end: "22:00" },
      { days: [5, 6], start: "08:00", end: "22:30" },
    ],
  },
  ganztags: { label: "Täglich 6–22 Uhr", blocks: [{ days: [0, 1, 2, 3, 4, 5, 6], start: "06:00", end: "22:00" }] },
  bad: {
    label: "Bad morgens und abends",
    blocks: [
      { days: [0, 1, 2, 3, 4, 5, 6], start: "05:30", end: "08:00" },
      { days: [0, 1, 2, 3, 4, 5, 6], start: "19:00", end: "21:30" },
    ],
  },
};
// Aufbau: Start = Hauswerk-Dashboard mit den Widgets aller Module, dann die Module als Reiter,
// zentrale Hauswerk-Einstellungen (gelten für alle Module) hinter dem Zahnrad oben rechts.
// Alles rund ums Heizen liegt im Modul „Heizwerk“ mit eigener Unterleiste und eigenen Einstellungen.
const HEAT_VIEWS = [
  { id: "overview", slug: "raeume", name: "Räume", icon: "mdi:radiator" },
  { id: "plans", slug: "heizplaene", name: "Heizpläne", icon: "mdi:calendar-clock", hidden: true }, // über Einstellungen › Heizpläne
  { id: "room", slug: "raum", name: "Raum", icon: "mdi:door", hidden: true }, // Raum-Detailseite
  { id: "report", slug: "bericht", name: "Bericht", icon: "mdi:chart-bar" },
  { id: "settings", slug: "einstellungen", name: "Einstellungen", icon: "mdi:tune-variant" },
];
const SHUT_VIEWS = [
  { id: "shutters", slug: "rolllaeden", name: "Rollläden", icon: "mdi:window-shutter" },
  { id: "shutset", slug: "einstellungen", name: "Einstellungen", icon: "mdi:tune-variant" },
];
const MODULES = [
  { id: "heizen", no: 1, name: "Heizwerk", icon: "mdi:radiator", logo: "heizen", views: HEAT_VIEWS.map((v) => v.id) },
  { id: "rollwerk", no: 2, name: "Rollwerk", icon: "mdi:window-shutter", logo: "rollwerk", views: SHUT_VIEWS.map((v) => v.id) },
];
// Geplante Module: nur ausgegraut angezeigt, noch ohne Funktion.
const COMING = [
  { name: "Licht", icon: "mdi:lightbulb-outline" },
  { name: "Garten", icon: "mdi:flower-outline" },
];
const SLUGS = { start: "start", house: "einstellungen", log: "protokoll", ...Object.fromEntries(HEAT_VIEWS.map((v) => [v.id, `heizen/${v.slug}`])),
  ...Object.fromEntries(SHUT_VIEWS.map((v) => [v.id, `rollwerk/${v.slug}`])) };
// Pop-ups von Rollwerk (Einstellungen unter Rollwerk › Einstellungen)
const WIZ_USES = [
  { id: "wohnen", label: "Wohnzimmer", icon: "mdi:sofa-outline", comfort: 21, eco: 18, plan: "berufstaetig", match: /wohn|living|stube/ },
  { id: "schlafen", label: "Schlafzimmer", icon: "mdi:bed-outline", comfort: 19, eco: 16.5, plan: "berufstaetig", match: /schlaf|bed/ },
  { id: "kind", label: "Kinderzimmer", icon: "mdi:teddy-bear", comfort: 20, eco: 17.5, plan: "ganztags", match: /kind|kids|jugend/ },
  { id: "bad", label: "Bad", icon: "mdi:shower", comfort: 22, eco: 18, plan: "bad", match: /bad|dusch|wc|toilet|bath/ },
  { id: "kueche", label: "Küche / Essen", icon: "mdi:silverware-fork-knife", comfort: 20, eco: 17, plan: "berufstaetig", match: /k(ü|ue)che|kitchen|ess/ },
  { id: "buero", label: "Büro", icon: "mdi:desk", comfort: 21, eco: 17, plan: "homeoffice", match: /b(ü|ue)ro|arbeit|office/ },
  { id: "flur", label: "Flur / Sonstiges", icon: "mdi:door", comfort: 18, eco: 16, plan: "ganztags", match: /flur|diele|gang|treppe|keller|hall/ },
];
const RW_POPS = ["rwcovers", "rwstorm", "rwrecovery"];
const RW_FEATURES = [["up", "Morgens öffnen"], ["down", "Abends schließen"], ["time", "Zeitsteuerung"], ["brightness", "Helligkeit"], ["sun", "Sonnenhöhe"], ["ventilate", "Lüften"], ["shading", "Beschattung"]];
const RW_SECTIONS = [
  ["tag", "Tagesablauf", "mdi:weather-sunset", "#f59e0b"], ["shade", "Sonnenschutz", "mdi:sun-thermometer-outline", "#f97316", "shading"],
  ["vent", "Fenster & Lüften", "mdi:window-open-variant", "#22c55e"], ["exc", "Ausnahmen", "mdi:account-clock-outline", "#a78bfa"],
  ["fine", "Feinheiten", "mdi:tune-variant", "#64748b"],
];
const RW_WORDS = { fn: "funktionen automatik öffnen schließen", pos: "stellung position prozent fahrzeit toleranz", time: "uhrzeit früh spät werktag wochenende kalender",
  bright: "helligkeit lux sensor", sun: "sonnenhöhe elevation dämmerung", vent: "lüften fenster gekippt aussperrschutz",
  shade: "beschattung hitze sonne azimut temperatur vorhersage", res: "bewohner schlafen schlafzimmer", man: "manuell hand übersteuerung zurücksetzen",
  delay: "verzögerung zufall", force: "erzwingen pause schalter", beh: "verhalten einmal am tag" };
const RW_SHADE_CONDS = [["azimuth", "Richtung"], ["elevation", "Sonnenhöhe"], ["brightness", "Helligkeit"], ["temp1", "Temp. innen"], ["temp2", "Temp. außen"], ["forecast_temp", "Vorhersage"], ["forecast_weather", "Wetterlage"], ["custom", "Eigene"]];
const RW_WEATHER = [["sunny", "Sonnig"], ["partlycloudy", "Teils bewölkt"], ["cloudy", "Bewölkt"], ["fog", "Nebel"], ["rainy", "Regen"], ["windy", "Windig"], ["exceptional", "Extrem"]];
const RW_VENT = [["ventilation_start_no_delay", "Beim Kippen ohne Verzögerung fahren"], ["ventilation_if_lower_enabled", "Auch herunterfahren auf Lüftungsstellung, wenn der Rollladen höher steht"],
  ["ventilation_after_shading_end", "Nach der Beschattung auf Lüftungsstellung statt ganz auf"], ["shading_over_ventilation", "Beschattung geht vor Lüften (auch bei gekipptem Fenster)"]];
const RW_LOCK_TILTED = [["lockout_tilted_closing", "beim Schließen"], ["lockout_tilted_shading_start", "beim Beginn der Beschattung"], ["lockout_tilted_shading_end", "beim Ende der Beschattung"]];
const RW_RESIDENT = [["closing", "Schließen, wenn der Bewohner schlafen geht"], ["opening", "Öffnen, wenn der Bewohner aufwacht (wenn Zeit/Helligkeit passen)"],
  ["allow_shading", "Beschattung erlauben, während er schläft"], ["allow_opening", "Öffnen erlauben, während er schläft"]];
const RW_MANUAL = [["opening", "Öffnen"], ["closing", "Schließen"], ["ventilation", "Lüften"], ["shading", "Beschattung"]];
const RW_RESET = [["fixed", "zu einer festen Uhrzeit"], ["timeout", "nach einiger Zeit"], ["in_position", "in einer bestimmten Stellung"]];
const RW_FORCE = [["force_pause", "Pause – Rollwerk fährt nichts", "mdi:pause-circle-outline"], ["force_up", "Öffnen erzwingen", "mdi:arrow-up-bold"], ["force_down", "Schließen erzwingen", "mdi:arrow-down-bold"],
  ["force_ventilate", "Lüften erzwingen", "mdi:window-open-variant"], ["force_shading", "Beschattung erzwingen", "mdi:sun-thermometer-outline"]];
const RW_BEHAVIOR = [["prevent_higher_position_closing", "Abends nicht höher fahren, als der Rollladen schon steht"], ["prevent_lowering_when_closing_if_shaded", "Abends in der Beschattungsstellung bleiben (nicht weiter herunter)"],
  ["prevent_shading_end_if_closed", "Beschattung nicht beenden, wenn der Rollladen schon zu ist"], ["prevent_opening_after_shading_end", "Nach der Beschattung nicht öffnen"],
  ["prevent_opening_after_ventilation_end", "Nach dem Lüften nicht öffnen"], ["prevent_opening_multiple_times", "Nur einmal am Tag öffnen"],
  ["prevent_closing_multiple_times", "Nur einmal am Tag schließen"], ["prevent_shading_multiple_times", "Nur einmal am Tag beschatten"]];
const FACADE_NAMES = { N: "Nord", NO: "Nordost", O: "Ost", SO: "Südost", S: "Süd", SW: "Südwest", W: "West", NW: "Nordwest" };
// Pop-ups, die zu den zentralen Hauswerk-Einstellungen gehören (alle anderen gehören zu Heizwerk)
const HOUSE_POPS = ["presence", "vacation", "weather", "notify", "radio", "access", "look"];
// Akzentfarben der Darstellung: [gespeicherter Wert (null = Standard), Name, Anzeigefarbe]
const ACCENTS = [
  [null, "Türkis", "#14b8a6"], ["#0ea5e9", "Himmelblau"], ["#3b82f6", "Blau"], ["#8b5cf6", "Violett"],
  ["#ec4899", "Pink"], ["#f43f5e", "Rot"], ["#f59e0b", "Orange"], ["#84cc16", "Grün"],
];
// Kategorien des Protokolls (Filter-Chips); off = standardmäßig ausgeblendet
const LOG_CATS = {
  presence: { name: "Anwesenheit", icon: "mdi:home-account", c: "#8b5cf6" },
  season: { name: "Saison", icon: "mdi:sun-snowflake-variant", c: "#f97316" },
  target: { name: "Ziel & Heizung", icon: "mdi:thermometer-auto", c: "#14b8a6" },
  window: { name: "Fenster", icon: "mdi:window-open-variant", c: "#3b82f6" },
  manual: { name: "Von Hand", icon: "mdi:hand-back-right-outline", c: "#a78bfa" },
  health: { name: "Geräte", icon: "mdi:heart-pulse", c: "#f43f5e" },
  command: { name: "Thermostat-Befehle", icon: "mdi:access-point", c: "#94a3b8", off: true },
  settings: { name: "Einstellungen", icon: "mdi:cog-outline", c: "#64748b" },
  notify: { name: "Nachrichten", icon: "mdi:message-badge-outline", c: "#0ea5e9" },
};
const SKIES = [["night", "Nacht"], ["dawn", "Sonnenaufgang"], ["day", "Tag"], ["dusk", "Sonnenuntergang"]];
const DEFAULT_VIEW = "start";

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (v, d = 1) => (v === null || v === undefined || isNaN(v) ? "–" : Number(v).toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d }));
const int = (v) => Math.round(v || 0).toLocaleString("de-DE");
const clone = (o) => JSON.parse(JSON.stringify(o));
const hm = (s) => {
  const [h, m] = String(s || "0:0").split(":").map(Number);
  return h * 60 + m;
};
const clampT = (t) => Math.min(30, Math.max(5, Math.round(t * 2) / 2));
/** Farbskala für Temperaturen: kühl blau, mittel grün/gelb, warm orange. */
const tempColor = (t) => {
  if (t == null) return "var(--muted)";
  if (t < 16.5) return "#60a5fa";
  if (t < 18.5) return "#5eead4";
  if (t < 20) return "#a3e635";
  if (t < 21.5) return "#fde047";
  if (t < 23) return "#fbbf24";
  return "#fb923c";
};
/** Farbe für Text: im hellen Theme abgedunkelt, damit sie auf Weiß lesbar bleibt. */
const tint = (c) => `color-mix(in srgb, ${c}, var(--text) var(--shade))`;

class HauswerkPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = this._viewFromPath() || DEFAULT_VIEW;
    this._onLocation = () => {
      const v = this._viewFromPath();
      if (v && v !== this._tab) this._setView(v, false);
    };
    this._data = null;
    this._status = null;
    this._dialog = null;
    this._plan = null;
    this._settings = null;
    this._pop = null;
    this._reports = {};
    this._reportDays = 7;
    this._error = null;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    // Design, Akzentfarbe, Hintergrund und Größe (Hauswerk › Einstellungen › Darstellung)
    this._applyLook(this._pop?.id === "look" ? this._settings : null);
    if (first) this._init();
    // Startseite mit Shortcuts, Werten, Wetter oder Fenstern: Änderungen in HA zeigen (höchstens alle 3 s)
    else if (this._tab === "start" && this._data && !this._busy && Date.now() - (this._hassAt || 0) > 3000 &&
      this._widgets().some((w) => ["shortcuts", "values", "weather", "windows"].includes(w.type))) {
      this._hassAt = Date.now();
      this._renderMain();
    }
  }
  get hass() {
    return this._hass;
  }

  /** Einstellungs-Zeile: Titel mit „?“, Unterzeile, Wert oder Bedienelement rechts (ctl = Bedienelement, am Handy volle Breite). */
  _setRow(key, title, sub, value, text, ctl = false) {
    const on = !!this._help?.[key];
    return `
      <div class="wxr ${ctl ? "ctl" : ""}">
        <div class="wxr-l"><b>${title}<button class="qm ${on ? "on" : ""}" data-action="help" data-k="${key}" aria-label="Erklärung zu ${title}">?</button></b>${sub ? `<small>${sub}</small>` : ""}${on ? `<p class="wxr-h">${text}</p>` : ""}</div>
        <div class="wxr-v">${value}</div>
      </div>`;
  }

  /** Darstellung anwenden: aus den gespeicherten Einstellungen oder (Vorschau) aus dem offenen Pop-up. */
  _applyLook(src) {
    const p = src || this._data?.settings || {};
    const theme = p.look_theme || "auto";
    // auto = hell oder dunkel wie in Home Assistant eingestellt (Profil › Design)
    this.toggleAttribute("dark", theme === "dark" || (theme === "auto" && !!this._hass?.themes?.darkMode));
    const c = /^#[0-9a-f]{6}$/i.test(p.look_accent || "") ? p.look_accent : null;
    if (c) {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16) / 255);
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      // im hellen Design etwas dunkler, damit Text in der Akzentfarbe auf Weiß lesbar bleibt
      this.style.setProperty("--accent", this.hasAttribute("dark") ? c : `color-mix(in srgb, ${c} 82%, #000)`);
      this.style.setProperty("--ink", lum > 0.6 ? "#1f2328" : "#fff");
    } else {
      this.style.removeProperty("--accent");
      this.style.removeProperty("--ink");
    }
    const bg = p.look_background || "pattern";
    this.setAttribute("bg", bg);
    if (bg === "daytime") this.setAttribute("sky", this._skyPhase());
    else this.removeAttribute("sky");
    this.setAttribute("size", this._lookSize());
  }

  /** Tageszeit für den Himmel in der Kopfzeile: aus sun.sun, sonst aus der Uhrzeit. */
  _skyPhase() {
    const s = this._hass?.states?.[this._data?.settings?.sun_entity || "sun.sun"];
    const el = Number(s?.attributes?.elevation);
    if (s && !isNaN(el)) {
      if (el > 6) return "day";
      if (el < -6) return "night";
      return s.attributes.rising ? "dawn" : "dusk";
    }
    const h = new Date().getHours();
    return h < 6 || h >= 21 ? "night" : h < 8 ? "dawn" : h < 18 ? "day" : "dusk";
  }

  /** Größe der Oberfläche: nur auf diesem Gerät gemerkt. */
  _lookSize() {
    try {
      return localStorage.getItem("hauswerk.groesse") || "m";
    } catch (e) {
      return "m";
    }
  }

  /** Uhrzeit und Wetter oben rechts (je nach Darstellung). */
  _headInfo() {
    const p = this._data.settings;
    const parts = [];
    if (p.look_header_clock) parts.push(`<span class="hclock">${new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</span>`);
    if (p.look_header_weather !== false) {
      const w = this._weather();
      if (w) parts.push(`<span class="hwx" title="${esc(w.name)}: ${esc(w.label)}"><ha-icon icon="${w.icon}"></ha-icon>${fmt(w.temp)}°</span>`);
    }
    return parts.length ? `<div class="hinfo">${parts.join("")}</div>` : "";
  }
  set narrow(value) {
    this._narrow = value;
    this.toggleAttribute("narrow", !!value);
  }
  set panel(value) {
    this._panel = value;
  }
  set route(_) {}

  connectedCallback() {
    if (this._hass && this._data && !this._unsub) this._subscribe();
    window.addEventListener("location-changed", this._onLocation);
    window.addEventListener("popstate", this._onLocation);
    // Uhrzeit in der Kopfzeile aktuell halten (ohne die Seite neu zu zeichnen)
    this._clock = setInterval(() => {
      const c = this.shadowRoot.querySelector(".hclock");
      if (c) c.textContent = new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    }, 15000);
    this._timer = setInterval(() => {
      this._reports = {};
      if (["start", "overview", "report"].includes(this._tab)) this._renderMain();
    }, 5 * 60 * 1000);
  }
  disconnectedCallback() {
    window.removeEventListener("location-changed", this._onLocation);
    window.removeEventListener("popstate", this._onLocation);
    clearInterval(this._timer);
    clearInterval(this._clock);
    if (this._io) this._io.disconnect();
    for (const sub of Object.values(this._fcSubs || {})) sub.then((u) => u()).catch(() => {});
    this._fcSubs = {};
    this._fc = {};
    if (this._unsub) {
      this._unsub.then((u) => u()).catch(() => {});
      this._unsub = null;
    }
    if (this._rwUnsub) {
      this._rwUnsub.then((u) => u && u()).catch(() => {});
      this._rwUnsub = null;
    }
    // Protokoll beim nächsten Öffnen neu laden
    if (this._logUnsub) this._logUnsub.then((u) => u()).catch(() => {});
    this._logUnsub = null;
    this._log = null;
  }

  async _init() {
    this._renderShell();
    try {
      this._data = await this._hass.callWS({ type: "hauswerk/heizen/get" });
      this._status = this._data.status;
      this._renderShell();
      this._renderMain();
      this._subscribe();
    } catch (err) {
      this._error = err.message || String(err);
      this._renderMain();
    }
  }

  _subscribe() {
    this._unsub = this._hass.connection.subscribeMessage(
      (status) => {
        this._status = status;
        if (["start", "overview"].includes(this._tab) && !this._busy) this._renderMain();
        else this._renderChrome();
      },
      { type: "hauswerk/heizen/subscribe" }
    );
    if (this._data?.rollwerk) {
      this._rwStatus = this._data.rollwerk.status;
      this._rwUnsub = this._hass.connection.subscribeMessage(
        (status) => {
          this._rwStatus = status;
          if (["shutters", "start"].includes(this._tab) && !this._busy && !this._pop) this._renderMain();
        },
        { type: "hauswerk/rollwerk/subscribe" }
      ).catch(() => null);
    }
  }

  async _ws(msg) {
    try {
      return await this._hass.callWS(msg);
    } catch (err) {
      this._toast(err.message || "Fehler beim Speichern");
      throw err;
    }
  }

  get _admin() {
    return !!this._data?.is_admin;
  }

  _rooms() {
    return Object.values(this._data?.rooms || {}).sort((a, b) => a.name.localeCompare(b.name, "de"));
  }

  _roomColor(id) {
    const ids = this._rooms().map((r) => r.id);
    return ROOM_COLORS[Math.max(0, ids.indexOf(id)) % ROOM_COLORS.length];
  }

  _report(days) {
    if (this._reports[days]) return this._reports[days];
    if (!this._reports["loading" + days]) {
      this._reports["loading" + days] = true;
      this._hass
        .callWS({ type: "hauswerk/heizen/report", days })
        .then((r) => (this._reports[days] = r))
        .catch(() => (this._reports[days] = {}))
        .finally(() => {
          delete this._reports["loading" + days];
          this._renderMain();
        });
    }
    return null;
  }

  // ------------------------------------------------------------ Gerüst
  _renderShell() {
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div id="sentinel" aria-hidden="true"></div>
      <header class="top" id="head"></header>
      <div class="app">
        <div id="chips"></div>
        <main id="main"><div class="loading"><div class="spinner"></div></div></main>
      </div>
      <nav id="bnav" class="bnav" aria-label="Navigation"></nav>
      <div id="dialog"></div>
      <div id="pop"></div>
      <div id="toast" class="toast" hidden></div>`;
    this._renderChrome();
    // Kopfzeile schrumpft, sobald gescrollt wird (funktioniert mit jedem Scroll-Container)
    if (this._io) this._io.disconnect();
    const sentinel = this.shadowRoot.getElementById("sentinel");
    if (sentinel && "IntersectionObserver" in window) {
      this._io = new IntersectionObserver(([e]) => this.shadowRoot.getElementById("head")?.classList.toggle("slim", !e.isIntersecting));
      this._io.observe(sentinel);
    }
    if (!this._listening) {
      this._listening = true;
      const root = this.shadowRoot;
      root.addEventListener("click", (e) => this._onClick(e));
      root.addEventListener("input", (e) => this._onInput(e));
      root.addEventListener("change", (e) => this._onInput(e, true));

    }
  }

  _markTab() {
    this._renderChrome();
  }

  // ------------------------------------------------------------ Navigation (eigene Adresse je Modul)
  get _base() {
    return `/${this._panel?.url_path || "hauswerk"}`;
  }

  _viewFromPath() {
    const parts = location.pathname.split("/").filter(Boolean);
    if (parts[0] !== (this._panel?.url_path || "hauswerk")) return null;
    if (parts[1] === "heizen" && parts[2] === "raum" && parts[3]) {
      this._roomId = decodeURIComponent(parts[3]);
      return "room";
    }
    if (parts[1] === "heizen") {
      // /hauswerk/heizen ohne Unterseite = Räume
      const slug = `heizen/${parts[2] || "raeume"}`;
      return Object.keys(SLUGS).find((k) => SLUGS[k] === slug) || "overview";
    }
    if (parts[1] === "rollwerk") return parts[2] === "einstellungen" ? "shutset" : "shutters";
    // /hauswerk/einstellungen = zentrale Hauswerk-Einstellungen
    if (parts[1] === "einstellungen") return "house";
    if (parts[1] === "protokoll") return "log";
    // alte Adressen (/hauswerk/raeume …) weiter verstehen
    const old = HEAT_VIEWS.find((v) => v.slug === parts[1]);
    return old ? old.id : DEFAULT_VIEW;
  }

  _setView(view, push = true) {
    if (this._tab === "plans" && view !== "plans" && this._plan?.dirty && !confirm("Ungespeicherte Änderungen am Heizplan verwerfen?")) return;
    if (view !== this._tab) this._setQuery = "";
    this._tab = view;
    if (view === "settings" || view === "house") this._settings = null;
    // Adresse nur innerhalb von Home Assistant ändern (nicht in der Vorschau-Datei)
    if (push && location.pathname.startsWith(this._base)) {
      history.pushState(null, "", `${this._base}/${SLUGS[view]}${view === "room" ? `/${encodeURIComponent(this._roomId)}` : ""}`);
      window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    }
    this._renderMain();
    window.scrollTo({ top: 0 });
  }

  // ------------------------------------------------------------ Kopfleiste, Modul-Reiter, Status-Chips
  _renderChrome() {
    const head = this.shadowRoot.getElementById("head");
    if (head) head.innerHTML = this._headHtml();
    const bnav = this.shadowRoot.getElementById("bnav");
    if (bnav) bnav.innerHTML = this._data && !this._error ? this._bnavHtml() : "";
    const chips = this.shadowRoot.getElementById("chips");
    if (chips)
      chips.innerHTML =
        this._data && !this._error
          ? (["start", "overview", "room", "house", "log", "shutters", "shutset"].includes(this._tab) ? "" : this._chipsHtml())
            + (MODULES[0].views.includes(this._tab) ? this._heatNavHtml() : "") + (MODULES[1].views.includes(this._tab) ? this._rwNavHtml() : "")
          : "";
  }

  /** Untere Leiste fürs Handy: Start · Module · Einstellungen (Unterseiten eines Moduls über seine Unterleiste). */
  _bnavHtml() {
    const f = this._data ? this._facts() : null;
    const on = (ids) => (ids.includes(this._tab) ? "on" : "");
    const item = (tab, ids, icon, label, badge = "") =>
      `<button class="bn ${on(ids)}" data-action="tab" data-tab="${tab}"><span class="bi">${modIcon(icon)}${badge}</span><span>${label}</span></button>`;
    return [
      item("start", ["start"], "mdi:view-dashboard-outline", "Start"),
      ...MODULES.map((m) =>
        item(m.views.includes(this._tab) ? this._tab : m.views[0], m.views, m.logo ? `logo:${m.logo}` : m.icon, m.name,
          m.id === "heizen" && f && (f.open || f.heating) ? `<em class="${f.open ? "warn" : ""}">${f.open || f.heating}</em>` : "")
      ),
      item("house", ["house", "log"], "mdi:cog-outline", "Einstellungen"),
    ].join("");
  }

  _facts() {
    const rooms = this._rooms();
    const st = this._status?.rooms || {};
    const infos = rooms.map((r) => st[r.id] || {});
    return {
      rooms,
      heating: infos.filter((s) => s.heating).length,
      open: infos.filter((s) => s.windows_open).length,
      hints: this._hints().filter((h) => h.lvl === "warn").length,
      withPlan: rooms.filter((r) => r.schedule_entity || this._data.plans?.[r.plan_id] || (r.schedule || []).length).length,
    };
  }

  /** Alle Hinweise an einer Stelle: warn = sollte man beheben, info = gut zu wissen. */
  _hints() {
    const out = [];
    const S = this._hass?.states || {};
    const s = this._status || {};
    const set = this._data?.settings || {};
    const bad = (id) => !S[id] || ["unavailable", "unknown"].includes(S[id].state);
    const add = (lvl, icon, text, sub, action, data = {}) => out.push({ lvl, icon, text, sub, action, data });
    for (const r of this._rooms()) {
      const rs = s.rooms?.[r.id] || {};
      const climates = r.climates || [];
      if (r.enabled === false) {
        add("info", "mdi:robot-off-outline", "Automatik aus", r.name, "room-edit", { id: r.id });
        continue;
      }
      if (!climates.length) add("warn", "mdi:thermostat", "Kein Thermostat zugeordnet", r.name, "room-edit", { id: r.id, rtab: "devices" });
      for (const c of climates) if (bad(c)) add("warn", "mdi:lan-disconnect", "Thermostat nicht erreichbar", `${r.name} · ${this._entityName(c)}`, "room-edit", { id: r.id, rtab: "devices" });
      if (r.temp_sensor && bad(r.temp_sensor)) add("warn", "mdi:thermometer-off", "Raumsensor nicht erreichbar", `${r.name} · ${this._entityName(r.temp_sensor)}`, "room-edit", { id: r.id, rtab: "devices" });
      else if (climates.length && rs.room_temp == null && s.rooms) add("warn", "mdi:thermometer-off", "Kein Messwert", r.name, "room-edit", { id: r.id, rtab: "devices" });
      for (const w of r.windows || []) if (bad(w)) add("info", "mdi:window-shutter-alert", "Fensterkontakt nicht erreichbar", `${r.name} · ${this._entityName(w)}`, "room-edit", { id: r.id, rtab: "devices" });
      if (r.schedule_entity && bad(r.schedule_entity)) add("warn", "mdi:calendar-remove", "Zeitplan nicht erreichbar", `${r.name} · ${this._entityName(r.schedule_entity)}`, "room-edit", { id: r.id });
      else if (!r.schedule_entity && !this._data.plans?.[r.plan_id] && !(r.schedule || []).length) add("info", "mdi:calendar-blank-outline", "Kein Heizplan – bleibt auf Eco", r.name, "plan-open", { id: r.id });
      for (const b of rs.battery_low || [])
        add("warn", b.level === 0 ? "mdi:battery-alert-variant-outline" : "mdi:battery-10", `Batterie schwach${b.level ? ` · ${fmt(b.level, 0)} %` : ""}`, `${r.name} · ${b.name}`, "room-edit", { id: r.id, rtab: "devices" });
      if (rs.vent) add("info", "mdi:weather-windy", `Jetzt lüften – ${fmt(rs.vent.rh, 0)} % Luftfeuchte`, `${r.name} · draußen trockenere Luft (${fmt(rs.vent.outside_g)} statt ${fmt(rs.vent.inside_g)} g/m³), Taupunkt ${fmt(rs.vent.dew_point)} °C`, "settings-go", { sub: "vent" });
      else if (rs.humidity >= 70) add("info", "mdi:water-alert", `Luftfeuchte ${fmt(rs.humidity, 0)} %`, `${r.name} · Lüften bringt gerade wenig, draußen ist es ähnlich feucht`, "settings-go", { sub: "vent" });
      if (rs.cold_radiator && (s.cold_rooms || []).length < 2)
        add("warn", "mdi:radiator-off", "Heizkörper bleibt kalt", `${r.name} · Ventil ${fmt(rs.cold_radiator.valve, 0)} % seit ${rs.cold_radiator.minutes} Min., nur +${fmt(rs.cold_radiator.rise)} °C – entlüften oder Ventilstift prüfen`, "room-page", { id: r.id });
      for (const c of rs.conflicts || [])
        add("warn", "mdi:account-switch-outline", "Zweite Regelung stellt dasselbe Thermostat", `${r.name} · ${c.name} · ${c.by.join(", ")}`, "room-edit", { id: r.id, rtab: "devices" });
      for (const c of rs.pair_broken || [])
        add("info", "mdi:link-variant-off", "Heizkörper folgt dem Wandthermostat nicht", `${r.name} · ${this._entityName(c)} – Hauswerk stellt es selbst`, "room-edit", { id: r.id, rtab: "devices" });
      for (const c of rs.duty_blocked || [])
        add("warn", "mdi:access-point-off", "Gerät darf gerade nicht funken", `${r.name} · ${this._entityName(c)} · Duty Cycle erreicht`, "settings-go", { sub: "radio" });
      if (rs.window_virtual) add("info", "mdi:window-open-variant", "Fenster vermutlich offen", `${r.name} · Temperatur fällt schnell – Fensterpause`, "tab", { tab: "overview" });
    }
    for (const o of this._openWindows ? this._openWindows() : []) {
      const mins = o.s.last_changed ? (Date.now() - new Date(o.s.last_changed)) / 60000 : 0;
      if (mins >= 30) add("info", "mdi:window-open-variant", `Fenster seit ${mins < 90 ? `${Math.round(mins)} Min.` : `${fmt(mins / 60)} h`} offen`, `${o.room.name} · ${this._entityName(o.id)}`, "tab", { tab: "overview" });
    }
    if ((s.cold_rooms || []).length >= 2) add("warn", "mdi:water-boiler-alert", "Mehrere Heizkörper bleiben kalt", `${s.cold_rooms.map((id) => this._data.rooms[id]?.name || id).join(", ")} – liefert die Heizung Wärme? Vorlauf, Wasserdruck und Pumpe prüfen`, "settings-go", { sub: "demand", heat: true });
    if (s.demand?.error) add("warn", "mdi:water-boiler-off", "Wärmeerzeuger nicht erreichbar", `${this._entityName(this._data.settings.demand_entity)} – Wärmeanforderung pausiert`, "settings-go", { sub: "demand", heat: true });
    if (s.radio?.busy) add("warn", "mdi:access-point-network", `Funk ausgelastet · ${fmt(s.radio.level, 0)} %`, `${this._entityName(s.radio.entity)} · Hauswerk sendet nur wichtige Änderungen`, "settings-go", { sub: "radio" });
    if (s.vacation_calendar_error) add("warn", "mdi:calendar-alert", "Urlaubskalender nicht lesbar", s.vacation_calendar_error, "settings-go", { sub: "vacation" });
    for (const [pid, err] of Object.entries(s.plan_errors || {})) add("warn", "mdi:calendar-alert", `Kalender von Plan „${this._data.plans?.[pid]?.name || pid}“ nicht lesbar`, err, "plan-sel", { kind: "plan", id: pid });
    for (const x of this._wxAlerts()) add("info", x.icon, x.text, x.sub, "settings-go", { sub: "weather" });
    if (!(set.persons || []).length) add("info", "mdi:account-question-outline", "Keine Personen gewählt", "Ohne Personen gibt es kein automatisches „Abwesend“", "settings-go", { sub: "presence" });
    return out.sort((a, b) => (a.lvl === b.lvl ? 0 : a.lvl === "warn" ? -1 : 1));
  }

  _headHtml() {
    const mod = MODULES.find((m) => m.views.includes(this._tab));
    const sub = [...HEAT_VIEWS, ...SHUT_VIEWS].find((v) => v.id === this._tab);
    const roomName = this._tab === "room" ? this._data?.rooms?.[this._roomId]?.name : null;
    const title = mod ? `${mod.name}${roomName ? ` · ${roomName}` : sub ? ` · ${sub.name}` : ""}` : this._tab === "house" ? "Einstellungen" : this._tab === "log" ? "Protokoll" : "Start";
    const f = this._data ? this._facts() : null;
    const badge = (id) => {
      if (!f || id !== "heizen") return "";
      return f.open ? `<em class="badge warn">${f.open} OFFEN</em>` : f.heating ? `<em class="badge ok">${f.heating} HEIZT</em>` : "";
    };
    const tab = (id, name, icon, target) => `
      <button class="mtab ${id === "start" ? (this._tab === "start" ? "active" : "") : mod?.id === id ? "active" : ""}" data-action="tab" data-tab="${target}">
        ${modIcon(icon)}<span class="mt"><b>${name}</b></span>${badge(id)}
      </button>`;
    const soon = (m) => `
      <button class="mtab soon" disabled title="${m.name}: kommt später" aria-label="${m.name}, noch nicht verfügbar">
        <ha-icon icon="${m.icon}"></ha-icon><span class="mt"><b>${m.name}</b></span>
      </button>`;
    return `
      <div class="bar">
        <button class="menu" data-action="menu" aria-label="Menü"><ha-icon icon="mdi:menu"></ha-icon></button>
        <div class="brand">${LOGO}</div>
        <div class="ttl"><small>HAUSWERK</small><b>${esc(title)}</b><span>Haussteuerung · Version ${VERSION}</span></div>
        <div class="hacts">
          ${this._data ? this._headInfo() : ""}
          ${(() => {
            if (!this._data) return "";
            const h = this._hints();
            const warn = h.filter((x) => x.lvl === "warn").length;
            return `<button class="bell ${warn ? "warn" : h.length ? "info" : ""}" data-action="hints-open" title="${h.length ? `${h.length} Hinweis${h.length > 1 ? "e" : ""}` : "Keine Hinweise"}" aria-label="Hinweise">
              <ha-icon icon="${h.length ? "mdi:bell-badge-outline" : "mdi:bell-outline"}"></ha-icon>${warn ? `<em>${warn}</em>` : h.length ? "<i></i>" : ""}</button>`;
          })()}
          ${this._data ? `<button class="bell gear ${["house", "log"].includes(this._tab) ? "on" : ""}" data-action="tab" data-tab="house" title="Hauswerk-Einstellungen (für alle Module)" aria-label="Einstellungen"><ha-icon icon="mdi:cog-outline"></ha-icon></button>` : ""}
        </div>
      </div>
      <nav class="mtabs">
        ${tab("start", "Start", "mdi:view-dashboard-outline", "start")}
        ${MODULES.map((m) => tab(m.id, m.name, m.logo ? `logo:${m.logo}` : m.icon, mod?.id === m.id ? this._tab : m.views[0])).join("")}
        ${COMING.map(soon).join("")}
      </nav>`;
  }

  /** Unterleiste im Modul Heizen: Räume, Heizpläne, Bericht, Einstellungen. */
  _heatNavHtml() {
    const f = this._facts();
    const badge = (id) => {
      if (id === "overview") return f.open ? `<em class="warn">${f.open} offen</em>` : f.heating ? `<em class="ok">${f.heating} heizt</em>` : "";
      if (id === "plans" && f.rooms.length - f.withPlan > 0) return `<em>${f.rooms.length - f.withPlan} ohne Plan</em>`;
      return "";
    };
    return `<nav class="heatnav">${HEAT_VIEWS.filter((v) => !v.hidden).map(
      (v) => `<button class="hnav ${this._tab === v.id || (v.id === "settings" && this._tab === "plans") || (v.id === "overview" && this._tab === "room") ? "on" : ""}" data-action="tab" data-tab="${v.id}"><ha-icon icon="${v.icon}"></ha-icon><span>${v.name}</span>${badge(v.id)}</button>`
    ).join("")}</nav>`;
  }

  _chipsHtml() {
    const f = this._facts();
    if (!f.rooms.length) return "";
    const s = this._status || {};
    const set = this._data.settings;
    const c = (icon, val, cap, k = "", action = "") =>
      `<${action ? `button data-action="${action}"` : "span"} class="schip" ${k ? `style="--c:${k}"` : ""}><ha-icon icon="${icon}"></ha-icon><span><b>${esc(val)}</b><small>${esc(cap)}</small></span></${action ? "button" : "span"}>`;
    const presence = s.vacation ? ["mdi:palm-tree", "Urlaub", "#34d399"] : s.away ? ["mdi:home-export-outline", "abwesend", "#94a3b8"] : set.party ? ["mdi:party-popper", "Party", "#e879f9"] : set.guest ? ["mdi:account-group-outline", "Gäste", "#e879f9"] : ["mdi:home-heart", "zu Hause", "#34d399"];
    return `<div class="schips">${[
      c(f.heating ? "mdi:fire" : "mdi:fire-off", `${f.heating} von ${f.rooms.length}`, "heizen", f.heating ? "#fb923c" : ""),
      c(f.open ? "mdi:window-open-variant" : "mdi:window-closed-variant", f.open ? `${f.open} offen` : "alle zu", "Fenster", f.open ? "#22d3ee" : "#34d399"),
      c(presence[0], presence[1], "Anwesenheit", presence[2]),
      s.outside_temp != null ? c(s.outside_temp <= 0 ? "mdi:snowflake-thermometer" : "mdi:thermometer", `${fmt(s.outside_temp)} °C`, "Außen") : "",
      s.summer ? c("mdi:weather-sunny", "Sommerpause", "Saison", "#facc15") : "",
      set.eco_force ? c("mdi:leaf", "erzwungen", "Eco", "#22c55e") : "",
      s.long_away ? c("mdi:snowflake-thermometer", "Frostschutz", "lange weg", "#38bdf8") : "",
      s.liming ? c("mdi:water-sync", "läuft", "Entkalken", "#38bdf8") : "",
      c(f.hints ? "mdi:alert-circle-outline" : "mdi:check-circle-outline", f.hints ? `${f.hints} Hinweis${f.hints > 1 ? "e" : ""}` : "alles gut", "Hinweise", f.hints ? "#f59e0b" : "#34d399", "hints-open"),
    ].join("")}</div>`;
  }

  _toast(text) {
    const el = this.shadowRoot.getElementById("toast");
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => (el.hidden = true), 3500);
  }

  _renderMain() {
    const main = this.shadowRoot.getElementById("main");
    if (!main) return;
    if (this._error) {
      main.innerHTML = `<section class="card empty"><ha-icon icon="mdi:alert-circle-outline"></ha-icon><h2>Hauswerk antwortet nicht</h2><p>${esc(this._error)}</p></section>`;
      return;
    }
    this._applyLook(this._pop?.id === "look" ? this._settings : null);
    this._renderChrome();
    // Hintergrund passend zum Bereich: Startseite oder Heizen
    this.setAttribute("view", MODULES[0].views.includes(this._tab) ? "heat" : "start");
    if (!this._data) return;
    const view = { start: this._viewStart, house: this._viewHouse, log: this._viewLog, overview: this._viewOverview, plans: this._viewPlans, report: this._viewReport, settings: this._viewSettings, room: this._viewRoom,
      shutters: this._viewShutters, shutset: () => this._settingsPage("rw") }[this._tab] || this._viewStart;
    main.innerHTML = view.call(this);
  }

  // ------------------------------------------------------------ Bausteine
  _chip(mode, label) {
    const m = MODE[mode] || MODE.aus;
    return `<span class="mode" style="--c:${m.c}"><ha-icon icon="${m.i}"></ha-icon>${esc(label)}</span>`;
  }

  _stepper(kind, key, value, { placeholder = null, small = false } = {}) {
    const shown = value ?? placeholder;
    return `
      <div class="stepper ${small ? "small" : ""}">
        <button class="sbtn" data-action="step" data-kind="${kind}" data-key="${esc(key)}" data-delta="-0.5" aria-label="kälter">−</button>
        <b style="color:${value == null ? "var(--muted)" : tint(tempColor(shown))}">${fmt(shown)} °C</b>
        <button class="sbtn" data-action="step" data-kind="${kind}" data-key="${esc(key)}" data-delta="0.5" aria-label="wärmer">+</button>
      </div>`;
  }

  _sectionHead(icon, title, right = "") {
    return `<div class="shead"><ha-icon icon="${icon}"></ha-icon><h3>${title}</h3><span class="grow"></span>${right}</div>`;
  }

  // ------------------------------------------------------------ Start (Zuhause mit Modul-Kacheln)
  _viewStart() {
    const f = this._facts();
    const n = f.rooms.length;
    const warn = this._hints().filter((h) => h.lvl === "warn");
    const list = this._widgets();
    const edit = this._wEdit && this._admin;
    return `
      ${warn.length ? `
      <button class="hstrip" data-action="hints-open">
        <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
        <span class="grow"><b>${warn.length} Hinweis${warn.length > 1 ? "e" : ""}</b> · ${esc(warn[0].text)}${warn[0].sub ? ` (${esc(warn[0].sub)})` : ""}${warn.length > 1 ? " …" : ""}</span>
        <span class="hs-go">Anzeigen<ha-icon icon="mdi:chevron-right"></ha-icon></span>
      </button>` : ""}

      <div class="shead outer">
        <ha-icon icon="mdi:widgets-outline"></ha-icon><h3>Übersicht</h3><span class="grow"></span>
        ${this._admin ? `
          ${edit ? `<button class="link" data-action="w-add-open"><ha-icon icon="mdi:plus"></ha-icon>Widget</button>` : ""}
          <button class="link" data-action="w-edit"><ha-icon icon="${edit ? "mdi:check" : "mdi:pencil-outline"}"></ha-icon>${edit ? "Fertig" : "Anpassen"}</button>` : ""}
      </div>
      ${list.length
        ? `<div class="wgrid">${list.map((w, i) => this._widget(w, i, edit, list.length)).join("")}</div>`
        : `<section class="card empty small"><p>Keine Widgets.${this._admin ? ` <button class="link inline" data-action="w-add-open">Widget hinzufügen</button>` : ""}</p></section>`}
      ${n ? "" : `
      <section class="card empty">
        <ha-icon icon="mdi:home-plus-outline"></ha-icon><h2>Noch keine Räume</h2>
        <p>Lege einen Raum an und ordne Thermostate, Fensterkontakte und einen Raumsensor zu.</p>
        ${this._admin ? `<button class="primary" data-action="room-new"><ha-icon icon="mdi:plus"></ha-icon>Raum anlegen</button>` : ""}
      </section>`}`;
  }

  // ------------------------------------------------------------ Widgets der Startseite
  /** Widgets aus den Einstellungen (für alle Benutzer gleich), sonst eine Grundauswahl. */
  _widgets() {
    const list = this._data.settings.start_widgets;
    return Array.isArray(list) ? list : DEFAULT_WIDGETS.map((w, i) => ({ id: `d${i}`, title: null, entities: [], ...w }));
  }

  /** Größe eines Widgets: s = klein, m = mittel, l = groß (alte Angabe „w“ = groß). */
  _wSize(w) {
    return w.size === "w" ? "l" : ["s", "m", "l"].includes(w.size) ? w.size : "m";
  }

  async _saveWidgets(list) {
    this._data.settings = await this._ws({ type: "hauswerk/heizen/settings/save", settings: { start_widgets: list } });
    this._renderMain();
  }

  _widget(w, i, edit, count) {
    const def = WIDGETS[w.type];
    if (!def) return "";
    const z = this._wSize(w);
    let body;
    try {
      body = this[`_w_${w.type}`](w, z);
    } catch (err) {
      body = `<p class="muted small">Widget kann nicht angezeigt werden.</p>`;
    }
    const tools = edit
      ? `<span class="wtools">
          <button class="icon tiny" data-action="w-move" data-i="${i}" data-d="-1" title="Nach vorne" ${i === 0 ? "disabled" : ""}><ha-icon icon="mdi:chevron-left"></ha-icon></button>
          <button class="icon tiny" data-action="w-move" data-i="${i}" data-d="1" title="Nach hinten" ${i === count - 1 ? "disabled" : ""}><ha-icon icon="mdi:chevron-right"></ha-icon></button>
          <button class="icon tiny" data-action="w-conf" data-i="${i}" title="Einstellen"><ha-icon icon="mdi:cog-outline"></ha-icon></button>
          <button class="icon tiny danger-t" data-action="w-del" data-i="${i}" title="Entfernen"><ha-icon icon="mdi:close"></ha-icon></button>
        </span>`
      : def.go
        ? `<button class="link tiny" data-action="tab" data-tab="${def.go}" title="Öffnen"><span>Öffnen</span><ha-icon icon="mdi:chevron-right"></ha-icon></button>`
        : def.pop && this._admin && z !== "s"
          ? `<button class="icon tiny" data-action="settings-go" data-sub="${def.pop}" title="Einstellungen"><ha-icon icon="mdi:cog-outline"></ha-icon></button>`
          : "";
    return `
      <section class="card wdg sz-${z} ${edit ? "edit" : ""}" style="--c:${def.c}">
        <div class="wh"><span class="wic"><ha-icon icon="${def.icon}"></ha-icon></span><b>${esc(w.title || def.name)}</b><span class="grow"></span>${tools}</div>
        <div class="wb">${body}</div>
      </section>`;
  }

  /** Kennzahlen fürs Heizen-Widget. */
  _heatFacts() {
    const f = this._facts();
    const st = this._status?.rooms || {};
    const temps = f.rooms.map((r) => st[r.id]?.room_temp).filter((t) => t != null);
    const avg = temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : null;
    const below = f.rooms.filter((r) => {
      const x = st[r.id] || {};
      return x.room_temp != null && x.target != null && !["aus", "fenster", "sommer", "warm", "entkalken"].includes(x.mode) && x.target - x.room_temp >= 0.5;
    }).length;
    const rep = this._report(14);
    const today = rep ? this._sumDay(rep, 13) : null;
    const v = this._status?.summer
      ? ["mdi:weather-sunny", "Sommerpause", "#facc15"]
      : f.open
        ? ["mdi:window-open-variant", `${f.open} Fenster offen`, "#22d3ee"]
        : below
          ? ["mdi:thermometer-chevron-up", `${below} unter Soll`, "#fb923c"]
          : ["mdi:check-circle-outline", "Alle im Soll", "#34d399"];
    return { f, st, avg, today, v };
  }

  _w_heat(w, z) {
    const { f, st, avg, today, v } = this._heatFacts();
    const big = `<div class="wbig"><span>${fmt(avg)}<small>°C</small></span>${z === "s" ? "" : `<span class="wverdict" style="--c:${v[2]}"><ha-icon icon="${v[0]}"></ha-icon>${v[1]}</span>`}</div>`;
    if (z === "s") return `${big}<div class="wline" style="--c:${v[2]}"><ha-icon icon="${v[0]}"></ha-icon>${v[1]}</div>`;
    const mini = (icon, val, cap) => `<div class="wmini"><ha-icon icon="${icon}"></ha-icon><b>${val}</b><small>${cap}</small></div>`;
    const minis = `
      <div class="wminis">
        ${mini(f.heating ? "mdi:fire" : "mdi:fire-off", `${f.heating}/${f.rooms.length}`, "heizen")}
        ${mini(f.open ? "mdi:window-open-variant" : "mdi:window-closed-variant", f.open || "0", "offen")}
        ${mini("mdi:timer-outline", today ? fmt(today.heat / 60) : "–", "h heute")}
      </div>`;
    if (z === "m") return big + minis;
    // groß: zusätzlich jeder Raum mit Ist, Soll und Betriebsart
    const rows = f.rooms
      .map((r) => {
        const rs = st[r.id] || {};
        const m = MODE[rs.mode] || MODE.aus;
        if (!(r.climates || []).length) return `<div class="wroom setup"><ha-icon icon="${esc(roomIcon(r))}"></ha-icon><b>${esc(r.name)}</b><span class="grow"></span><small>nicht eingerichtet</small></div>`;
        return `<div class="wroom" style="--c:${m.c}"><ha-icon icon="${esc(roomIcon(r))}"></ha-icon><b>${esc(r.name)}</b>
          <span class="grow"></span>${rs.heating ? `<ha-icon class="gf" icon="mdi:fire"></ha-icon>` : ""}<span>${fmt(rs.room_temp)}°</span><small>→ ${fmt(rs.target)}°</small><ha-icon class="wm" icon="${m.i}" title="${esc(rs.mode_label || "")}"></ha-icon></div>`;
      })
      .join("");
    return `<div class="wsplit"><div>${big}${minis}</div><div class="wrooms">${rows}</div></div>`;
  }

  /** Bekannte Personen mit Ort und Entfernung zu Hause (GPS der Person, sonst Entfernungs-Sensor). */
  _people(idsArg = null, zoneArg = null) {
    const st = this._hass.states;
    const ids = idsArg || ((this._data.settings.persons || []).length ? this._data.settings.persons : Object.keys(st).filter((e) => e.startsWith("person.")));
    const zoneId = zoneArg || this._data.settings.home_zone || "zone.home";
    const home = st[zoneId]?.attributes || st["zone.home"]?.attributes || {};
    // Zustand einer Person in der Wohnung: „home“ bei zone.home, sonst der Name der Zone
    const homeState = zoneId === "zone.home" ? "home" : st[zoneId]?.attributes?.friendly_name || "home";
    const rad = (d) => (d * Math.PI) / 180;
    const km = (a) => {
      if (a.latitude == null || home.latitude == null) return null;
      const dLat = rad(a.latitude - home.latitude), dLon = rad(a.longitude - home.longitude);
      const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(home.latitude)) * Math.cos(rad(a.latitude)) * Math.sin(dLon / 2) ** 2;
      return 6371 * 2 * Math.asin(Math.sqrt(h));
    };
    const toKm = (v, unit) => (v == null || isNaN(v) ? null : unit === "m" ? v / 1000 : unit === "mi" ? v * 1.609 : unit === "ft" ? v * 0.0003048 : v);
    return ids
      .map((id) => {
        const s = st[id];
        if (!s) return null;
        const a = s.attributes || {};
        const slug = id.split(".")[1];
        const name = a.friendly_name || slug;
        let dist = km(a);
        if (dist == null) {
          // Entfernungs-Sensor der Person, z. B. aus der Integration „Nähe“
          const sensor = (this._data.settings.proximity_sensors || []).concat(Object.keys(st).filter((e) => e.startsWith("sensor.") && st[e].attributes.device_class === "distance"))
            .find((e) => e.includes(slug) || (st[e]?.attributes?.friendly_name || "").toLowerCase().includes(name.toLowerCase()));
          if (sensor) dist = toKm(parseFloat(st[sensor].state), st[sensor].attributes.unit_of_measurement);
        }
        const home_ = s.state === homeState;
        const zone = !home_ && s.state !== "not_home" && !["unknown", "unavailable"].includes(s.state) ? st[`zone.${s.state}`]?.attributes?.friendly_name || s.state : null;
        const where = home_ ? "zu Hause" : zone || (["unknown", "unavailable"].includes(s.state) ? "unbekannt" : "unterwegs");
        // Abstand in Metern (erst ab 10 km in Kilometern)
        const distTxt = home_ || dist == null ? "" : dist < 10 ? `${(Math.round((dist * 1000) / 10) * 10).toLocaleString("de-DE")} m` : `${fmt(dist, 0)} km`;
        return { id, name, home: home_, where, dist, distTxt, pic: a.entity_picture || null };
      })
      .filter(Boolean)
      .sort((a, b) => (b.home - a.home) || (a.dist ?? 1e9) - (b.dist ?? 1e9));
  }

  _peopleHtml(z) {
    const people = this._people();
    if (!people.length) return z === "s" ? "" : `<p class="muted small" style="margin-top:10px">Keine Personen bekannt – unter Einstellungen › Anwesenheit wählen.</p>`;
    const av = (p) => (p.pic ? `<img src="${esc(p.pic)}" alt="">` : `<span>${esc(p.name.trim().slice(0, 1).toUpperCase())}</span>`);
    if (z === "s")
      return `<div class="ppl-s">${people.map((p) => `<span class="pav ${p.home ? "home" : ""}" title="${esc(p.name)}: ${esc(p.where)}${p.distTxt ? ` · ${p.distTxt}` : ""}">${av(p)}<em>${p.home ? "⌂" : esc(p.distTxt || "–")}</em></span>`).join("")}</div>`;
    return `<div class="ppl">${people
      .map(
        (p) => `
        <div class="prow ${p.home ? "home" : ""}">
          <span class="pav">${av(p)}</span>
          <span class="grow"><b>${esc(p.name)}</b><small><ha-icon icon="${p.home ? "mdi:home" : p.where === "unterwegs" ? "mdi:map-marker-distance" : "mdi:map-marker-outline"}"></ha-icon>${esc(p.where)}</small></span>
          <em>${p.home ? "" : esc(p.distTxt || "–")}</em>
        </div>`
      )
      .join("")}</div>`;
  }

  _w_presence(w, z) {
    if (z !== "s") return this._presenceCard(true) + this._peopleHtml(z);
    // klein: nur der aktuelle Zustand und drei Knöpfe
    const s = this._status || {};
    const mode = s.vacation ? "urlaub" : s.away ? "abwesend" : "home";
    const dis = this._admin ? "" : "disabled";
    const b = (id, icon, label) => `<button class="pq ${mode === id ? "on" : ""}" data-action="presence" data-mode="${id}" title="${label}" ${dis}><ha-icon icon="${icon}"></ha-icon></button>`;
    const label = { home: "Zu Hause", abwesend: "Abwesend", urlaub: "Urlaub" }[mode];
    return `<div class="wstate">${label}${this._data.settings.guest ? " · Gäste" : ""}${this._data.settings.party ? " · Party" : ""}</div>
      <div class="pqs">${b("home", "mdi:home-heart", "Zu Hause")}${b("abwesend", "mdi:home-export-outline", "Abwesend")}${b("urlaub", "mdi:palm-tree", "Urlaub")}</div>
      ${this._peopleHtml("s")}`;
  }

  _w_weather(w, z) {
    const wx = this._weather();
    if (!wx) return `<p class="muted small">Keine Wetter-Entität gefunden. Unter Einstellungen › Wetter auswählen.</p>`;
    const head = `<div class="wwx"><ha-icon icon="${wx.icon}"></ha-icon><div><b>${fmt(wx.temp)} °C</b><span>${esc(wx.label)}</span></div></div>`;
    if (z === "s") return head;
    const extra = wx.extra ? `<p class="muted small" style="margin:8px 0 0">${wx.extra}</p>` : "";
    if (z === "m") return head + extra;
    // groß: dazu die nächsten Stunden
    return `<div class="wsplit"><div>${head}${extra}</div><div>${this._w_forecast({ mode: "hourly", entities: [] }, "s", true)}</div></div>`;
  }

  _w_rooms(w, z) {
    const st = this._status?.rooms || {};
    const rooms = this._rooms();
    if (!rooms.length) return `<p class="muted small">Noch keine Räume.</p>`;
    if (z === "s") {
      const heating = rooms.filter((r) => st[r.id]?.heating).length;
      return `<div class="wbig"><span>${heating}<small>von ${rooms.length} heizen</small></span></div>
        <div class="wdots">${rooms.map((r) => `<i title="${esc(r.name)}: ${fmt(st[r.id]?.room_temp)} °C" style="background:${(MODE[st[r.id]?.mode] || MODE.aus).c}"></i>`).join("")}</div>`;
    }
    return `<div class="gmini ${z === "m" ? "two" : ""}">${rooms
      .map((r) => {
        const rs = st[r.id] || {};
        const m = MODE[rs.mode] || MODE.aus;
        return `<button class="gm" style="--acc:${this._roomColor(r.id)}; --c:${m.c}" data-action="room-open" data-id="${r.id}">
          <span class="gh"><ha-icon icon="${esc(roomIcon(r))}"></ha-icon><span class="gn">${esc(r.name)}</span>${rs.heating ? `<ha-icon class="gf" icon="mdi:fire"></ha-icon>` : ""}</span>
          <span class="gt">${fmt(rs.room_temp)}<small>°C</small></span>
          ${z === "l" ? `<span class="gl"><ha-icon icon="${m.i}"></ha-icon>${esc(rs.mode_label || "Automatik aus")}${rs.target != null && rs.mode !== "aus" ? ` · ${fmt(rs.target)} °C` : ""}</span>` : ""}
        </button>`;
      })
      .join("")}</div>`;
  }

  _w_shortcuts(w, z) {
    const ids = w.entities || [];
    if (!ids.length) return `<p class="muted small">Noch keine Knöpfe.${this._admin && z !== "s" ? " Über „Anpassen“ › Zahnrad Szenen, Skripte, Schalter oder Lichter wählen." : ""}</p>`;
    return `<div class="wsc ${z}">${ids
      .map((id) => {
        const s = this._hass.states[id];
        const d = id.split(".")[0];
        const on = s && ["on", "open", "unlocked", "playing", "heat"].includes(s.state);
        const icon = s?.attributes?.icon || SC_ICONS[d] || "mdi:gesture-tap";
        const name = s?.attributes?.friendly_name || id;
        const stateTxt = ["script", "scene", "button", "input_button"].includes(d) ? "" : `<small>${s ? (on ? "an" : "aus") : "fehlt"}</small>`;
        return `<button class="sc ${on ? "on" : ""} ${s ? "" : "missing"}" data-action="w-sc" data-e="${esc(id)}" title="${esc(name)}">
          <ha-icon icon="${esc(icon)}"></ha-icon>${z === "s" ? "" : `<span>${esc(name)}</span>${z === "l" ? stateTxt : ""}`}</button>`;
      })
      .join("")}</div>`;
  }

  _openWindows() {
    const open = [];
    for (const r of this._rooms()) {
      for (const id of r.windows || []) {
        const s = this._hass.states[id];
        if (s && ["on", "open", "opening", "true"].includes(String(s.state).toLowerCase())) open.push({ room: r, s, id });
      }
    }
    return open;
  }

  _w_windows(w, z) {
    const open = this._openWindows();
    if (z === "s")
      return `<div class="wbig"><span style="color:${open.length ? tint("#22d3ee") : "inherit"}">${open.length}<small>offen</small></span></div>
        <div class="wline" style="--c:${open.length ? "#22d3ee" : "#34d399"}"><ha-icon icon="${open.length ? "mdi:window-open-variant" : "mdi:check"}"></ha-icon>${open.length ? esc(open.map((o) => o.room.name).join(", ")) : "alles zu"}</div>`;
    if (!open.length) return `<div class="wok"><ha-icon icon="mdi:window-closed-variant"></ha-icon>Alle Fenster und Türen zu</div>`;
    return `<div class="wlist">${open
      .map(({ room, s, id }) => {
        const mins = s.last_changed ? Math.max(0, Math.round((Date.now() - new Date(s.last_changed)) / 60000)) : null;
        const rs = this._status?.rooms?.[room.id] || {};
        return `<div class="wrow"><ha-icon icon="mdi:window-open-variant" style="color:#22d3ee"></ha-icon><span class="grow"><b>${esc(room.name)}</b><small>${esc(this._entityName(id))}${z === "l" ? ` · ${rs.mode === "fenster" ? "Heizung pausiert" : rs.window_pending ? "Pause beginnt gleich" : "heizt weiter"}` : ""}</small></span><em>${mins == null ? "" : mins < 60 ? `${mins} Min.` : `${fmt(mins / 60)} h`}</em></div>`;
      })
      .join("")}</div>`;
  }

  _w_schedule(w, z) {
    const st = this._status?.rooms || {};
    const rows = this._rooms()
      .filter((r) => r.enabled !== false)
      .map((r) => ({ r, i: this._schedInfo(r, st[r.id] || {}) }));
    if (!rows.length) return `<p class="muted small">Noch keine Räume.</p>`;
    if (z === "s") {
      // klein: der Raum, der als Nächstes warm wird
      const next = rows.filter((x) => !x.i.comfort && st[x.r.id]?.next_change != null).sort((a, b) => st[a.r.id].next_change - st[b.r.id].next_change)[0] || rows.find((x) => !x.i.comfort);
      const on = rows.filter((x) => x.i.comfort).length;
      return `<div class="wbig"><span>${on}<small>in Komfort</small></span></div>
        ${next ? `<div class="wline" style="--c:#f59e0b"><ha-icon icon="mdi:clock-outline"></ha-icon>${esc(next.r.name)}: ${esc(next.i.text.replace("Komfort ", ""))}</div>` : ""}`;
    }
    const day = (new Date().getDay() + 6) % 7;
    return `<div class="wlist">${rows
      .map(({ r, i }) => `<div class="wrow ${z === "l" ? "tall" : ""}"><ha-icon icon="${esc(roomIcon(r))}"></ha-icon>
        <span class="grow"><b>${esc(r.name)}</b><small>${esc(i.src)}</small>${z === "l" && i.blocks ? this._dayBar(i.blocks, r, day, true) : ""}</span><em class="${i.comfort ? "hot" : ""}">${esc(i.text)}</em></div>`)
      .join("")}</div>`;
  }

  _w_report(w, z) {
    const rep = this._report(7);
    if (!rep) return `<div class="chart-empty"><div class="spinner"></div></div>`;
    const days = Array.from({ length: 7 }, (_, i) => this._sumDay(rep, i).heat / 60);
    const sum = days.reduce((a, b) => a + b, 0);
    if (z === "s") return `<div class="wbig"><span>${fmt(sum)}<small>h</small></span></div><div class="wline"><ha-icon icon="mdi:calendar-week"></ha-icon>7 Tage · Ø ${fmt(sum / 7)} h</div>`;
    const max = Math.max(1, ...days);
    const dates = (rep[this._rooms()[0]?.id] || []).map((x) => x.date);
    const bars = `
      <div class="wbars">${days
        .map((h, i) => `<div class="wbar" title="${fmt(h)} h">${z === "l" ? `<em>${fmt(h)}</em>` : ""}<i style="height:${Math.max(3, (h / max) * 100)}%"></i><small>${i === 6 ? "heute" : dates[i] ? DAYS[(new Date(dates[i]).getDay() + 6) % 7] : ""}</small></div>`)
        .join("")}</div>`;
    const foot = `<p class="muted small" style="margin:8px 0 0">${fmt(sum)} h in 7 Tagen · Ø ${fmt(sum / 7)} h am Tag</p>`;
    if (z === "m") return bars + foot;
    // groß: dazu die Räume mit den meisten Stunden
    const per = this._rooms()
      .map((r) => ({ r, h: (rep[r.id] || []).reduce((a, x) => a + (x.heat_min || 0), 0) / 60 }))
      .sort((a, b) => b.h - a.h);
    const top = Math.max(1, ...per.map((x) => x.h));
    return `<div class="wsplit"><div>${bars}${foot}</div><div class="wlist">${per
      .map(({ r, h }) => `<div class="wrow"><span class="rdot" style="background:${this._roomColor(r.id)}"></span><span class="grow"><b>${esc(r.name)}</b><span class="hbar"><i style="width:${(h / top) * 100}%; background:${this._roomColor(r.id)}"></i></span></span><em>${fmt(h)} h</em></div>`)
      .join("")}</div></div>`;
  }

  /** Kälteeinbruch und Sturm aus der Vorhersage (Grenzen unter Hauswerk › Einstellungen › Wetter). */
  _wxAlerts() {
    const p = this._data?.settings || {};
    const S = this._hass?.states || {};
    const id = p.weather_entity || Object.keys(S).find((e) => e.startsWith("weather."));
    const st = id && S[id];
    if (!st || !this._hass.connection) return [];
    const feat = Number(st.attributes.supported_features || 0);
    const out = [];
    const day = (iso) => new Date(iso).toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "numeric" });
    const cold = Number(p.cold_snap_temp ?? 0);
    if (feat & 1) {
      const fc = this._forecast(id, "daily");
      const low = (fc?.list || []).slice(0, 3).map((x) => ({ t: x.templow ?? x.temperature, at: x.datetime })).filter((x) => x.t != null)
        .reduce((a, b) => (a && a.t <= b.t ? a : b), null);
      if (low && low.t < cold) out.push({ icon: "mdi:snowflake-alert", text: `Kälteeinbruch: bis ${fmt(low.t)} °C`, sub: `${day(low.at)} · Grenze ${fmt(cold)} °C` });
    }
    const kmh = (v, u) => (v == null ? null : u === "m/s" ? v * 3.6 : u === "mph" ? v * 1.609 : u === "kn" ? v * 1.852 : v);
    const u = st.attributes.wind_speed_unit || "km/h";
    const limit = Number(p.storm_kmh ?? 70);
    let gust = kmh(st.attributes.wind_gust_speed ?? null, u);
    let at = null;
    if (feat & 2) {
      const fc = this._forecast(id, "hourly");
      for (const x of (fc?.list || []).filter((x) => new Date(x.datetime) - Date.now() < 24 * 3600e3)) {
        const v = kmh(x.wind_gust_speed ?? x.wind_speed ?? null, u);
        if (v != null && (gust == null || v > gust)) {
          gust = v;
          at = x.datetime;
        }
      }
    }
    if (gust != null && gust >= limit)
      out.push({ icon: "mdi:weather-windy", text: `Sturm: Böen bis ${fmt(gust, 0)} km/h`, sub: `${at ? `${day(at)}, ${new Date(at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}` : "jetzt"} · Grenze ${fmt(limit, 0)} km/h` });
    return out;
  }

  /** Prognose einer weather-Entität abonnieren (wie die Wetterkarte von Home Assistant). */
  _forecast(entityId, type) {
    this._fc = this._fc || {};
    this._fcSubs = this._fcSubs || {};
    const key = `${entityId}|${type}`;
    if (!this._fcSubs[key]) {
      this._fcSubs[key] = this._hass.connection.subscribeMessage(
        (msg) => {
          this._fc[key] = { list: msg.forecast || [] };
          if (this._tab === "start" && !this._busy) this._renderMain();
        },
        { type: "weather/subscribe_forecast", entity_id: entityId, forecast_type: type }
      );
      this._fcSubs[key].catch((err) => {
        this._fc[key] = { error: err?.message || "Prognose nicht verfügbar" };
        if (this._tab === "start") this._renderMain();
      });
    }
    return this._fc[key];
  }

  _w_forecast(w, z, embedded = false) {
    const id = (w.entities || [])[0] || this._data.settings.weather_entity || Object.keys(this._hass.states).find((e) => e.startsWith("weather."));
    const st = id && this._hass.states[id];
    if (!st) return `<p class="muted small">Keine Wetter-Entität gefunden.${this._admin ? " Über „Anpassen“ › Zahnrad eine wählen." : ""}</p>`;
    // Was kann die Entität? 1 = täglich, 2 = stündlich, 4 = zweimal täglich
    const feat = Number(st.attributes.supported_features || 0);
    let type = w.mode || "hourly";
    if (type === "hourly" && !(feat & 2) && feat & 1) type = "daily";
    if (type === "daily" && !(feat & 1) && feat & 2) type = "hourly";
    const fc = this._forecast(id, type);
    if (!fc) return `<div class="chart-empty"><div class="spinner"></div></div>`;
    if (fc.error) return `<p class="muted small">${esc(fc.error)}</p>`;
    const hourly = type === "hourly";
    // Je Größe mehr Spalten: klein 4, mittel 6 (Stunden) bzw. 4 (Tage), groß 12 bzw. 7
    const count = embedded ? 6 : z === "s" ? (hourly ? 4 : 3) : z === "m" ? (hourly ? 6 : 4) : hourly ? 12 : 7;
    const items = fc.list.slice(0, count);
    if (!items.length) return `<p class="muted small">Keine Prognose verfügbar.</p>`;
    const temps = items.flatMap((x) => [x.temperature, x.templow]).filter((t) => t != null);
    const lo = Math.min(...temps), hi = Math.max(...temps);
    const unit = st.attributes.temperature_unit || "°C";
    // Hinweis für die Heizung: tiefster Wert der nächsten 24 h
    const next24 = hourly ? fc.list.filter((x) => new Date(x.datetime) - Date.now() < 24 * 3600e3) : fc.list.slice(0, 2);
    const lows = next24.map((x) => ({ t: x.templow ?? x.temperature, at: x.datetime })).filter((x) => x.t != null);
    const min = lows.length ? lows.reduce((a, b) => (b.t < a.t ? b : a)) : null;
    const set = this._data.settings;
    let hint = "";
    if (z === "s" || embedded) hint = "";
    else if (min && min.t <= 0) hint = `<span class="fchint" style="--c:#38bdf8"><ha-icon icon="mdi:snowflake-alert"></ha-icon>Frost: bis ${fmt(min.t)} ${unit}${hourly ? ` um ${new Date(min.at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}` : ""}</span>`;
    else if (set.summer_mode === "auto" && min && min.t >= (set.summer_temp ?? 16)) hint = `<span class="fchint" style="--c:#facc15"><ha-icon icon="mdi:weather-sunny"></ha-icon>Mild: Sommerpause ab ${fmt(set.summer_temp ?? 16)} °C möglich</span>`;
    else if (min) hint = `<span class="fchint"><ha-icon icon="mdi:thermometer-low"></ha-icon>Tiefstwert ${hourly ? "24 h" : "bis morgen"}: ${fmt(min.t)} ${unit}</span>`;
    const label = (x, i) => {
      const d = new Date(x.datetime);
      if (hourly) return i === 0 ? "jetzt" : String(d.getHours()).padStart(2, "0") + (z === "s" || embedded ? "" : " Uhr");
      if (d.toDateString() === new Date().toDateString()) return "heute";
      return d.toLocaleDateString("de-DE", { weekday: "short" });
    };
    const pos = (t) => (hi > lo ? ((t - lo) / (hi - lo)) * 100 : 50);
    const detail = z === "l" && !embedded;
    return `
      ${hint ? `<div class="fchints">${hint}</div>` : ""}
      <div class="fc ${hourly ? "hourly" : "daily"} ${z === "s" || embedded ? "tight" : ""}">${items
        .map((x, i) => {
          const [icon, text] = WEATHER[x.condition] || ["mdi:weather-partly-cloudy", x.condition || ""];
          const rain = x.precipitation_probability ?? null;
          return `
          <div class="fci" title="${esc(text)}">
            <small>${label(x, i)}</small>
            <ha-icon icon="${icon}"></ha-icon>
            <b style="color:${tint(tempColor(x.temperature))}">${fmt(x.temperature, 0)}°</b>
            ${!hourly && x.templow != null ? `
              ${detail ? `<span class="fcr"><i style="bottom:${pos(x.templow)}%; height:${Math.max(6, pos(x.temperature) - pos(x.templow))}%"></i></span>` : ""}
              <em>${fmt(x.templow, 0)}°</em>` : ""}
            ${z !== "s" && !embedded ? `<small class="fcp ${rain >= 50 ? "wet" : ""}">${rain != null ? `<ha-icon icon="mdi:water-outline"></ha-icon>${fmt(rain, 0)} %` : x.precipitation ? `${fmt(x.precipitation)} mm` : "&nbsp;"}</small>` : ""}
          </div>`;
        })
        .join("")}</div>`;
  }

  _w_values(w, z) {
    const ids = w.entities || [];
    if (!ids.length) return `<p class="muted small">Noch keine Werte.${this._admin && z !== "s" ? " Über „Anpassen“ › Zahnrad Sensoren wählen." : ""}</p>`;
    const val = (id) => {
      const s = this._hass.states[id];
      const unit = s?.attributes?.unit_of_measurement || "";
      const num = s && !isNaN(parseFloat(s.state)) && isFinite(s.state);
      return { s, txt: s ? `${num ? Number(s.state).toLocaleString("de-DE", { maximumFractionDigits: 2 }) : esc(s.state)}${unit ? ` ${esc(unit)}` : ""}` : "fehlt" };
    };
    if (z === "s") {
      // klein: der erste Wert groß, weitere als Zeile
      const a = val(ids[0]);
      return `<div class="wval"><b>${a.txt}</b><small>${esc(a.s?.attributes?.friendly_name || ids[0])}</small></div>
        ${ids[1] ? `<div class="wline"><ha-icon icon="mdi:plus"></ha-icon>${ids.length - 1} weitere</div>` : ""}`;
    }
    return `<div class="wlist ${z === "l" ? "cols" : ""}">${ids
      .map((id) => {
        const { s, txt } = val(id);
        return `<div class="wrow"><ha-icon icon="${esc(s?.attributes?.icon || "mdi:gauge")}"></ha-icon><span class="grow"><b>${esc(s?.attributes?.friendly_name || id)}</b>${z === "l" && s?.last_changed ? `<small>seit ${new Date(s.last_changed).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</small>` : ""}</span><em>${txt}</em></div>`;
      })
      .join("")}</div>`;
  }
  // ------------------------------------------------------------ Modul 1: Räume
  _viewOverview() {
    const rooms = this._rooms();
    const st = this._status?.rooms || {};
    const s = this._status || {};
    const set = this._data.settings;
    const f = this._facts();
    const n = rooms.length;
    const avgOf = (list) => (list.length ? list.reduce((a, b) => a + b, 0) / list.length : null);
    const avg = avgOf(rooms.map((r) => st[r.id]?.room_temp).filter((t) => t != null));
    const avgTarget = avgOf(rooms.filter((r) => !["fenster", "aus", "sommer"].includes(st[r.id]?.mode)).map((r) => st[r.id]?.target).filter((t) => t != null));
    const hum = avgOf(rooms.map((r) => st[r.id]?.humidity).filter((h) => h != null));
    const below = rooms.filter((r) => {
      const x = st[r.id] || {};
      return x.room_temp != null && x.target != null && !["aus", "fenster", "sommer", "warm", "entkalken"].includes(x.mode) && x.target - x.room_temp >= 0.5;
    });
    const rep = this._report(14);
    const today = rep ? this._sumDay(rep, 13) : null;
    const date = new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
    const w = this._weather();
    // Kurzurteil: das Wichtigste zuerst
    const verdict = !n
      ? { i: "mdi:home-plus-outline", c: "#94a3b8", t: "Noch keine Räume angelegt" }
      : s.summer
        ? { i: "mdi:weather-sunny", c: "#facc15", t: "Sommerpause – die Thermostate ruhen" }
        : f.open
          ? { i: "mdi:window-open-variant", c: "#22d3ee", t: `${f.open} ${f.open > 1 ? "Räume lüften" : "Raum lüftet"} – dort pausiert die Heizung` }
          : s.vacation
            ? { i: "mdi:palm-tree", c: "#34d399", t: `Urlaub – alle Räume auf ${fmt(set.vacation_temp)} °C` }
            : s.away
              ? { i: "mdi:home-export-outline", c: "#94a3b8", t: "Niemand zu Hause – abgesenkt" }
              : s.approaching
                ? { i: "mdi:home-import-outline", c: "#34d399", t: "Jemand kommt heim – es wird schon geheizt" }
                : below.length
                  ? { i: "mdi:thermometer-chevron-up", c: "#fb923c", t: `${below.length} ${below.length > 1 ? "Räume" : "Raum"} unter Soll – ${f.heating ? "wird aufgeheizt" : "Heizung prüfen"}` }
                  : { i: "mdi:check-circle-outline", c: "#34d399", t: "Alle Räume im Soll" };
    const presence = s.vacation ? ["mdi:palm-tree", "Urlaub"] : s.away ? ["mdi:home-export-outline", "Abwesend"] : set.party ? ["mdi:party-popper", "Party"] : set.guest ? ["mdi:account-group-outline", "Gäste"] : ["mdi:home-heart", "Zu Hause"];
    const stat = (icon, label, value, sub = "", c = "") =>
      `<div class="hstat" ${c ? `style="--c:${c}"` : ""}><ha-icon icon="${icon}"></ha-icon><span><small>${label}</small><b>${value}</b>${sub ? `<em>${sub}</em>` : ""}</span></div>`;
    const compact = this._roomView() === "compact";

    return `
      <section class="hero">
        <div class="hero-row">
          <div class="hero-text">
            <div class="hero-label"><ha-icon icon="mdi:home-thermometer-outline"></ha-icon>Im Haus · ${date}</div>
            <div class="hero-line"><div class="hero-big">${fmt(avg)}<span>°C</span></div>
            <div class="verdict" style="--c:${verdict.c}"><ha-icon icon="${verdict.i}"></ha-icon>${verdict.t}</div></div>
          </div>
          ${w ? `
          <div class="wx" title="${esc(w.name)}">
            <ha-icon icon="${w.icon}"></ha-icon>
            <div><b>${fmt(w.temp)} °C</b><small>${esc(w.label)}</small>${w.extra ? `<small>${w.extra}</small>` : ""}</div>
          </div>` : ""}
        </div>
        <div class="hstats">
          ${stat(f.heating ? "mdi:fire" : "mdi:fire-off", "Heizen", `${f.heating} von ${n}`, "Räumen", f.heating ? "#fb923c" : "")}
          ${stat(f.open ? "mdi:window-open-variant" : "mdi:window-closed-variant", "Fenster", f.open ? `${f.open} offen` : "alle zu", "", f.open ? "#22d3ee" : "")}
          ${stat(w ? w.icon : "mdi:thermometer", "Außen", s.outside_temp != null || w ? `${fmt(s.outside_temp ?? w?.temp)} °C` : "–", w ? esc(w.label) : "")}
          ${hum != null ? stat(humidityInfo(hum).i, "Luftfeuchte Ø", `${fmt(hum, 0)} %`, humidityInfo(hum).t) : ""}
          ${stat("mdi:timer-outline", "Heute geheizt", today ? `${fmt(today.heat / 60)} h` : "–", presence[1])}
        </div>
      </section>

      <div class="shead outer">
        <ha-icon icon="mdi:floor-plan"></ha-icon><h3>Räume</h3><span class="count">${n}</span><span class="grow"></span>
        ${n ? `<div class="vtog" role="group" aria-label="Ansicht">
          <button class="${compact ? "" : "on"}" data-action="room-view" data-v="detail" title="Detailliert"><ha-icon icon="mdi:view-agenda-outline"></ha-icon><span>Detailliert</span></button>
          <button class="${compact ? "on" : ""}" data-action="room-view" data-v="compact" title="Kompakt"><ha-icon icon="mdi:view-grid-outline"></ha-icon><span>Kompakt</span></button>
        </div>` : ""}
        ${this._admin && n ? `<button class="link" data-action="room-new"><ha-icon icon="mdi:plus"></ha-icon>Raum</button>` : ""}
      </div>
      ${
        n
          ? `<div class="rooms ${compact ? "compact" : ""}">${rooms.map((r) => (compact ? this._roomMini(r) : this._roomCard(r))).join("")}</div>`
          : `<section class="card empty">
              <ha-icon icon="mdi:home-plus-outline"></ha-icon>
              <h2>Noch keine Räume</h2>
              <p>Lege einen Raum an und ordne Thermostate, Fensterkontakte und einen Raumsensor zu.</p>
              ${this._admin ? `<button class="primary" data-action="room-new"><ha-icon icon="mdi:plus"></ha-icon>Raum anlegen</button>` : ""}
            </section>`
      }`;
  }

  /** Raumkacheln: detailliert oder kompakt (je Gerät gemerkt). */
  _roomView() {
    if (this._view) return this._view;
    try {
      this._view = localStorage.getItem("hauswerk.raumansicht") || localStorage.getItem("heizwerk.raumansicht") || "detail";
    } catch (e) {
      this._view = "detail";
    }
    return this._view;
  }

  /** Wetter aus der gewählten weather-Entität, sonst der ersten gefundenen. */
  _weather() {
    const id = this._data.settings.weather_entity || Object.keys(this._hass.states).find((e) => e.startsWith("weather."));
    const w = id && this._hass.states[id];
    if (!w || ["unavailable", "unknown"].includes(w.state)) return null;
    const a = w.attributes || {};
    const [icon, label] = WEATHER[w.state] || ["mdi:weather-partly-cloudy", w.state];
    const extra = [a.wind_speed != null ? `Wind ${fmt(a.wind_speed, 0)} ${a.wind_speed_unit || "km/h"}` : "", a.humidity != null ? `${fmt(a.humidity, 0)} % Feuchte` : ""].filter(Boolean).join(" · ");
    return { icon, label, temp: this._status?.outside_temp ?? a.temperature, extra, name: a.friendly_name || id };
  }
  _gauge(avg, target) {
    // Eigener Ring: Bogen 135°…405°, Skala 14–26 °C
    const pct = (t) => Math.min(1, Math.max(0, ((t ?? 14) - 14) / 12));
    const R = 62, C = 2 * Math.PI * R, arc = 0.75 * C;
    const val = pct(avg) * arc;
    const tAng = 135 + pct(target) * 270;
    const tx = 80 + R * Math.cos((tAng * Math.PI) / 180);
    const ty = 80 + R * Math.sin((tAng * Math.PI) / 180);
    return `
      <div class="gauge" aria-hidden="true">
        <svg viewBox="0 0 160 160">
          <defs><linearGradient id="g" x1="0" x2="1" y1="1" y2="0"><stop offset="0" stop-color="#5eead4"/><stop offset=".6" stop-color="#fde047"/><stop offset="1" stop-color="#fb923c"/></linearGradient></defs>
          <circle cx="80" cy="80" r="${R}" fill="none" stroke="rgba(255,255,255,.14)" stroke-width="12" stroke-linecap="round"
            stroke-dasharray="${arc} ${C}" transform="rotate(135 80 80)"/>
          <circle cx="80" cy="80" r="${R}" fill="none" stroke="url(#g)" stroke-width="12" stroke-linecap="round"
            stroke-dasharray="${val} ${C}" transform="rotate(135 80 80)"/>
          ${target != null ? `<circle cx="${tx}" cy="${ty}" r="7" fill="#fff" stroke="rgba(0,0,0,.25)" stroke-width="2"/>` : ""}
          <text x="80" y="76" text-anchor="middle" class="g-small">Soll Ø</text>
          <text x="80" y="100" text-anchor="middle" class="g-big">${fmt(target)}°</text>
        </svg>
      </div>`;
  }

  _presenceCard(inline = false) {
    const s = this._status || {};
    const settings = this._data.settings;
    const mode = s.vacation ? "urlaub" : s.away ? "abwesend" : "home";
    const persons = (settings.persons || []).length;
    const text = {
      home: persons
        ? `Heizpläne laufen normal · abwesend nach ${settings.away_delay} Min. ohne Personen`
        : `Heizpläne laufen normal · <button class="link inline" data-action="settings-go" data-sub="presence">Personen wählen</button>, damit Abwesenheit erkannt wird`,
      abwesend: `${s.long_away ? `Lange niemand da – Frostschutz ${fmt(settings.frost_temp)} °C` : settings.away_action === "off" ? "Thermostate aus" : settings.away_mode === "offset" ? `Alle Räume ${fmt(settings.away_offset)} °C kühler` : `Alle Räume höchstens ${fmt(settings.away_temp)} °C`} · ${s.presence_force ? "von Hand gesetzt" : "endet, wenn jemand heimkommt"}`,
      urlaub: (() => {
        // Ende des Urlaubs: aus dem laufenden Kalendertermin oder dem eingetragenen Zeitraum
        const src = settings.vacation_source || "period";
        const ev = src === "calendar" ? (s.vacation_events || []).find((e) => new Date(e.start) <= new Date()) : null;
        const end = settings.vacation ? null : ev ? new Date(new Date(ev.end).getTime() - 1) : src === "period" && settings.vacation_to ? new Date(settings.vacation_to) : null;
        return `Alle Räume auf ${fmt(settings.vacation_temp)} °C${end ? ` bis ${end.toLocaleDateString("de-DE")}` : ""}${ev && !settings.vacation ? ` · laut Kalender: ${esc(ev.summary || "Termin")}` : ""}`;
      })(),
    }[mode];
    const dis = this._admin ? "" : "disabled";
    const seg = (id, icon, label) =>
      `<button class="pseg ${mode === id ? "on" : ""}" data-action="presence" data-mode="${id}" ${dis}><ha-icon icon="${icon}"></ha-icon><span>${label}</span></button>`;
    const toggle = (key, icon, label, title) =>
      `<label class="ptoggle ${settings[key] ? "on" : ""}" title="${title}"><input type="checkbox" data-action="hmode" data-key="${key}" ${settings[key] ? "checked" : ""} ${dis}><ha-icon icon="${icon}"></ha-icon><span>${label}</span></label>`;
    return `
      <section class="${inline ? "" : "card "}presence">
        <div class="pbar">
          <div class="psegs">
            ${seg("home", "mdi:home-heart", "Zu Hause")}
            ${seg("abwesend", "mdi:home-export-outline", "Abwesend")}
            ${seg("urlaub", "mdi:palm-tree", "Urlaub")}
          </div>
          <div class="ptoggles">
            ${toggle("guest", "mdi:account-group-outline", "Gäste", "Gäste: nie auf Abwesend absenken")}
            ${toggle("party", "mdi:party-popper", "Party", "Party: alle Räume auf Komfort")}
            ${toggle("eco_force", "mdi:leaf", "Eco", "Eco erzwingen: alle Räume auf Eco")}
          </div>
        </div>
        <p class="ptext"><ha-icon icon="mdi:information-outline"></ha-icon><span>${text}</span></p>
      </section>`;
  }

  _kpi(color, icon, label, value, unit, sub) {
    return `
      <div class="kpi" style="--k:${color}">
        <div class="kpi-l"><ha-icon icon="${icon}"></ha-icon>${label}</div>
        <div class="kpi-v">${value}<span>${unit}</span></div>
        <div class="kpi-s">${sub || "&nbsp;"}</div>
      </div>`;
  }

  _sumDay(rep, idx) {
    const out = { heat: 0, pause: 0, comfort: 0, open: 0 };
    for (const rows of Object.values(rep)) {
      const r = rows[idx];
      if (!r) continue;
      out.heat += r.heat_min;
      out.pause += r.pause_min;
      out.comfort += r.comfort_min;
      out.open += r.openings;
    }
    return out;
  }

  _sumRange(rep, from, to) {
    const out = { heat: 0, pause: 0, comfort: 0, open: 0 };
    for (let i = from; i < to; i++) {
      const d = this._sumDay(rep, i);
      for (const k in out) out[k] += d[k];
    }
    return out;
  }

  _stackChart(rep, days, key) {
    const rooms = this._rooms();
    const W = 1000, H = 240, padL = 44, padB = 28, padT = 10;
    const totals = Array.from({ length: days }, (_, i) => rooms.reduce((a, r) => a + ((rep[r.id] || [])[i]?.[key] || 0), 0));
    const hoursMode = key === "heat_min";
    const maxRaw = Math.max(...totals, hoursMode ? 60 : 10);
    const unit = hoursMode ? 60 : 1;
    const stepCount = 4;
    let step = Math.ceil(maxRaw / unit / stepCount);
    if (hoursMode && step > 2) step = Math.ceil(step / 2) * 2;
    if (!hoursMode) step = Math.max(5, Math.ceil(step / 5) * 5);
    const max = step * stepCount * unit;
    const y = (v) => padT + (H - padT - padB) * (1 - v / max);
    const bw = (W - padL) / days;
    const grid = Array.from({ length: stepCount + 1 }, (_, i) => {
      const v = i * step * unit;
      return `<line x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}" class="gl"/><text x="${padL - 10}" y="${y(v) + 4}" text-anchor="end" class="ax">${int(v / unit)}</text>`;
    }).join("");
    const anyData = totals.some((t) => t > 0);
    let bars = "";
    let labels = "";
    const dates = (rep[rooms[0]?.id] || []).map((r) => r.date);
    for (let i = 0; i < days; i++) {
      let acc = 0;
      const x = padL + i * bw + bw * 0.2;
      rooms.forEach((r) => {
        const v = (rep[r.id] || [])[i]?.[key] || 0;
        if (!v) return;
        const y1 = y(acc + v), y0 = y(acc);
        bars += `<rect x="${x}" y="${y1}" width="${bw * 0.6}" height="${Math.max(0, y0 - y1 - 2)}" rx="4" fill="${this._roomColor(r.id)}"><title>${esc(r.name)}: ${hoursMode ? fmt(v / 60) + " h" : int(v) + " Min."}</title></rect>`;
        acc += v;
      });
      const isToday = i === days - 1;
      if (isToday || i % Math.ceil(days / 7) === (days - 1) % Math.ceil(days / 7)) {
        const label = isToday ? "heute" : dates[i] ? new Date(dates[i]).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) : "";
        labels += `<text x="${padL + i * bw + bw / 2}" y="${H - 6}" text-anchor="middle" class="ax ${isToday ? "today" : ""}">${label}</text>`;
      }
    }
    return `
      <div class="chart-wrap">
        <svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${grid}${bars}${labels}</svg>
        ${anyData ? "" : `<div class="chart-note">Noch keine Werte. Heizwerk zählt ab jetzt jede Minute mit.</div>`}
      </div>
      <div class="legend">
        <span class="muted">${hoursMode ? "Stunden" : "Minuten"}</span>
        ${rooms.map((r) => `<span><i style="background:${this._roomColor(r.id)}"></i>${esc(r.name)}</span>`).join("")}
      </div>`;
  }

  /** Raum ohne Thermostat: ruhige graue Kachel mit genau einem Knopf. */
  _roomSetup(room, mini = false) {
    return `
      <article class="${mini ? "rmini" : "room"} setup" id="room-${room.id}" style="--rc:${this._roomColor(room.id)}">
        <div class="${mini ? "rm-head" : "room-head"}">
          <${mini ? "span" : "div"} class="${mini ? "rm-ic" : "room-ic"}"><ha-icon icon="${esc(roomIcon(room))}"></ha-icon></${mini ? "span" : "div"}>
          ${mini ? `<b class="rm-name">${esc(room.name)}</b>` : `<div class="room-t"><h4>${esc(room.name)}</h4><small>noch nicht eingerichtet</small></div>`}
        </div>
        <div class="setup-b">
          ${mini ? "" : `<p><ha-icon icon="mdi:thermostat-box"></ha-icon>Ordne ein Thermostat zu – dann regelt Heizwerk diesen Raum.</p>`}
          ${this._admin ? `<button class="secondary" data-action="room-edit" data-id="${room.id}" data-rtab="devices"><ha-icon icon="mdi:link-variant-plus"></ha-icon>Geräte zuordnen</button>` : `<p class="muted small">Noch nicht eingerichtet</p>`}
        </div>
      </article>`;
  }

  _roomCard(room) {
    if (!(room.climates || []).length) return this._roomSetup(room);
    const s = this._status?.rooms?.[room.id] || {};
    const mode = s.mode || "aus";
    const until = s.override_until ? new Date(s.override_until).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : null;
    const canStep = !["aus", "fenster", "sommer", "entkalken", "boost"].includes(mode);
    const canBoost = !["aus", "fenster", "entkalken"].includes(mode) && (room.climates || []).length;
    // Nur was auffällt, als kleines Symbol neben dem Namen (Text im Tooltip)
    const icons = [];
    const si = (icon, c, title, text = "") => `<span class="si" style="--c:${c}" title="${esc(title)}"><ha-icon icon="${icon}"></ha-icon>${text}</span>`;
    if (s.windows_open) icons.push(si("mdi:window-open-variant", "#22d3ee", s.window_pending ? "Fenster offen – Pause beginnt gleich" : "Fenster offen"));
    if (s.occupied === true) icons.push(si("mdi:account-check-outline", "#fbbf24", "Präsenzmelder: jemand im Raum"));
    else if (s.occupied === false) icons.push(si("mdi:account-off-outline", "var(--muted)", "Präsenzmelder: niemand im Raum"));
    const dv = this._devIndicators(room);
    if (dv.valve != null)
      icons.push(si("mdi:valve", dv.valve > 0 ? "#fb923c" : "var(--muted)", `Ventil${dv.valves > 1 ? "e (höchster Wert)" : ""}: ${fmt(dv.valve, 0)} % offen`, `${fmt(dv.valve, 0)} %`));
    // Fußbodenheizung: nur das Symbol, solange sie heizt (Details als Quickinfo)
    if (dv.floor?.on) icons.push(si("mdi:heating-coil", "#f97316", `${dv.floor.label} heizt – ${dv.floor.names}`));
    if (s.assist?.on) icons.push(si("mdi:radiator", "#f97316", "Heizkörper hilft nach (Mischbetrieb)"));
    const hum = humidityInfo(s.humidity);
    if (hum) icons.push(si(hum.i, hum.t ? hum.c : "var(--muted)", `Luftfeuchte ${fmt(s.humidity, 0)} %${hum.t ? " – " + hum.t : ""}`, `${fmt(s.humidity, 0)} %`));
    const tr = !["aus", "fenster", "sommer", "entkalken", "warm", "boost"].includes(mode) ? trend(s.room_temp, s.target) : null;
    // Genau ein Hinweis, der wichtigste zuerst
    const note = (() => {
      if (!(room.climates || []).length) return `<div class="room-note warn"><ha-icon icon="mdi:alert-outline"></ha-icon>Kein Thermostat zugeordnet${this._admin ? `<span class="grow"></span><button class="link" data-action="room-edit" data-id="${room.id}" data-rtab="devices">Zuordnen</button>` : ""}</div>`;
      if (mode === "manuell" && until) return `<div class="room-note"><ha-icon icon="mdi:hand-back-right-outline"></ha-icon>Manuell bis ${until}<span class="grow"></span><button class="link" data-action="ovr-reset" data-id="${room.id}">Zurück zum Plan</button></div>`;
      if (mode === "boost" && until) return `<div class="room-note boost"><ha-icon icon="mdi:rocket-launch-outline"></ha-icon>Boost bis ${until}<span class="grow"></span><button class="link" data-action="ovr-reset" data-id="${room.id}">Beenden</button></div>`;
      if (s.window_pending) return `<div class="room-note"><ha-icon icon="mdi:window-open-variant"></ha-icon>Fenster offen – Heizpause beginnt gleich</div>`;
      if (mode === "vorheizen") {
        const mins = s.comfort_in ?? s.next_change;
        const at = mins != null ? new Date(Date.now() + mins * 60000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : null;
        return `<div class="room-note pre"><ha-icon icon="${s.preheat_mode === "smart" ? "mdi:brain" : "mdi:clock-fast"}"></ha-icon><span>Heizt vor${at ? ` – ${fmt(s.target)} °C ab ${at}` : ""}${s.preheat_mode === "smart" && s.heat_rate ? `<small> · ${fmt(s.heat_rate)} °C/h</small>` : ""}</span></div>`;
      }
      if (mode === "warm") return `<div class="room-note warmn"><ha-icon icon="mdi:thermometer-check"></ha-icon>Warm genug – aus, bis unter ${fmt(s.target)} °C</div>`;
      return "";
    })();
    const auto = room.enabled !== false;
    const menu = this._admin
      ? `<details class="rmenu">
          <summary class="icon" title="Mehr"><ha-icon icon="mdi:dots-horizontal"></ha-icon></summary>
          <div class="rm-pop">
            <button data-action="plan-open" data-id="${room.id}"><ha-icon icon="mdi:calendar-clock"></ha-icon>Heizplan</button>
            <button data-action="room-edit" data-id="${room.id}"><ha-icon icon="mdi:cog-outline"></ha-icon>Bearbeiten</button>
            <button data-action="room-auto" data-id="${room.id}"><ha-icon icon="${auto ? "mdi:robot-off-outline" : "mdi:robot-outline"}"></ha-icon>Automatik ${auto ? "ausschalten" : "einschalten"}</button>
          </div>
        </details>`
      : "";
    return `
      <article class="room tap ${mode === "aus" ? "off" : ""}" id="room-${room.id}" style="--rc:${this._roomColor(room.id)}" data-action="room-quick" data-id="${room.id}" title="Tippen für manuelle Änderungen">
        <div class="room-head">
          <div class="room-ic">
            <ha-icon icon="${esc(roomIcon(room))}"></ha-icon>
            ${s.heating ? `<span class="flame" title="Heizt"><ha-icon icon="mdi:fire"></ha-icon></span>` : ""}
          </div>
          <div class="room-t"><h4><button class="rlink" data-action="room-page" data-id="${room.id}" title="Raum öffnen">${esc(room.name)}</button></h4>${icons.length ? `<small><span class="sis">${icons.join("")}</span></small>` : ""}</div>
          ${this._chip(mode, s.mode_label || "Automatik aus")}
          ${canBoost ? `<button class="icon ${mode === "boost" ? "hot" : ""}" title="${mode === "boost" ? "Boost beenden" : `Boost: ${this._data.settings.boost_minutes || 30} Min. volle Leistung`}" data-action="${mode === "boost" ? "ovr-reset" : "boost"}" data-id="${room.id}"><ha-icon icon="mdi:rocket-launch-outline"></ha-icon></button>` : ""}
          ${menu}
        </div>
        <div class="room-body">
          <div class="room-now">
            <div class="room-temp">${fmt(s.room_temp)}<span>°C</span></div>
            ${tr ? `<div class="trend" style="--c:${tr.c}"><ha-icon icon="${tr.i}"></ha-icon>${tr.t}</div>` : ""}
          </div>
          <div class="room-set">
            <small><ha-icon icon="mdi:target"></ha-icon>Soll</small>
            ${canStep ? this._stepper("ovr", room.id, s.target, { small: true }) : `<b class="tgt" style="color:${tint(tempColor(s.target))}">${fmt(s.target)} °C</b>`}
          </div>
        </div>
        ${this._schedStrip(room, s)}
        ${note}
      </article>`;
  }

  // ------------------------------------------------------------ Raum-Detailseite
  _viewRoom() {
    const room = this._data.rooms[this._roomId];
    const back = `<button class="link back" data-action="tab" data-tab="overview"><ha-icon icon="mdi:chevron-left"></ha-icon>Räume</button>`;
    if (!room) return `${back}<section class="card empty"><ha-icon icon="mdi:door-closed-cancel"></ha-icon><h2>Raum nicht gefunden</h2></section>`;
    const s = this._status?.rooms?.[room.id] || {};
    const S = this._hass.states;
    const set = this._data.settings;
    const d = this._data.defaults[room.type] || {};
    const val = (id, attr) => {
      const st = S[id];
      if (!st) return "fehlt";
      if (attr) return st.attributes[attr] != null ? `${fmt(st.attributes[attr])} °C` : "–";
      const u = st.attributes.unit_of_measurement || "";
      return `${isNaN(parseFloat(st.state)) ? st.state : fmt(parseFloat(st.state))}${u ? ` ${u}` : ""}`;
    };
    const dev = (icon, label, id, value, ok = true) => `
      <div class="wrow"><ha-icon icon="${icon}"></ha-icon><span class="grow"><b>${esc(this._devType(id))}</b><small>${esc(this._entityName(id))}${label ? ` · ${label}` : ""}</small></span><em class="${ok ? "" : "bad"}">${value}</em></div>`;
    const devices = [
      ...(room.climates || []).map((id) => {
        const st = S[id];
        const bad = !st || ["unavailable", "unknown"].includes(st.state);
        const v = this._valveOf(id);
        const follows = (s.followers || []).includes(id);
        const assist = (s.assist?.entities || []).includes(id);
        return dev(follows || assist ? "mdi:radiator" : "mdi:thermostat",
          assist ? `Zusatzheizung, gerade ${s.assist.on ? "an" : "zu"}` : follows ? "folgt dem Wandthermostat" : "stellt ein", id, bad ? "nicht erreichbar" : `${val(id, "current_temperature")} → ${val(id, "temperature")}${st.attributes.hvac_action === "heating" ? " · heizt" : ""}${v != null ? ` · Ventil ${fmt(v, 0)} %` : ""}`, !bad);
      }),
      ...(room.windows || []).map((id) => {
        const st = S[id];
        const open = st && ["on", "open", "opening", "true"].includes(String(st.state).toLowerCase());
        return dev(open ? "mdi:window-open-variant" : "mdi:window-closed-variant", "", id, !st ? "fehlt" : open ? "offen" : "zu", !!st);
      }),
      ...(room.show_entities || []).map((id) => {
        const st = S[id];
        const bad = !st || ["unavailable", "unknown"].includes(st.state);
        const v = this._valveOf(id);
        const dom = id.split(".")[0];
        const sw = this._switchOf(id);
        if (sw != null) return dev("mdi:heating-coil", "nur Anzeige", id, bad ? "nicht erreichbar" : sw ? "an – heizt" : "aus", !bad);
        const label = "nur Anzeige";
        return dev(v != null ? "mdi:valve" : dom === "climate" ? "mdi:thermostat-box" : "mdi:eye-outline", label, id, bad ? "nicht erreichbar" : v != null ? `${fmt(v, 0)} % offen${dom === "climate" ? ` · ${esc(this._fmtState(st))}` : ""}` : esc(this._fmtState(st)), !bad);
      }),
      room.temp_sensor ? dev("mdi:thermometer", "Raumtemperatur", room.temp_sensor, val(room.temp_sensor), !!S[room.temp_sensor]) : "",
      room.humidity_sensor ? dev("mdi:water-percent", "", room.humidity_sensor, val(room.humidity_sensor), !!S[room.humidity_sensor]) : "",
      room.presence_sensor ? dev("mdi:motion-sensor", "", room.presence_sensor, S[room.presence_sensor]?.state === "on" ? "jemand da" : "leer", !!S[room.presence_sensor]) : "",
    ].join("");
    const preMode = room.preheat_mode || set.preheat_mode || "fixed";
    const kv = (k, v) => `<div class="kv"><span>${k}</span><b>${v}</b></div>`;
    const settings = [
      kv("Komfort / Eco", `${fmt(room.comfort)} / ${fmt(room.eco)} °C`),
      kv("Heizplan", esc(this._planLabel(room))),
      kv("Vorheizen", preMode === "smart" ? `lernend${s.heat_rate ? ` · ${fmt(s.heat_rate)} °C/h` : ""}` : preMode === "off" ? "aus" : `${room.lead_min ?? this._leadFor(room.type)} Min.`),
      kv("Fensterpause nach", `${room.window_delay ?? d.window_delay ?? 0} s`),
      kv("Bei offenem Fenster", (room.pause_mode || d.pause_mode) === "off" ? "aus" : `${fmt(room.window_temp ?? set.frost_temp)} °C`),
      kv("Automatik", room.enabled === false ? "aus" : "an"),
    ].join("");
    const rep = this._report(7);
    const rows = rep?.[room.id] || [];
    const sum = (k) => rows.reduce((a, x) => a + (x[k] || 0), 0);
    const temps = rows.map((x) => x.avg_temp).filter((t) => t != null);
    const week = rep
      ? `<div class="wminis four">
          <div class="wmini"><ha-icon icon="mdi:fire"></ha-icon><b>${fmt(sum("heat_min") / 60)} h</b><small>geheizt</small></div>
          <div class="wmini"><ha-icon icon="mdi:sofa-outline"></ha-icon><b>${fmt(sum("comfort_min") / 60)} h</b><small>Komfort</small></div>
          <div class="wmini"><ha-icon icon="mdi:window-open-variant"></ha-icon><b>${int(sum("openings"))}×</b><small>gelüftet</small></div>
          <div class="wmini"><ha-icon icon="mdi:thermometer"></ha-icon><b>${temps.length ? fmt(temps.reduce((a, b) => a + b, 0) / temps.length) : "–"} °C</b><small>Ø Raum</small></div>
        </div>`
      : `<div class="chart-empty"><div class="spinner"></div></div>`;
    return `
      ${back}
      <div class="rpage">${this._roomCard(room)}</div>
      <section class="card">
        ${this._sectionHead("mdi:chart-line", "Letzte 24 Stunden", `<span class="rlegend"><span><i class="lt"></i>Raum</span><span><i class="ls"></i>Soll</span><span><i class="lh"></i>heizt</span><span><i class="lw"></i>Fenster offen</span></span>`)}
        ${this._historyChart(room)}
      </section>
      <div class="rp-grid">
        <section class="card">${this._sectionHead("mdi:devices", "Geräte", this._admin ? `<button class="link" data-action="room-edit" data-id="${room.id}" data-rtab="devices">Ändern</button>` : "")}<div class="wlist">${devices || `<p class="muted small">Noch keine Geräte zugeordnet.</p>`}</div></section>
        <section class="card">${this._sectionHead("mdi:tune-variant", "Einstellungen", this._admin ? `<button class="link" data-action="room-edit" data-id="${room.id}">Bearbeiten</button>` : "")}<div class="kvs">${settings}</div></section>
        <section class="card">${this._sectionHead("mdi:calendar-week", "Letzte 7 Tage", `<button class="link" data-action="tab" data-tab="report">Bericht</button>`)}${week}</section>
      </div>`;
  }

  /** Verlauf der letzten 24 h aus dem Recorder (Soll-Sensor von Heizwerk, sonst das Thermostat). */
  _history(room) {
    this._hist = this._hist || {};
    const h = this._hist[room.id];
    if (h && (h.loading || Date.now() - h.at < 5 * 60000)) return h;
    const sensor = this._data.target_sensors?.[room.id];
    const climate = (room.climates || [])[0];
    const ids = [sensor, climate, room.temp_sensor].filter(Boolean);
    this._hist[room.id] = { loading: true, at: Date.now() };
    if (!ids.length) {
      this._hist[room.id] = { at: Date.now(), error: "Keine Entitäten mit Verlauf" };
      return this._hist[room.id];
    }
    this._hass
      .callWS({ type: "history/history_during_period", start_time: new Date(Date.now() - 24 * 3600e3).toISOString(), entity_ids: ids, minimal_response: false, no_attributes: false, significant_changes_only: false })
      .then((res) => (this._hist[room.id] = { at: Date.now(), res, sensor, climate, temp: room.temp_sensor }))
      .catch((err) => (this._hist[room.id] = { at: Date.now(), error: err?.message || "Verlauf nicht verfügbar" }))
      .finally(() => this._tab === "room" && this._roomId === room.id && this._renderMain());
    return this._hist[room.id];
  }

  _historyChart(room) {
    const h = this._history(room);
    if (h.loading) return `<div class="chart-empty"><div class="spinner"></div></div>`;
    if (h.error) return `<p class="muted small">${esc(h.error)}</p>`;
    // Einträge vereinheitlichen: komprimiert (s, a, lu) oder ausführlich (state, attributes, last_updated)
    const norm = (list) =>
      (list || []).map((x) => ({ s: x.s ?? x.state, a: x.a ?? x.attributes ?? {}, t: x.lu != null ? x.lu * 1000 : new Date(x.last_updated || x.last_changed).getTime() }));
    const num = (v) => (v == null || v === "" || isNaN(parseFloat(v)) ? null : parseFloat(v));
    let pts = [];
    if (h.sensor && h.res[h.sensor]?.length) {
      let last = {};
      pts = norm(h.res[h.sensor]).map((x) => {
        // Attribute fehlen bei unveränderten Einträgen: letzten Stand weiterführen
        last = { ...last, ...x.a };
        return { t: x.t, target: num(x.s), temp: num(last.raumtemperatur), heat: !!last.heizt, win: !!last.fenster_offen };
      });
    } else if (h.climate && h.res[h.climate]?.length) {
      let last = {};
      pts = norm(h.res[h.climate]).map((x) => {
        last = { ...last, ...x.a };
        return { t: x.t, target: num(last.temperature), temp: num(last.current_temperature), heat: last.hvac_action === "heating", win: false };
      });
    }
    // eigener Raumsensor hat Vorrang für die Ist-Kurve
    const tempPts = h.temp && h.res[h.temp]?.length ? norm(h.res[h.temp]).map((x) => ({ t: x.t, v: num(x.s) })) : pts.map((p) => ({ t: p.t, v: p.temp }));
    if (!pts.length && !tempPts.length) return `<p class="muted small">Noch kein Verlauf aufgezeichnet.</p>`;
    const W = 1000, H = 220, L = 70, B = 24, T = 10;
    const t1 = Date.now(), t0 = t1 - 24 * 3600e3;
    const vals = [...tempPts.map((p) => p.v), ...pts.map((p) => p.target)].filter((v) => v != null);
    let lo = Math.floor(Math.min(...vals) - 0.5), hi = Math.ceil(Math.max(...vals) + 0.5);
    if (hi - lo < 4) hi = lo + 4;
    const x = (t) => L + ((Math.max(t0, t) - t0) / (t1 - t0)) * (W - L);
    const y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
    // Bänder: heizt (unten), Fenster offen (oben)
    const bands = (key, y0, hgt, cls) => {
      let out = "", start = null;
      pts.forEach((p, i) => {
        if (p[key] && start == null) start = p.t;
        const next = pts[i + 1]?.t ?? t1;
        if (start != null && (!p[key] || i === pts.length - 1)) {
          const end = p[key] ? next : p.t;
          out += `<rect class="${cls}" x="${x(start)}" y="${y0}" width="${Math.max(2, x(end) - x(start))}" height="${hgt}" rx="2"/>`;
          start = null;
        }
      });
      return out;
    };
    const line = (list, key) => {
      const ok = list.filter((p) => p[key] != null);
      if (!ok.length) return "";
      return ok.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p[key]).toFixed(1)}`).join("") + `L${x(t1)},${y(ok[ok.length - 1][key]).toFixed(1)}`;
    };
    const step = (list, key) => {
      const ok = list.filter((p) => p[key] != null);
      if (!ok.length) return "";
      let dStr = `M${x(ok[0].t).toFixed(1)},${y(ok[0][key]).toFixed(1)}`;
      for (let i = 1; i < ok.length; i++) dStr += `H${x(ok[i].t).toFixed(1)}V${y(ok[i][key]).toFixed(1)}`;
      return dStr + `H${x(t1)}`;
    };
    // Beschriftung als HTML, damit sie auf schmalen Bildschirmen nicht verzerrt
    const ticks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) * i) / 4);
    const grid = ticks.map((v) => `<line class="gl" x1="${L}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/>`).join("");
    const ylab = ticks.map((v) => `<span style="top:${(y(v) / H) * 100}%">${fmt(v, 0)}°</span>`).join("");
    const hours = `<div class="hx">${Array.from({ length: 5 }, (_, i) => `<span>${i === 4 ? "jetzt" : new Date(t0 + i * 6 * 3600e3).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</span>`).join("")}</div>`;
    return `
      <div class="chart-wrap hwrap">
        <div class="hy">${ylab}</div>
        <svg class="chart hist" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
          ${grid}
          ${bands("heat", H - B - 8, 8, "bh")}
          ${bands("win", T, 8, "bw")}
          <path class="ps" d="${step(pts, "target")}"/>
          <path class="pt" d="${line(tempPts, "v")}"/>
        </svg>
        ${hours}
      </div>`;
  }

  /** Zeitfenster, nach denen der Raum heizt (null bei Zeitplan/Kalender aus Home Assistant). */
  _roomBlocks(room) {
    if (room.schedule_entity) return null;
    const plan = this._data.plans?.[room.plan_id];
    if (plan) return plan.calendar ? null : plan.schedule || [];
    return room.schedule || [];
  }

  /** Woher die Komfortzeiten kommen, ob gerade Komfort ist und wann sich das ändert. */
  _schedInfo(room, s) {
    const plan = this._data.plans?.[room.plan_id];
    const blocks = this._roomBlocks(room);
    const now = new Date();
    let src, icon, comfort = false;
    if (room.schedule_entity) {
      const cal = room.schedule_entity.startsWith("calendar.");
      icon = cal ? "mdi:calendar-sync" : "mdi:home-assistant";
      src = this._entityName(room.schedule_entity);
      comfort = this._hass.states[room.schedule_entity]?.state === "on";
    } else if (plan?.calendar) {
      icon = "mdi:calendar-sync";
      src = plan.name;
      comfort = (this._status?.plan_events?.[plan.id] || []).some((e) => new Date(e.start) <= now && now < new Date(e.end));
    } else {
      icon = plan ? "mdi:calendar-multiple" : "mdi:calendar-edit";
      src = plan ? plan.name : "Eigener Plan";
      const day = (now.getDay() + 6) % 7;
      const min = now.getHours() * 60 + now.getMinutes();
      comfort = this._daySegments(blocks, room, day).some(([a, b, , c]) => c && a <= min && min < b);
    }
    let mins = s.next_change;
    if (blocks && blocks.length) mins = this._nextSwitch(blocks, room, comfort) ?? mins;
    let text;
    if (blocks && !blocks.length) text = "keine Komfortzeit – immer Eco";
    else if (mins == null) text = comfort ? "Komfortzeit läuft" : "keine Komfortzeit in Sicht";
    else {
      const at = new Date(now.getTime() + mins * 60000);
      const same = at.toDateString() === now.toDateString();
      const tomorrow = new Date(now.getTime() + 864e5).toDateString() === at.toDateString();
      const when = `${same ? "" : tomorrow ? "morgen " : at.toLocaleDateString("de-DE", { weekday: "short" }) + " "}${at.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`;
      text = comfort ? `Komfort bis ${when}` : `Komfort ab ${when}`;
    }
    return { src, icon, comfort, text, blocks };
  }

  /** Minuten bis Komfort beginnt bzw. endet, aus den Zeitfenstern (bis zu 7 Tage voraus). */
  _nextSwitch(blocks, room, comfort) {
    const now = new Date();
    const today = (now.getDay() + 6) % 7;
    const min = now.getHours() * 60 + now.getMinutes();
    for (let k = 0; k < 8; k++) {
      const segs = this._daySegments(blocks, room, (today + k) % 7);
      for (const [a, , , c] of segs) {
        if (k === 0 && a <= min) continue;
        if (c !== comfort && a > 0) return k * 1440 + a - min;
        if (c !== comfort && a === 0 && k > 0) return k * 1440 - min;
      }
    }
    return null;
  }

  /** Heutiger Zeitplan als Streifen mit Jetzt-Marke (Raumkarten). */
  _schedStrip(room, s, mini = false) {
    if (room.enabled === false) return "";
    const info = this._schedInfo(room, s);
    const day = (new Date().getDay() + 6) % 7;
    return `
      <div class="rsched ${mini ? "mini" : ""} ${info.comfort ? "on" : ""}">
        <div class="rs-top"><ha-icon icon="${info.icon}"></ha-icon><span class="rs-src">${esc(info.src)}</span><span class="grow"></span><b>${esc(info.text)}</b></div>
        ${info.blocks ? this._dayBar(info.blocks, room, day, true) : ""}
      </div>`;
  }

  /** Kompakte Raumkachel: Temperatur, Soll, Betriebsart und der heutige Plan. */
  _wrapInd(html) {
    return html.trim() ? `<div class="rm-ind">${html}</div>` : "";
  }

  _roomMini(room) {
    if (!(room.climates || []).length) return this._roomSetup(room, true);
    const s = this._status?.rooms?.[room.id] || {};
    const mode = s.mode || "aus";
    const m = MODE[mode] || MODE.aus;
    const info = room.enabled === false ? null : this._schedInfo(room, s);
    const day = (new Date().getDay() + 6) % 7;
    return `
      <article class="rmini tap ${mode === "aus" ? "off" : ""}" id="room-${room.id}" style="--rc:${this._roomColor(room.id)}; --c:${m.c}" data-action="room-quick" data-id="${room.id}" title="Tippen für manuelle Änderungen">
        <div class="rm-head">
          <span class="rm-ic"><ha-icon icon="${esc(roomIcon(room))}"></ha-icon></span>
          <button class="rm-name rlink" data-action="room-page" data-id="${room.id}" title="Raum öffnen">${esc(room.name)}</button>
          ${this._admin ? `<button class="icon tiny" data-action="room-edit" data-id="${room.id}" title="Bearbeiten"><ha-icon icon="mdi:cog-outline"></ha-icon></button>` : ""}
        </div>
        ${this._wrapInd(`
          ${s.heating ? `<ha-icon class="rm-fire" icon="mdi:fire" title="Heizt"></ha-icon>` : ""}
          ${s.windows_open ? `<ha-icon class="rm-win" icon="mdi:window-open-variant" title="Fenster offen"></ha-icon>` : ""}
          ${(() => {
            const dv = this._devIndicators(room);
            return (dv.valve != null ? `<span class="rm-dev ${dv.valve > 0 ? "on" : ""}" title="Ventil ${fmt(dv.valve, 0)} % offen"><ha-icon icon="mdi:valve"></ha-icon>${fmt(dv.valve, 0)}%</span>` : "")
              + (dv.floor?.on ? `<span class="rm-dev on" title="${esc(dv.floor.label)} heizt – ${esc(dv.floor.names)}"><ha-icon icon="mdi:heating-coil"></ha-icon></span>` : "")
              + (s.assist?.on ? `<span class="rm-dev on" title="Heizkörper hilft nach (Mischbetrieb)"><ha-icon icon="mdi:radiator"></ha-icon></span>` : "");
          })()}
        `)}
        <div class="rm-body">
          <span class="rm-temp">${fmt(s.room_temp)}<small>°C</small></span>
          <span class="rm-tgt"><small>Soll</small><b style="color:${tint(tempColor(s.target))}">${fmt(s.target)} °C</b></span>
        </div>
        <div class="rm-mode"><ha-icon icon="${m.i}"></ha-icon>${esc(s.mode_label || "Automatik aus")}${info ? `<span class="grow"></span><small>${esc(info.text)}</small>` : ""}</div>
        ${info?.blocks ? this._dayBar(info.blocks, room, day, true) : ""}
      </article>`;
  }

  // ------------------------------------------------------------ Heizpläne: gemeinsame Pläne, im Raum auswählbar
  _viewPlans() {
    const rooms = this._rooms();
    const plans = this._planList();
    const P = this._plan;
    const valid = P && (P.kind === "plan" ? !P.id || this._data.plans?.[P.id] : this._data.rooms[P.id]);
    if (!valid) {
      this._plan = null;
      if (plans.length) this._selectPlan("plan", plans[0].id);
      else if (rooms.length) this._selectPlan("room", rooms[0].id);
    }
    const plan = this._plan;
    const dis = this._admin ? "" : "disabled";
    const isOn = (kind, id) => plan && plan.kind === kind && plan.id === id;
    const roomIc = (r) =>
      r.schedule_entity ? "mdi:home-assistant" : this._data.plans?.[r.plan_id] ? "mdi:link-variant" : (r.schedule || []).length ? "mdi:calendar-edit" : "mdi:calendar-blank-outline";
    const pills = `
      <button class="link back" data-action="tab" data-tab="settings"><ha-icon icon="mdi:chevron-left"></ha-icon>Einstellungen</button>
      <section class="card plangroups">
        <div class="pg">
          <span class="pg-l"><ha-icon icon="mdi:calendar-multiple"></ha-icon>Gemeinsame Pläne</span>
          <div class="pills">
            ${plans.map((p) => `<button class="pill ${isOn("plan", p.id) ? "on" : ""}" data-action="plan-sel" data-kind="plan" data-id="${p.id}"><ha-icon icon="${p.calendar ? "mdi:calendar-sync" : "mdi:calendar-clock"}"></ha-icon>${esc(p.name)}<em>${this._planRooms(p.id).length}</em></button>`).join("")}
            ${plan && plan.kind === "plan" && !plan.id ? `<button class="pill on"><ha-icon icon="mdi:calendar-plus"></ha-icon>${esc(plan.name || "Neuer Plan")}</button>` : ""}
            ${this._admin ? `<button class="pill add" data-action="plan-new"><ha-icon icon="mdi:plus"></ha-icon>Neuer Plan</button>` : ""}
          </div>
        </div>
        ${rooms.length ? `
        <div class="pg">
          <span class="pg-l"><ha-icon icon="mdi:floor-plan"></ha-icon>Räume</span>
          <div class="pills">
            ${rooms.map((r) => `<button class="pill ${isOn("room", r.id) ? "on" : ""}" style="--rc:${this._roomColor(r.id)}" data-action="plan-sel" data-kind="room" data-id="${r.id}" title="${esc(this._planLabel(r))}"><i></i>${esc(r.name)}<ha-icon class="pi" icon="${roomIc(r)}"></ha-icon></button>`).join("")}
          </div>
        </div>` : ""}
      </section>`;
    if (!plan) {
      return `${pills}<section class="card empty"><ha-icon icon="mdi:calendar-blank"></ha-icon><h2>Noch keine Heizpläne</h2>
        <p>Lege einen gemeinsamen Plan an und wähle ihn in den Räumen aus – oder lege zuerst einen Raum an.</p>
        ${this._admin ? `<button class="primary" data-action="plan-new"><ha-icon icon="mdi:plus"></ha-icon>Plan anlegen</button>` : ""}</section>`;
    }

    // Raum, der einem Zeitplan/Kalender oder einem gemeinsamen Plan folgt: nur Hinweis, Bearbeiten beim Plan
    if (plan.kind === "room") {
      const room = this._data.rooms[plan.id];
      const select = this._admin ? this._planSelect(room) : "";
      if (room.schedule_entity) {
        const se = this._hass.states[room.schedule_entity];
        const cal = room.schedule_entity.startsWith("calendar.");
        const nextIso = cal ? (se?.state === "off" ? se?.attributes?.start_time : null) : se?.attributes?.next_event;
        const next = nextIso ? new Date(nextIso).toLocaleString("de-DE", { weekday: "short", hour: "2-digit", minute: "2-digit" }) : null;
        return `${pills}
          <section class="card empty">
            <ha-icon icon="${cal ? "mdi:calendar-sync" : "mdi:home-assistant"}"></ha-icon>
            <h2>${esc(room.name)} folgt ${cal ? "einem Kalender" : "einem Zeitplan"} aus Home Assistant</h2>
            <p><b>${esc(this._entityName(room.schedule_entity))}</b> ist gerade <b>${se?.state === "on" ? (cal ? "mit Termin (Komfort)" : "an (Komfort)") : (cal ? "ohne Termin (Eco)" : "aus (Eco)")}</b>${next ? ` · nächster ${cal ? "Termin" : "Wechsel"} ${next}` : ""}.</p>
            ${select}
          </section>`;
      }
      const shared = this._data.plans?.[room.plan_id];
      if (shared) {
        return `${pills}
          <section class="card empty">
            <ha-icon icon="mdi:link-variant"></ha-icon>
            <h2>${esc(room.name)} nutzt den Plan „${esc(shared.name)}“</h2>
            <p>Änderungen am Plan gelten für alle Räume, die ihn nutzen: ${this._planRooms(shared.id).map((r) => esc(r.name)).join(", ")}.</p>
            ${select}
            <div class="row-btns">
              <button class="secondary" data-action="plan-sel" data-kind="plan" data-id="${shared.id}"><ha-icon icon="mdi:calendar-edit"></ha-icon>Plan bearbeiten</button>
              ${this._admin ? `<button class="secondary" data-action="plan-own" data-id="${room.id}"><ha-icon icon="mdi:content-copy"></ha-icon>Eigene Kopie für ${esc(room.name)}</button>` : ""}
            </div>
          </section>`;
      }
    }

    const ref = this._planRef();
    const day = plan.day;
    const using = plan.kind === "plan" && plan.id ? this._planRooms(plan.id) : [];
    const head =
      plan.kind === "plan"
        ? `
        <div class="plan-head">
          <div class="grow">
            ${this._admin ? `<input class="plan-name" type="text" maxlength="60" data-planname value="${esc(plan.name)}" placeholder="Name des Plans">` : `<h2>${esc(plan.name)}</h2>`}
            <div class="muted small">${using.length ? `Genutzt von ${using.map((r) => `<span class="uchip" style="--rc:${this._roomColor(r.id)}"><i></i>${esc(r.name)}</span>`).join(" ")}` : "Noch von keinem Raum genutzt – im Raum unter „Heizplan“ auswählen."}</div>
          </div>
          ${this._admin && plan.id ? `<button class="icon boxed" title="Plan löschen" data-action="plan-delete"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>` : ""}
        </div>
        <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Komfort- und Eco-Temperatur kommen vom jeweiligen Raum; ein Zeitfenster kann eine eigene Temperatur haben.</p>`
        : `
        <div class="plan-head">
          <div class="grow"><h2>Eigener Heizplan</h2><div class="muted">${esc(ref.name)} · ${TYPES[ref.type].label}</div></div>
          <div class="plan-temps">
            <span class="tpill" style="--c:${tempColor(ref.comfort)}">Komfort <b>${fmt(ref.comfort)} °C</b></span>
            <span class="tpill" style="--c:#93c5fd">Eco <b>${fmt(ref.eco)} °C</b></span>
          </div>
        </div>
        ${this._admin ? `<div class="row-btns">${this._planSelect(ref)}<button class="link" data-action="plan-promote"><ha-icon icon="mdi:calendar-multiple"></ha-icon>Als gemeinsamen Plan speichern</button></div>` : ""}`;

    // Gemeinsamer Plan: feste Zeitfenster oder live aus einem Kalender
    const src =
      plan.kind === "plan"
        ? `<div class="field"><span><ha-icon icon="mdi:source-branch"></ha-icon> Komfortzeiten kommen aus</span>
            <div class="segs small">${[["times", "Zeitfenster", "mdi:clock-outline"], ["cal", "HA-Kalender (live)", "mdi:calendar-sync"]]
              .map(([v, l, i]) => `<button class="seg ${(plan.cal ? "cal" : "times") === v ? "on" : ""}" data-action="plan-src" data-v="${v}" ${dis}><ha-icon icon="${i}"></ha-icon>${l}</button>`)
              .join("")}</div></div>`
        : "";
    const saveBar = this._admin && plan.dirty ? `
      <div class="savebar">
        <button class="secondary" data-action="plan-revert">Verwerfen</button>
        <button class="primary" data-action="plan-save">Speichern</button>
      </div>` : "";
    if (plan.kind === "plan" && plan.cal) {
      const st = this._status || {};
      const saved = plan.id ? this._data.plans?.[plan.id] : null;
      const fresh = saved && saved.calendar === plan.calendar && (saved.keyword || "") === (plan.keyword || "");
      const events = fresh ? st.plan_events?.[plan.id] || [] : null;
      const err = fresh ? st.plan_errors?.[plan.id] : null;
      const now = new Date();
      const when = (iso) => new Date(iso).toLocaleString("de-DE", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
      const hhmm = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
      return `
        ${pills}
        <section class="card">
          ${head}
          ${src}
          <div class="field"><span><ha-icon icon="mdi:calendar"></ha-icon> Kalender</span>${this._picker("plan_calendar", plan.calendar ? [plan.calendar] : [])}</div>
          <label class="field"><span><ha-icon icon="mdi:text-search"></ha-icon> Nur Termine mit diesen Wörtern (mit Komma getrennt, leer = alle)</span>
            <input type="text" maxlength="200" data-plankw value="${esc(plan.keyword || "")}" placeholder="z. B. Homeoffice, Heizen" ${dis}></label>
          <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Läuft ein Termin, heizen alle Räume mit diesem Plan auf Komfort, sonst Eco – vor dem nächsten Termin wird vorgeheizt. Ganztägige Termine zählen nicht. Neue oder geänderte Termine übernimmt Heizwerk innerhalb von 5 Minuten.</p>
          ${err ? `<p class="note warn"><ha-icon icon="mdi:alert-outline"></ha-icon>Kalender nicht lesbar: ${esc(err)}</p>` : ""}
          ${events ? `
          <div class="lbl">Nächste Komfortzeiten</div>
          <div class="evlist">${events.length ? events.map((e) => {
            const on = new Date(e.start) <= now;
            return `<div class="ev ${on ? "live" : ""}"><ha-icon icon="${on ? "mdi:fire" : "mdi:calendar-clock"}"></ha-icon>
              <span class="grow"><b>${esc(e.summary || "Termin")}</b><small>${when(e.start)} – ${hhmm(e.end)}</small></span>${on ? `<em class="badge ok">JETZT</em>` : ""}</div>`;
          }).join("") : `<p class="muted small">In den nächsten 8 Tagen kein passender Termin – die Räume bleiben auf Eco.</p>`}</div>`
          : plan.calendar ? `<p class="muted small"><ha-icon icon="mdi:content-save-outline"></ha-icon>Nach dem Speichern zeigt Heizwerk hier die nächsten Termine.</p>` : ""}
        </section>
        ${saveBar}`;
    }

    this._planRefDay = [ref, day];
    return `
      ${pills}
      <section class="card">
        ${head}
        ${src}
        <div class="lbl">Vorschau für Tag${plan.kind === "plan" ? ` <span class="muted small">(mit ${using.length ? esc(ref.name) : "Komfort 21 °C / Eco 18 °C"})</span>` : ""}</div>
        <div class="daypills">
          ${DAYS.map((d, i) => `<button class="dp ${i === day ? "on" : ""}" data-action="plan-preview" data-day="${i}">${d}</button>`).join("")}
        </div>
        <div id="plan-preview">${this._planPreview(plan, ref, day)}</div>
      </section>

      <div class="blocks">
        ${plan.blocks.length ? plan.blocks.map((b, i) => this._blockCard(b, i, ref, dis)).join("") : `<section class="card empty small"><p>Keine Komfortzeiten: ${plan.kind === "plan" ? "Räume mit diesem Plan bleiben" : `${esc(ref.name)} bleibt`} immer auf Eco.</p></section>`}
      </div>

      ${this._admin ? `
      <div class="plan-tools">
        <button class="addbtn" data-action="plan-add"><ha-icon icon="mdi:plus"></ha-icon>Zeitfenster hinzufügen</button>
        <label class="ghost select-link"><ha-icon icon="mdi:file-download-outline"></ha-icon>Vorlage laden
          <select data-action="plan-preset"><option value=""></option>${Object.entries(PLAN_PRESETS).map(([k, p]) => `<option value="${k}">${esc(p.label)}</option>`).join("")}</select>
        </label>
        <button class="ghost" data-action="import-open"><ha-icon icon="mdi:calendar-import"></ha-icon>Aus Kalender importieren</button>
      </div>
      <div class="savebar" id="plan-savebar" ${plan.dirty ? "" : "hidden"}>
        <button class="secondary" data-action="plan-revert">Verwerfen</button>
        <button class="primary" data-action="plan-save">Speichern</button>
      </div>` : ""}`;
  }

  /** Tagesbalken, Legende und Wochenübersicht des Plan-Editors. */
  _planPreview(plan, ref, day) {
    return `
        ${this._dayBar(plan.blocks, ref, day)}
        <div class="muted small legend-line">${["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][day]}
          <span><i style="background:color-mix(in srgb, #60a5fa 38%, var(--card2))"></i>Eco</span>
          <span><i style="background:${tempColor(ref.comfort)}"></i>Komfort</span>
          <span><i style="background:linear-gradient(90deg,#fde047,#fb923c)"></i>eigene Temperatur</span>
        </div>
        <div class="week-mini">
          ${DAYS.map((d, i) => `<div class="wm-row"><span>${d}</span>${this._dayBar(plan.blocks, ref, i, true)}</div>`).join("")}
        </div>`;
  }

  /** Nach einer Uhrzeit-Änderung nur Vorschau, Dauer und Speicherleiste anpassen – ohne Neuzeichnen,
   *  damit der Uhrzeit-Wähler am Handy offen bleibt und die Seite nicht springt. */
  _planSoftUpdate(i) {
    const root = this.shadowRoot;
    this._plan.dirty = true;
    const bar = root.getElementById("plan-savebar");
    if (bar) bar.hidden = false;
    const prev = root.getElementById("plan-preview");
    if (prev && this._planRefDay) prev.innerHTML = this._planPreview(this._plan, ...this._planRefDay);
    const b = this._plan.blocks[i];
    const dur = root.querySelector(`.dur[data-i="${i}"]`);
    if (b && dur) {
      let d = hm(b.end) - hm(b.start);
      if (d <= 0) d += 1440;
      dur.textContent = `${Math.floor(d / 60)} h${d % 60 ? ` ${d % 60} min` : ""}${hm(b.end) <= hm(b.start) ? " · bis zum Folgetag" : ""}`;
    }
  }

  /** Räume, die einen gemeinsamen Plan nutzen. */
  _planRooms(planId) {
    return this._rooms().filter((r) => r.plan_id === planId && !r.schedule_entity);
  }

  /** Raum für Vorschau-Farben: der Raum selbst bzw. der erste Raum, der den Plan nutzt. */
  _planRef() {
    const P = this._plan;
    if (P.kind === "room") return this._data.rooms[P.id];
    const first = P.id ? this._planRooms(P.id)[0] : null;
    return first || { name: "Beispiel", type: "heizkoerper", comfort: 21, eco: 18 };
  }

  /** Auswahl, welchem Plan ein Raum folgt (direkt speichern). */
  _planSelect(room) {
    if (room.schedule_entity) {
      return `<button class="secondary" data-action="room-edit" data-id="${room.id}"><ha-icon icon="mdi:calendar-edit"></ha-icon>Im Raum auf einen Heizplan umstellen</button>`;
    }
    return `
      <label class="field inline-sel"><span><ha-icon icon="mdi:calendar-clock"></ha-icon> ${esc(room.name)} folgt</span>
        <select data-action="room-plan" data-id="${room.id}">
          ${this._planList().map((p) => `<option value="${p.id}" ${room.plan_id === p.id ? "selected" : ""}>Plan „${esc(p.name)}“</option>`).join("")}
          <option value="" ${this._data.plans?.[room.plan_id] ? "" : "selected"}>Eigener Plan</option>
        </select>
      </label>`;
  }

  _selectPlan(kind, id) {
    const day = this._plan?.day ?? (new Date().getDay() + 6) % 7;
    const src = kind === "plan" ? this._data.plans?.[id] : this._data.rooms[id];
    this._plan = { kind, id, name: src?.name || "", blocks: clone(src?.schedule || []), dirty: false, day,
      cal: kind === "plan" && !!src?.calendar, calendar: src?.calendar || null, keyword: src?.keyword || "" };
  }
  /** Segmente eines Tages: [start, end, temp, isComfort], lückenlos 0–1440. */
  _daySegments(blocks, room, day) {
    const cover = [];
    for (const b of blocks) {
      const s = hm(b.start);
      let e = hm(b.end);
      if (e <= s) e += 1440;
      const t = b.temp ?? room.comfort;
      for (const d of b.days || []) {
        if (d === day) cover.push([s, Math.min(e, 1440), t]);
        if (e > 1440 && (d + 1) % 7 === day) cover.push([0, e - 1440, t]);
      }
    }
    const cuts = new Set([0, 1440]);
    cover.forEach(([s, e]) => (cuts.add(s), cuts.add(e)));
    const pts = [...cuts].sort((a, b) => a - b);
    const segs = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      const hits = cover.filter(([s, e]) => s <= a && b <= e).map((c) => c[2]);
      const t = hits.length ? Math.max(...hits) : room.eco;
      const last = segs[segs.length - 1];
      if (last && last[2] === t) last[1] = b;
      else segs.push([a, b, t, hits.length > 0]);
    }
    return segs;
  }

  _dayBar(blocks, room, day, mini = false) {
    const segs = this._daySegments(blocks, room, day);
    const now = new Date();
    const today = (now.getDay() + 6) % 7;
    const nowPct = ((now.getHours() * 60 + now.getMinutes()) / 1440) * 100;
    const bar = segs
      .map(
        ([s, e, t, comfort]) =>
          `<div class="dseg ${comfort ? "" : "eco"}" style="left:${(s / 1440) * 100}%;width:${((e - s) / 1440) * 100}%;background:${tempColor(t)}" title="${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}–${String(Math.floor(e / 60)).padStart(2, "0")}:${String(e % 60).padStart(2, "0")} · ${fmt(t)} °C"></div>`
      )
      .join("");
    if (mini) return `<div class="dbar mini">${bar}${day === today ? `<div class="now" style="left:${nowPct}%"></div>` : ""}</div>`;
    return `
      <div class="dbar">${bar}${day === today ? `<div class="now" style="left:${nowPct}%"></div>` : ""}</div>
      <div class="dscale">${[0, 6, 12, 18, 24].map((h) => `<span>${h}</span>`).join("")}</div>`;
  }

  _blockCard(b, i, room, dis) {
    const days = b.days || [];
    let dur = hm(b.end) - hm(b.start);
    if (dur <= 0) dur += 1440;
    const durTxt = dur > 0 ?`${Math.floor(dur / 60)} h${dur % 60 ? ` ${dur % 60} min` : ""}` : "";
    return `
      <section class="block" style="--tc:${tempColor(b.temp ?? room.comfort)}">
        <div class="block-top">
          <div class="times">
            <label class="timebox"><input type="time" value="${esc(b.start)}" data-plan="start" data-i="${i}" ${dis}><ha-icon icon="mdi:clock-outline"></ha-icon></label>
            <span class="muted">bis</span>
            <label class="timebox"><input type="time" value="${esc(b.end)}" data-plan="end" data-i="${i}" ${dis}><ha-icon icon="mdi:clock-outline"></ha-icon></label>
<span class="dur" data-i="${i}">${durTxt}${durTxt && hm(b.end) <= hm(b.start) ? " · bis zum Folgetag" : ""}</span>
          </div>
          <div class="block-temp">
            ${this._admin ? this._stepper("blk", i, b.temp, { placeholder: room.comfort }) : `<b style="color:${tint(tempColor(b.temp ?? room.comfort))}">${fmt(b.temp ?? room.comfort)} °C</b>`}
            ${b.temp != null && this._admin ? `<button class="link tiny" data-action="blk-comfort" data-i="${i}">= Komfort</button>` : `<span class="tiny muted">${b.temp == null ? "Komfort" : ""}</span>`}
          </div>
          ${this._admin ? `<button class="icon boxed" title="Entfernen" data-action="plan-del" data-i="${i}"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>` : ""}
        </div>
        <div class="lbl">Gilt an (mehrere Tage möglich)</div>
        <div class="daypills">
          ${DAYS.map((d, di) => `<button class="dp ${days.includes(di) ? "on" : ""}" data-action="plan-day" data-i="${i}" data-day="${di}" ${dis}>${d}</button>`).join("")}
        </div>
        ${this._admin ? `
        <div class="quick">
          <button class="link" data-action="plan-days" data-i="${i}" data-set="0,1,2,3,4">Mo–Fr</button>
          <button class="link" data-action="plan-days" data-i="${i}" data-set="5,6">Sa–So</button>
          <button class="link" data-action="plan-days" data-i="${i}" data-set="0,1,2,3,4,5,6">Alle Tage</button>
          <button class="link" data-action="plan-copy" data-i="${i}"><ha-icon icon="mdi:content-copy"></ha-icon>Kopie</button>
        </div>` : ""}
      </section>`;
  }


  // ------------------------------------------------------------ Rollwerk
  _rwCovers() {
    return (this._data?.settings?.rw_covers || []).map((id) => ({ id, st: this._hass.states[id], cfg: this._data.rollwerk?.covers?.[id] || {}, rs: this._rwStatus?.covers?.[id] || {} }));
  }

  _rwPos(st) {
    if (!st) return null;
    const p = Number(st.attributes?.current_position);
    return Number.isFinite(p) ? p : st.state === "open" ? 100 : st.state === "closed" ? 0 : null;
  }

  _rwNavHtml() {
    return `<nav class="heatnav">${SHUT_VIEWS.map((v) => `<button class="hnav ${this._tab === v.id ? "on" : ""}" data-action="tab" data-tab="${v.id}"><ha-icon icon="${v.icon}"></ha-icon><span>${v.name}</span></button>`).join("")}</nav>`;
  }

  _viewShutters() {
    const covers = this._rwCovers();
    const s = this._rwStatus || {};
    if (!this._data.rollwerk) return `<section class="card empty"><ha-icon icon="mdi:window-shutter-alert"></ha-icon><h2>Rollwerk nicht geladen</h2><p>Bitte Home Assistant neu starten.</p></section>`;
    if (!covers.length)
      return `<section class="card empty"><ha-icon icon="mdi:window-shutter"></ha-icon><h2>Noch keine Rollläden</h2>
        <p>Wähle die Rollläden, die Rollwerk fahren soll – morgens auf, abends zu, Sonnenschutz, Lüften und Sturmschutz.</p>
        ${this._admin ? `<button class="primary" data-action="cwiz-open"><ha-icon icon="mdi:auto-fix"></ha-icon>Rollladen hinzufügen</button>` : ""}</section>`;
    const pos = covers.map((c) => this._rwPos(c.st)).filter((x) => x != null);
    const nOpen = pos.filter((x) => x >= 95).length;
    const nClosed = pos.filter((x) => x <= 5).length;
    const sun = s.sun || {};
    const fact = (icon, val, cap, c = "") => `<div class="kv2" ${c ? `style="--c:${c}"` : ""}><ha-icon icon="${icon}"></ha-icon><span><b>${esc(val)}</b><small>${esc(cap)}</small></span></div>`;
    const all = covers.map((c) => c.id).join(",");
    const first = (covers.find((c) => (c.cfg.profile || "standard") === "standard") || covers[0])?.rs || {};
    const head = `
      <section class="card rw-sum">
        <div class="rw-sum-h">
          <div><small class="muted">Rollwerk · heute</small><h2>${nOpen} offen · ${nClosed} zu${pos.length - nOpen - nClosed ? ` · ${pos.length - nOpen - nClosed} halb` : ""}</h2></div>
          <div class="rw-all">${this._admin ? `<button class="secondary small" data-action="cwiz-open" title="Rollladen hinzufügen"><ha-icon icon="mdi:plus"></ha-icon></button>` : ""}<button class="secondary small" data-action="rw-cmd" data-ids="${all}" data-a="open"><ha-icon icon="mdi:arrow-up"></ha-icon>Alle hoch</button><button class="secondary small" data-action="rw-cmd" data-ids="${all}" data-a="close"><ha-icon icon="mdi:arrow-down"></ha-icon>Alle runter</button></div>
        </div>
        <div class="kv2s">
          ${fact("mdi:weather-sunset-up", first.up ? first.up.join("–") : "–", "öffnen · frühestens–spätestens")}
          ${fact("mdi:weather-sunset-down", first.down ? first.down.join("–") : "–", "schließen · frühestens–spätestens")}
          ${fact("mdi:white-balance-sunny", sun.elevation != null ? `${fmt(sun.elevation, 0)}° hoch` : "–", sun.azimuth != null ? `Richtung ${fmt(sun.azimuth, 0)}°` : "Sonne")}
          ${fact(s.storm ? "mdi:weather-windy-variant" : "mdi:weather-windy", s.gust != null ? `${fmt(s.gust, 0)} km/h` : "–", s.storm ? "Sturm – alle hoch" : `Böen · Sturm ab ${fmt(s.storm_kmh, 0)}`, s.storm ? "#ef4444" : "")}
        </div>
        ${s.free_day ? `<p class="muted small"><ha-icon icon="mdi:calendar-star"></ha-icon>Heute gilt der Wochenend-Zeitplan.</p>` : ""}
      </section>`;
    const groups = new Map();
    for (const c of covers) {
      const area = c.rs.area || "Ohne Raum";
      if (!groups.has(area)) groups.set(area, []);
      groups.get(area).push(c);
    }
    const tile = (c) => {
      const p = this._rwPos(c.st);
      const bad = !c.st || ["unavailable", "unknown"].includes(c.st.state);
      const moving = c.st?.state === "opening" ? "fährt hoch" : c.st?.state === "closing" ? "fährt runter" : "";
      const posTxt = bad ? "nicht erreichbar" : moving || (p == null ? c.st.state : p >= 95 ? "offen" : p <= 5 ? "zu" : `${fmt(p, 0)} % offen`);
      const flags = [];
      const cat = c.rs.cat;
      if (cat === "storm") flags.push(["mdi:weather-windy-variant", "Sturmschutz", "#ef4444"]);
      else if (cat === "force") flags.push(["mdi:gesture-tap-button", "Erzwungen", "#ef4444"]);
      else if (c.rs.contact_open) flags.push(["mdi:door-open", "offen – Aussperrschutz", "#f59e0b"]);
      else if (c.rs.contact_tilted) flags.push(["mdi:window-open-variant", "gekippt – lüften", "#22c55e"]);
      else if (cat === "shading") flags.push(["mdi:sun-thermometer-outline", "Beschattung", "#f97316"]);
      else if (cat === "away") flags.push(["mdi:home-export-outline", "niemand zu Hause", "#94a3b8"]);
      if (c.rs.resident) flags.push(["mdi:sleep", "Bewohner schläft", "#a78bfa"]);
      if (c.rs.manual) flags.push(["mdi:hand-back-right-outline", c.rs.blocked ? "von Hand – Automatik wartet" : "von Hand", "#8b5cf6"]);
      if (c.cfg.auto === false) flags.push(["mdi:robot-off-outline", "Automatik aus", "#94a3b8"]);
      const icon = bad ? "mdi:window-shutter-alert" : p != null && p >= 95 ? "mdi:window-shutter-open" : "mdi:window-shutter";
      const why = c.rs.reason && c.cfg.auto !== false ? `Automatik: ${c.rs.reason}${c.rs.target != null ? ` → ${c.rs.target >= 100 ? "offen" : c.rs.target === 0 ? "zu" : `${c.rs.target} %`}` : ""}` : "";
      return `
        <article class="card rw-c ${bad ? "bad" : ""}">
          <div class="rw-top">
            <span class="sr-ic" style="--c:${p != null && p <= 5 ? "#64748b" : "#0ea5e9"}"><ha-icon icon="${icon}"></ha-icon></span>
            <span class="grow"><b>${esc(this._entityName(c.id))}</b><small>${esc(posTxt)}${why ? ` · ${esc(why)}` : ""}</small></span>
            ${this._admin ? `<button class="icon" data-action="pop-open" data-pop="rwc:${esc(c.id)}" title="Einstellungen dieses Rollladens"><ha-icon icon="mdi:cog-outline"></ha-icon></button>` : ""}
          </div>
          ${c.cfg.auto !== false && this._rwStatus?.timelines?.[c.cfg.profile || "standard"] ? `<div class="rw-next">${this._rwDayBar(this._rwStatus.timelines[c.cfg.profile || "standard"], true)}${c.rs.next ? `<small><ha-icon icon="mdi:clock-outline"></ha-icon>Als Nächstes: ${esc(c.rs.next)}</small>` : ""}</div>` : ""}
          ${flags.length ? `<div class="rw-flags">${flags.map(([i, l, k]) => `<span style="--c:${k}"><ha-icon icon="${i}"></ha-icon>${l}</span>`).join("")}${c.rs.manual ? `<button class="link" data-action="rw-cmd" data-ids="${esc(c.id)}" data-a="resume"><ha-icon icon="mdi:robot-outline"></ha-icon>Automatik übernimmt</button>` : ""}</div>` : ""}
          <div class="rw-ctl">
            <button class="sbtn" data-action="rw-cmd" data-ids="${esc(c.id)}" data-a="open" title="hoch" ${bad ? "disabled" : ""}><ha-icon icon="mdi:arrow-up"></ha-icon></button>
            <button class="sbtn" data-action="rw-cmd" data-ids="${esc(c.id)}" data-a="stop" title="Stopp" ${bad ? "disabled" : ""}><ha-icon icon="mdi:stop"></ha-icon></button>
            <button class="sbtn" data-action="rw-cmd" data-ids="${esc(c.id)}" data-a="close" title="runter" ${bad ? "disabled" : ""}><ha-icon icon="mdi:arrow-down"></ha-icon></button>
            <input class="rw-range" type="range" min="0" max="100" step="5" value="${p ?? 0}" data-rwpos="${esc(c.id)}" style="--v:${p ?? 0}%" ${bad ? "disabled" : ""} aria-label="Stellung">
          </div>
        </article>`;
    };
    return head + [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0], "de"))
      .map(([area, list]) => `<div class="rw-area"><h3>${esc(area)}</h3><div class="rw-grid">${list.map(tile).join("")}</div></div>`).join("");
  }

  _rwProfiles() {
    const all = this._data.rollwerk?.profiles || {};
    return Object.entries(all).map(([id, p]) => ({ id, ...p })).sort((a, b) => (a.id === "standard" ? -1 : b.id === "standard" ? 1 : String(a.name).localeCompare(String(b.name), "de")));
  }

  _rwProfName(pid) {
    return this._data.rollwerk?.profiles?.[pid || "standard"]?.name || "Standard";
  }

  /** Wonach öffnet/schließt das Verhalten? time | sun | cal | free */
  _rwMode(p) {
    const f = p.features || [];
    if (!f.includes("time")) return "free";
    if (p.time_mode === "calendar") return "cal";
    return f.includes("sun") || f.includes("brightness") ? "sun" : "time";
  }

  /** Tagesleiste: Nacht, offen, Beschattung möglich, jetzt-Strich und Zeiten darunter. */
  _rwDayBar(tl, small = false) {
    if (!tl) return "";
    const m = (hm) => (hm ? Number(hm.slice(0, 2)) * 60 + Number(hm.slice(3, 5)) : null);
    const pc = (x) => `${((x / 1440) * 100).toFixed(2)}%`;
    const o = m(tl.open), c = m(tl.close);
    const from = o ?? 0, to = c ?? 1440;
    const now = new Date();
    const nowM = now.getHours() * 60 + now.getMinutes();
    const segs = [`<i class="d-day" style="left:${pc(from)};width:${pc(Math.max(0, to - from))}"></i>`]
      .concat((tl.shade || []).map(([a, b]) => `<i class="d-shade" style="left:${pc(m(a))};width:${pc(Math.max(10, m(b) - m(a)))}"></i>`));
    const lab = [tl.open ? `<span style="left:${pc(o)}">${tl.approx ? "~" : ""}${tl.open}</span>` : "", tl.close ? `<span style="left:${pc(c)}">${tl.approx ? "~" : ""}${tl.close}</span>` : ""].join("");
    return `<div class="rwday ${small ? "small" : ""}"><div class="rwday-bar">${segs.join("")}<b class="d-now" style="left:${pc(nowM)}"></b></div>${small ? "" : `<div class="rwday-lab">${lab}</div>`}</div>`;
  }

  /** Kurztext eines Verhaltens für Listen. */
  _rwProfSum(p) {
    const tl = this._rwStatus?.timelines?.[p.id];
    const mode = this._rwMode(p);
    const parts = [];
    if (tl?.open || tl?.close) parts.push(`heute ${tl.open || "–"} auf · ${tl.close || "–"} zu`);
    else parts.push({ time: "nach Uhrzeit", sun: "mit der Sonne", cal: "nach Kalender", free: "nur Sonne/Helligkeit" }[mode]);
    if ((p.features || []).includes("shading")) parts.push(`Sonnenschutz${p.window_dir != null ? ` (${this._rwDirName(p.window_dir)})` : ""}`);
    if (p.away_mode && p.away_mode !== "normal") parts.push("Abwesend: " + (p.away_mode === "closed" ? "zu" : "beschattet"));
    return parts.join(" · ");
  }

  _rwDirName(deg) {
    return ["Nord", "Nordost", "Ost", "Südost", "Süd", "Südwest", "West", "Nordwest"][Math.round(((Number(deg) % 360) + 360) % 360 / 45) % 8];
  }

  _rwRows(p) {
    const covers = this._rwCovers();
    const s = this._rwStatus || {};
    const profiles = this._rwProfiles();
    const rows = [
      { g: "Rollläden", id: "cwiz", icon: "mdi:auto-fix", c: "#0ea5e9", title: "Rollladen hinzufügen", sum: "Assistent: Richtung, Fensterkontakt, Raum und Verhalten in sechs Schritten", words: "assistent neu hinzufügen rollladen" },
      { g: "Rollläden", id: "rwcovers", icon: "mdi:window-shutter-settings", c: "#0ea5e9", title: "Welche Rollläden?",
        sum: covers.length ? `${covers.length} gewählt` : "Noch keine gewählt", warn: !covers.length, words: "rollladen rollo jalousie auswahl geräte" },
      ...covers.map((c) => ({
        g: "Rollläden", id: `rwc:${c.id}`, icon: "mdi:window-shutter", c: c.cfg.auto === false ? "#94a3b8" : "#38bdf8",
        title: this._entityName(c.id), off: c.cfg.auto === false,
        sum: [`Verhalten „${this._rwProfName(c.cfg.profile)}“`, c.cfg.contact_open || c.cfg.contact_tilted ? "mit Fensterkontakt" : "", c.cfg.storm === false ? "ohne Sturmschutz" : ""].filter(Boolean).join(" · "),
        words: `${c.id} verhalten profil fenster tür kontakt`,
      })),
      ...profiles.map((x) => {
        const n = covers.filter((c) => (c.cfg.profile || "standard") === x.id).length;
        return { g: "Verhalten", id: `rwp:${x.id}:tag`, icon: "mdi:tune-variant", c: "#f59e0b", title: `${x.name} · ${n} ${n === 1 ? "Rollladen" : "Rollläden"}`,
          sum: this._rwProfSum(x), words: `verhalten profil ${x.name} zeiten sonnenschutz lüften ausnahmen` };
      }),
      { g: "Verhalten", id: "rwp::tag", icon: "mdi:plus", c: "#0ea5e9", title: "Neues Verhalten", sum: "z. B. für eine Fassade oder das Schlafzimmer – startet als Kopie von „Standard“", words: "profil verhalten neu anlegen kopie" },
      { g: "Allgemein", id: "rwstorm", icon: "mdi:weather-windy-variant", c: "#ef4444", title: "Sturmschutz",
        sum: p.rw_storm !== false ? `hoch ab ${fmt(p.storm_kmh ?? 70, 0)} km/h Böen${s.gust != null ? ` · jetzt ${fmt(s.gust, 0)} km/h` : ""}` : "Aus", words: "sturm wind böen schutz" },
      { g: "Allgemein", id: "rwrecovery", icon: "mdi:restart", c: "#64748b", title: "Nach Neustart",
        sum: { never: "nichts nachholen", outage: "verpasste Wechsel nachholen", always: "immer auf Sollstellung fahren" }[p.rw_recovery || "never"], words: "neustart stromausfall nachholen recovery" },
      { g: "Allgemein", go: "house", icon: "mdi:home-cog-outline", c: "#94a3b8", title: "Aus Hauswerk übernommen",
        sum: "Anwesenheit, Urlaub, Feiertage, Sonnenstand, Wetter, Sturmgrenze und Böen-Sensor – gelten für alle Module", words: "anwesenheit urlaub sonne wetter feiertage hauswerk" },
    ];
    return rows;
  }

  _rwPop(id) {
    const p = this._settings;
    const { sw } = this._setHelpers(p);
    const s = this._rwStatus || {};
    const row = (k, title, sub, value, text, ctl) => this._setRow(k, title, sub, value, text, ctl);
    switch (id) {
      case "rwcovers":
        return { icon: "mdi:window-shutter-settings", c: "#0ea5e9", title: "Welche Rollläden?", sub: "Rollwerk",
          body: `<p class="muted">Gewählte Rollläden fährt Rollwerk nach ihrem Verhalten. Verhalten und Fensterkontakte stellst du danach je Rollladen ein. Gruppen wie „Alle Rollläden“ besser weglassen.</p>
            <div class="field"><span><ha-icon icon="mdi:window-shutter"></ha-icon> Rollläden</span>${this._picker("rw_covers", p.rw_covers || [])}</div>` };
      case "rwstorm":
        return { icon: "mdi:weather-windy-variant", c: "#ef4444", title: "Sturmschutz", sub: "Rollwerk · alle Rollläden",
          body: `<div class="wxrows">${row("rt0", "Sturmschutz", `hoch ab ${fmt(p.storm_kmh ?? 70, 0)} km/h Böen`, sw("rw_storm"), "Bei Sturm fahren die Rollläden hoch, damit der Behang nicht beschädigt wird, und bleiben oben, bis die Böen 15 Minuten lang unter 80 % der Grenze liegen. Je Rollladen abschaltbar.")}</div>
            <div class="rq-facts"><span style="--c:${s.storm ? "#ef4444" : "#22c55e"}"><ha-icon icon="mdi:weather-windy"></ha-icon>${s.gust != null ? `Böen jetzt ${fmt(s.gust, 0)} km/h` : "keine Windwerte"}</span>${s.storm ? `<span style="--c:#ef4444"><ha-icon icon="mdi:alert"></ha-icon>Sturmschutz aktiv</span>` : ""}</div>
            <p class="muted small"><ha-icon icon="mdi:home-cog-outline"></ha-icon>Sturmgrenze und Böen-Sensor stehen unter <button class="link inline" data-action="settings-go" data-sub="weather">Hauswerk › Wetter</button> – sie gelten für alle Module.</p>` };
      case "rwrecovery": {
        const { segs } = this._setHelpers(p);
        return { icon: "mdi:restart", c: "#64748b", title: "Nach Neustart", sub: "Rollwerk · alle Rollläden",
          body: `${segs("rw_recovery", [["never", "Nichts"], ["outage", "Verpasstes"], ["always", "Immer"]], "never")}
            <p class="muted small">„Nichts“: nach einem Neustart fährt Rollwerk erst beim nächsten Wechsel. „Verpasstes“: war Home Assistant während eines Wechsels aus (z. B. Stromausfall morgens), fährt Rollwerk das nach. „Immer“: nach jedem Neustart auf die aktuelle Sollstellung.</p>` };
      }
    }
    return { icon: "mdi:help", c: "#94a3b8", title: id, body: "" };
  }

  /** Kompass: Fensterrichtung antippen; Sonnenschutz-Bereich und Sonne jetzt. */
  _rwCompass(p) {
    const cx = 110, cy = 110, R = 82;
    const pt = (deg, r) => [cx + r * Math.sin((deg * Math.PI) / 180), cy - r * Math.cos((deg * Math.PI) / 180)];
    const s0 = Number(p.azimuth_start ?? 95), s1 = Number(p.azimuth_end ?? 265);
    const span = (((s1 - s0) % 360) + 360) % 360;
    const [ax, ay] = pt(s0, R), [bx, by] = pt(s1, R);
    const sector = `<path d="M${cx},${cy} L${ax.toFixed(1)},${ay.toFixed(1)} A${R},${R} 0 ${span > 180 ? 1 : 0} 1 ${bx.toFixed(1)},${by.toFixed(1)} Z" class="cp-sec"/>`;
    const sun = this._rwStatus?.sun || {};
    const sunDot = sun.azimuth != null && sun.elevation > 0 ? (() => { const [x, y] = pt(sun.azimuth, R * (1 - Math.min(sun.elevation, 80) / 110)); return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="9" class="cp-sun"/>`; })() : "";
    const dirs = [["N", 0], ["NO", 45], ["O", 90], ["SO", 135], ["S", 180], ["SW", 225], ["W", 270], ["NW", 315]];
    const btns = dirs.map(([l, d]) => { const [x, y] = pt(d, R + 16); const on = Number(p.window_dir) === d; return `<g class="cp-b ${on ? "on" : ""}" data-action="rwp-dir" data-v="${d}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="15"/><text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}">${l}</text></g>`; }).join("");
    const win = p.window_dir != null ? (() => { const [x, y] = pt(Number(p.window_dir), R - 6); return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" class="cp-win"/>`; })() : "";
    return `<div class="compass"><svg viewBox="0 0 220 220" aria-label="Fensterrichtung">
      <circle cx="${cx}" cy="${cy}" r="${R}" class="cp-ring"/>${sector}${win}<rect x="${cx - 14}" y="${cy - 9}" width="28" height="18" rx="4" class="cp-house"/>${sunDot}${btns}</svg>
      <p class="muted small">${p.window_dir != null ? `Fenster zeigt nach <b>${this._rwDirName(p.window_dir)}</b> – Sonne zählt von ${fmt(s0, 0)}° bis ${fmt(s1, 0)}°.` : "Tippe an, wohin das Fenster zeigt."}${sun.azimuth != null && sun.elevation > 0 ? " ● Sonne jetzt." : ""}</p></div>`;
  }

  /** Verhalten bearbeiten: fünf Abschnitte, einfach oder mit „Experte“ alle Einstellungen der Cover Control Automation. */
  _rwpPop(pid, sec) {
    const d = this._pop.draft;
    const profiles = this._data.rollwerk?.profiles || {};
    if (!d.prof) {
      d.pid = pid || null;
      d.prof = clone(profiles[pid] || { ...(profiles.standard || {}), name: "Neues Verhalten" });
    }
    const p = d.prof;
    const ex = this._expertOn();
    const dis = this._admin ? "" : "disabled";
    const S = this._hass.states;
    const st = this._rwStatus || {};
    const row = (k, title, sub, ctl, text) => text ? this._setRow(`rwp_${k}`, title, sub, ctl, text, true)
      : `<div class="wxr ctl"><div class="wxr-l"><b>${title}</b>${sub ? `<small>${sub}</small>` : ""}</div><div class="wxr-v">${ctl}</div></div>`;
    const num = (k, def, min, max, step, unit) => `<div class="unit"><input type="number" min="${min}" max="${max}" step="${step}" data-rwp="${k}" data-kind="num" value="${p[k] ?? ""}" placeholder="${def ?? "–"}" ${dis}><i>${unit}</i></div>`;
    const time = (k) => `<input type="time" data-rwp="${k}" data-kind="time" value="${esc(p[k] || "")}" ${dis}>`;
    const bool = (k) => `<label class="switch"><input type="checkbox" data-rwp="${k}" data-kind="bool" ${p[k] ? "checked" : ""} ${dis}><span></span></label>`;
    const feat = (f) => `<label class="switch"><input type="checkbox" data-action="rwp-feat" data-v="${f}" ${(p.features || []).includes(f) ? "checked" : ""} ${dis}><span></span></label>`;
    const text = (k) => `<input type="text" data-rwp="${k}" data-kind="text" value="${esc(p[k] || "")}" maxlength="60" ${dis}>`;
    const ent = (k, test, none = "keiner") => {
      const ids = Object.keys(S).filter((id) => test(id, S[id].attributes || {}) || id === p[k]).sort((a, b) => this._entityName(a).localeCompare(this._entityName(b), "de"));
      return `<select class="rwsel" data-rwp="${k}" data-kind="entity" ${dis}><option value="">${none}</option>${ids.map((id) => `<option value="${esc(id)}" ${p[k] === id ? "selected" : ""}>${esc(this._entityName(id))}</option>`).join("")}</select>`;
    };
    const dc = (cls, ...dom) => (id, a) => dom.some((x) => id.startsWith(`${x}.`)) && (!cls || a.device_class === cls || id.includes(cls));
    const bin = (id) => /^(binary_sensor|input_boolean|switch)\./.test(id);
    const chips = (k, opts) => `<div class="chips rwchips">${opts.map(([v, l, i]) => `<button class="chip ${(p[k] || []).includes(v) ? "on" : ""}" data-action="rwp-tog" data-k="${k}" data-v="${v}" ${dis}>${i ? `<ha-icon icon="${i}"></ha-icon>` : ""}${l}</button>`).join("")}</div>`;
    const choice = (k, opts, action = "rwp-set") => `<div class="segs small">${opts.map(([v, l, i]) => `<button class="seg ${String(k === "_mode" ? this._rwMode(p) : p[k] ?? "") === String(v) ? "on" : ""}" data-action="${action}" data-k="${k}" data-v="${v}" ${dis}>${i ? `<ha-icon icon="${i}"></ha-icon>` : ""}${l}</button>`).join("")}</div>`;
    const checks = (k, opts) => `<div class="rwchecks">${opts.map(([v, l]) => { const on = (p[k] || []).includes(v); return `<button class="rwck ${on ? "on" : ""}" data-action="rwp-tog" data-k="${k}" data-v="${v}" ${dis}><ha-icon icon="${on ? "mdi:checkbox-marked" : "mdi:checkbox-blank-outline"}"></ha-icon><span>${l}</span></button>`; }).join("")}</div>`;
    const lbl = (t) => `<div class="lbl">${t}</div>`;
    const note = (t, icon = "mdi:information-outline") => `<p class="muted small"><ha-icon icon="${icon}"></ha-icon>${t}</p>`;
    const exBox = (html) => (ex ? `<div class="rwex"><div class="rwex-h"><ha-icon icon="mdi:school-outline"></ha-icon>Experte</div>${html}</div>` : "");
    const has = (f) => (p.features || []).includes(f);
    const meta = RW_SECTIONS.find(([x]) => x === sec) || RW_SECTIONS[0];
    const users = Object.entries(this._data.rollwerk?.covers || {}).filter(([, c]) => (c.profile || "standard") === (d.pid || "")).map(([id]) => this._entityName(id));
    let body = "";
    switch (sec) {
      case "tag": {
        const mode = this._rwMode(p);
        const win = (a, b) => (mode === "time" ? row(a, "Uhrzeit", "", time(a)) : `${row(a, "Frühestens", "", time(a))}${row(b, "Spätestens", "", time(b))}`);
        body = `${!d.pid ? `<label class="field"><span><ha-icon icon="mdi:form-textbox"></ha-icon> Name</span>${text("name")}</label>` : ""}
          ${lbl("Wonach?")}${choice("_mode", [["time", "Uhrzeit", "mdi:clock-outline"], ["sun", "Mit der Sonne", "mdi:weather-sunset"], ...(ex || mode === "cal" ? [["cal", "Kalender", "mdi:calendar"]] : []), ...(ex || mode === "free" ? [["free", "Nur Sonne", "mdi:white-balance-sunny"]] : [])], "rwp-mode")}
          ${mode === "sun" ? note("Öffnet frühestens zur ersten Zeit, sobald die Sonne hoch genug steht – spätestens zur zweiten. Abends genauso andersherum.", "mdi:weather-sunset") : ""}
          <div class="wxrows">${row("up", "Morgens öffnen", "", feat("up"))}</div>
          ${has("up") && mode !== "cal" && mode !== "free" ? `${lbl("Öffnen · Werktag")}<div class="wxrows">${win("up_early", "up_late")}</div>${lbl("Öffnen · Wochenende & Feiertag")}<div class="wxrows">${win("up_early_we", "up_late_we")}</div>` : ""}
          <div class="wxrows">${row("down", "Abends schließen", "", feat("down"))}</div>
          ${has("down") && mode !== "cal" && mode !== "free" ? `${lbl("Schließen · vor Werktag")}<div class="wxrows">${win("down_early", "down_late")}</div>${lbl("Schließen · vor freiem Tag")}<div class="wxrows">${win("down_early_we", "down_late_we")}</div>` : ""}
          ${mode === "sun" || mode === "free" ? `${lbl("Sonnenhöhe")}<div class="wxrows">
            ${row("su", "Öffnen ab", "0° = Sonnenaufgang", num("sun_up", 0, -20, 60, 0.5, "°"), "Negativ = in der Dämmerung, z. B. −4°. Positiv = erst wenn die Sonne über Nachbarhäusern steht.")}
            ${row("sd", "Schließen ab", "0° = Sonnenuntergang", num("sun_down", 0, -20, 60, 0.5, "°"))}</div>` : ""}
          ${mode === "cal" ? `<label class="field"><span><ha-icon icon="mdi:calendar"></ha-icon> Kalender</span>${ent("calendar", (id) => id.startsWith("calendar."), "–")}</label>
            <div class="wxrows">${row("co", "Termin fürs Öffnen", "Titel enthält", text("cal_open"), "Beginn = früheste, Ende = späteste Zeit.")}${row("cc", "Termin fürs Schließen", "Titel enthält", text("cal_close"))}</div>` : ""}
          ${note("Feiertage und Sonnenstand kommen aus Hauswerk › Einstellungen (Anwesenheit bzw. Wetter).", "mdi:home-cog-outline")}
          ${exBox(`${lbl("Helligkeit")}<div class="wxrows">${row("bf", "Helligkeit nutzen", "", feat("brightness"))}</div>
            ${has("brightness") ? `<label class="field"><span><ha-icon icon="mdi:brightness-5"></ha-icon> Helligkeitssensor</span>${ent("brightness_sensor", dc("illuminance", "sensor"))}</label>
            <div class="wxrows">${row("bu", "Öffnen ab", "", num("brightness_up", 0, 0, 200000, 10, "lx"))}${row("bd", "Schließen bis", "", num("brightness_down", 0, 0, 200000, 10, "lx"))}
              ${row("bh", "Spielraum", "", num("brightness_hyst", 0, 0, 10000, 10, "lx"))}${row("bt", "Mindestens so lange", "", num("brightness_duration", 30, 0, 3600, 5, "s"))}</div>` : ""}
            <div class="wxrows">${row("st", "Sonne mindestens so lange", "", num("sun_duration", 30, 0, 3600, 5, "s"))}</div>
            ${lbl("Sonne und Helligkeit verknüpfen")}${choice("bs_operator", [["or", "Eins reicht"], ["and", "Beide nötig"]])}
            <label class="field"><span><ha-icon icon="mdi:calendar-arrow-right"></ha-icon> Sensor „Arbeitstag morgen“ (fürs Schließen)</span>${ent("workday_tomorrow", (id) => id.startsWith("binary_sensor.") && /workday|arbeitstag/.test(id))}</label>`)}`;
        break;
      }
      case "shade": {
        const live = Object.entries(st.covers || {}).filter(([, c]) => c.profile === d.pid && c.shade_start);
        const sym = (v) => (v == null ? "–" : v ? "✓" : "✗");
        body = `<div class="wxrows">${row("sf", "Sonnenschutz", "tagsüber gegen Hitze und Blendung", feat("shading"))}</div>
          ${has("shading") ? `${lbl("Wohin zeigt das Fenster?")}${this._rwCompass(p)}
          ${(() => {
            const tok = (k, def, step, min, max, unit) => `<span class="tok"><button class="tok-b" data-action="rwp-step" data-k="${k}" data-d="${-step}" data-def="${def}" data-min="${min}" data-max="${max}" ${dis} aria-label="weniger">−</button><b>${fmt(p[k] ?? def, step < 1 ? 1 : 0)}${unit}</b><button class="tok-b" data-action="rwp-step" data-k="${k}" data-d="${step}" data-def="${def}" data-min="${min}" data-max="${max}" ${dis} aria-label="mehr">+</button></span>`;
            const dir = p.window_dir != null ? `<span class="tok txt">${this._rwDirName(p.window_dir)}</span>` : `<span class="tok txt warn">Richtung?</span>`;
            return `<div class="rwsent"><ha-icon icon="mdi:sun-thermometer-outline"></ha-icon><p>Beschatten, wenn die Sonne aufs Fenster nach ${dir} scheint, mindestens ${tok("elevation_min", 25, 5, 0, 80, "°")} hoch steht und es draußen wärmer als ${tok("temp2_min", 18, 1, 5, 40, " °C")} ist. Der Rollladen fährt dann auf ${tok("pos_shading", 25, 5, 0, 100, " %")} – und wieder hoch, sobald eins davon nicht mehr stimmt.</p></div>`;
          })()}
          ${note("Außentemperatur aus Hauswerk › Wetter. Wartezeit 5 Minuten, damit kurze Sonne nichts auslöst.", "mdi:home-cog-outline")}
          ${live.length ? `${lbl("Jetzt")}<div class="evlist">${live.map(([id, c]) => `<div class="ev ${c.shading ? "live" : ""}"><ha-icon icon="${c.shading ? "mdi:sun-thermometer-outline" : "mdi:window-shutter"}"></ha-icon><span class="grow"><b>${esc(this._entityName(id))}</b><small>${RW_SHADE_CONDS.filter(([k]) => c.shade_start[k] != null).map(([k, l]) => `${l} ${sym(c.shade_start[k])}`).join(" · ")}</small></span>${c.shading ? `<em class="badge">AKTIV</em>` : ""}</div>`).join("")}</div>` : ""}
          ${exBox(`${lbl("Beschattung beginnt, wenn …")}<small class="muted">alle davon</small>${chips("shade_start_and", RW_SHADE_CONDS)}<small class="muted">eins davon</small>${chips("shade_start_or", RW_SHADE_CONDS)}
            ${lbl("Beschattung endet, wenn …")}<small class="muted">alle davon</small>${chips("shade_end_and", RW_SHADE_CONDS)}<small class="muted">eins davon</small>${chips("shade_end_or", RW_SHADE_CONDS)}
            ${note("Nicht messbare Bedingungen (kein Sensor) zählen nicht mit.")}
            <div class="wxrows">${row("az1", "Richtung von", "", num("azimuth_start", 95, 0, 360, 1, "°"))}${row("az2", "Richtung bis", "", num("azimuth_end", 265, 0, 360, 1, "°"))}
              ${row("el1", "Sonnenhöhe mindestens", "", num("elevation_min", 25, 0, 90, 1, "°"), "Tief stehende Sonne wird oft von Nachbarhäusern oder Bäumen verdeckt.")}${row("el2", "Sonnenhöhe höchstens", "", num("elevation_max", 90, 0, 90, 1, "°"))}
              ${row("t2h", "Spielraum außen", "", num("temp2_hyst", 0.2, 0, 5, 0.1, "°C"))}</div>
            <label class="field"><span><ha-icon icon="mdi:thermometer"></ha-icon> Eigener Außensensor (leer = Hauswerk › Wetter)</span>${ent("temp2_sensor", dc("temperature", "sensor"), "aus Hauswerk › Wetter")}</label>
            <label class="field"><span><ha-icon icon="mdi:home-thermometer-outline"></ha-icon> Temperatur innen</span>${ent("temp1_sensor", dc("temperature", "sensor"))}</label>
            <div class="wxrows">${row("t1", "Innen ab", "", num("temp1_min", 18, 0, 40, 0.5, "°C"))}${row("t1h", "Spielraum innen", "", num("temp1_hyst", 0.2, 0, 5, 0.1, "°C"))}</div>
            <label class="field"><span><ha-icon icon="mdi:brightness-5"></ha-icon> Helligkeitssensor</span>${ent("shade_brightness_sensor", dc("illuminance", "sensor"))}</label>
            <div class="wxrows">${row("sb1", "Beginnt ab", "", num("shade_bright_start", 35000, 0, 200000, 100, "lx"))}${row("sb2", "Endet unter", "", num("shade_bright_end", 25000, 0, 200000, 100, "lx"))}
              ${row("fc", "Vorhersage-Höchstwert ab", "aus Hauswerk › Wetter", num("forecast_temp", "", -10, 45, 0.5, "°C"))}</div>
            <small class="muted">Wetterlage</small>${chips("weather_conditions", RW_WEATHER)}
            <label class="field"><span><ha-icon icon="mdi:toggle-switch-outline"></ha-icon> Eigene Bedingung (an = erfüllt)</span>${ent("shade_custom", bin)}</label>
            <div class="wxrows">${row("w1", "Warten vor Beginn", "", num("shade_wait_start", 300, 0, 7200, 30, "s"))}${row("w2", "Warten vor Ende", "", num("shade_wait_end", 300, 0, 7200, 30, "s"))}
              ${row("w3", "Sofort enden", "wenn die Sonne das Fenster verlässt", bool("shade_end_immediate"))}
              ${row("pa", "Andere Stellung", "wenn der Schalter an ist", num("pos_shading_alt", "", 0, 100, 1, "%"))}</div>
            <label class="field"><span><ha-icon icon="mdi:toggle-switch-outline"></ha-icon> Schalter für andere Stellung</span>${ent("shading_alt_entity", bin)}</label>`)}` : ""}`;
        break;
      }
      case "vent": {
        const mine = Object.entries(this._data.rollwerk?.covers || {}).filter(([, c]) => (c.profile || "standard") === (d.pid || ""));
        body = `${lbl("Tür ganz offen")}${choice("pos_lockout", [["", "Nicht herunterfahren"], ["30", "Höchstens 30 %"], ["50", "Höchstens 50 %"]], "rwp-lock")}
          ${note("So sperrt dich die Terrassentür nicht aus. Hochfahren geht immer.", "mdi:door-open")}
          <div class="wxrows">${row("vf", "Fenster gekippt: lüften", "Rollladen auf Lüftungsstellung", feat("ventilate"))}${has("ventilate") ? row("pv", "Lüftungsstellung", "", num("pos_ventilate", 30, 0, 100, 5, "%")) : ""}</div>
          ${lbl("Kontakte")}${mine.length ? `<div class="evlist">${mine.map(([id, c]) => `<div class="ev"><ha-icon icon="mdi:window-shutter"></ha-icon><span class="grow"><b>${esc(this._entityName(id))}</b><small>${[c.contact_open ? `offen: ${esc(this._entityName(c.contact_open))}` : "", c.contact_tilted ? `gekippt: ${esc(this._entityName(c.contact_tilted))}` : ""].filter(Boolean).join(" · ") || "kein Kontakt"}</small></span><button class="link" data-action="pop-open" data-pop="rwc:${esc(id)}">ändern</button></div>`).join("")}</div>` : note("Noch kein Rollladen nutzt dieses Verhalten.")}
          ${exBox(`${lbl("Lüften")}${checks("vent_options", RW_VENT)}${lbl("Aussperrschutz auch bei gekipptem Fenster")}${checks("lockout_tilted", RW_LOCK_TILTED)}`)}`;
        break;
      }
      case "exc": {
        const manual = !(p.manual_block || []).length ? "next" : (p.manual_reset || []).includes("timeout") ? "hours" : "night";
        body = `${lbl("Wenn niemand zu Hause ist")}${choice("away_mode", [["normal", "Wie immer"], ["closed", "Tagsüber zu"], ["shade", "Beschattet"]])}
          <div class="rq-facts"><span style="--c:${st.away ? "#94a3b8" : "#22c55e"}"><ha-icon icon="${st.away ? "mdi:home-export-outline" : "mdi:home-account"}"></ha-icon>${st.away ? "Gerade niemand zu Hause" : "Jemand ist zu Hause"}</span>${st.vacation ? `<span style="--c:#34d399"><ha-icon icon="mdi:palm-tree"></ha-icon>Urlaub</span>` : ""}</div>
          <div class="wxrows">${row("vr", "Urlaub: Zeiten verschieben", "zufällig bis zu", num("vacation_random", 0, 0, 60, 5, "Min."), "Im Urlaub öffnet und schließt jeder Rollladen jeden Tag etwas anders – das Haus wirkt bewohnt.")}</div>
          ${note(`Wer zu Hause ist und wann Urlaub ist, stellst du einmal für alle Module ein: <button class="link inline" data-action="settings-go" data-sub="presence">Anwesenheit</button> · <button class="link inline" data-action="settings-go" data-sub="vacation">Urlaub</button>.`, "mdi:home-cog-outline")}
          ${lbl("Von Hand verstellt – Stellung bleibt …")}<div class="segs small">${[["next", "bis zum nächsten Wechsel"], ["night", "bis Mitternacht"], ["hours", "einige Stunden"]].map(([v, l]) => `<button class="seg ${manual === v ? "on" : ""}" data-action="rwp-man" data-v="${v}" ${dis}>${l}</button>`).join("")}</div>
          ${manual === "hours" ? `<div class="wxrows">${row("ro", "Wie lange", "", num("reset_timeout", 120, 5, 1440, 5, "Min."))}</div>` : ""}
          ${lbl("Schlafzimmer")}<label class="field"><span><ha-icon icon="mdi:bed-outline"></ha-icon> Schlaf-Schalter (an = schläft)</span>${ent("resident_sensor", bin)}</label>
          ${p.resident_sensor ? checks("resident_config", RW_RESIDENT) : note("Solange der Schalter an ist, öffnet der Rollladen morgens nicht – z. B. der Schlafmodus vom Handy.", "mdi:sleep")}
          ${exBox(`${lbl("Hand-Stellung bleibt bei …")}${checks("manual_block", RW_MANUAL)}${lbl("Zurücksetzen")}${checks("manual_reset", RW_RESET)}
            <div class="wxrows">${(p.manual_reset || []).includes("fixed") ? row("rt", "Uhrzeit", "", time("reset_time")) : ""}${(p.manual_reset || []).includes("in_position") ? row("rp", "In Stellung", "", num("reset_position", 100, 0, 100, 1, "%")) : ""}
              ${row("rr", "Danach gleich fahren", "auf die aktuelle Sollstellung", bool("manual_recover"))}</div>
            ${lbl("Erzwingen per Schalter")}${RW_FORCE.map(([k, l, i]) => `<label class="field"><span><ha-icon icon="${i}"></ha-icon> ${l}</span>${ent(k, bin)}</label>`).join("")}`)}`;
        break;
      }
      case "fine":
        body = `<label class="field"><span><ha-icon icon="mdi:form-textbox"></ha-icon> Name</span>${text("name")}</label>
          <div class="wxrows">${row("po", "Offen", "100 % = ganz offen", num("pos_open", 100, 0, 100, 1, "%"))}${row("pc", "Geschlossen", "z. B. 10 % für Lüftungsschlitze", num("pos_close", 0, 0, 100, 1, "%"))}</div>
          ${exBox(`<div class="wxrows">${row("pt", "Toleranz", "", num("tolerance", 0, 0, 20, 1, "%"))}${row("pd", "Fahrzeit", "einmal ganz auf oder zu", num("drive_time", 90, 5, 300, 5, "s"))}
            ${row("df", "Verzögerung fest", "", num("delay_fix", 0, 0, 600, 1, "s"))}${row("dr", "Verzögerung zufällig bis", "", num("delay_random", 5, 0, 600, 1, "s"), "Verteilt die Fahrten, damit nicht alle Rollläden gleichzeitig funken.")}</div>
            ${lbl("Verhalten im Detail")}${checks("behavior", RW_BEHAVIOR)}`)}
          ${d.pid ? note(users.length ? `Genutzt von: ${users.map(esc).join(", ")}` : "Noch kein Rollladen nutzt dieses Verhalten – zuordnen im Rollladen.", "mdi:window-shutter") : ""}
          ${this._admin && d.pid && d.pid !== "standard" ? `<button class="secondary danger small" data-action="rwp-del"><ha-icon icon="mdi:delete-outline"></ha-icon>${d.confirm ? "Wirklich löschen? Rollläden nutzen dann „Standard“" : "Verhalten löschen"}</button>` : ""}`;
        break;
    }
    const tl = d.pid ? st.timelines?.[d.pid] : null;
    const isNew = !d.pid;
    return {
      icon: meta[2], c: meta[3], title: isNew ? "Neues Verhalten" : esc(p.name || ""), sub: `Verhalten · ${meta[1]}`,
      body: `<div class="rwtop">${tl ? `<div class="grow">${this._rwDayBar(tl)}</div>` : `<span class="grow muted small">${isNew ? "Tagesleiste nach dem Anlegen" : ""}</span>`}
          <button class="rwexp ${ex ? "on" : ""}" data-action="rw-expert" title="Alle Einstellungen wie bei der Cover Control Automation"><ha-icon icon="mdi:school-outline"></ha-icon>Experte</button></div>
        <div class="rwsecs">${RW_SECTIONS.map(([x, t, i, c, f]) => `<button class="rwsec ${x === sec ? "on" : ""} ${f && !(p.features || []).includes(f) ? "off" : ""}" data-action="rwp-sec" data-sec="${x}" style="--c:${c}"><ha-icon icon="${i}"></ha-icon>${t}</button>`).join("")}</div>${body}`,
      foot: `<button class="secondary" data-action="pop-close">${this._admin ? "Abbrechen" : "Schließen"}</button>
        ${this._admin ? `<button class="primary" data-action="rwp-save"><ha-icon icon="mdi:content-save-outline"></ha-icon>${isNew ? "Anlegen" : "Speichern"}</button>` : ""}`,
    };
  }

  // ------------------------------------------------------------ Assistent „Rollladen hinzufügen“
  _cwizDraft() {
    return { step: 0, covers: [], contacts: {}, use: "wohnen", shade: true, temp: 24, mode: "sun", pick: null,
      prof: { window_dir: null, azimuth_start: 95, azimuth_end: 265 } };
  }

  _cwizOpen() {
    this._openPop("cwiz", this._cwizDraft());
  }

  /** Fenster- und Türkontakte im Bereich eines Rollladens: offen (Tür/Fenster) und gekippt (Name mit „kipp“/„tilt“). */
  _cwizContacts(coverId) {
    const S = this._hass.states;
    const area = this._hass.entities?.[coverId]?.area_id || this._hass.devices?.[this._hass.entities?.[coverId]?.device_id]?.area_id;
    const ids = area ? this._areaEntities(area) : [];
    const contacts = ids.filter((id) => id.startsWith("binary_sensor.") && ["door", "window", "opening", "garage_door"].includes(S[id]?.attributes?.device_class));
    const tilted = contacts.find((id) => /kipp|tilt/.test(`${id} ${S[id]?.attributes?.friendly_name || ""}`.toLowerCase()));
    const open = contacts.find((id) => id !== tilted && S[id]?.attributes?.device_class === "door") || contacts.find((id) => id !== tilted);
    return { all: contacts, open: open || null, tilted: tilted || null };
  }

  /** Passt ein vorhandenes Verhalten? Gleiche Richtung, gleiche Art (Schlafzimmer), gleicher Sonnenschutz. */
  _cwizMatch(d) {
    const sleep = d.use === "schlafen";
    return this._rwProfiles().find((p) => Number(p.window_dir) === Number(d.prof.window_dir) && !!p.resident_sensor === false
      && (p.features || []).includes("shading") === d.shade && (sleep ? /schlaf/i.test(p.name) : !/schlaf/i.test(p.name))) || null;
  }

  _cwizPop() {
    const d = this._pop.draft;
    const S = this._hass.states;
    const steps = ["Rollladen", "Richtung", "Fenster", "Raum", "Verhalten", "Fertig"];
    const name = (id) => esc(this._entityName(id));
    const bar = `<div class="wiz-bar">${steps.map((s, i) => `<button class="wiz-dot ${i === d.step ? "on" : i < d.step ? "done" : ""}" data-action="cwiz-go" data-i="${i}" ${i > d.step && !this._cwizOk(i - 1) ? "disabled" : ""}><i>${i < d.step ? "✓" : i + 1}</i><span>${s}</span></button>`).join("")}</div>`;
    const tick = (on, radio = false) => `<ha-icon icon="${radio ? (on ? "mdi:radiobox-marked" : "mdi:radiobox-blank") : on ? "mdi:checkbox-marked" : "mdi:checkbox-blank-outline"}"></ha-icon>`;
    let body = "";
    switch (d.step) {
      case 0: {
        const have = new Set(this._data.settings.rw_covers || []);
        const all = Object.keys(S).filter((id) => id.startsWith("cover.") && !have.has(id) && !(S[id].attributes?.entity_id || []).length);
        const groups = new Map();
        for (const id of all) {
          const a = this._areaOf(id) || "Ohne Bereich";
          if (!groups.has(a)) groups.set(a, []);
          groups.get(a).push(id);
        }
        body = `<p class="muted">Welche Rollläden sollen dazukommen? Mehrere gleichzeitig gehen auch – z. B. alle Fenster einer Seite, sie bekommen dann dasselbe Verhalten.</p>
          ${all.length ? [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0], "de")).map(([a, ids]) => `<div class="lbl">${esc(a)}</div>${ids.map((id) => `<button class="wiz-dev ${d.covers.includes(id) ? "on" : ""}" data-action="cwiz-cover" data-id="${esc(id)}">${tick(d.covers.includes(id))}<span class="grow"><b>${name(id)}</b><small>${esc(this._fmtState(S[id]))}${S[id].attributes?.current_position != null ? ` · ${S[id].attributes.current_position} %` : ""}</small></span></button>`).join("")}`).join("")
            : `<p class="note"><ha-icon icon="mdi:check-all"></ha-icon>Alle Rollläden sind schon in Rollwerk.</p>`}`;
        break;
      }
      case 1:
        body = `<p class="muted">Wohin zeigt das Fenster${d.covers.length > 1 ? " (bei allen gewählten)" : ""}? Danach richtet sich der Sonnenschutz.</p>${this._rwCompass(d.prof)}
          <button class="wiz-dev ${d.prof.window_dir == null ? "on" : ""}" data-action="cwiz-nodir">${tick(d.prof.window_dir == null, true)}<span class="grow"><b>Weiß nicht / egal</b><small>ohne Sonnenschutz nach Richtung</small></span></button>`;
        break;
      case 2:
        body = `<p class="muted">Gibt es einen Kontakt am Fenster oder an der Tür? Dann sperrt dich der Rollladen nicht aus und lüftet bei gekipptem Fenster.</p>
          ${d.covers.map((cid) => {
            const f = this._cwizContacts(cid);
            const c = d.contacts[cid] || {};
            const opts = [...new Set([...f.all, c.open, c.tilted].filter(Boolean))];
            const sel = (k) => `<select data-cwiz="${esc(cid)}" data-k="${k}"><option value="">keiner</option>${Object.keys(S).filter((id) => id.startsWith("binary_sensor.") && (["door", "window", "opening"].includes(S[id].attributes?.device_class) || opts.includes(id))).sort((a, b) => (opts.includes(b) - opts.includes(a)) || this._entityName(a).localeCompare(this._entityName(b), "de")).map((id) => `<option value="${esc(id)}" ${c[k] === id ? "selected" : ""}>${name(id)}${this._areaOf(id) ? ` (${esc(this._areaOf(id))})` : ""}</option>`).join("")}</select>`;
            return `<div class="cwiz-c"><b><ha-icon icon="mdi:window-shutter"></ha-icon>${name(cid)}</b>
              <label class="field"><span><ha-icon icon="mdi:door-open"></ha-icon> ganz offen (Tür/Fenster)</span>${sel("open")}</label>
              <label class="field"><span><ha-icon icon="mdi:window-open-variant"></ha-icon> gekippt</span>${sel("tilted")}</label>
              ${f.all.length ? `<small class="muted">${f.all.length} Kontakt${f.all.length > 1 ? "e" : ""} im selben Bereich gefunden${c.open || c.tilted ? " und vorausgewählt" : ""}.</small>` : ""}</div>`;
          }).join("")}`;
        break;
      case 3: {
        const uses = [["wohnen", "Wohnraum", "mdi:sofa-outline", "morgens auf, abends zu"], ["schlafen", "Schlafzimmer", "mdi:bed-outline", "später auf, früher zu, bleibt beim Ausschlafen zu"],
          ["kind", "Kinderzimmer", "mdi:teddy-bear", "früher zu"], ["neben", "Nebenraum", "mdi:door", "nur Sonnen- und Sturmschutz"]];
        body = `<p class="muted">Was für ein Raum ist das?</p>
          ${uses.map(([v, t, i, s]) => `<button class="wiz-type ${d.use === v ? "on" : ""}" data-action="cwiz-use" data-v="${v}"><ha-icon icon="${i}"></ha-icon><span><b>${t}</b><small>${s}</small></span></button>`).join("")}
          <div class="lbl">Öffnen und schließen</div>
          <div class="segs small">${[["sun", "Mit der Sonne", "mdi:weather-sunset"], ["time", "Nach Uhrzeit", "mdi:clock-outline"]].map(([v, l, i]) => `<button class="seg ${d.mode === v ? "on" : ""}" data-action="cwiz-mode" data-v="${v}"><ha-icon icon="${i}"></ha-icon>${l}</button>`).join("")}</div>
          <div class="wxrows"><div class="wxr"><div class="wxr-l"><b>Sonnenschutz</b><small>${d.prof.window_dir == null ? "braucht die Richtung aus Schritt 2" : `bei Sonne aus ${this._rwDirName(d.prof.window_dir)}`}</small></div>
            <div class="wxr-v"><label class="switch"><input type="checkbox" data-action="cwiz-shade" ${d.shade && d.prof.window_dir != null ? "checked" : ""} ${d.prof.window_dir == null ? "disabled" : ""}><span></span></label></div></div>
          ${d.shade && d.prof.window_dir != null ? `<div class="wxr"><div class="wxr-l"><b>Ab Außentemperatur</b></div><div class="wxr-v"><div class="wiz-temp"><button class="sbtn" data-action="cwiz-t" data-d="-1">−</button><b>${fmt(d.temp, 0)} °C</b><button class="sbtn" data-action="cwiz-t" data-d="1">+</button></div></div></div>` : ""}</div>`;
        break;
      }
      case 4: {
        const match = this._cwizMatch(d);
        if (d.pick == null) d.pick = match ? match.id : "new";
        const opt = (v, t, s) => `<button class="wiz-dev ${d.pick === v ? "on" : ""}" data-action="cwiz-pick" data-v="${esc(v)}">${tick(d.pick === v, true)}<span class="grow"><b>${t}</b><small>${s}</small></span></button>`;
        body = `<p class="muted">Rollläden mit gleichem Verhalten lassen sich später gemeinsam ändern.</p>
          ${opt("new", `Neues Verhalten „${esc(this._cwizName(d))}“`, "aus deinen Antworten")}
          ${this._rwProfiles().map((p) => opt(p.id, `„${esc(p.name)}“${match?.id === p.id ? " – passt" : ""}`, esc(this._rwProfSum(p)))).join("")}`;
        break;
      }
      case 5: {
        const line = (icon, t, v) => `<div class="kv"><ha-icon icon="${icon}"></ha-icon><span>${t}</span><b>${v}</b></div>`;
        const cs = d.covers.filter((c) => d.contacts[c]?.open || d.contacts[c]?.tilted).length;
        body = `<div class="wiz-sum">
            ${line("mdi:window-shutter", "Rollläden", d.covers.map(name).join(", "))}
            ${line("mdi:compass-outline", "Fenster zeigt nach", d.prof.window_dir == null ? "–" : this._rwDirName(d.prof.window_dir))}
            ${line("mdi:door-open", "Mit Kontakt", `${cs} von ${d.covers.length}`)}
            ${line("mdi:tune-variant", "Verhalten", d.pick === "new" ? `neu: „${esc(this._cwizName(d))}“` : `„${esc(this._rwProfName(d.pick))}“`)}
            ${d.pick === "new" ? line("mdi:sun-thermometer-outline", "Sonnenschutz", d.shade && d.prof.window_dir != null ? `ab ${fmt(d.temp, 0)} °C außen` : "aus") : ""}
          </div>${note2("Rollwerk fährt erst beim nächsten Wechsel (z. B. abends schließen) – nicht sofort nach dem Anlegen.")}`;
        break;
      }
    }
    function note2(t) { return `<p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>${t}</p>`; }
    const last = d.step === steps.length - 1;
    return {
      icon: "mdi:auto-fix", c: "#0ea5e9", title: "Rollladen hinzufügen", sub: `Schritt ${d.step + 1} von ${steps.length} · ${steps[d.step]}`,
      body: bar + body,
      foot: `${d.step ? `<button class="secondary" data-action="cwiz-go" data-i="${d.step - 1}"><ha-icon icon="mdi:chevron-left"></ha-icon>Zurück</button>` : `<button class="secondary" data-action="pop-close">Abbrechen</button>`}
        ${last ? `<button class="primary" data-action="cwiz-save"><ha-icon icon="mdi:check"></ha-icon>Hinzufügen</button>`
          : `<button class="primary" data-action="cwiz-go" data-i="${d.step + 1}" ${this._cwizOk(d.step) ? "" : "disabled"}>Weiter<ha-icon icon="mdi:chevron-right"></ha-icon></button>`}`,
    };
  }

  _cwizOk(step) {
    const d = this._pop?.draft || {};
    return step === 0 ? d.covers?.length > 0 : true;
  }

  _cwizName(d) {
    const dir = d.prof.window_dir != null ? this._rwDirName(d.prof.window_dir) : "";
    const use = { schlafen: "Schlafzimmer", kind: "Kinderzimmer", neben: "Nebenraum" }[d.use] || "";
    return [use, dir].filter(Boolean).join(" ") || "Wohnraum";
  }

  /** Neues Verhalten aus den Antworten: Kopie von „Standard“, angepasst an Raum, Richtung und Sonnenschutz. */
  _cwizProfile(d) {
    const base = clone(this._data.rollwerk?.profiles?.standard || {});
    const f = new Set(["up", "down", "time"]);
    if (d.mode === "sun") f.add("sun");
    if (d.use === "neben") { f.delete("up"); f.delete("down"); }
    const shade = d.shade && d.prof.window_dir != null;
    if (shade) f.add("shading"); else f.delete("shading");
    const p = { ...base, name: this._cwizName(d), features: [...f], time_mode: "times" };
    if (d.prof.window_dir != null) Object.assign(p, { window_dir: d.prof.window_dir, azimuth_start: d.prof.azimuth_start, azimuth_end: d.prof.azimuth_end });
    if (shade) p.temp2_min = d.temp;
    if (d.use === "schlafen") Object.assign(p, { up_early: "07:30", up_late: "08:30", up_early_we: "09:00", up_late_we: "10:00", down_early: "19:00", down_late: "21:30", down_early_we: "19:30", down_late_we: "22:30" });
    if (d.use === "kind") Object.assign(p, { down_early: "17:30", down_late: "20:00", down_early_we: "18:00", down_late_we: "20:30" });
    if (d.mode === "time") for (const [a, b] of [["up_early", "up_late"], ["up_early_we", "up_late_we"], ["down_early", "down_late"], ["down_early_we", "down_late_we"]]) p[b] = p[a];
    return p;
  }

  async _cwizSave() {
    const d = this._pop.draft;
    let pid = d.pick;
    if (pid === "new") {
      const res = await this._ws({ type: "hauswerk/rollwerk/profile/save", profile_id: null, profile: this._cwizProfile(d) });
      this._data.rollwerk.profiles = res.profiles;
      pid = res.profile_id;
    }
    const covers = [...new Set([...(this._data.settings.rw_covers || []), ...d.covers])];
    this._data.settings = await this._ws({ type: "hauswerk/heizen/settings/save", settings: { rw_covers: covers } });
    for (const cid of d.covers) {
      const c = d.contacts[cid] || {};
      const res = await this._ws({ type: "hauswerk/rollwerk/cover/save", entity_id: cid, cover: { profile: pid, contact_open: c.open || null, contact_tilted: c.tilted || null, auto: true, storm: true } });
      this._data.rollwerk.covers = res.covers;
    }
    const n = d.covers.length;
    this._closePop();
    this._renderMain();
    this._toast(n === 1 ? `${this._entityName(d.covers[0])} hinzugefügt` : `${n} Rollläden hinzugefügt`);
  }

  _rwcPop(entityId) {
    const d = this._pop.draft;
    if (!d.cfg) d.cfg = clone(this._data.rollwerk?.covers?.[entityId] || {});
    const c = d.cfg;
    const dis = this._admin ? "" : "disabled";
    const line = (label, sub, ctl) => `<div class="wxr"><div class="wxr-l"><b>${label}</b>${sub ? `<small>${sub}</small>` : ""}</div><div class="wxr-v">${ctl}</div></div>`;
    const tog = (k, def, label, sub) => line(label, sub, `<label class="switch"><input type="checkbox" data-rwc="${k}" ${(c[k] ?? def) ? "checked" : ""} ${dis}><span></span></label>`);
    const contacts = Object.keys(this._hass.states).filter((id) => /^(binary_sensor|input_boolean)\./.test(id) &&
      (["door", "window", "opening", "garage_door"].includes(this._hass.states[id].attributes?.device_class) || /t(ü|ue)r|door|fenster|window|kipp|tilt/.test(id)) || id === c.contact_open || id === c.contact_tilted)
      .sort((a, b) => this._entityName(a).localeCompare(this._entityName(b), "de"));
    const sel = (k) => `<select data-rwc="${k}" ${dis}><option value="">keiner</option>${contacts.map((id) => `<option value="${esc(id)}" ${c[k] === id ? "selected" : ""}>${esc(this._entityName(id))}</option>`).join("")}</select>`;
    const rs = this._rwStatus?.covers?.[entityId] || {};
    const pid = c.profile || "standard";
    const profiles = this._rwProfiles();
    return {
      icon: "mdi:window-shutter", c: "#0ea5e9", title: "Rollladen", sub: `${esc(this._entityName(entityId))}${rs.area ? ` · ${esc(rs.area)}` : ""}`,
      body: `
        <div class="wxrows">${tog("auto", true, "Automatik", "nach dem Verhalten fahren")}${tog("storm", true, "Sturmschutz", "bei Sturm hochfahren")}</div>
        <div class="field"><span><ha-icon icon="mdi:tune-variant"></ha-icon> Verhalten</span>
          <div class="segs small">${profiles.map((x) => `<button class="seg ${x.id === pid ? "on" : ""}" data-action="rwc-set" data-k="profile" data-v="${esc(x.id)}" ${dis}>${esc(x.name)}</button>`).join("")}</div></div>
        ${this._rwDayBar(this._rwStatus?.timelines?.[pid])}
        <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>${esc(this._rwProfSum({ id: pid, ...(this._data.rollwerk?.profiles?.[pid] || {}) }))} · <button class="link inline" data-action="pop-open" data-pop="rwp:${esc(pid)}:tag">Verhalten bearbeiten</button></p>
        <label class="field"><span><ha-icon icon="mdi:door-open"></ha-icon> Kontakt „ganz offen“ – Aussperrschutz</span>${sel("contact_open")}</label>
        <label class="field"><span><ha-icon icon="mdi:window-open-variant"></ha-icon> Kontakt „gekippt“ – Lüften</span>${sel("contact_tilted")}</label>
        <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Ganz offen: der Rollladen fährt nicht herunter, bis zu ist – so sperrt dich die Terrassentür nicht aus. Gekippt: Lüftungsstellung (Verhalten › Fenster & Lüften). Ein Kontakt mit mehreren Zuständen (offen/gekippt) kann bei beiden stehen.</p>
        ${rs.reason ? `<div class="rq-facts"><span style="--c:#0ea5e9"><ha-icon icon="mdi:robot-outline"></ha-icon>${esc(rs.reason)}${rs.target != null ? ` → ${rs.target} %` : ""}</span>${rs.up ? `<span><ha-icon icon="mdi:weather-sunset-up"></ha-icon>${rs.up.join("–")}</span>` : ""}${rs.down ? `<span><ha-icon icon="mdi:weather-sunset-down"></ha-icon>${rs.down.join("–")}</span>` : ""}</div>` : ""}`,
      foot: `<button class="secondary" data-action="pop-close">${this._admin ? "Abbrechen" : "Schließen"}</button>
        ${this._admin ? `<button class="primary" data-action="rwc-save" data-id="${esc(entityId)}"><ha-icon icon="mdi:content-save-outline"></ha-icon>Speichern</button>` : ""}`,
    };
  }

  // ------------------------------------------------------------ Bericht
  _viewReport() {
    const rooms = this._rooms();
    const days = this._reportDays;
    const rep = this._report(days);
    const pills = `<div class="pills">${[7, 14, 30]
      .map((d) => `<button class="pill ${d === days ? "on" : ""}" data-action="report-days" data-days="${d}">${d} Tage</button>`)
      .join("")}</div>`;
    if (!rooms.length) return `${pills}<section class="card empty"><ha-icon icon="mdi:chart-bar"></ha-icon><h2>Noch keine Räume</h2></section>`;
    if (!rep) return `${pills}<section class="card"><div class="chart-empty"><div class="spinner"></div></div></section>`;
    const tot = this._sumRange(rep, 0, days);
    const row = (r) => {
      const rows = rep[r.id] || [];
      const sum = (k) => rows.reduce((a, x) => a + (x[k] || 0), 0);
      const temps = rows.map((x) => x.avg_temp).filter((t) => t != null);
      const avg = temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : null;
      return `<tr>
        <td><span class="rdot" style="background:${this._roomColor(r.id)}"></span>${esc(r.name)}<small>${TYPES[r.type].label}</small></td>
        <td>${fmt(sum("heat_min") / 60)} h</td><td>${fmt(sum("comfort_min") / 60)} h</td>
        <td>${int(sum("pause_min"))} Min.</td><td>${int(sum("openings"))}×</td>
        <td style="color:${tint(tempColor(avg))}">${fmt(avg)} °C</td></tr>`;
    };
    return `
      ${pills}
      <div class="kpis">
        ${this._kpi("#2dd4bf", "mdi:fire", "Geheizt", fmt(tot.heat / 60), "h", `Ø ${fmt(tot.heat / 60 / days)} h am Tag`)}
        ${this._kpi("#60a5fa", "mdi:sofa-outline", "Komfortzeit", fmt(tot.comfort / 60), "h", "Summe aller Räume")}
        ${this._kpi("#a78bfa", "mdi:window-open-variant", "Fensterpause", int(tot.pause), "Min.", "Thermostat abgesenkt")}
        ${this._kpi("#f472b6", "mdi:window-maximize", "Fenster geöffnet", int(tot.open), "×", `in ${days} Tagen`)}
      </div>
      <section class="card">
        ${this._sectionHead("mdi:fire", `Heizdauer pro Tag · ${days} Tage`)}
        ${this._stackChart(rep, days, "heat_min")}
      </section>
      <section class="card">
        ${this._sectionHead("mdi:window-open-variant", `Fensterpause pro Tag · ${days} Tage`)}
        ${this._stackChart(rep, days, "pause_min")}
      </section>
      ${this._valveHeat(rooms, rep, days)}
      <section class="card">
        ${this._sectionHead("mdi:table", "Räume im Vergleich")}
        <div class="table-wrap"><table>
          <thead><tr><th>Raum</th><th>Geheizt</th><th>Komfort</th><th>Pause</th><th>Fenster</th><th>Ø Raum</th></tr></thead>
          <tbody>${rooms.map(row).join("")}</tbody>
        </table></div>
        <p class="muted small">Geheizt: Minuten, in denen ein Thermostat „heizt“ meldet (ohne diese Angabe: Raum unter Soll).</p>
      </section>`;
  }

  /** Ventilöffnung je Raum und Stunde (Ø über die gewählten Tage) als Wärmekarte. */
  _valveHeat(rooms, rep, days) {
    const rowsOf = (id) => rep[id] || [];
    const hourAvg = (id) => Array.from({ length: 24 }, (_, h) => {
      const vals = rowsOf(id).map((x) => (x.valve_hours || [])[h]).filter((v) => v != null);
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    });
    const withData = rooms.filter((r) => rowsOf(r.id).some((x) => x.valve_avg != null));
    if (!withData.length) return `<section class="card">${this._sectionHead("mdi:valve", "Ventilöffnung über den Tag")}<p class="muted small">Noch keine Werte – Hauswerk sammelt die Ventilöffnung ab jetzt minütlich (Thermostate, Ventil-Sensoren und Fußbodenheizung).</p></section>`;
    const color = (v) => v == null ? "var(--card2)" : `color-mix(in srgb, #f97316 ${Math.round(12 + v * 0.88)}%, var(--card2))`;
    const row = (r) => {
      const hs = hourAvg(r.id);
      const avgs = rowsOf(r.id).map((x) => x.valve_avg).filter((v) => v != null);
      const avg = avgs.length ? avgs.reduce((a, b) => a + b, 0) / avgs.length : null;
      return `<div class="vh-row"><span class="vh-name"><span class="rdot" style="background:${this._roomColor(r.id)}"></span>${esc(r.name)}<small>Ø ${avg != null ? `${fmt(avg, 0)} %` : "–"}</small></span>
        <div class="vh-cells">${hs.map((v, h) => `<i style="background:${color(v)}" title="${String(h).padStart(2, "0")}–${String(h + 1).padStart(2, "0")} Uhr: ${v == null ? "keine Werte" : `${fmt(v, 0)} %`}"></i>`).join("")}</div></div>`;
    };
    return `<section class="card">
      ${this._sectionHead("mdi:valve", `Ventilöffnung über den Tag · Ø ${days} Tage`)}
      <div class="vh">${withData.map(row).join("")}
        <div class="vh-row vh-axis"><span class="vh-name"></span><div class="vh-cells">${Array.from({ length: 24 }, (_, h) => `<b>${h % 6 === 0 ? h : ""}</b>`).join("")}</div></div>
      </div>
      <p class="muted small">Je dunkler, desto weiter offen. Räume, die schon vor Komfortbeginn lange voll offen sind, heizen zu spät vor; Räume mit wenig Öffnung brauchen kaum Wärme – dort lohnt eine niedrigere Komforttemperatur oder späteres Vorheizen.</p>
    </section>`;
  }

  // ------------------------------------------------------------ Einstellungen: eine flache Liste, Details im Pop-up
  _setHelpers(p) {
    const dis = this._admin ? "" : "disabled";
    return {
      dis,
      minutes: (key, def, min = 0, max = 240, step = 1, unit = "Min.") =>
        `<div class="unit"><input type="number" step="${step}" min="${min}" max="${max}" data-set="${key}" value="${p[key] ?? def}" ${dis}><i>${unit}</i></div>`,
      segs: (key, options, def) =>
        `<div class="segs small">${options
          .map(([v, l, icon]) => `<button class="seg ${String(p[key] || def) === String(v) ? "on" : ""}" data-action="set-seg" data-key="${key}" data-v="${v}" ${dis}>${icon ? `<ha-icon icon="${icon}"></ha-icon>` : ""}${l}</button>`)
          .join("")}</div>`,
      sw: (key) => `<label class="switch"><input type="checkbox" data-set="${key}" ${p[key] ? "checked" : ""} ${dis}><span></span></label>`,
      head: (icon, title) => `<div class="sub-h"><ha-icon icon="${icon}"></ha-icon>${title}</div>`,
    };
  }

  /** Anzeigename eines notify-Dienstes: mobile_app_pixel_8 → Pixel 8. */
  _notifyName(x) {
    const name = String(x).replace(/^mobile_app_/, "").replace(/_/g, " ");
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  _planList() {
    return Object.values(this._data.plans || {}).sort((a, b) => a.name.localeCompare(b.name, "de"));
  }

  /** Woher ein Raum seine Komfortzeiten bekommt, als Kurztext. */
  _planLabel(r) {
    if (r.schedule_entity) return `${r.schedule_entity.startsWith("calendar.") ? "Kalender" : "Zeitplan"} ${this._entityName(r.schedule_entity)}`;
    const plan = this._data.plans?.[r.plan_id];
    if (plan) return `Plan „${plan.name}“${plan.calendar ? " (Kalender)" : ""}`;
    return (r.schedule || []).length ? "eigener Plan" : "ohne Plan";
  }

  _leadFor(type, p = this._data.settings) {
    return type === "flaeche" ? p.lead_floor ?? 120 : p.lead_radiator ?? 15;
  }

  /** Einstellungen als Zeilen: scope "house" = Hauswerk (gilt für alle Module), "heat" = nur Heizwerk. */
  _settingRows(scope) {
    const p = this._data.settings;
    const s = this._status || {};
    const rooms = this._rooms();
    const plans = this._planList();
    const persons = (p.persons || []).length;
    const d = (iso) => new Date(iso).toLocaleDateString("de-DE", { day: "numeric", month: "short" });
    if (scope === "rw") return this._rwRows(p);
    if (scope === "house") {
      const vac = {
        off: "Nur von Hand",
        period: p.vacation_from && p.vacation_to ? `${d(p.vacation_from)} – ${d(p.vacation_to)}` : "Zeitraum – keiner eingetragen",
        calendar: p.vacation_calendar ? `Kalender ${this._entityName(p.vacation_calendar)}` : "Kalender – keiner gewählt",
      }[p.vacation_source || "period"];
      const n = this._widgets().length;
      return [
        { g: "Haus", id: "presence", icon: "mdi:home-account", c: "#34d399", title: "Anwesenheit",
          sum: persons ? `${persons} Person${persons > 1 ? "en" : ""} · abwesend nach ${p.away_delay} Min.${p.arrive_delay ? ` · zu Hause nach ${p.arrive_delay} Min.` : ""}${p.workday_entity ? " · Feiertage erkannt" : ""}` : "Noch keine Personen gewählt",
          warn: !persons, words: "personen abwesend heimweg nähe entfernung gäste feiertag arbeitstag workday wochenende" },
        { g: "Haus", id: "vacation", icon: "mdi:palm-tree", c: "#34d399", title: "Urlaub", sum: vac, on: s.vacation, words: "kalender zeitraum stichwort ferien reise" },
        { g: "Haus", id: "weather", icon: "mdi:weather-partly-cloudy", c: "#60a5fa", title: "Wetter",
          sum: `${p.weather_entity ? this._entityName(p.weather_entity) : "Wetter automatisch"}${p.outside_sensor ? ` · Außen: ${this._entityName(p.outside_sensor)}` : ""} · Kälte < ${fmt(p.cold_snap_temp ?? 0)} °C · Sturm ab ${fmt(p.storm_kmh ?? 70, 0)} km/h`,
          warn: this._wxAlerts().length > 0, words: "wetter außentemperatur sensor prognose sonne kälteeinbruch sturm frost heizgrenze" },
        { g: "Haus", id: "notify", icon: "mdi:cellphone-message", c: "#0ea5e9", title: "Benachrichtigungen",
          sum: (p.notify_targets || []).length || p.notify_ha
            ? `${[...(p.notify_targets || []).map((x) => this._notifyName(x)), ...(p.notify_ha ? ["Home Assistant"] : [])].join(", ")}${p.notify_quiet ? ` · Ruhezeit ${p.notify_quiet_from || "22:00"}–${p.notify_quiet_to || "07:00"}` : ""}`
            : "Noch keine App gewählt – Nachrichten nur im Protokoll",
          words: "handy app nachricht push benachrichtigung fenster batterie frost ruhezeit thermostat" },
        { g: "Darstellung", id: "look", icon: "mdi:palette-outline", c: "#a78bfa", title: "Darstellung",
          sum: `${{ auto: "Wie Home Assistant", light: "Hell", dark: "Dunkel" }[p.look_theme || "auto"]} · Akzent ${(ACCENTS.find(([v]) => v === (p.look_accent || null)) || [0, "eigene Farbe"])[1]} · Hintergrund ${{ pattern: "Muster", daytime: "Tageszeit", plain: "schlicht" }[p.look_background || "pattern"]}`,
          words: "design farbe akzent hell dunkel hintergrund tageszeit himmel uhr uhrzeit wetter kopfzeile größe tablet" },
        { g: "Darstellung", start: true, icon: "mdi:view-dashboard-edit-outline", c: "#2dd4bf", title: "Widgets der Startseite",
          sum: `${n} Widget${n === 1 ? "" : "s"} · für alle Benutzer gleich`, words: "start dashboard widget übersicht anpassen" },
        ...MODULES.map((m) => ({ g: "Module", go: m.views.find((v) => v === "settings" || v === "shutset") || m.views[0], icon: `logo:${m.logo}`, c: m.id === "rollwerk" ? "#0ea5e9" : "#fb923c", title: m.name,
          sum: m.id === "rollwerk" ? `${(p.rw_covers || []).length} Rollläden · ${Object.keys(this._data.rollwerk?.profiles || {}).length} Verhalten` : `${rooms.length} ${rooms.length === 1 ? "Raum" : "Räume"} · Heizpläne, Vorheizen, Saison und mehr`,
          words: m.id === "rollwerk" ? "rollwerk rollladen rollo module" : "heizen heizung räume module" })),
        ...COMING.map((m) => ({ g: "Module", soon: true, icon: m.icon, c: "#94a3b8", title: m.name, sum: "Kommt später", words: `${m.name.toLowerCase()} module` })),
        { g: "System", go: "log", icon: "mdi:text-box-search-outline", c: "#64748b", title: "Protokoll",
          sum: "Was wann warum entschieden wurde · 14 Tage", words: "protokoll log verlauf ereignisse warum debug" },
        (() => {
          const rd = s.radio || {};
          return { g: "System", id: "radio", icon: "mdi:access-point-network", c: rd.busy ? "#f97316" : "#64748b", title: "Funk-Auslastung",
            sum: rd.level != null ? `${fmt(rd.level, 0)} % · ${rd.busy ? "ausgelastet – Hauswerk drosselt" : `drosselt ab ${fmt(rd.limit ?? 70, 0)} %`} · ${s.commands_hour ?? 0} Befehle/Std.`
              : (rd.entities || []).length ? "Sensor gerade ohne Wert" : "Kein Duty-Cycle-Sensor gefunden",
            warn: !!rd.busy, words: "funk duty cycle homematic ccu auslastung befehle drosseln" };
        })(),
        { g: "System", id: "access", icon: "mdi:shield-account-outline", c: "#94a3b8", title: "Berechtigungen",
          sum: p.allow_users ? "Alle Benutzer dürfen ändern" : "Nur Administratoren dürfen ändern", words: "admin benutzer rechte tablet speichern" },
      ];
    }
    const season = {
      off: "Immer Heizperiode",
      auto: `Sommerpause ab ${fmt(p.summer_temp ?? 16)} °C außen`,
      entity: `Nach ${p.season_entity ? this._entityName(p.season_entity) : "Entität"}`,
      on: "Sommerpause von Hand an",
    }[p.summer_mode || "off"];
    const pre = { smart: "Lernend", fixed: `Feste Zeit · ${this._leadFor("heizkoerper")} / ${this._leadFor("flaeche")} Min.`, off: "Aus" }[p.preheat_mode || "fixed"] + (p.preheat_weather && (p.preheat_mode || "fixed") !== "off" ? " · nach Wetter" : "");
    const hum = rooms.filter((r) => r.humidity_sensor).length;
    const own = rooms.filter((r) => r.preheat_mode).length;
    const shared = rooms.filter((r) => !r.schedule_entity && this._data.plans?.[r.plan_id]).length;
    const away = p.away_action === "off" ? "Thermostate aus" : p.away_mode === "offset" ? `${fmt(p.away_offset)} °C kühler` : `höchstens ${fmt(p.away_temp)} °C`;
    const rows = [
      { g: "Hauswerk", go: "house", icon: "mdi:home-cog-outline", c: "#2dd4bf", title: "Zentrale Einstellungen",
        sum: "Anwesenheit, Urlaub, Wetter, Benachrichtigungen und Berechtigungen gelten für alle Module", words: "anwesenheit urlaub wetter personen berechtigungen zentral" },
      { g: "Heizen", id: "absence", icon: "mdi:home-export-outline", c: "#94a3b8", title: "Abwesenheit & Urlaub",
        sum: `Abwesend: ${away} · Urlaub: ${fmt(p.vacation_temp)} °C${Number(p.long_away_days) > 0 ? ` · nach ${p.long_away_days} Tagen Frostschutz` : ""}`,
        on: s.vacation || s.away, words: "abwesend urlaub absenken temperatur frostschutz lange" },
      { g: "Heizen", id: "season", icon: s.summer ? "mdi:weather-sunny" : "mdi:snowflake-thermometer", c: "#facc15", title: "Saison", sum: season + (s.summer ? " · gerade Sommerpause" : ""), words: "sommer sommerpause heizperiode außentemperatur" },
      { g: "Heizen", id: "plans", icon: "mdi:calendar-clock", c: "#60a5fa", title: "Heizpläne",
        sum: plans.length ? `${plans.length} gemeinsame${plans.length === 1 ? "r Plan" : " Pläne"} · ${shared} von ${rooms.length} Räumen nutzen sie` : "Noch kein gemeinsamer Plan", go: "plans", words: "zeitplan komfortzeit kalender import vorlage" },
      { g: "Heizen", id: "preheat", icon: "mdi:clock-fast", c: "#fb923c", title: "Vorheizen", sum: pre + (own ? ` · ${own} ${own > 1 ? "Räume" : "Raum"} mit eigener Einstellung` : ""), words: "lernen lernend fest aus vorlauf aufheizen" },
      { g: "Heizen", id: "vent", icon: "mdi:weather-windy", c: "#22d3ee", title: "Lüften & Schimmelschutz",
        sum: Number(p.vent_rh ?? 65) > 0 ? `Hinweis ab ${p.vent_rh ?? 65} % Luftfeuchte · ${hum} ${hum === 1 ? "Raum" : "Räume"} mit Feuchtesensor` : "Aus",
        words: "lüften feucht schimmel taupunkt bad dusche luftfeuchte" },
      (() => {
        const dm = s.demand;
        const label = { low: p.demand_action === "off" ? "aus – kein Raum braucht Wärme" : `abgesenkt auf ${fmt(p.demand_low ?? 17)} °C`, raise: "angehoben fürs Vorheizen", normal: "normal – Räume brauchen Wärme" };
        return { g: "Heizen", id: "demand", icon: "mdi:water-boiler", c: dm?.state === "low" ? "#22c55e" : "#f97316", title: "Wärmeanforderung",
          sum: p.demand_entity ? `${this._entityName(p.demand_entity)} · ${dm?.error ? "nicht erreichbar" : label[dm?.state || "normal"]}` : "Aus – Wärmeerzeuger läuft unabhängig",
          words: "vaillant kessel therme wärmepumpe heizung bedarf absenken vorlauf energie sparen" };
      })(),
      { g: "Heizen", id: "protect", icon: "mdi:snowflake-thermometer", c: "#38bdf8", title: "Frostschutz", sum: `${fmt(p.frost_temp)} °C bei offenem Fenster und in der Sommerpause`, words: "fenster frost" },
      { g: "Heizen", id: "boost", icon: "mdi:rocket-launch-outline", c: "#f43f5e", title: "Boost", sum: `${p.boost_minutes || 30} Min. volle Leistung`, words: "boost schnell" },
      { g: "Heizen", id: "liming", icon: "mdi:water-sync", c: "#38bdf8", title: "Entkalkungsschutz",
        sum: p.liming ? `${["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][p.liming_day ?? 0]}, ${p.liming_time || "10:00"} Uhr · ${p.liming_minutes || 5} Min.` : "Aus", words: "ventil entkalken festsitzen" },
      { g: "Heizen", id: "calibration", icon: "mdi:tune-vertical-variant", c: "#a78bfa", title: "Kalibrierung", sum: `Offset höchstens alle ${p.calibration_interval || 10} Min. anpassen`, words: "offset kalibrieren batterie" },
      ...rooms.map((r) => ({ g: "Räume", room: r, icon: roomIcon(r), c: this._roomColor(r.id), title: r.name,
        sum: `${TYPES[r.type].label} · ${(r.climates || []).length}× Thermostat · ${this._planLabel(r)}`, off: r.enabled === false, words: "raum thermostat" })),
    ];
    if (!rooms.length) rows.push({ g: "Räume", newRoom: true, icon: "mdi:plus", c: "#2dd4bf", title: "Raum anlegen", sum: "Thermostate, Fenster und Sensoren zuordnen", words: "raum neu" });
    return rows;
  }

  // ------------------------------------------------------------ Protokoll (Hauswerk › Einstellungen › Protokoll)
  /** Einträge laden und neue live empfangen (einmal je geöffnetem Panel). */
  _logInit() {
    if (this._log) return;
    this._log = { loading: true, entries: [] };
    this._hass
      .callWS({ type: "hauswerk/log/get" })
      .then((r) => {
        this._log = { entries: r.entries || [], days: r.days || 14, live: false, at: Date.now() };
        this._logUnsub = this._hass.connection.subscribeMessage(
          (e) => {
            this._log.entries.push(e);
            this._log.at = Date.now();
            if (this._tab === "log") this._renderLogList();
          },
          { type: "hauswerk/log/subscribe" }
        );
        this._logUnsub.then(() => {
          this._log.live = true;
          if (this._tab === "log") this._renderLogList();
        }).catch(() => {});
        if (this._tab === "log") this._renderMain();
      })
      .catch((err) => {
        this._log = { error: err?.message || "Protokoll nicht verfügbar", entries: [] };
        if (this._tab === "log") this._renderMain();
      });
  }

  /** Eingeschaltete Kategorien (je Gerät gemerkt). */
  _logCats() {
    if (!this._logCatSet) {
      let list = null;
      try {
        list = JSON.parse(localStorage.getItem("hauswerk.protokoll.kategorien") || "null");
      } catch (e) {
        list = null;
      }
      this._logCatSet = new Set(Array.isArray(list) ? list : Object.keys(LOG_CATS).filter((k) => !LOG_CATS[k].off));
    }
    return this._logCatSet;
  }

  _viewLog() {
    this._logInit();
    const L = this._log || {};
    const cats = this._logCats();
    const rooms = this._rooms();
    const sel = this._logRoom || "";
    const back = `<button class="link back" data-action="tab" data-tab="house"><ha-icon icon="mdi:chevron-left"></ha-icon>Einstellungen</button>`;
    return `
      ${back}
      <section class="card lg">
        <div class="lg-head">
          <span class="lg-ic"><ha-icon icon="mdi:text-box-search-outline"></ha-icon></span>
          <div class="grow"><h2>Protokoll</h2><small>Was wann warum entschieden wurde · ${L.days || 14} Tage</small></div>
          <span class="lg-live ${L.live ? "on" : ""}" id="lg-live">${this._logLiveHtml()}</span>
        </div>
        <div class="lg-chips">${[["", "Alle Räume", "#94a3b8"], ...rooms.map((r) => [r.id, r.name, this._roomColor(r.id)])]
          .map(([id, name, c]) => `<button class="lg-room ${sel === id ? "on" : ""}" style="--c:${c}" data-action="log-room" data-id="${id}"><i></i>${esc(name)}</button>`)
          .join("")}</div>
        <div class="lg-chips">${Object.entries(LOG_CATS)
          .map(([k, d]) => `<button class="lg-cat ${cats.has(k) ? "on" : ""}" style="--c:${d.c}" data-action="log-cat" data-k="${k}" aria-pressed="${cats.has(k)}"><ha-icon icon="${d.icon}"></ha-icon>${d.name}</button>`)
          .join("")}</div>
        <div class="search lg-search"><ha-icon icon="mdi:magnify"></ha-icon><input type="search" data-action="log-search" placeholder="Suchen … (z. B. Fenster, Boost, Offset)" value="${esc(this._logQuery || "")}" autocomplete="off"></div>
        <div id="log-list">${this._logList()}</div>
      </section>`;
  }

  _logLiveHtml() {
    const L = this._log || {};
    const time = L.at ? new Date(L.at).toLocaleTimeString("de-DE") : "";
    return `<i></i>${L.live ? "live" : L.error ? "getrennt" : "verbinde …"}${time ? ` · ${time}` : ""}`;
  }

  /** Nur Liste und Live-Anzeige neu zeichnen (Suchfeld behält den Fokus). */
  _renderLogList() {
    const list = this.shadowRoot.getElementById("log-list");
    if (list) list.innerHTML = this._logList();
    const live = this.shadowRoot.getElementById("lg-live");
    if (live) {
      live.innerHTML = this._logLiveHtml();
      live.classList.toggle("on", !!this._log?.live);
    }
  }

  _logList() {
    const L = this._log || {};
    if (L.loading) return `<div class="chart-empty"><div class="spinner"></div></div>`;
    if (L.error) return `<p class="note warn"><ha-icon icon="mdi:alert-outline"></ha-icon>${esc(L.error)}</p>`;
    const cats = this._logCats();
    const room = this._logRoom || "";
    const q = (this._logQuery || "").toLowerCase().trim();
    const rooms = this._data.rooms || {};
    const roomName = (e) => rooms[e.room]?.name || e.rn || "";
    const hits = [];
    for (let i = L.entries.length - 1; i >= 0; i--) {
      const e = L.entries[i];
      if (!cats.has(e.cat) && LOG_CATS[e.cat]) continue;
      if (room && e.room !== room) continue;
      if (q && !`${e.title} ${e.why || ""} ${roomName(e)} ${LOG_CATS[e.cat]?.name || ""}`.toLowerCase().includes(q)) continue;
      hits.push(e);
    }
    if (!hits.length)
      return `<section class="empty small"><ha-icon icon="mdi:text-box-remove-outline"></ha-icon><p>${L.entries.length ? "Keine Einträge für diese Auswahl." : "Noch keine Einträge – ab jetzt protokolliert Hauswerk jede Entscheidung."}</p></section>`;
    const limit = this._logLimit || 200;
    const today = new Date().toDateString();
    const yesterday = new Date(Date.now() - 864e5).toDateString();
    let html = "";
    let lastDay = null;
    for (const e of hits.slice(0, limit)) {
      const d = new Date(e.ts * 1000);
      const ds = d.toDateString();
      if (ds !== lastDay) {
        lastDay = ds;
        html += `<div class="lg-day">${ds === today ? "Heute" : ds === yesterday ? "Gestern" : d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" })}</div>`;
      }
      const def = LOG_CATS[e.cat] || { icon: "mdi:information-outline", c: "#94a3b8" };
      const rn = roomName(e);
      const rc = rooms[e.room] ? this._roomColor(e.room) : "#94a3b8";
      const lead = ["settings", "command", "health"].includes(e.cat) ? "Details" : "Warum";
      html += `
        <div class="lg-row">
          <time>${d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</time>
          <span class="lg-i" style="--c:${def.c}" title="${esc(def.name || "")}"><ha-icon icon="${def.icon}"></ha-icon></span>
          <div class="lg-b">
            <div class="lg-t">${rn ? `<span class="lg-badge" style="--c:${rc}">${esc(rn)}</span>` : ""}<b>${esc(e.title)}</b></div>
            ${e.why ? `<p><b>${lead}:</b> ${esc(e.why)}</p>` : ""}
          </div>
        </div>`;
    }
    if (hits.length > limit) html += `<button class="secondary wide lg-more" data-action="log-more">Ältere anzeigen (${hits.length - limit} weitere)</button>`;
    return html;
  }

  /** Einstellungen des Moduls Heizwerk. */
  _viewSettings() {
    return this._settingsPage("heat");
  }

  /** Zentrale Hauswerk-Einstellungen: gelten für alle Module. */
  _viewHouse() {
    return this._settingsPage("house");
  }

  _settingsPage(scope) {
    const intro = scope === "house"
      ? `<p class="muted small setintro"><ha-icon icon="mdi:home-cog-outline"></ha-icon>Diese Einstellungen gelten für ganz Hauswerk und alle Module. Was nur das Heizen betrifft, steht unter <button class="link inline" data-action="tab" data-tab="settings">Heizwerk › Einstellungen</button>.</p>`
      : "";
    return `
      ${intro}
      <div class="setsearch search"><ha-icon icon="mdi:magnify"></ha-icon><input type="search" data-action="set-search" placeholder="Einstellung suchen …" value="${esc(this._setQuery || "")}" autocomplete="off"></div>
      <div id="set-list">${this._settingsList(scope)}</div>`;
  }

  _settingsList(scope = this._tab === "house" ? "house" : this._tab === "shutset" ? "rw" : "heat") {
    const q = (this._setQuery || "").toLowerCase().trim();
    const rows = this._settingRows(scope).filter((r) => !q || `${r.g} ${r.title} ${r.sum} ${r.words}`.toLowerCase().includes(q));
    if (!rows.length) return `<section class="card empty small"><p>Nichts gefunden für „${esc(q)}“.</p></section>`;
    const row = (r) => {
      const attrs = r.soon
        ? "disabled"
        : r.room
          ? `data-action="room-edit" data-id="${r.room.id}" ${this._admin ? "" : "disabled"}`
          : r.newRoom
            ? `data-action="room-new" ${this._admin ? "" : "disabled"}`
            : r.start
              ? `data-action="start-edit" ${this._admin ? "" : "disabled"}`
              : r.go
                ? `data-action="tab" data-tab="${r.go}"`
                : `data-action="pop-open" data-pop="${r.id}"`;
      return `
        <button class="srow ${r.warn ? "warn" : ""} ${r.off || r.soon ? "off" : ""}" ${attrs}>
          <span class="sr-ic ${String(r.icon).startsWith("logo:") ? "logo" : ""}" style="--c:${r.c}">${modIcon(r.icon)}</span>
          <span class="sr-t"><b>${esc(r.title)}${r.on ? ` <em class="badge ok">AKTIV</em>` : ""}${r.off ? ` <em class="badge">AUTOMATIK AUS</em>` : ""}${r.soon ? ` <em class="badge">BALD</em>` : ""}</b><small>${esc(r.sum)}</small></span>
          ${r.soon ? "" : `<ha-icon class="sr-go" icon="mdi:chevron-right"></ha-icon>`}
        </button>`;
    };
    return [...new Set(rows.map((r) => r.g))]
      .map(
        (g) => `
        <section class="card sgroup">
          <div class="sg-h">${g}${g === "Räume" && this._admin && this._rooms().length ? `<span class="grow"></span><button class="link" data-action="room-new"><ha-icon icon="mdi:plus"></ha-icon>Raum</button>` : ""}</div>
          ${rows.filter((r) => r.g === g).map(row).join("")}
        </section>`
      )
      .join("");
  }

  // ------------------------------------------------------------ Pop-ups
  _openPop(id, draft = {}) {
    this._settings = clone(this._data.settings);
    this._pop = { id, draft };
    this._renderPop();
  }

  _closePop() {
    this._pop = null;
    this._settings = null;
    this._renderPop();
  }

  /** Nach einer Änderung an Einstellungen neu zeichnen: das offene Pop-up, sonst die Seite. */
  _refreshSettings() {
    if (this._pop) this._renderPop();
    else this._renderMain();
  }

  _renderPop() {
    const host = this.shadowRoot.getElementById("pop");
    if (!host) return;
    // Darstellung: Änderungen sofort als Vorschau zeigen, beim Abbrechen wieder die gespeicherten
    this._applyLook(this._pop?.id === "look" ? this._settings : null);
    if (!this._pop) {
      host.innerHTML = "";
      return;
    }
    const scroll = host.querySelector(".sheet-body")?.scrollTop || 0;
    const def = this._popDef(this._pop.id);
    const foot =
      def.foot ??
      `<button class="secondary" data-action="pop-close">${this._admin ? "Abbrechen" : "Schließen"}</button>
       ${this._admin ? `<button class="primary" data-action="pop-save"><ha-icon icon="mdi:content-save-outline"></ha-icon>Speichern</button>` : ""}`;
    host.innerHTML = `
      <div class="backdrop" data-action="pop-close"></div>
      <div class="sheet pop" role="dialog" aria-label="${esc(def.title)}">
        <div class="sheet-head">
          <span class="sr-ic big" style="--c:${def.c}"><ha-icon icon="${def.icon}"></ha-icon></span>
          <div class="grow"><h2>${def.title}</h2>${def.sub ? `<div class="muted">${def.sub}</div>` : ""}</div>
          <button class="icon boxed" data-action="pop-close" title="Schließen"><ha-icon icon="mdi:close"></ha-icon></button>
        </div>
        <div class="sheet-body">${this._admin || def.open ? "" : `<p class="note warn"><ha-icon icon="mdi:lock-outline"></ha-icon>Nur ansehen: Ändern dürfen Administratoren – oder alle, wenn ein Admin es unter „Berechtigungen“ freigibt.</p>`}${def.body}</div>
        <div class="sheet-foot">${foot}</div>
      </div>`;
    const body = host.querySelector(".sheet-body");
    if (body && this._pop.keep) body.scrollTop = scroll;
    this._pop.keep = true;
  }

  _popDef(id) {
    if (id === "rwiz") return this._wizPop();
    if (id === "cwiz") {
      if (!this._pop.draft.covers) Object.assign(this._pop.draft, this._cwizDraft());
      return this._cwizPop();
    }
    if (String(id).startsWith("rwc:")) return this._rwcPop(id.slice(4));
    if (RW_POPS.includes(id)) return this._rwPop(id);
    if (String(id).startsWith("rwp:")) { const [, pid, sec] = String(id).split(":"); return this._rwpPop(pid, RW_SECTIONS.some(([x]) => x === sec) ? sec : "tag"); }
    const p = this._settings;
    const s = this._status || {};
    const { minutes, segs, sw, head, dis } = this._setHelpers(p);
    const rooms = this._rooms();
    const st = s.rooms || {};
    const date = (iso, time = false) =>
      new Date(iso).toLocaleString("de-DE", time ? { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" } : { weekday: "short", day: "numeric", month: "short" });
    switch (id) {
      case "presence": {
        const S = this._hass.states;
        const st = this._status || {};
        const persons = [...new Set(Object.keys(S).filter((e) => e.startsWith("person.")).concat(p.persons || []))];
        const chosen = new Set(p.persons || []);
        const zones = Object.keys(S).filter((e) => e.startsWith("zone.")).sort((a, b) => (a === "zone.home" ? -1 : b === "zone.home" ? 1 : a.localeCompare(b)));
        const people = new Map(this._people(persons, p.home_zone || "zone.home").map((x) => [x.id, x]));
        const state = st.vacation
          ? ["mdi:palm-tree", "Urlaub", "#34d399"]
          : p.presence_force === "away"
            ? ["mdi:home-export-outline", "Abwesend – von Hand", "#94a3b8"]
            : st.away
              ? ["mdi:home-export-outline", "Niemand da", "#94a3b8"]
              : st.approaching
                ? ["mdi:home-import-outline", "Jemand kommt heim", "#14b8a6"]
                : ["mdi:home-account", (p.persons || []).length ? "Jemand da" : "Keine Personen gewählt", (p.persons || []).length ? "#14b8a6" : "#f59e0b"];
        const chip = (id) => {
          const x = people.get(id);
          const txt = !x ? "fehlt" : x.home ? "da" : x.distTxt || x.where;
          return `<button class="pchip ${chosen.has(id) ? "on" : ""} ${x?.home ? "home" : ""}" data-action="person-toggle" data-id="${esc(id)}" aria-pressed="${chosen.has(id)}" ${dis}><i></i>${esc(x?.name || this._entityName(id))} · ${esc(txt)}</button>`;
        };
        const step = (key, def) =>
          `<div class="mstep"><button data-action="min-step" data-key="${key}" data-d="-5" aria-label="5 Minuten weniger" ${dis}>−</button><b>${p[key] ?? def} min</b><button data-action="min-step" data-key="${key}" data-d="5" aria-label="5 Minuten mehr" ${dis}>+</button></div>`;
        const row = (k, title, sub, value, text, ctl) => this._setRow(k, title, sub, value, text, ctl);
        return {
          icon: "mdi:home-account", c: "#8b5cf6", title: "Anwesenheit", sub: "Hauswerk · gilt für alle Module",
          body: `
            <span class="pstate" style="--c:${state[2]}"><ha-icon icon="${state[0]}"></ha-icon>${state[1]}</span>
            <div class="wxsrcs">
              <div class="wxsrc">${row("who", "Wer wohnt hier?", "Tippen zum Aus- und Abwählen", `<div class="pchips">${persons.map(chip).join("") || `<span class="muted small">Keine Personen in Home Assistant</span>`}</div>`,
                "Gewählte Personen zählen, sobald sie in der Wohnung sind (über die Ortung ihres Handys in Home Assistant). Sind alle weg, gilt das Haus nach der Wartezeit als abwesend. Ohne gewählte Personen gibt es kein automatisches „Abwesend“. Über „Hinzufügen“ wählst du auch Handys oder Tracker (device_tracker) direkt; „Neue Person“ legt eine Person in Home Assistant an.", true)}
              <div class="wxr-pk">${this._picker("person_add", p.persons || [])}
                ${this._data.user_admin ? (this._newPerson != null ? `
                <div class="newp"><input type="text" maxlength="40" data-newp placeholder="Name, z. B. Julia" value="${esc(this._newPerson)}"><button class="primary small" data-action="person-create"><ha-icon icon="mdi:account-plus-outline"></ha-icon>Anlegen</button><button class="link tiny" data-action="person-new">Abbrechen</button></div>
                <p class="muted small">Legt die Person in Home Assistant an. Damit Hauswerk sie orten kann, ordnest du ihr danach unter Einstellungen › Personen ihr Handy zu.</p>`
                : `<button class="pk-add" data-action="person-new"><ha-icon icon="mdi:account-plus-outline"></ha-icon>Neue Person in Home Assistant anlegen</button>`) : ""}</div></div>
            </div>
            <div class="wxrows">
              ${row("zone", "Wohnung (Zone)", "wo „zu Hause“ ist", `<select data-set="home_zone" ${dis}>${zones.map((z) => `<option value="${esc(z)}" ${(p.home_zone || "zone.home") === z ? "selected" : ""}>${esc(z === "zone.home" && this._entityName(z) === z ? "Home (Zuhause)" : this._entityName(z))}</option>`).join("")}</select>`,
                "Die Zone aus Home Assistant, in der eine Person als zu Hause gilt – meist „Home“. Abstände rechnet Hauswerk zur Mitte dieser Zone.", true)}
              ${row("delay", "Absenken nach", "damit kurze Wege nichts auslösen", step("away_delay", 10),
                "Erst wenn alle gewählten Personen so lange weg sind, gilt das Haus als abwesend. Was dann passiert, legt jedes Modul fest – fürs Heizen unter Heizwerk › Abwesenheit & Urlaub.")}
              ${row("arrive", "Zu Hause nach", "nach dem Heimkommen", step("arrive_delay", 0),
                "So lange nach dem Heimkommen bleibt es noch bei „abwesend“ – z. B. damit ein kurzer Zwischenstopp nicht gleich alles hochheizt. 0 = sofort.")}
              ${row("vac", "Urlaub", "von Hand – bleibt an, bis du ihn ausschaltest", sw("vacation"),
                "Schaltet Urlaub für alle Module. Automatisch per Zeitraum oder Kalender: Hauswerk › Einstellungen › Urlaub.")}
              ${row("guest", "Gäste da", "nicht absenken, auch wenn alle Bewohner weg sind", sw("guest"),
                "Solange Gäste da sind, gilt das Haus nie als abwesend – auch wenn alle gewählten Personen unterwegs sind.")}
            </div>
            ${head("mdi:calendar-star", "Feiertage")}
            <div class="wxsrcs">
              <div class="wxsrc">${row("holi", "Arbeitstag-Sensor", p.workday_entity ? `Feiertage wie ${Number(p.workday_as ?? 6) === 5 ? "Samstag" : "Sonntag"}${Object.values(st.rooms || {}).some((x) => x.holiday) ? " · heute Feiertag" : ""}` : "aus – Feiertage wie normale Werktage", "",
                "Mit dem Sensor der Home-Assistant-Integration „Arbeitstag“ (Workday) erkennt Hauswerk Feiertage: Ist er an einem Werktag aus, gelten die Zeiten des Wochenendes – in Heizwerk für alle Heizpläne, später auch für Rollläden und Licht. Zeitpläne und Kalender aus Home Assistant bleiben unverändert. Noch keinen Sensor? Unter Geräte & Dienste die Integration „Arbeitstag“ für dein Bundesland hinzufügen.")}
              <div class="wxr-pk">${this._picker("workday_entity", p.workday_entity ? [p.workday_entity] : [])}
                ${p.workday_entity ? `<div class="field"><span>An Feiertagen wie am</span>${segs("workday_as", [["5", "Samstag", "mdi:calendar-weekend"], ["6", "Sonntag", "mdi:calendar-weekend-outline"]], "6")}</div>` : ""}</div></div>
            </div>
            ${head("mdi:map-marker-radius-outline", "Auf dem Heimweg")}
            <div class="wxrows">
              ${row("near", "Näher als", "gilt schon als zu Hause (0 = aus)", `<div class="unit"><input type="number" step="50" min="0" max="50000" data-set="proximity_m" value="${Math.round(p.proximity_m ?? 0)}" ${dis}><i>m</i></div>`,
                "Ist eine Person näher als dieser Abstand zur Wohnung, gilt das Haus schon als bewohnt – Heizwerk heizt dann zum Beispiel schon vor. Der Abstand kommt aus der Ortung der Person oder aus einem Entfernungs-Sensor.", true)}
            </div>
            <div class="field"><span>Entfernungs-Sensoren (optional, z. B. aus der Integration „Nähe“)</span>${this._picker("proximity_sensors", p.proximity_sensors || [])}</div>
            <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Party und Eco schaltest du in der Hausmodus-Leiste auf der Startseite. Präsenzmelder einzelner Räume stehen am Raum unter „Geräte“.</p>`,
        };
      }

      case "absence":
        return {
          icon: "mdi:home-export-outline", c: "#94a3b8", title: "Abwesenheit & Urlaub", sub: "Heizwerk · was die Heizung tut, wenn niemand da ist",
          body: `
            <p class="muted small"><ha-icon icon="mdi:home-cog-outline"></ha-icon>Wer zu Hause ist und wann Urlaub ist, stellst du zentral ein: <button class="link inline" data-action="settings-go" data-sub="presence">Anwesenheit</button> · <button class="link inline" data-action="settings-go" data-sub="vacation">Urlaub</button></p>
            ${head("mdi:home-export-outline", "Wenn niemand da ist")}
            <div class="field">${segs("away_action", [["lower", "Absenken", "mdi:thermometer-chevron-down"], ["off", "Thermostate aus", "mdi:power"]], "lower")}</div>
            ${(p.away_action || "lower") === "lower" ? `
            <div class="field">${segs("away_mode", [["temp", "Auf höchstens …", "mdi:thermometer"], ["offset", "Um … kühler", "mdi:arrow-down-thin"]], "temp")}</div>
            ${(p.away_mode || "temp") === "offset"
              ? `<label class="field narrow"><span>Absenkung</span><div class="unit"><input type="number" step="0.5" min="0" max="10" data-set="away_offset" value="${p.away_offset ?? 2}" ${dis}><i>°C</i></div></label>`
              : `<div class="field"><span>Höchstens</span>${this._stepper("set", "away_temp", p.away_temp)}</div>`}` : ""}
            <label class="field narrow"><span><ha-icon icon="mdi:snowflake-thermometer"></ha-icon> Frostschutz, wenn so lange niemand da war (0 = nie)</span><div class="unit"><input type="number" step="1" min="0" max="60" data-set="long_away_days" value="${p.long_away_days ?? 0}" ${dis}><i>Tage</i></div></label>
            ${head("mdi:palm-tree", "Im Urlaub")}
            <div class="field"><span>Temperatur im Urlaub (alle Räume)</span>${this._stepper("set", "vacation_temp", p.vacation_temp)}</div>`,
        };

      case "vacation": {
        const src = p.vacation_source || "period";
        const saved = this._data.settings;
        const events = src === "calendar" && saved.vacation_calendar === p.vacation_calendar && saved.vacation_keywords === p.vacation_keywords ? s.vacation_events || [] : null;
        return {
          icon: "mdi:palm-tree", c: "#34d399", title: "Urlaub", sub: "Hauswerk · gilt für alle Module",
          body: `
            <div class="field"><span>Urlaub automatisch erkennen</span>${segs("vacation_source", [["off", "Aus", "mdi:close-circle-outline"], ["period", "Zeitraum", "mdi:calendar-range"], ["calendar", "HA-Kalender", "mdi:calendar-search"]], "period")}</div>
            ${src === "period" ? `
            <div class="row2">
              <label class="field"><span><ha-icon icon="mdi:calendar-start"></ha-icon> Von</span><input type="date" data-set="vacation_from" value="${esc(p.vacation_from || "")}" ${dis}></label>
              <label class="field"><span><ha-icon icon="mdi:calendar-end"></ha-icon> Bis</span><input type="date" data-set="vacation_to" value="${esc(p.vacation_to || "")}" ${dis}></label>
            </div>` : ""}
            ${src === "calendar" ? `
            <div class="field"><span><ha-icon icon="mdi:calendar"></ha-icon> Kalender</span>${this._picker("vacation_calendar", p.vacation_calendar ? [p.vacation_calendar] : [])}</div>
            <label class="field"><span><ha-icon icon="mdi:text-search"></ha-icon> Stichworte im Termin-Titel (mit Komma getrennt, leer = jeder Termin)</span>
              <input type="text" maxlength="200" data-set="vacation_keywords" value="${esc(p.vacation_keywords ?? "")}" placeholder="Urlaub, Ferien" ${dis}></label>
            <p class="muted small">Läuft ein passender Termin, ist Urlaub – auch ganztägige und mehrtägige Termine. Hauswerk schaut alle 5 Minuten nach.</p>
            ${s.vacation_calendar_error && events ? `<p class="note warn"><ha-icon icon="mdi:alert-outline"></ha-icon>Kalender nicht lesbar: ${esc(s.vacation_calendar_error)}</p>` : ""}
            ${events ? `
            <div class="lbl">Gefundene Termine</div>
            <div class="evlist">${events.length ? events.map((e) => `
              <div class="ev ${new Date(e.start) <= new Date() ? "live" : ""}"><ha-icon icon="${new Date(e.start) <= new Date() ? "mdi:palm-tree" : "mdi:calendar-blank-outline"}"></ha-icon>
                <span class="grow"><b>${esc(e.summary || "Termin")}</b><small>${date(e.start)} – ${date(new Date(e.end).getTime() - 1)}</small></span>${new Date(e.start) <= new Date() ? `<em class="badge ok">JETZT</em>` : ""}</div>`).join("") : `<p class="muted small">In den nächsten 4 Monaten kein passender Termin.</p>`}</div>`
            : `<p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Nach dem Speichern zeigt Hauswerk hier die gefundenen Termine.</p>`}` : ""}
            ${src === "off" ? `<p class="muted small">Urlaub nur von Hand.</p>` : ""}
            <p class="muted small"><ha-icon icon="mdi:gesture-tap"></ha-icon>Von Hand geht es immer: „Urlaub“ in der Hausmodus-Leiste oder <code>switch.hauswerk_urlaub</code> für Automationen.</p>
            <p class="muted small"><ha-icon icon="mdi:radiator"></ha-icon>Die Temperatur im Urlaub stellst du unter <button class="link inline" data-action="settings-go" data-sub="absence">Heizwerk › Abwesenheit & Urlaub</button> ein.</p>`,
        };
      }

      case "season":
        return {
          icon: "mdi:weather-sunny", c: "#facc15", title: "Saison", sub: "Heizperiode oder Sommerpause – für alle Räume",
          body: `
            <p class="muted">In der Sommerpause bleiben die Thermostate aus. Zurück in den Heizbetrieb geht es 1 °C unter der Schwelle.</p>
            <div class="field"><span>Sommerpause</span>${segs("summer_mode", [["off", "Nie", "mdi:close-circle-outline"], ["auto", "Nach Außentemperatur", "mdi:thermometer-auto"], ["entity", "Nach Entität", "mdi:toggle-switch-outline"], ["on", "Jetzt an", "mdi:weather-sunny"]], "off")}</div>
            ${p.summer_mode === "auto" ? `
            <div class="row2">
              <div class="field"><span>Außentemperatur</span>${this._picker("outside_sensor", p.outside_sensor ? [p.outside_sensor] : [])}</div>
              <div class="field"><span>Sommerpause ab</span>${this._stepper("set", "summer_temp", p.summer_temp ?? 16)}</div>
            </div>` : ""}
            ${p.summer_mode === "entity" ? `
            <div class="field"><span>Heizperiode (an = heizen, aus = Sommerpause)</span>${this._picker("season_entity", p.season_entity ? [p.season_entity] : [])}</div>` : ""}
            ${["auto", "entity"].includes(p.summer_mode) ? `
            <div class="field"><span>Wenn ${p.summer_mode === "auto" ? "der Außensensor" : "die Entität"} nicht verfügbar ist</span>${segs("summer_fallback", [["keep", "Zustand halten", "mdi:pause-circle-outline"], ["heat", "Heizen", "mdi:fire"], ["summer", "Sommerpause", "mdi:weather-sunny"]], "keep")}</div>` : ""}
            ${p.summer_mode && p.summer_mode !== "off" ? `
            <div class="field"><span>Thermostate in der Sommerpause</span>${segs("summer_action", [["off", "Ausschalten", "mdi:power"], ["frost", "Frostschutz", "mdi:snowflake"]], "off")}</div>` : ""}`,
        };

      case "preheat": {
        const mode = p.preheat_mode || "fixed";
        const own = rooms.filter((r) => r.preheat_mode);
        const label = { smart: "lernend", fixed: "feste Zeit", off: "aus" };
        return {
          icon: "mdi:clock-fast", c: "#fb923c", title: "Vorheizen", sub: "Für alle Räume – je Raum änderbar",
          body: `
            <p class="muted">Damit ein Raum zu Beginn der Komfortzeit schon warm ist, heizt Heizwerk vorher los.</p>
            <div class="field">${segs("preheat_mode", [["smart", "Lernen", "mdi:brain"], ["fixed", "Feste Zeit", "mdi:timer-outline"], ["off", "Aus", "mdi:timer-off-outline"]], "fixed")}</div>
            ${mode === "fixed" ? `
            <div class="row2">
              <label class="field"><span><ha-icon icon="mdi:radiator"></ha-icon> Heizkörper</span>${minutes("lead_radiator", 15, 0, 600, 5)}</label>
              <label class="field"><span><ha-icon icon="mdi:heating-coil"></ha-icon> Flächenheizung</span>${minutes("lead_floor", 120, 0, 600, 5)}</label>
            </div>
            <p class="muted small">So viele Minuten vor Beginn der Komfortzeit geht es los. Fußbodenheizungen brauchen deutlich länger.</p>` : ""}
            ${mode === "smart" ? `
            <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Heizwerk misst bei jedem Aufheizen, wie viele Grad pro Stunde ein Raum schafft, und startet so früh, dass er pünktlich warm ist – mit 15 % Reserve. Höchstens ${this._data.defaults.heizkoerper.preheat_max} Min. (Heizkörper) bzw. ${this._data.defaults.flaeche.preheat_max} Min. (Fläche) vorher; je Raum änderbar.</p>
            <div class="lbl">Gelernt</div>
            <div class="evlist">${rooms.map((r) => {
              const rs = st[r.id] || {};
              return `<div class="ev"><ha-icon icon="${esc(roomIcon(r))}"></ha-icon><span class="grow"><b>${esc(r.name)}</b><small>${rs.heat_rate ? `${fmt(rs.heat_rate)} °C/h${rs.learned ? " · gelernt" : " · Startwert"}` : "noch nichts gemessen"}</small></span>
                ${rs.learned && this._admin ? `<button class="link tiny" data-action="preheat-reset" data-id="${r.id}"><ha-icon icon="mdi:restore"></ha-icon>neu lernen</button>` : ""}</div>`;
            }).join("") || `<p class="muted small">Noch keine Räume.</p>`}</div>` : ""}
            ${mode === "off" ? `<p class="muted small">Räume heizen erst zu Beginn der Komfortzeit los.</p>` : ""}
            ${mode !== "off" ? `
            ${head("mdi:weather-snowy", "Nach Wetter")}
            <label class="check"><span><b>Vorlauf nach Außentemperatur anpassen</b><small>Bei Kälte früher, an milden Tagen später. Bezug sind 5 °C draußen: je Grad kälter 4 % mehr Vorlauf, je Grad wärmer 4 % weniger (höchstens 0,6- bis 1,8-fach).${mode === "smart" ? " Gelernte Werte rechnet Heizwerk auf 5 °C um, damit kalte und milde Tage vergleichbar sind." : ""}</small></span>${sw("preheat_weather")}</label>
            ${(() => {
              const f = Object.values(st)[0]?.preheat_factor;
              const out = s.outside_temp;
              return this._data.settings.preheat_weather && f ? `<p class="muted small"><ha-icon icon="mdi:thermometer"></ha-icon>Gerade ${fmt(f, 2)}-facher Vorlauf${out != null ? ` bei ${fmt(out)} °C außen` : ""}${mode === "fixed" ? ` – Heizkörper ${Math.round(this._leadFor("heizkoerper") * f)} Min., Fläche ${Math.round(this._leadFor("flaeche") * f)} Min` : ""}.</p>` : "";
            })()}` : ""}
            ${own.length ? `<p class="muted small"><ha-icon icon="mdi:home-edit-outline"></ha-icon>Eigene Einstellung: ${own.map((r) => `${esc(r.name)} (${label[r.preheat_mode]})`).join(", ")} – änderbar am Raum unter „Vorheizen & Fenster“.</p>` : ""}`,
        };
      }

      case "rq": {
        const d = this._pop.draft;
        const room = this._data.rooms[d.id] || {};
        const rs = st[d.id] || {};
        const mode = rs.mode || "aus";
        const m = MODE[mode] || MODE.aus;
        const dv = this._devIndicators(room);
        const until = rs.override_until ? new Date(rs.override_until).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : null;
        const blocked = { aus: "Die Automatik ist aus – Heizwerk stellt nichts ein.", fenster: "Fenster offen – die Fensterpause geht vor, die Änderung gilt danach.", sommer: "Sommerpause – die Änderung gilt erst in der Heizperiode.", entkalken: "Gerade läuft der Entkalkungsschutz." }[mode];
        const next = rs.next_change != null ? new Date(Date.now() + rs.next_change * 60000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : null;
        const durs = [["", next ? `bis ${next}` : "bis Planwechsel"], ["1", "1 h"], ["2", "2 h"], ["4", "4 h"], ["8", "8 h"]];
        const facts = [
          [m.i, rs.mode_label || "Automatik aus", m.c],
          ["mdi:thermometer", `Jetzt ${fmt(rs.room_temp)} °C`, "var(--muted)"],
          ["mdi:target", `Soll ${fmt(rs.target)} °C`, tint(tempColor(rs.target))],
          ...(rs.humidity != null ? [["mdi:water-percent", `${fmt(rs.humidity, 0)} %`, "var(--muted)"]] : []),
          ...(dv.valve != null ? [["mdi:valve", `Ventil ${fmt(dv.valve, 0)} %`, dv.valve > 0 ? "#fb923c" : "var(--muted)"]] : []),
          ...(dv.floor?.on ? [["mdi:heating-coil", `${dv.floor.label} heizt`, "#f97316"]] : []),
          ...(rs.assist ? [["mdi:radiator", rs.assist.on ? "Heizkörper hilft nach" : "Heizkörper zu", rs.assist.on ? "#f97316" : "#64748b"]] : []),
          ...(rs.windows_open ? [["mdi:window-open-variant", "Fenster offen", "#22d3ee"]] : []),
        ];
        const auto = room.enabled !== false;
        return {
          icon: roomIcon(room), c: this._roomColor(room.id), title: esc(room.name || "Raum"), sub: "Manuell ändern", open: true,
          body: `
            <div class="rq-facts">${facts.map(([i, txt, c]) => `<span style="--c:${c}"><ha-icon icon="${i}"></ha-icon>${esc(txt)}</span>`).join("")}</div>
            ${blocked ? `<p class="note"><ha-icon icon="mdi:information-outline"></ha-icon>${blocked}</p>` : ""}
            ${(mode === "manuell" || mode === "boost") && until ? `<div class="room-note ${mode === "boost" ? "boost" : ""}"><ha-icon icon="${mode === "boost" ? "mdi:rocket-launch-outline" : "mdi:hand-back-right-outline"}"></ha-icon>${mode === "boost" ? "Boost" : "Manuell"} bis ${until}<span class="grow"></span><button class="link" data-action="ovr-reset" data-id="${room.id}">Zurück zum Plan</button></div>` : ""}
            <div class="rq-temp">
              <small>Gewünschte Temperatur</small>
              ${this._stepper("rq", room.id, d.temp)}
              <div class="rq-quick">
                <button class="pill ${d.temp === room.comfort ? "on" : ""}" data-action="rq-temp" data-t="${room.comfort ?? 21}"><ha-icon icon="mdi:sofa-outline"></ha-icon>Komfort ${fmt(room.comfort ?? 21)} °C</button>
                <button class="pill ${d.temp === room.eco ? "on" : ""}" data-action="rq-temp" data-t="${room.eco ?? 18}"><ha-icon icon="mdi:leaf"></ha-icon>Eco ${fmt(room.eco ?? 18)} °C</button>
              </div>
            </div>
            <div class="lbl">Wie lange?</div>
            <div class="segs small rq-dur">${durs.map(([h, l]) => `<button class="seg ${String(d.hours ?? "") === h ? "on" : ""}" data-action="rq-dur" data-h="${h}">${l}</button>`).join("")}</div>
            <div class="rq-more">
              ${(room.climates || []).length && !["aus", "fenster", "entkalken"].includes(mode) ? `<button class="qbtn hot" data-action="rq-boost" data-id="${room.id}"><ha-icon icon="mdi:rocket-launch-outline"></ha-icon>Boost ${this._data.settings.boost_minutes || 30} Min.</button>` : ""}
              <button class="qbtn" data-action="room-page" data-id="${room.id}" data-hint="1"><ha-icon icon="mdi:chart-line"></ha-icon>Raumseite</button>
              ${this._admin ? `<button class="qbtn" data-action="plan-open" data-id="${room.id}" data-hint="1"><ha-icon icon="mdi:calendar-clock"></ha-icon>Heizplan</button>
              <button class="qbtn" data-action="room-auto" data-id="${room.id}" data-hint="1"><ha-icon icon="${auto ? "mdi:robot-off-outline" : "mdi:robot-outline"}"></ha-icon>Automatik ${auto ? "aus" : "an"}</button>` : ""}
            </div>`,
          foot: `<button class="secondary" data-action="pop-close">Abbrechen</button>
                 <button class="primary" data-action="rq-apply"><ha-icon icon="mdi:check"></ha-icon>Übernehmen</button>`,
        };
      }

      case "radio": {
        const rd = this._status?.radio || {};
        const ids = rd.entities || [];
        const val = (id) => {
          const x = this._hass.states[id];
          return !x || ["unavailable", "unknown"].includes(x.state) ? "nicht erreichbar" : `${fmt(Number(x.state), 1)} %`;
        };
        const blocked = Object.values(this._status?.rooms || {}).flatMap((x) => x.duty_blocked || []);
        return {
          icon: "mdi:access-point-network", c: "#64748b", title: "Funk-Auslastung", sub: "Hauswerk · Duty Cycle, z. B. Homematic IP",
          body: `
            <div class="rq-facts">
              <span style="--c:${rd.busy ? "#f97316" : "#22c55e"}"><ha-icon icon="mdi:access-point"></ha-icon>${rd.level != null ? `Jetzt ${fmt(rd.level, 0)} %` : "kein Wert"}</span>
              <span style="--c:${rd.busy ? "#f97316" : "#22c55e"}"><ha-icon icon="${rd.busy ? "mdi:speedometer-slow" : "mdi:check"}"></ha-icon>${rd.busy ? "ausgelastet – gedrosselt" : "frei"}</span>
              <span style="--c:#64748b"><ha-icon icon="mdi:send-outline"></ha-icon>${this._status?.commands_hour ?? 0} Befehle in der letzten Stunde</span>
            </div>
            <p class="muted">Funkzentralen wie die Homematic-CCU dürfen nur begrenzt senden (Duty Cycle, 1 % der Zeit). Bei 100 % nimmt sie keine Befehle mehr an – Thermostate bleiben dann auf dem alten Wert. Ab der Grenze schickt Hauswerk nur noch Wechsel der Betriebsart (z. B. Fenster auf, Komfort beginnt) und Änderungen ab 1 °C, höchstens alle 15 Minuten je Thermostat, und lässt Ventil- und Kalibrier-Befehle weg. Meldet ein einzelnes Gerät „Duty Cycle erreicht“, bekommt es solange keine Befehle.</p>
            <label class="field narrow"><span><ha-icon icon="mdi:speedometer"></ha-icon> Drosseln ab</span>${minutes("radio_limit", 70, 30, 95, 5, "%")}</label>
            <div class="lbl">${(p.radio_entities || []).length ? "Gewählte Sensoren" : "Automatisch gefunden"} (höchster Wert zählt)</div>
            <div class="evlist">${ids.map((id) => `<div class="wrow"><ha-icon icon="mdi:access-point"></ha-icon><span class="grow"><b>${esc(this._entityName(id))}</b><small>${esc(id)}</small></span><em class="${id === rd.entity && rd.busy ? "bad" : ""}">${val(id)}</em></div>`).join("") || `<p class="muted small">Kein Sensor mit „duty_cycle“ gefunden – ohne Sensor drosselt Hauswerk nicht.</p>`}</div>
            ${blocked.length ? `<p class="muted small"><ha-icon icon="mdi:alert-outline"></ha-icon>Gerade gesperrt: ${blocked.map((x) => esc(this._entityName(x))).join(", ")}</p>` : ""}
            <div class="field"><span>Sensoren selbst wählen (leer = automatisch)</span>${this._picker("radio_entities", p.radio_entities || [])}</div>`,
        };
      }

      case "notify": {
        const services = Object.keys(this._hass.services?.notify || {})
          .filter((x) => !["notify", "persistent_notification", "send_message"].includes(x))
          .sort((a, b) => (a.startsWith("mobile_app_") === b.startsWith("mobile_app_") ? a.localeCompare(b) : a.startsWith("mobile_app_") ? -1 : 1));
        const chosen = new Set(p.notify_targets || []);
        const all = [...new Set([...services, ...chosen])];
        const chip = (x) => `<button class="pchip ${chosen.has(x) ? "on" : ""}" data-action="notify-toggle" data-id="${esc(x)}" aria-pressed="${chosen.has(x)}" ${dis}><i></i>${esc(this._notifyName(x))}${chosen.has(x) && !services.includes(x) ? " · fehlt" : ""}</button>`;
        const row = (k, title, sub, value, text, ctl) => this._setRow(k, title, sub, value, text, ctl);
        const saved = (this._data.settings.notify_targets || []).length || this._data.settings.notify_ha;
        // Art je Anlass (früher an/aus)
        for (const k of ["notify_window", "notify_offline", "notify_frost", "notify_battery", "notify_cold"]) {
          if (p[k] === true || p[k] == null) p[k] = "normal";
          else if (p[k] === false) p[k] = "off";
        }
        const MODES_N = [["off", "Aus", "mdi:bell-off-outline"], ["log", "Protokoll", "mdi:text-box-outline"], ["normal", "Normal", "mdi:bell-outline"], ["important", "Wichtig", "mdi:bell-alert-outline"]];
        const kind = (key, title, sub, extra, text) => `<div class="wxsrc">${row(key, title, sub, extra || "", text, !!extra)}<div class="wxr-pk">${segs(key, MODES_N, "normal").replace('class="segs small"', 'class="segs small n4"')}</div></div>`;
        return {
          icon: "mdi:cellphone-message", c: "#0ea5e9", title: "Benachrichtigungen", sub: "Hauswerk · aufs Handy über die Home-Assistant-App",
          body: `
            <div class="wxrows">
              ${row("apps", "An wen?", "Geräte mit der Home-Assistant-App", `<div class="pchips">${all.map(chip).join("") || `<span class="muted small">Keine App gefunden</span>`}</div>`,
                "Jedes Handy mit der Home-Assistant-App bringt einen Dienst „notify.mobile_app_…“ mit. Gewählte Geräte bekommen die Nachrichten als Push-Mitteilung. Ohne Auswahl landen sie nur im Protokoll.", true)}
            </div>
            <div class="wxrows">
              ${row("nha", "Auch in Home Assistant", "als Mitteilung in der Seitenleiste (Glocke)", sw("notify_ha"),
                "Zusätzlich zur App erscheint die Nachricht als Mitteilung in Home Assistant und verschwindet von selbst, sobald der Anlass erledigt ist (z. B. Fenster zu).")}
            </div>
            ${saved && this._admin ? `<button class="secondary small" data-action="notify-test"><ha-icon icon="mdi:send-outline"></ha-icon>Testnachricht senden</button>` : ""}
            ${head("mdi:bell-ring-outline", "Wann und wie?")}
            <p class="muted small">Je Anlass: <b>Aus</b> · <b>Protokoll</b> (nur dort, kein Push) · <b>Normal</b> (Push, in der Ruhezeit zurückgehalten) · <b>Wichtig</b> (sofort, auch in der Ruhezeit; durchbricht „Nicht stören“ auf dem iPhone, hohe Priorität auf Android).</p>
            <div class="wxsrcs">
              ${kind("notify_window", "Fenster lange offen", `ab ${p.notify_window_min ?? 30} Min.`, minutes("notify_window_min", 30, 5, 720, 5),
                "Steht ein Fenster eines Raums so lange offen, kommt eine Nachricht – einmal je Öffnen.")}
              ${kind("notify_offline", "Thermostat nicht erreichbar", `seit ${p.notify_offline_min ?? 15} Min.`, minutes("notify_offline_min", 15, 1, 720, 5),
                "Meldet sich ein Thermostat so lange nicht mehr (z. B. Funk weg, Batterie leer), kommt eine Nachricht. Kommt es zurück, ist die Sache erledigt.")}
              ${kind("notify_frost", "Frost erwartet", `Vorhersage unter ${fmt(p.cold_snap_temp ?? 0)} °C · Grenze unter Wetter`, "",
                "Sagt die Wettervorhersage für die nächsten 3 Tage einen Tiefstwert unter der Grenze „Kälteeinbruch“ (Hauswerk › Wetter) voraus, kommt eine Nachricht.")}
              ${kind("notify_battery", "Batterie schwach", `unter ${p.battery_low ?? 20} %`, minutes("battery_low", 20, 5, 60, 5, "%"),
                "Hauswerk sucht an Thermostaten, Fensterkontakten und Raumsensoren nach Batterie-Sensoren. Liegt einer unter der Grenze, erscheint ein Hinweis unter der Glocke – und je nach Art eine Nachricht. Die Grenze gilt auch für die Glocke.")}
              ${kind("notify_cold", "Heizkörper bleibt kalt", "Ventil offen, Raum wird nicht wärmer", "",
                "Steht ein Ventil eine Stunde lang auf 90 % oder mehr, der Raum liegt mindestens 0,5 °C unter Soll und wird trotzdem nicht wärmer, kommt eine Nachricht. Mögliche Ursachen: Luft im Heizkörper, hängender Ventilstift oder die Heizung liefert keine Wärme.")}
            </div>
            ${head("mdi:sleep", "Ruhezeit")}
            <div class="wxrows">
              ${row("quiet", "Nachts nicht stören", "Nachrichten danach senden, falls noch aktuell", sw("notify_quiet"),
                "In der Ruhezeit hält Hauswerk Nachrichten zurück und schickt sie danach – aber nur, wenn der Anlass noch besteht (das Fenster also noch offen ist). Im Protokoll stehen sie sofort.")}
              ${p.notify_quiet ? row("qtime", "Von – bis", "", `<div class="nrow"><input type="time" data-set="notify_quiet_from" value="${esc(p.notify_quiet_from || "22:00")}" ${dis}><span>–</span><input type="time" data-set="notify_quiet_to" value="${esc(p.notify_quiet_to || "07:00")}" ${dis}></div>`,
                "Auch über Mitternacht, z. B. 22:00 – 07:00.", true) : ""}
            </div>
            <p class="muted small"><ha-icon icon="mdi:text-box-search-outline"></ha-icon>Jede Nachricht steht auch im <button class="link inline" data-action="tab" data-tab="log">Protokoll</button> unter „Nachrichten“ – mit dem Hinweis, ob sie gesendet oder zurückgehalten wurde.</p>`,
        };
      }

      case "vent": {
        const withHum = rooms.filter((r) => r.humidity_sensor);
        return {
          icon: "mdi:weather-windy", c: "#22d3ee", title: "Lüften & Schimmelschutz", sub: "Heizwerk · rechnet mit absoluter Feuchte und Taupunkt",
          body: `
            <p class="muted">Ist es drinnen feucht und die Luft draußen trockener, erscheint unter der Glocke „Jetzt lüften“. Verglichen wird die Wassermenge in der Luft (g/m³) – kalte Winterluft ist fast immer trockener, schwüle Sommerluft oft nicht.</p>
            <label class="field narrow"><span><ha-icon icon="mdi:water-percent"></ha-icon> Hinweis ab Luftfeuchte (0 = aus)</span>${minutes("vent_rh", 65, 0, 95, 5, "%")}</label>
            <div class="lbl">Räume mit Feuchtesensor</div>
            <div class="evlist">${withHum.map((r) => {
              const rs = st[r.id] || {};
              return `<div class="ev ${rs.vent ? "live" : ""}"><ha-icon icon="${rs.vent ? "mdi:weather-windy" : "mdi:water-percent"}"></ha-icon><span class="grow"><b>${esc(r.name)}</b><small>${rs.humidity != null ? `${fmt(rs.humidity, 0)} %` : "–"}${rs.vent ? ` · jetzt lüften · Taupunkt ${fmt(rs.vent.dew_point)} °C` : ""}${r.shower_boost ? ` · nach dem Duschen ${r.shower_boost} Min. nachheizen` : ""}</small></span>${rs.vent ? `<em class="badge ok">LÜFTEN</em>` : ""}</div>`;
            }).join("") || `<p class="muted small">Noch kein Raum hat einen Feuchtesensor – am Raum unter „Geräte“ zuordnen.</p>`}</div>
            <p class="muted small"><ha-icon icon="mdi:shower-head"></ha-icon>Nach dem Duschen nachheizen stellst du am Raum unter „Geräte“ ein (braucht einen Feuchtesensor).</p>`,
        };
      }

      case "demand": {
        const dm = this._status?.demand || {};
        const ent = p.demand_entity;
        const zst = ent ? this._hass.states[ent] : null;
        const need = dm.need || [];
        const stLabel = !ent ? "aus" : dm.error ? "nicht erreichbar" : dm.state === "low" ? (p.demand_action === "off" ? "aus – kein Raum braucht Wärme" : "abgesenkt") : dm.state === "raise" ? "angehoben fürs Vorheizen" : "normal";
        const roomsV = rooms.map((r) => ({ r, v: st[r.id]?.valve_all, m: st[r.id]?.mode })).filter((x) => x.v != null || ["vorheizen", "boost"].includes(x.m));
        return {
          icon: "mdi:water-boiler", c: "#f97316", title: "Wärmeanforderung", sub: "Heizwerk · Wärmeerzeuger nach Bedarf der Räume",
          body: `
            <p class="muted">Aus den Ventilöffnungen aller Räume weiß Hauswerk, ob überhaupt Wärme gebraucht wird. Braucht <b>kein</b> Raum Wärme, senkt es den Wärmeerzeuger (z. B. die Zone der Vaillant-Anlage) ab oder schaltet ihn aus – sobald ein Raum wieder Wärme braucht, kommt sofort der alte Wert zurück. Beim Vorheizen kann es ihn anheben. Warmwasser ist davon nicht betroffen.</p>
            <div class="field"><span><ha-icon icon="mdi:water-boiler"></ha-icon> Wärmeerzeuger (Klima-Entität, leer = aus)</span>${this._picker("demand_entity", ent ? [ent] : [])}</div>
            ${ent ? `
            <div class="rq-facts">
              <span style="--c:${dm.state === "low" ? "#22c55e" : "#f97316"}"><ha-icon icon="mdi:water-boiler"></ha-icon>Jetzt: ${esc(stLabel)}</span>
              ${zst ? `<span style="--c:#64748b"><ha-icon icon="mdi:thermometer"></ha-icon>Soll ${fmt(Number(zst.attributes.temperature))} °C · ${esc(this._fmtState(zst))}</span>` : ""}
              ${dm.orig_temp != null ? `<span style="--c:#64748b"><ha-icon icon="mdi:restore"></ha-icon>normal ${fmt(dm.orig_temp)} °C</span>` : ""}
            </div>
            <label class="field"><span>Wenn kein Raum Wärme braucht</span>${segs("demand_action", [["lower", "Absenken", "mdi:thermometer-chevron-down"], ["off", "Ausschalten", "mdi:power"]], "lower")}</label>
            ${(p.demand_action || "lower") === "lower" ? `<label class="field narrow"><span><ha-icon icon="mdi:thermometer-low"></ha-icon> Absenken auf</span>${minutes("demand_low", 17, 5, 25, 0.5, "°C")}</label>` : ""}
            <label class="field narrow"><span><ha-icon icon="mdi:valve"></ha-icon> Ein Raum braucht Wärme ab Ventilöffnung</span>${minutes("demand_valve", 15, 1, 80, 1, "%")}</label>
            <label class="field narrow"><span><ha-icon icon="mdi:timer-sand"></ha-icon> Erst absenken nach</span>${minutes("demand_hold", 20, 5, 180, 5)}</label>
            <label class="field narrow"><span><ha-icon icon="mdi:clock-fast"></ha-icon> Beim Vorheizen anheben um (0 = nein)</span>${minutes("demand_preheat", 0, 0, 5, 0.5, "°C")}</label>
            <div class="lbl">Räume gerade</div>
            <div class="evlist">${roomsV.map(({ r, v, m }) => {
              const hot = ["vorheizen", "boost"].includes(m) || (v ?? 0) >= Number(p.demand_valve ?? 15);
              return `<div class="ev ${hot ? "live" : ""}"><ha-icon icon="${hot ? "mdi:fire" : "mdi:valve-closed"}"></ha-icon><span class="grow"><b>${esc(r.name)}</b><small>${v != null ? `Ventil ${fmt(v, 0)} %` : "ohne Ventilwert"}${["vorheizen", "boost"].includes(m) ? ` · ${MODE[m]?.label || m}` : ""}</small></span>${hot ? `<em class="badge">BRAUCHT WÄRME</em>` : ""}</div>`;
            }).join("") || `<p class="muted small">Kein Raum meldet eine Ventilöffnung – dann entscheidet die Raumtemperatur.</p>`}</div>
            <p class="muted small"><ha-icon icon="mdi:alert-outline"></ha-icon>Bitte vorsichtig einstellen: Absenken wirkt über die Heizkurve auf die Vorlauftemperatur. Bei Vaillant (myVaillant) setzt Hauswerk dafür eine zeitlich begrenzte Temperatur-Schnellwahl und erneuert sie bei Bedarf alle 30 Min. Alles steht im Protokoll unter „Ziel & Heizung“.</p>` : ""}`,
        };
      }

      case "protect":
        return {
          icon: "mdi:snowflake-thermometer", c: "#38bdf8", title: "Frostschutz",
          body: `
            <p class="muted">Diese Temperatur bekommen Thermostate bei offenem Fenster und in der Sommerpause (wenn sie nicht ausgeschaltet werden). Wann die Fensterpause beginnt, stellst du je Raum ein.</p>
            <div class="field narrow">${this._stepper("set", "frost_temp", p.frost_temp)}</div>`,
        };

      case "boost":
        return {
          icon: "mdi:rocket-launch-outline", c: "#f43f5e", title: "Boost",
          body: `
            <p class="muted">Der <ha-icon icon="mdi:rocket-launch-outline"></ha-icon>-Knopf auf einer Raumkarte dreht die Thermostate des Raums für eine Weile ganz auf.</p>
            <label class="field narrow"><span>Dauer</span>${minutes("boost_minutes", 30, 5, 240, 5)}</label>`,
        };

      case "liming":
        return {
          icon: "mdi:water-sync", c: "#38bdf8", title: "Entkalkungsschutz",
          body: `
            <label class="check"><span><b>Einmal pro Woche alle Ventile öffnen</b><small>Damit sie über den Sommer nicht festsitzen.</small></span>${sw("liming")}</label>
            ${p.liming ? `
            <div class="row3">
              <label class="field"><span>Tag</span><select data-set="liming_day" ${dis}>${["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
                .map((d, i) => `<option value="${i}" ${Number(p.liming_day ?? 0) === i ? "selected" : ""}>${d}</option>`)
                .join("")}</select></label>
              <label class="field"><span>Uhrzeit</span><input type="time" data-set="liming_time" value="${esc(p.liming_time || "10:00")}" ${dis}></label>
              <label class="field"><span>Dauer</span>${minutes("liming_minutes", 5, 1, 60)}</label>
            </div>
            <label class="check"><span><b>Auch in der Heizperiode</b><small>Sonst nur in der Sommerpause (oder immer, wenn keine Sommerpause genutzt wird).</small></span>${sw("liming_winter")}</label>` : ""}`,
        };

      case "hints": {
        const h = this._hints();
        const row = (x) => {
          const data = Object.entries(x.data).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");
          const can = this._admin || !["room-edit", "plan-open", "plan-sel"].includes(x.action);
          return `<button class="hint ${x.lvl}" ${can ? `data-action="${x.action}" data-hint="1" ${data}` : "disabled"}>
            <span class="sr-ic"><ha-icon icon="${x.icon}"></ha-icon></span>
            <span class="sr-t"><b>${esc(x.text)}</b>${x.sub ? `<small class="wrap">${esc(x.sub)}</small>` : ""}</span>
            ${can ? `<ha-icon class="sr-go" icon="mdi:chevron-right"></ha-icon>` : ""}</button>`;
        };
        const warn = h.filter((x) => x.lvl === "warn"), info = h.filter((x) => x.lvl === "info");
        return {
          icon: h.length ? "mdi:bell-badge-outline" : "mdi:bell-check-outline", c: warn.length ? "#f59e0b" : "#34d399", title: "Hinweise",
          sub: h.length ? `${warn.length} zu beheben · ${info.length} zur Info` : "Alles in Ordnung",
          body: h.length
            ? `${warn.length ? `<div class="lbl">Bitte beheben</div><div class="hints">${warn.map(row).join("")}</div>` : ""}
               ${info.length ? `<div class="lbl" style="margin-top:14px">Gut zu wissen</div><div class="hints">${info.map(row).join("")}</div>` : ""}`
            : `<div class="wok"><ha-icon icon="mdi:check-circle-outline"></ha-icon>Keine Hinweise – alles läuft.</div>`,
          foot: `<button class="secondary" data-action="pop-close">Schließen</button>`,
        };
      }

      case "widget-add": {
        const have = new Set(this._widgets().map((w) => w.type));
        return {
          icon: "mdi:widgets-outline", c: "#2dd4bf", title: "Widget hinzufügen", sub: "Erscheint auf der Startseite für alle Benutzer",
          body: `<div class="wcat">${Object.entries(WIDGETS)
            .map(([k, d]) => `
              <button class="wcat-i" data-action="w-add" data-type="${k}" style="--c:${d.c}">
                <span class="sr-ic"><ha-icon icon="${d.icon}"></ha-icon></span>
                <span class="sr-t"><b>${d.name}${have.has(k) ? ` <em class="badge">SCHON DA</em>` : ""}</b><small class="wrap">${d.text}</small></span>
                <ha-icon class="sr-go" icon="mdi:plus"></ha-icon>
              </button>`)
            .join("")}</div>`,
          foot: `<button class="secondary" data-action="pop-close">Schließen</button>`,
        };
      }

      case "widget": {
        const dr = this._pop.draft;
        const w = this._widgets()[dr.i] || {};
        const def = WIDGETS[w.type] || {};
        return {
          icon: def.icon || "mdi:widgets-outline", c: def.c || "#2dd4bf", title: `Widget „${def.name || ""}“`,
          body: `
            <label class="field"><span>Titel (leer = „${def.name || ""}“)</span><input type="text" maxlength="40" data-pop="title" value="${esc(dr.title)}" placeholder="${esc(def.name || "")}"></label>
            <div class="field"><span>Größe</span>
              <div class="segs small">${[["s", "Klein", "mdi:square-small"], ["m", "Mittel", "mdi:square-outline"], ["l", "Groß", "mdi:rectangle-outline"]]
                .map(([v, l, i]) => `<button class="seg ${dr.size === v ? "on" : ""}" data-action="w-size" data-v="${v}"><ha-icon icon="${i}"></ha-icon>${l}</button>`)
                .join("")}</div>
              <small class="muted">${{ s: "Klein: nur das Wichtigste auf einen Blick.", m: "Mittel: mit Kennzahlen bzw. Liste.", l: "Groß: volle Breite mit allen Einzelheiten." }[dr.size] || ""}</small></div>
            ${def.forecast ? `
            <div class="field"><span>Zeitraum</span>
              <div class="segs small">${[["hourly", "Nächste Stunden", "mdi:clock-outline"], ["daily", "Nächste Tage", "mdi:calendar-week"]]
                .map(([v, l, i]) => `<button class="seg ${(dr.mode || "hourly") === v ? "on" : ""}" data-action="w-mode" data-v="${v}"><ha-icon icon="${i}"></ha-icon>${l}</button>`)
                .join("")}</div></div>
            <div class="field"><span>Wetter-Entität (leer = wie unter Einstellungen › Wetter)</span>${this._picker("w_weather", dr.w_weather ? [dr.w_weather] : [])}</div>
            <p class="muted small">Kann die Entität keine Stunden-Prognose, zeigt das Widget die Tage (und umgekehrt).</p>` : ""}
            ${def.config ? `
            <div class="field"><span>${w.type === "shortcuts" ? "Knöpfe: Szenen, Skripte, Schalter, Lichter …" : "Sensoren und andere Entitäten"}</span>${this._picker("w_entities", dr.w_entities || [])}</div>
            <p class="muted small">${w.type === "shortcuts" ? "Ein Tipp schaltet um bzw. startet Skript oder Szene. Es gelten die Rechte des angemeldeten Benutzers." : "Zeigt den aktuellen Wert mit Einheit."}</p>` : ""}`,
          foot: `<button class="secondary" data-action="pop-close">Abbrechen</button><button class="primary" data-action="w-save"><ha-icon icon="mdi:content-save-outline"></ha-icon>Speichern</button>`,
        };
      }

      case "weather": {
        const S = this._hass.states;
        const weathers = Object.keys(S).filter((e) => e.startsWith("weather.")).sort();
        const wid = p.weather_entity || weathers[0];
        const w = wid ? S[wid] : null;
        const a = w?.attributes || {};
        const sunId = p.sun_entity || "sun.sun";
        const sun = S[sunId];
        const sa = sun?.attributes || {};
        const label = (WEATHER[w?.state] || [null, w?.state || "–"])[1];
        const own = p.outside_sensor && S[p.outside_sensor] ? parseFloat(S[p.outside_sensor].state) : null;
        const tNow = own ?? a.temperature;
        const hhmm = (iso) => (iso ? new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "–");
        const unit = a.wind_speed_unit || "km/h";
        const help = this._help || {};
        const row = (key, title, sub, value, text, ctl = false) => `
          <div class="wxr ${ctl ? "ctl" : ""}">
            <div class="wxr-l"><b>${title}<button class="qm ${help[key] ? "on" : ""}" data-action="help" data-k="${key}" aria-label="Erklärung zu ${title}">?</button></b>${sub ? `<small>${sub}</small>` : ""}${help[key] ? `<p class="wxr-h">${text}</p>` : ""}</div>
            <div class="wxr-v">${value}</div>
          </div>`;
        const num = (key, def, min, max, step, u) =>
          `<div class="unit"><input type="number" step="${step}" min="${min}" max="${max}" data-set="${key}" value="${p[key] ?? def}" ${dis}><i>${u}</i></div>`;
        const alerts = this._wxAlerts();
        return {
          icon: "mdi:weather-partly-cloudy", c: "#60a5fa", title: "Wetter", sub: "Hauswerk · für Startseite, Widgets und alle Module",
          body: `
            <div class="wxsrcs">
              <div class="wxsrc">${row("src", "Wetterquelle", p.weather_entity ? "gewählt" : weathers.length ? `automatisch: ${esc(this._entityName(weathers[0]))}` : "keine gefunden", "",
                "Die Wetter-Entität (z. B. OpenWeatherMap, Met.no) liefert Wetterlage, Vorhersage, Wind und Luftfeuchte. Leer = die erste gefundene.")}
              <div class="wxr-pk">${this._picker("weather_entity", p.weather_entity ? [p.weather_entity] : [])}</div></div>
              <div class="wxsrc">${row("out", "Außentemperatur von", p.outside_sensor ? "eigene Wetterstation statt Wetterdienst" : "leer = vom Wetterdienst", "",
                "Ein eigener Temperatursensor misst meist genauer als der Wetterdienst. Die Vorhersage kommt weiterhin vom Wetterdienst. Heizwerk nutzt ihn auch für die Sommerpause nach Außentemperatur.")}
              <div class="wxr-pk">${this._picker("outside_sensor", p.outside_sensor ? [p.outside_sensor] : [])}</div></div>
              <div class="wxsrc">${row("sunsrc", "Sonnenstand", sun ? "für Tageszeit, Sonnenauf- und -untergang" : "nicht gefunden – Integration „Sonne“ hinzufügen", "",
                "Die Entität der Home-Assistant-Integration „Sonne“ (meist sun.sun). Hauswerk nutzt sie für die Darstellung nach Tageszeit, Sonnenauf- und -untergang und für die Rollläden (Rollwerk).")}
              <div class="wxr-pk">${this._picker("sun_entity", [p.sun_entity || (S["sun.sun"] ? "sun.sun" : null)].filter(Boolean))}</div></div>
              <div class="wxsrc">${row("windsrc", "Böen von", p.wind_sensor ? "eigener Windsensor" : "leer = vom Wetterdienst", "",
                "Ein eigener Wind- oder Böen-Sensor (z. B. Wetterstation auf dem Dach). Rollwerk nutzt ihn für den Sturmschutz der Rollläden.")}
              <div class="wxr-pk">${this._picker("wind_sensor", p.wind_sensor ? [p.wind_sensor] : [])}</div></div>
            </div>
            ${head("mdi:clock-outline", "Jetzt")}
            ${w ? `
            <div class="wxrows">
              ${row("now", "Aktuell", a.apparent_temperature != null ? `gefühlt ${fmt(a.apparent_temperature)} °C` : own != null ? "Temperatur von der eigenen Station" : "", `${esc(label)} · ${fmt(tNow)} °C`,
                "Wetterlage laut Wetterdienst, Temperatur von der eigenen Station (falls gewählt). „Gefühlt“ berücksichtigt Wind und Feuchte.")}
              ${row("hum", "Feuchte", "", a.humidity != null ? `${fmt(a.humidity, 0)} %` : "–", "Relative Luftfeuchte draußen laut Wetterdienst.")}
              ${row("wind", "Wind", a.wind_gust_speed != null ? `Böen ${fmt(a.wind_gust_speed)} ${esc(unit)}` : "", a.wind_speed != null ? `${fmt(a.wind_speed)} ${esc(unit)}` : "–",
                "Mittlere Windgeschwindigkeit laut Wetterdienst; Böen, falls der Dienst sie liefert.")}
              ${row("sun", "Sonne", sun ? `Höhe ${fmt(sa.elevation)}°` : `${esc(sunId)} fehlt`, sun ? (sun.state === "above_horizon" ? "über dem Horizont" : "unter dem Horizont") : "–",
                "Aus der Home-Assistant-Integration „Sonne“ (oben unter „Sonnenstand“ wählbar). Hauswerk nutzt sie für die Darstellung nach Tageszeit und für die Rollläden (Rollwerk).")}
              ${row("rise", "Sonnenaufgang", "nächster Sonnenaufgang", hhmm(sa.next_rising), "Nächster Sonnenaufgang laut Sonnenstand-Entität.")}
              ${row("set", "Sonnenuntergang", "nächster Sonnenuntergang", hhmm(sa.next_setting), "Nächster Sonnenuntergang laut Sonnenstand-Entität.")}
            </div>` : `<p class="note warn"><ha-icon icon="mdi:weather-cloudy-alert"></ha-icon>Keine Wetter-Entität gefunden – z. B. die Integration „Met.no“ oder „OpenWeatherMap“ einrichten.</p>`}
            ${head("mdi:alert-outline", "Grenzwerte")}
            <div class="wxrows">
              ${row("limit", "Heizgrenze", p.summer_mode === "auto" ? "darunter gilt die Heizsaison" : "nur bei Saison „Nach Außentemperatur“",
                `<button class="link" data-action="settings-go" data-sub="season">${fmt(p.summer_temp ?? 16)} °C</button>`,
                "Ab dieser Außentemperatur macht Heizwerk Sommerpause (1 °C Hysterese). Einstellbar unter Heizwerk › Einstellungen › Saison.")}
              ${row("cold", "Kälteeinbruch", "Vorhersage unter diesem Wert", num("cold_snap_temp", 0, -30, 25, 0.5, "°C"),
                "Sagt die Vorhersage der nächsten 3 Tage einen Tiefstwert unter dieser Grenze voraus, erscheint ein Hinweis unter der Glocke.", true)}
              ${row("storm", "Sturm", "Böen ab dieser Stärke", num("storm_kmh", 70, 20, 200, 5, "km/h"),
                "Erwartet die Vorhersage der nächsten 24 Stunden Böen (oder Wind) ab dieser Stärke, erscheint ein Hinweis unter der Glocke.", true)}
            </div>
            ${alerts.length ? `<div class="lbl">Gerade aktiv</div><div class="evlist">${alerts.map((x) => `<div class="ev live"><ha-icon icon="${x.icon}"></ha-icon><span class="grow"><b>${esc(x.text)}</b><small>${esc(x.sub)}</small></span></div>`).join("")}</div>` : ""}`,
        };
      }

      case "look": {
        const acc = p.look_accent || null;
        const known = ACCENTS.some(([v]) => v === acc);
        const bg = p.look_background || "pattern";
        const now = this._skyPhase();
        const size = this._lookSize();
        const bgText = {
          pattern: "Dezentes Muster je Bereich: Glut und aufsteigende Wärme bei Heizwerk, Punkte auf der Startseite.",
          daytime: "Die Kopfzeile folgt dem Sonnenstand (sun.sun, sonst der Uhrzeit): Nacht, Sonnenaufgang, Tag und Sonnenuntergang.",
          plain: "Ruhiger, einfarbiger Hintergrund – gut für Wand-Tablets.",
        }[bg];
        return {
          icon: "mdi:palette-outline", c: "#a78bfa", title: "Darstellung", sub: "Hauswerk · für alle Module und Benutzer",
          body: `
            ${head("mdi:theme-light-dark", "Design")}
            <div class="field">${segs("look_theme", [["auto", "Wie Home Assistant", "mdi:home-assistant"], ["light", "Hell", "mdi:white-balance-sunny"], ["dark", "Dunkel", "mdi:weather-night"]], "auto")}</div>
            ${head("mdi:palette-outline", "Akzentfarbe")}
            <div class="swatches">
              ${ACCENTS.map(([v, name, show]) => `<button class="sw ${acc === v ? "on" : ""}" style="--c:${show || v}" data-action="look-accent" data-v="${v || ""}" title="${name}" aria-label="${name}" ${dis}></button>`).join("")}
              <label class="sw custom ${known ? "" : "on"}" style="--c:${known ? "#94a3b8" : acc}" title="Eigene Farbe"><input type="color" data-look-color value="${known ? "#14b8a6" : acc}" aria-label="Eigene Farbe" ${dis}></label>
              <span class="muted small">Eigene</span>
            </div>
            ${head("mdi:image-filter-hdr", "Hintergrund")}
            <div class="field">${segs("look_background", [["pattern", "Muster", "mdi:texture-box"], ["daytime", "Tageszeit", "mdi:weather-sunset"], ["plain", "Schlicht", "mdi:square-rounded-outline"]], "pattern")}</div>
            <p class="muted small">${bgText}</p>
            ${bg === "daytime" ? `<div class="skies">${SKIES.map(([k, l]) => `<div class="skyc"><div class="sky ${k === now ? "on" : ""}" style="background:var(--sky-${k})">${k === now ? "<em>jetzt</em>" : ""}</div><small>${l}</small></div>`).join("")}</div>` : ""}
            ${head("mdi:page-layout-header", "Kopfzeile")}
            <label class="check"><span><b>Wetter anzeigen</b><small>Außentemperatur und Wetterlage oben rechts. Die Quelle stellst du unter Hauswerk › Wetter ein.</small></span>${sw("look_header_weather")}</label>
            <label class="check"><span><b>Uhrzeit anzeigen</b><small>Praktisch für Wand-Tablets. Auf dem Handy ausgeblendet.</small></span>${sw("look_header_clock")}</label>
            ${head("mdi:cellphone-cog", "Auf diesem Gerät")}
            <div class="field"><span>Größe</span><div class="segs small">${[["s", "Kompakt", "mdi:format-font-size-decrease"], ["m", "Normal", "mdi:format-size"], ["l", "Groß", "mdi:format-font-size-increase"]]
              .map(([v, l, i]) => `<button class="seg ${size === v ? "on" : ""}" data-action="look-size" data-v="${v}"><ha-icon icon="${i}"></ha-icon>${l}</button>`)
              .join("")}</div></div>
            <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Die Größe gilt nur für dieses Gerät und sofort – z. B. größer auf dem Wand-Tablet, kompakter am Handy. Alles andere gilt nach dem Speichern für alle.</p>`,
        };
      }

      case "access":
        return {
          icon: "mdi:shield-account-outline", c: "#94a3b8", title: "Berechtigungen", sub: "Hauswerk · gilt für alle Module",
          body: `
            <p class="muted">Wer darf Einstellungen, Widgets, Räume und Heizpläne ändern? Temperatur ±, Boost und „Zurück zum Plan“ dürfen immer alle.</p>
            <label class="check"><span><b>Alle Benutzer dürfen ändern</b><small>Sinnvoll z. B. für ein Wand-Tablet mit eigenem Benutzer ohne Admin-Rechte.</small></span>
              <span class="switch"><input type="checkbox" data-set="allow_users" ${p.allow_users ? "checked" : ""} ${this._data.user_admin ? "" : "disabled"}><span></span></span></label>
            ${this._data.user_admin ? "" : `<p class="muted small"><ha-icon icon="mdi:lock-outline"></ha-icon>Das kann nur ein Administrator umstellen.</p>`}`,
        };

      case "calibration":
        return {
          icon: "mdi:tune-vertical-variant", c: "#a78bfa", title: "Kalibrierung",
          body: `
            <p class="muted">Gilt für Räume mit „Thermostat kalibrieren“: so oft wird der Offset am Gerät höchstens angepasst. Seltener schont die Batterien.</p>
            <label class="field narrow"><span>Höchstens alle</span>${minutes("calibration_interval", 10, 1, 120)}</label>`,
        };

      case "import": {
        const dr = this._pop.draft;
        const res = dr.result;
        return {
          icon: "mdi:calendar-import", c: "#60a5fa", title: "Aus Kalender importieren", sub: "Termine der nächsten 7 Tage werden Komfortzeiten",
          body: `
            <div class="field"><span><ha-icon icon="mdi:calendar"></ha-icon> Kalender</span>${this._picker("import_calendar", dr.import_calendar ? [dr.import_calendar] : [])}</div>
            <label class="field"><span><ha-icon icon="mdi:text-search"></ha-icon> Nur Termine mit diesen Wörtern (leer = alle)</span><input type="text" maxlength="200" data-pop="keyword" value="${esc(dr.keyword || "")}" placeholder="z. B. Homeoffice, Heizen"></label>
            <p class="muted small">Gleiche Uhrzeiten an mehreren Tagen werden zu einem Zeitfenster. Ganztägige Termine werden übersprungen. Danach kannst du alles wie gewohnt anpassen.</p>
            <button class="secondary wide" data-action="import-read" ${dr.import_calendar ? "" : "disabled"}><ha-icon icon="mdi:calendar-search"></ha-icon>Termine lesen</button>
            ${res ? `
            <div class="lbl" style="margin-top:16px">${res.length ? `${res.length} Zeitfenster gefunden` : "Keine passenden Termine gefunden"}</div>
            <div class="evlist">${res.map((b) => `<div class="ev"><ha-icon icon="mdi:clock-outline"></ha-icon><span class="grow"><b>${esc(b.start)} – ${esc(b.end)}</b><small>${b.days.map((d) => DAYS[d]).join(", ")}</small></span></div>`).join("")}</div>` : ""}`,
          foot: `<button class="secondary" data-action="pop-close">Abbrechen</button>
            ${res && res.length ? `<button class="secondary" data-action="import-apply" data-mode="append"><ha-icon icon="mdi:plus"></ha-icon>Hinzufügen</button>
            <button class="primary" data-action="import-apply" data-mode="replace"><ha-icon icon="mdi:swap-horizontal"></ha-icon>Ersetzen</button>` : ""}`,
        };
      }
    }
    return { icon: "mdi:cog", c: "#94a3b8", title: "Einstellung", body: "" };
  }
  // ------------------------------------------------------------ Raum-Dialog
  _expertOn() {
    if (this._expert == null) {
      try {
        this._expert = (localStorage.getItem("hauswerk.experte") ?? localStorage.getItem("heizwerk.experte")) === "1";
      } catch (e) {
        this._expert = false;
      }
    }
    return this._expert;
  }

  // ------------------------------------------------------------ Raum-Assistent
  /** Entitäten eines Home-Assistant-Bereichs (direkt oder über das Gerät zugeordnet). */
  _areaEntities(areaId) {
    const E = this._hass.entities || {};
    const D = this._hass.devices || {};
    return Object.keys(this._hass.states).filter((id) => {
      const e = E[id];
      if (!e || e.hidden || e.entity_category) return false;
      return (e.area_id || D[e.device_id]?.area_id) === areaId;
    });
  }

  /** Was der Assistent in einem Bereich findet: Thermostate, Fenster, Sensoren, Fußbodenheizung. */
  _wizScan(areaId) {
    const used = new Set(this._rooms().flatMap((r) => r.climates || []));
    const ids = areaId ? this._areaEntities(areaId) : [];
    const S = this._hass.states;
    const dc = (id) => S[id]?.attributes?.device_class;
    const dom = (id) => id.split(".")[0];
    const climates = ids.filter((id) => dom(id) === "climate" && this._devType(id) !== "Wärmeerzeuger");
    return {
      climates,
      free: climates.filter((id) => !used.has(id)),
      windows: ids.filter((id) => dom(id) === "binary_sensor" && ["window", "door", "opening", "garage_door"].includes(dc(id))),
      temps: ids.filter((id) => dom(id) === "sensor" && dc(id) === "temperature"),
      hums: ids.filter((id) => dom(id) === "sensor" && dc(id) === "humidity"),
      floor: ids.filter((id) => this._devType(id) === "Fußbodenheizung"),
    };
  }

  _wizOpen() {
    this._openPop("rwiz", { step: 0, area: null, name: "", use: null, type: "heizkoerper", climates: [], assist: [], windows: [], temp: null, hum: null, show: [],
      comfort: 21, eco: 18, plan: this._planList()[0]?.id ? `plan:${this._planList()[0].id}` : "preset:berufstaetig", open: false });
  }

  /** Bereich gewählt: Name und gefundene Geräte übernehmen, Nutzung am Namen erraten. */
  _wizArea(areaId) {
    const d = this._pop.draft;
    const area = this._hass.areas?.[areaId];
    const f = this._wizScan(areaId);
    const name = area?.name || "";
    const use = WIZ_USES.find((u) => u.match.test(name.toLowerCase()));
    Object.assign(d, { area: areaId, name, climates: f.free.length ? f.free : f.climates, windows: f.windows, temp: f.temps[0] || null, hum: f.hums[0] || null, show: f.floor, assist: [] });
    if (f.floor.length) d.type = "flaeche";
    if (use) this._wizUse(use.id);
  }

  _wizUse(id) {
    const d = this._pop.draft;
    const u = WIZ_USES.find((x) => x.id === id);
    if (!u) return;
    Object.assign(d, { use: id, comfort: u.comfort, eco: u.eco });
    if (!d.plan?.startsWith("plan:")) d.plan = `preset:${u.plan}`;
  }

  _wizPop() {
    const d = this._pop.draft;
    const steps = ["Raum", "Nutzung", "Heizung", "Geräte", "Zeiten", "Fertig"];
    const S = this._hass.states;
    const name = (id) => esc(this._entityName(id));
    const bar = `<div class="wiz-bar">${steps.map((s, i) => `<button class="wiz-dot ${i === d.step ? "on" : i < d.step ? "done" : ""}" data-action="wiz-go" data-i="${i}" ${i > d.step && !this._wizOk(i - 1) ? "disabled" : ""}><i>${i < d.step ? "✓" : i + 1}</i><span>${s}</span></button>`).join("")}</div>`;
    const tick = (on) => `<ha-icon icon="${on ? "mdi:checkbox-marked" : "mdi:checkbox-blank-outline"}"></ha-icon>`;
    const devRow = (k, id, on, extra = "") => `<button class="wiz-dev ${on ? "on" : ""}" data-action="wiz-tog" data-k="${k}" data-id="${esc(id)}">${tick(on)}<span class="grow"><b>${esc(this._devType(id))}</b><small>${name(id)} · ${esc(this._fmtState(S[id]))}${this._areaOf(id) && !d.area ? ` · ${esc(this._areaOf(id))}` : ""}</small></span>${extra}</button>`;
    const radio = (k, id, label) => `<button class="wiz-dev ${d[k] === id ? "on" : ""}" data-action="wiz-one" data-k="${k}" data-id="${esc(id || "")}"><ha-icon icon="${d[k] === id ? "mdi:radiobox-marked" : "mdi:radiobox-blank"}"></ha-icon><span class="grow"><b>${label}</b>${id ? `<small>${name(id)}</small>` : ""}</span></button>`;
    let body = "";
    switch (d.step) {
      case 0: {
        const areas = Object.values(this._hass.areas || {}).sort((a, b) => a.name.localeCompare(b.name, "de"));
        const taken = new Set(this._rooms().map((r) => r.name.toLowerCase()));
        body = `<p class="muted">Welcher Raum soll geheizt werden? Wähle einen Bereich aus Home Assistant – Thermostate, Fenster und Sensoren darin sucht der Assistent dann selbst.</p>
          <div class="wiz-areas">${areas.map((a) => {
            const f = this._wizScan(a.area_id);
            const done = taken.has(a.name.toLowerCase()) || (f.climates.length && !f.free.length);
            return `<button class="wiz-area ${d.area === a.area_id ? "on" : ""} ${done ? "done" : ""}" data-action="wiz-area" data-id="${esc(a.area_id)}">
              <ha-icon icon="${a.icon || "mdi:door"}"></ha-icon><b>${esc(a.name)}</b>
              <small>${done ? "schon angelegt" : f.climates.length ? `${f.climates.length} Thermostat${f.climates.length > 1 ? "e" : ""}${f.windows.length ? ` · ${f.windows.length} Fenster` : ""}` : "kein Thermostat"}</small></button>`;
          }).join("")}</div>
          <label class="field"><span><ha-icon icon="mdi:form-textbox"></ha-icon> Name des Raums</span><input type="text" data-wiz="name" value="${esc(d.name)}" placeholder="z. B. Wohnzimmer" maxlength="40"></label>
          ${!areas.length ? `<p class="muted small">In Home Assistant sind keine Bereiche angelegt – dann einfach einen Namen eingeben, die Geräte wählst du im übernächsten Schritt.</p>` : ""}`;
        break;
      }
      case 1:
        body = `<p class="muted">Wofür wird <b>${esc(d.name)}</b> genutzt? Daraus schlägt der Assistent Temperaturen und Heizzeiten vor – ändern kannst du alles.</p>
          <div class="wiz-areas">${WIZ_USES.map((u) => `<button class="wiz-area ${d.use === u.id ? "on" : ""}" data-action="wiz-use" data-id="${u.id}"><ha-icon icon="${u.icon}"></ha-icon><b>${u.label}</b><small>${fmt(u.comfort)} / ${fmt(u.eco)} °C</small></button>`).join("")}</div>`;
        break;
      case 2: {
        const opt = (v, icon, t, s) => `<button class="wiz-type ${d.type === v ? "on" : ""}" data-action="wiz-type" data-v="${v}"><ha-icon icon="${icon}"></ha-icon><span><b>${t}</b><small>${s}</small></span></button>`;
        body = `<p class="muted">Wie wird ${esc(d.name)} beheizt?</p>
          ${opt("heizkoerper", "mdi:radiator", "Heizkörper", "reagiert schnell: kurze Vorheizzeit, Pause schon nach 1 Minute offenem Fenster")}
          ${opt("flaeche", "mdi:heating-coil", "Fußbodenheizung", "träge: lange Vorheizzeit, wenig Absenkung, Pause erst nach 15 Minuten offenem Fenster")}
          ${opt("misch", "mdi:home-thermometer", "Fußbodenheizung + Heizkörper", "Wandthermostat regelt die Fußbodenheizung, Heizkörper helfen nur bei Bedarf (Mischbetrieb)")}`;
        break;
      }
      case 3: {
        const f = this._wizScan(d.area);
        const used = new Set(this._rooms().flatMap((r) => r.climates || []));
        const other = Object.keys(S).filter((id) => id.startsWith("climate.") && !f.climates.includes(id) && !used.has(id) && this._devType(id) !== "Wärmeerzeuger")
          .sort((a, b) => this._entityName(a).localeCompare(this._entityName(b), "de"));
        const chosen = new Set(d.climates);
        const extra = d.climates.filter((id) => !f.climates.includes(id));
        const asst = (id) => d.type === "misch" && chosen.has(id) && this._thermoKind(id) !== "wall"
          ? `<em class="wiz-role ${d.assist.includes(id) ? "on" : ""}" data-action="wiz-assist" data-id="${esc(id)}">${d.assist.includes(id) ? "Zusatz" : "folgt Wand"}</em>` : "";
        const wins = Object.keys(S).filter((id) => id.startsWith("binary_sensor.") && ["window", "door", "opening"].includes(S[id].attributes?.device_class));
        const winOther = wins.filter((id) => !f.windows.includes(id) && d.windows.includes(id));
        body = `<div class="lbl">Thermostate</div>
          ${f.climates.length ? f.climates.map((id) => devRow("climates", id, chosen.has(id), asst(id))).join("") : `<p class="muted small">In ${esc(d.name || "diesem Bereich")} hat der Assistent kein Thermostat gefunden.</p>`}
          ${extra.map((id) => devRow("climates", id, true, asst(id))).join("")}
          ${other.length ? `<label class="field"><span><ha-icon icon="mdi:plus"></ha-icon> Anderes Thermostat hinzufügen</span><select data-wiz-add="climates"><option value="">wählen …</option>${other.filter((id) => !chosen.has(id)).map((id) => `<option value="${esc(id)}">${name(id)}${this._areaOf(id) ? ` (${esc(this._areaOf(id))})` : ""}</option>`).join("")}</select></label>` : ""}
          ${d.type === "misch" ? `<p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Tippe bei einem Heizkörper auf „folgt Wand“, um ihn zur <b>Zusatzheizung</b> zu machen (in der CCU vorher aus der Heizgruppe nehmen). Die anderen folgen weiter dem Wandthermostat.</p>` : ""}
          <div class="lbl">Fenster & Türen</div>
          ${f.windows.map((id) => devRow("windows", id, d.windows.includes(id))).join("")}${winOther.map((id) => devRow("windows", id, true)).join("")}
          ${!f.windows.length ? `<p class="muted small">Keine Kontakte im Bereich – ohne Kontakt erkennt Hauswerk offene Fenster am Temperatursturz.</p>` : ""}
          <label class="field"><span><ha-icon icon="mdi:plus"></ha-icon> Anderen Kontakt hinzufügen</span><select data-wiz-add="windows"><option value="">wählen …</option>${wins.filter((id) => !d.windows.includes(id)).map((id) => `<option value="${esc(id)}">${name(id)}${this._areaOf(id) ? ` (${esc(this._areaOf(id))})` : ""}</option>`).join("")}</select></label>
          ${f.temps.length ? `<div class="lbl">Raumtemperatur messen mit</div>${radio("temp", null, "dem Thermostat")}${f.temps.map((id) => radio("temp", id, this._devType(id))).join("")}` : ""}
          ${f.hums.length ? `<div class="lbl">Luftfeuchte</div>${radio("hum", null, "keine")}${f.hums.map((id) => radio("hum", id, this._devType(id))).join("")}` : ""}
          ${f.floor.length ? `<div class="lbl">Nur anzeigen</div>${f.floor.map((id) => devRow("show", id, d.show.includes(id))).join("")}` : ""}`;
        break;
      }
      case 4: {
        const plans = this._planList();
        const step = (k) => `<div class="wiz-temp"><button class="sbtn" data-action="wiz-t" data-k="${k}" data-d="-0.5">−</button><b>${fmt(d[k])} °C</b><button class="sbtn" data-action="wiz-t" data-k="${k}" data-d="0.5">+</button></div>`;
        const planBtn = (v, t, s) => `<button class="wiz-dev ${d.plan === v ? "on" : ""}" data-action="wiz-plan" data-v="${v}"><ha-icon icon="${d.plan === v ? "mdi:radiobox-marked" : "mdi:radiobox-blank"}"></ha-icon><span class="grow"><b>${t}</b><small>${s}</small></span></button>`;
        const blocks = (b) => b.map((x) => `${x.days.length === 7 ? "täglich" : x.days.length === 5 && x.days[0] === 0 ? "Mo–Fr" : x.days.length === 2 && x.days[0] === 5 ? "Sa–So" : x.days.map((i) => "MDMDFSS"[i]).join("")} ${x.start}–${x.end}`).join(" · ");
        body = `<div class="wxrows">
            <div class="wxr"><div class="wxr-l"><b>Komfort</b><small>wenn jemand im Raum ist</small></div><div class="wxr-v">${step("comfort")}</div></div>
            <div class="wxr"><div class="wxr-l"><b>Eco</b><small>nachts und tagsüber ohne Nutzung</small></div><div class="wxr-v">${step("eco")}</div></div>
          </div>
          <div class="lbl">Heizzeiten (Komfort)</div>
          ${plans.map((p) => planBtn(`plan:${p.id}`, `Plan „${esc(p.name)}“`, `gemeinsam mit anderen Räumen${p.calendar ? " · aus Kalender" : ""}`)).join("")}
          ${Object.entries(PLAN_PRESETS).map(([k, p]) => planBtn(`preset:${k}`, `Eigener Plan: ${esc(p.label)}`, blocks(p.blocks))).join("")}
          <p class="muted small">Die Zeiten kannst du danach unter <i>Heizpläne</i> genau einstellen.</p>`;
        break;
      }
      case 5: {
        const plan = d.plan.startsWith("plan:") ? `Plan „${esc(this._data.plans?.[d.plan.slice(5)]?.name || "")}“` : esc(PLAN_PRESETS[d.plan.slice(7)]?.label || "");
        const line = (icon, t, v) => `<div class="kv"><ha-icon icon="${icon}"></ha-icon><span>${t}</span><b>${v}</b></div>`;
        const warn = !d.climates.length;
        body = `<div class="wiz-sum">
            ${line("mdi:door", "Raum", esc(d.name))}
            ${line("mdi:radiator", "Heizung", { heizkoerper: "Heizkörper", flaeche: "Fußbodenheizung", misch: "Fußbodenheizung + Heizkörper" }[d.type])}
            ${line("mdi:thermostat", "Thermostate", d.climates.length ? `${d.climates.length}${d.assist.length ? ` (${d.assist.length} Zusatz)` : ""}` : "keins")}
            ${line("mdi:window-open-variant", "Fenster", d.windows.length || "keine")}
            ${line("mdi:thermometer", "Messen mit", d.temp ? name(d.temp) : "Thermostat")}
            ${line("mdi:sofa-outline", "Komfort / Eco", `${fmt(d.comfort)} / ${fmt(d.eco)} °C`)}
            ${line("mdi:calendar-clock", "Heizzeiten", plan)}
          </div>
          ${warn ? `<p class="note warn"><ha-icon icon="mdi:alert-outline"></ha-icon>Ohne Thermostat kann Heizwerk den Raum nicht regeln – du kannst es später unter <i>Geräte</i> eintragen.</p>` : ""}
          <button class="wiz-dev ${d.open ? "on" : ""}" data-action="wiz-open">${tick(d.open)}<span class="grow"><b>Danach alle Einstellungen öffnen</b><small>Vorheizen, Fenster, Regelung, Experte …</small></span></button>`;
        break;
      }
    }
    const last = d.step === steps.length - 1;
    return {
      icon: "mdi:auto-fix", c: "#fb923c", title: "Raum anlegen", sub: `Schritt ${d.step + 1} von ${steps.length} · ${steps[d.step]}`,
      body: bar + body,
      foot: `${d.step ? `<button class="secondary" data-action="wiz-go" data-i="${d.step - 1}"><ha-icon icon="mdi:chevron-left"></ha-icon>Zurück</button>` : `<button class="secondary" data-action="wiz-expert" title="Ohne Assistent: alle Felder auf einmal">Ohne Assistent</button>`}
        ${last ? `<button class="primary" data-action="wiz-save"><ha-icon icon="mdi:check"></ha-icon>Raum anlegen</button>`
          : `<button class="primary" data-action="wiz-go" data-i="${d.step + 1}" ${this._wizOk(d.step) ? "" : "disabled"}>Weiter<ha-icon icon="mdi:chevron-right"></ha-icon></button>`}`,
    };
  }

  /** Darf es nach diesem Schritt weitergehen? */
  _wizOk(step) {
    const d = this._pop?.draft || {};
    if (step === 0) return !!String(d.name || "").trim();
    if (step === 1) return !!d.use;
    return true;
  }

  /** Raum aus dem Assistenten bauen und speichern. */
  async _wizSave() {
    const d = this._pop.draft;
    const room = { name: d.name.trim(), type: d.type === "misch" ? "flaeche" : d.type, comfort: d.comfort, eco: Math.min(d.eco, d.comfort), climates: d.climates, windows: d.windows,
      enabled: true, allow_manual: true, schedule: [] };
    if (d.temp) room.temp_sensor = d.temp;
    if (d.hum) room.humidity_sensor = d.hum;
    if (d.show.length) room.show_entities = d.show;
    if (d.type === "misch" && d.assist.length) room.assist_entities = d.assist;
    if (d.plan.startsWith("plan:")) room.plan_id = d.plan.slice(5);
    else room.schedule = clone(PLAN_PRESETS[d.plan.slice(7)]?.blocks || PLAN_PRESETS.berufstaetig.blocks);
    const saved = await this._saveRoom(room);
    if (!saved) return;
    const open = d.open;
    this._closePop();
    this._toast(`${saved.name} angelegt`);
    if (open) this._openRoom(saved);
  }

  _openRoom(room) {
    this._dialog = {
      room: room
        ? clone(room)
        : { name: "", type: "heizkoerper", comfort: 21, eco: 18, climates: [], windows: [], schedule: clone(PLAN_PRESETS.berufstaetig.blocks), enabled: true, allow_manual: true },
      isNew: !room,
    };
    // Altes Gesamt-Schalter-Feld in die zwei neuen Schalter überführen
    const r = this._dialog.room;
    if (r.allow_manual === false) {
      r.manual_device = r.manual_device ?? false;
      r.manual_ui = r.manual_ui ?? false;
    }
    r.allow_manual = true;
    // Neuer Raum: erster gemeinsamer Plan, falls es einen gibt
    const plans = this._planList();
    if (!room && plans.length) {
      r.plan_id = plans[0].id;
      r.schedule = [];
    }
    this._dialog.schedSrc = r.schedule_entity ? "entity" : this._data.plans?.[r.plan_id] ? "plan" : "own";
    this._renderDialog();
  }

  _renderDialog() {
    const host = this.shadowRoot.getElementById("dialog");
    if (!this._dialog) {
      host.innerHTML = "";
      return;
    }
    const scroll = host.querySelector(".sheet-body")?.scrollTop || 0;
    const r = this._dialog.room;
    const d = this._data.defaults[r.type];
    const tab = this._dialog.tab || "basis";
    const num = (key, unit, step, extra = "") =>
      `<div class="unit"><input type="number" step="${step}" data-room="${key}" value="${r[key] ?? ""}" placeholder="${d[key] ?? 0}" ${extra}><i>${unit}</i></div>`;
    const check = (key, icon, title, text, { on = !!r[key], disabled = false } = {}) =>
      `<label class="check"><ha-icon class="ck-ic" icon="${icon}"></ha-icon><span><b>${title}</b><small>${text}</small></span>
        <span class="switch"><input type="checkbox" data-room="${key}" ${on ? "checked" : ""} ${disabled ? "disabled" : ""}><span></span></span></label>`;
    const segs = (action, current, options) =>
      `<div class="segs small">${options
        .map(([v, l, icon]) => `<button class="seg ${current === v ? "on" : ""}" data-action="${action}" data-v="${v}">${icon ? `<ha-icon icon="${icon}"></ha-icon>` : ""}${l}</button>`)
        .join("")}</div>`;
    const hint = `<p class="muted small"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon>Leere Felder nutzen die Werte für ${TYPES[r.type].label} (grau).</p>`;
    const guessed = roomIcon({ ...r, icon: null });
    // Experten-Einstellungen nur auf Wunsch (gemerkt je Gerät)
    const ex = this._expertOn();
    const expertHint = (keys) => {
      const n = keys.filter((k) => r[k] != null && r[k] !== "" && r[k] !== false && !(Array.isArray(r[k]) && !r[k].length)).length;
      return `<button class="xhint" data-action="expert"><ha-icon icon="mdi:school-outline"></ha-icon><span>${n ? `${n} Experten-Einstellung${n > 1 ? "en" : ""} aktiv` : "Weitere Einstellungen für Experten"}</span><span class="grow"></span>Anzeigen<ha-icon icon="mdi:chevron-right"></ha-icon></button>`;
    };

    // Reiter mit Punkt, sobald dort etwas eingerichtet ist
    const TABS_D = [
      ["basis", "mdi:home-edit-outline", "Raum", false],
      ["devices", "mdi:thermostat", "Geräte", !!r.presence_sensor || !!(r.show_entities || []).length],
      ["window", "mdi:clock-fast", "Vorheizen & Fenster", !!r.window_detect || ["window_delay", "resume_delay", "lead_min", "max_setback", "pause_mode", "preheat_mode", "preheat_max"].some((k) => r[k] != null && r[k] !== "") || r.min_instead_of_off],
      ["control", "mdi:tune-variant", "Regelung", !!(r.compensation || r.calibration || r.valve_control || r.comfort_entity || r.eco_entity || Number(r.off_above) > 0 || Number(r.aggressive_range) > 0)],
    ];

    const views = {
      basis: () => `
        <label class="field"><span>Name</span><input type="text" maxlength="60" data-room="name" value="${esc(r.name)}" placeholder="z. B. Wohnzimmer"></label>
        <div class="field"><span>Symbol</span>
          <div class="icons">
            <button class="ic-pick ${!r.icon ? "on" : ""}" data-action="room-icon" data-v="" title="Automatisch aus dem Namen"><ha-icon icon="${guessed}"></ha-icon><em>Auto</em></button>
            ${ROOM_ICON_CHOICES.map((i) => `<button class="ic-pick ${r.icon === i ? "on" : ""}" data-action="room-icon" data-v="${i}" title="${i.replace("mdi:", "")}"><ha-icon icon="${i}"></ha-icon></button>`).join("")}
          </div>
        </div>
        <div class="field"><span>Heizungsart</span>
          <div class="types">
            ${Object.entries(TYPES)
              .map(([k, t]) => `
              <button class="type ${r.type === k ? "on" : ""}" data-action="room-type" data-type="${k}">
                <ha-icon icon="${t.icon}"></ha-icon><b>${t.label}</b><small>${t.text}</small>
              </button>`)
              .join("")}
          </div>
        </div>
        <div class="row2">
          <div class="field"><span><ha-icon icon="mdi:sofa-outline"></ha-icon> Komfort</span>${this._stepper("dlg", "comfort", r.comfort)}</div>
          <div class="field"><span><ha-icon icon="mdi:leaf"></ha-icon> Eco</span>${this._stepper("dlg", "eco", r.eco)}</div>
        </div>
        ${this._schedField(r, segs)}
        ${check("enabled", "mdi:robot-outline", "Automatik aktiv", "Aus: Heizwerk lässt die Thermostate dieses Raums in Ruhe.", { on: r.enabled !== false })}`,

      devices: () => `
        <div class="field"><span><ha-icon icon="mdi:thermostat"></ha-icon> Thermostate – Heizwerk stellt diese ein (z. B. das Wandthermostat)</span>${this._picker("climates", r.climates || [])}</div>
        ${(r.climates || []).length > 1 ? this._rolesBlock(r) : ""}
        <div class="field"><span><ha-icon icon="mdi:eye-outline"></ha-icon> Weitere Geräte – nur anzeigen</span>${this._picker("show_entities", r.show_entities || [])}</div>
        <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Z. B. Heizkörper-Thermostat oder Stellantrieb der Fußbodenheizung: Heizwerk zeigt Ventilöffnung und Werte an der Raumkarte und auf der Raumseite, stellt aber nichts daran ein.</p>
        <div class="field"><span><ha-icon icon="mdi:window-closed-variant"></ha-icon> Fenster- und Türkontakte</span>${this._picker("windows", r.windows || [])}</div>
        <div class="row2">
          <div class="field"><span><ha-icon icon="mdi:thermometer"></ha-icon> Raumtemperatur</span>${this._picker("temp_sensor", r.temp_sensor ? [r.temp_sensor] : [])}</div>
          <div class="field"><span><ha-icon icon="mdi:water-percent"></ha-icon> Luftfeuchte</span>${this._picker("humidity_sensor", r.humidity_sensor ? [r.humidity_sensor] : [])}</div>
        </div>
        <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Raumtemperatur und Luftfeuchte sind optional. Ohne Raumsensor nutzt Heizwerk den Messwert der Thermostate.</p>
        ${r.humidity_sensor ? `
        <div class="sub-h"><ha-icon icon="mdi:shower-head"></ha-icon>Nach dem Duschen</div>
        <div class="row2">
          <label class="field"><span>Nachheizen (0 = aus)</span><div class="unit"><input type="number" step="5" min="0" max="120" data-room="shower_boost" value="${r.shower_boost ?? ""}" placeholder="0"><i>Min.</i></div></label>
          <label class="field"><span>wenn die Luftfeuchte steigt um</span><div class="unit"><input type="number" step="1" min="3" max="40" data-room="shower_rise" value="${r.shower_rise ?? ""}" placeholder="10"><i>%-Punkte in 15 Min.</i></div></label>
        </div>
        <p class="muted small">Steigt die Feuchte so schnell (Duschen, Baden), heizt Heizwerk den Raum für diese Zeit auf Komfort – damit Wände und Handtücher trocknen. Höchstens einmal pro Stunde.</p>` : ""}
        <div class="sub-h"><ha-icon icon="mdi:motion-sensor"></ha-icon>Präsenzmelder im Raum <span class="muted small">· optional</span></div>
        <div class="field">${this._picker("presence_sensor", r.presence_sensor ? [r.presence_sensor] : [])}</div>
        ${r.presence_sensor ? `
        <div class="field"><span>Wann heizen</span>
          ${segs("presence-mode", r.presence_mode || "plan", [["plan", "In Komfortzeiten, wenn jemand da ist", "mdi:calendar-account-outline"], ["always", "Immer, sobald jemand da ist", "mdi:account-check-outline"]])}
        </div>
        <div class="row2">
          <label class="field"><span><ha-icon icon="mdi:account-arrow-right-outline"></ha-icon> Belegt nach</span>${num("presence_on", "Min.", 1, 'min="0" max="240"')}</label>
          <label class="field"><span><ha-icon icon="mdi:account-arrow-left-outline"></ha-icon> Leer nach</span>${num("presence_off", "Min.", 1, 'min="0" max="240"')}</label>
        </div>
        <div class="field"><span><ha-icon icon="mdi:calendar-clock"></ha-icon> Nur berücksichtigen, solange an (optional)</span>${this._picker("presence_schedule", r.presence_schedule ? [r.presence_schedule] : [])}</div>` : `<p class="muted small">Mit Präsenzmelder bleibt der Raum während der Komfortzeit auf Eco, solange niemand darin ist.</p>`}
        <p class="muted small"><ha-icon icon="mdi:home-account"></ha-icon>Wer zu Hause ist (Personen, Abwesend, Urlaub), gilt für das ganze Haus: Hauswerk › Einstellungen › Anwesenheit.</p>`,

      window: () => `
        ${hint}
        ${this._preheatSection(r, d, num, segs, ex)}
        <div class="sub-h"><ha-icon icon="mdi:window-open-variant"></ha-icon>Fenster</div>
        <div class="field"><span>Bei offenem Fenster</span>
          ${segs("pause-mode", r.pause_mode || "", [["", `Standard (${d.pause_mode === "off" ? "aus" : "Frostschutz"})`, "mdi:auto-mode"], ["frost", "Frostschutz", "mdi:snowflake"], ["off", "Ausschalten", "mdi:power"]])}
        </div>
        ${check("window_detect", "mdi:thermometer-chevron-down", "Fenster ohne Kontakt erkennen", "Fällt die Raumtemperatur in 5 Minuten stark, gilt das als offenes Fenster – Fensterpause für eine feste Zeit.")}
        ${r.window_detect ? `
        <div class="row2">
          <label class="field"><span><ha-icon icon="mdi:arrow-down-bold"></ha-icon> Temperatursturz ab</span><div class="unit"><input type="number" step="0.1" min="0.3" max="5" data-room="window_detect_drop" value="${r.window_detect_drop ?? ""}" placeholder="1,0"><i>°C in 5 Min.</i></div></label>
          <label class="field"><span><ha-icon icon="mdi:timer-sand"></ha-icon> Pause dann für</span><div class="unit"><input type="number" step="5" min="5" max="60" data-room="window_detect_min" value="${r.window_detect_min ?? ""}" placeholder="15"><i>Min.</i></div></label>
        </div>
        ${(r.windows || []).length ? `<p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Gilt zusätzlich zu den Fensterkontakten – z. B. für ein Fenster ohne Kontakt.</p>` : ""}` : ""}
        <div class="row2">
          <label class="field"><span><ha-icon icon="mdi:timer-sand"></ha-icon> Fensterpause nach</span>${num("window_delay", "s", 10, 'min="0" max="7200"')}</label>
          ${ex ? `<label class="field"><span><ha-icon icon="mdi:timer-play-outline"></ha-icon> Weiterheizen nach dem Schließen</span>${num("resume_delay", "s", 10, 'min="0" max="3600"')}</label>` : ""}
        </div>
        ${ex ? `
        <div class="sub-h"><ha-icon icon="mdi:school-outline"></ha-icon>Experte</div>
        <div class="row2">
          <label class="field"><span><ha-icon icon="mdi:arrow-collapse-down"></ha-icon> Höchstens absenken um</span>${num("max_setback", "°C", 0.5, 'min="0" max="15"')}</label>
          <label class="field"><span><ha-icon icon="mdi:window-open-variant"></ha-icon> Temperatur bei offenem Fenster</span><div class="unit"><input type="number" step="0.5" min="5" max="30" data-room="window_temp" value="${r.window_temp ?? ""}" placeholder="${fmt(this._data.settings.frost_temp)}"><i>°C</i></div></label>
        </div>
        ${check("min_instead_of_off", "mdi:thermometer-low", "Kleinste Temperatur statt Ausschalten", "Für Thermostate, die sich nicht zuverlässig aus- und wieder einschalten lassen.")}` : expertHint(["resume_delay", "max_setback", "window_temp", "min_instead_of_off"])}`,

      control: () => `
        ${check("manual_device", "mdi:hand-back-right-outline", "Am Gerät gedreht übernehmen", "Dreht jemand am Thermostat selbst, gilt der Wert bis zur nächsten Planänderung.", { on: r.allow_manual !== false && r.manual_device !== false })}
        ${check("manual_ui", "mdi:cellphone-cog", "In Home Assistant geändert übernehmen", "Ändert jemand das Thermostat in Home Assistant oder der App, gilt der Wert bis zur nächsten Planänderung.", { on: r.allow_manual !== false && r.manual_ui !== false })}
        ${r.type === "heizkoerper" ? check("compensation", "mdi:thermometer-plus", "Nach Raumsensor nachführen", "Misst das Thermostat am Heizkörper zu warm, wird der Sollwert um die Differenz (max. 4 °C) angehoben.", { disabled: !r.temp_sensor }) : ""}
        ${r.type === "heizkoerper" && !r.temp_sensor ? `<p class="muted small"><ha-icon icon="mdi:alert-circle-outline"></ha-icon>Nachführen braucht einen Raumsensor (Reiter Geräte).</p>` : ""}
        ${ex ? `
        <div class="sub-h"><ha-icon icon="mdi:school-outline"></ha-icon>Experte</div>
        ${hint}
        <div class="row2">
          <label class="field"><span><ha-icon icon="mdi:plus-minus-variant"></ha-icon> Fester Ausgleich am Thermostat</span>${num("target_offset", "°C", 0.5, 'min="-5" max="5"')}</label>
        </div>
        <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Regelt ein Thermostat dauerhaft zu kalt, z. B. +1 °C: Heizwerk schickt dann 1 °C mehr als den Sollwert.</p>
        ${check("calibration", "mdi:tune-vertical-variant", "Thermostat kalibrieren", "Setzt den Temperatur-Offset am Gerät (number-Entität mit „calibration“ oder „offset“ im Namen), damit es wie der Raumsensor misst. Ersetzt das Nachführen.", { disabled: !r.temp_sensor })}
        ${r.calibration ? `<div class="field"><span>Offset-Entität (leer = automatisch suchen)</span>${this._picker("calibration_entities", r.calibration_entities || [])}</div>` : ""}
        ${check("valve_control", "mdi:valve", "Ventil direkt steuern", "Für Thermostate mit Ventil-Entität (number mit „valve“ oder „position“ im Namen): Öffnung nach Abstand zum Soll.")}
        ${r.valve_control ? `
        <div class="row2">
          <label class="field"><span>Ganz offen ab</span>${num("valve_diff", "°C unter Soll", 0.1, 'min="0.2" max="5"')}</label>
          <label class="field"><span>Höchstens öffnen</span>${num("valve_max", "%", 5, 'min="10" max="100"')}</label>
        </div>
        <div class="field"><span>Ventil-Entität (leer = automatisch suchen)</span>${this._picker("valve_entities", r.valve_entities || [])}</div>` : ""}
        <div class="sub-h"><ha-icon icon="mdi:chart-bell-curve-cumulative"></ha-icon>Feinregelung <span class="muted small">· 0 = aus</span></div>
        <div class="row3">
          <label class="field"><span><ha-icon icon="mdi:thermometer-check"></ha-icon> Aus ab Soll +</span>${num("off_above", "°C", 0.1, 'min="0" max="5"')}</label>
          <label class="field"><span><ha-icon icon="mdi:arrow-expand-vertical"></ha-icon> Übersteuern ab</span>${num("aggressive_range", "°C", 0.1, 'min="0" max="5"')}</label>
          <label class="field"><span><ha-icon icon="mdi:plus-minus-variant"></ha-icon> Übersteuern um</span>${num("aggressive_offset", "°C", 0.5, 'min="0" max="5"')}</label>
        </div>
        <p class="muted small">Übersteuern stellt das Thermostat höher bzw. tiefer, solange der Raum weit vom Soll entfernt ist – träge Thermostate reagieren so schneller.</p>
        <div class="sub-h"><ha-icon icon="mdi:tune-vertical"></ha-icon>Komfort und Eco aus Helfern</div>
        <p class="muted small">Eine Zahl-Entität (z. B. input_number) ersetzt den festen Wert, so lässt er sich per Automation oder Dashboard ändern.</p>
        <div class="row2">
          <div class="field"><span><ha-icon icon="mdi:sofa-outline"></ha-icon> Komfort aus</span>${this._picker("comfort_entity", r.comfort_entity ? [r.comfort_entity] : [])}</div>
          <div class="field"><span><ha-icon icon="mdi:leaf"></ha-icon> Eco aus</span>${this._picker("eco_entity", r.eco_entity ? [r.eco_entity] : [])}</div>
        </div>` : expertHint(["target_offset", "calibration", "valve_control", "off_above", "aggressive_range", "aggressive_offset", "comfort_entity", "eco_entity"])}`,
    };

    host.innerHTML = `
      <div class="backdrop" data-action="dialog-close"></div>
      <div class="sheet" role="dialog" aria-label="Raum">
        <div class="sheet-head">
          <span class="rr-ic big" style="--rc:${r.id ? this._roomColor(r.id) : "var(--accent)"}"><ha-icon icon="${esc(roomIcon(r))}"></ha-icon></span>
          <div class="grow"><h2>${esc(r.name || (this._dialog.isNew ? "Neuer Raum" : "Raum"))}</h2><div class="muted">${this._dialog.isNew ? "Neuer Raum" : "Raum bearbeiten"} · ${TYPES[r.type].label}</div></div>
          <button class="icon boxed" data-action="dialog-close" title="Schließen"><ha-icon icon="mdi:close"></ha-icon></button>
        </div>
        <nav class="dtabs">
          ${TABS_D.map(([id, icon, label, dot]) => `<button class="dtab ${tab === id ? "on" : ""}" data-action="dialog-tab" data-tab="${id}" title="${label}"><ha-icon icon="${icon}"></ha-icon><span>${label}</span>${dot ? "<i></i>" : ""}</button>`).join("")}
          <span class="grow"></span>
          <button class="xtog ${ex ? "on" : ""}" data-action="expert" title="Experten-Einstellungen ${ex ? "ausblenden" : "anzeigen"}"><ha-icon icon="mdi:school-outline"></ha-icon><span>Experte</span><i></i></button>
        </nav>
        <div class="sheet-body">${views[tab]()}</div>
        <div class="sheet-foot">
          ${this._dialog.isNew ? "" : `<button class="danger" data-action="room-delete" title="Raum löschen"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>`}
          <button class="secondary" data-action="dialog-close">Abbrechen</button>
          <button class="primary" data-action="room-save"><ha-icon icon="mdi:content-save-outline"></ha-icon>Speichern</button>
        </div>
      </div>`;
    const body = host.querySelector(".sheet-body");
    if (body && this._dialog.keepScroll) body.scrollTop = scroll;
    this._dialog.keepScroll = true;
    const name = host.querySelector('[data-room="name"]');
    if (this._dialog.isNew && name && !this._dialog.focused) {
      this._dialog.focused = true;
      setTimeout(() => name.focus(), 50);
    }
  }

  _preheatSection(r, d, num, segs, ex = true) {
    const global = this._data.settings.preheat_mode || "fixed";
    const label = { smart: "lernend", fixed: "feste Zeit", off: "aus" };
    const mode = r.preheat_mode || global;
    const st = r.id ? this._status?.rooms?.[r.id] || {} : {};
    const learned = st.learned;
    const rate = st.heat_rate;
    const example = rate ? Math.round((2 / rate) * 60 * 1.15 + 5) : null;
    return `
      <div class="sub-h"><ha-icon icon="mdi:clock-fast"></ha-icon>Vorheizen</div>
      <p class="muted small">Damit der Raum zu Beginn einer Komfortzeit schon warm ist, heizt Heizwerk vorher los.</p>
      <div class="field">
        ${segs("preheat-mode", r.preheat_mode || "", [["", `Wie alle Räume (${label[global]})`, "mdi:home-outline"], ["smart", "Lernen", "mdi:brain"], ["fixed", "Feste Zeit", "mdi:timer-outline"], ["off", "Aus", "mdi:timer-off-outline"]])}
      </div>
      ${mode === "smart" ? `
        <div class="row2">
          ${ex ? `<label class="field"><span><ha-icon icon="mdi:timer-alert-outline"></ha-icon> Höchstens vorher</span>${num("preheat_max", "Min.", 10, 'min="10" max="600"')}</label>` : ""}
          <div class="field"><span><ha-icon icon="mdi:speedometer"></ha-icon> Aufheizgeschwindigkeit</span>
            <div class="learn ${learned ? "ok" : ""}">
              <b>${rate ? `${fmt(rate)} °C/h` : "–"}</b>
              <small>${!r.id ? "wird nach dem Speichern gelernt" : learned ? `gelernt · 2 °C wärmer ≈ ${example} min` : `Startwert · lernt beim nächsten Aufheizen`}</small>
              ${learned && this._admin ? `<button class="link tiny" data-action="preheat-reset" data-id="${r.id}"><ha-icon icon="mdi:restore"></ha-icon>neu lernen</button>` : ""}
            </div>
          </div>
        </div>
        <p class="muted small"><ha-icon icon="mdi:information-outline"></ha-icon>Heizwerk misst bei jedem Aufheizen, wie viele Grad pro Stunde der Raum schafft, und rechnet daraus die Startzeit aus – mit 15 % Reserve.</p>` : ""}
      ${mode === "fixed" ? `
        <div class="row2">
          <label class="field"><span><ha-icon icon="mdi:timer-outline"></ha-icon> Vorheizen vor Komfortbeginn</span>
            <div class="unit"><input type="number" step="5" min="0" max="600" data-room="lead_min" value="${r.lead_min ?? ""}" placeholder="${this._leadFor(r.type)}"><i>Min.</i></div></label>
        </div>` : ""}
      ${mode === "off" ? `<p class="muted small">Der Raum heizt erst zu Beginn der Komfortzeit los.</p>` : ""}`;
  }

  /** Woher der Raum seine Komfortzeiten bekommt: gemeinsamer Plan, eigener Plan oder Home Assistant. */
  _schedField(r, segs) {
    const plans = this._planList();
    const src = this._dialog.schedSrc;
    return `
      <div class="field"><span><ha-icon icon="mdi:calendar-clock"></ha-icon> Heizplan</span>
        ${segs("sched-src", src, [["plan", "Gemeinsamer Plan", "mdi:calendar-multiple"], ["own", "Eigener Plan", "mdi:calendar-edit"], ["entity", "Aus Home Assistant", "mdi:home-assistant"]])}
      </div>
      ${src === "plan" ? (plans.length ? `
      <label class="field"><span>Plan</span>
        <select data-room="plan_id">${plans.map((p) => `<option value="${p.id}" ${r.plan_id === p.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></label>
      <p class="muted small">Zeiten des Plans änderst du unter Heizpläne – sie gelten für alle Räume mit diesem Plan. Komfort und Eco bleiben die Werte dieses Raums.</p>`
        : `<p class="note warn"><ha-icon icon="mdi:calendar-alert"></ha-icon>Noch kein gemeinsamer Plan. Lege einen unter Heizpläne an – bis dahin nutzt der Raum seinen eigenen Plan.</p>`) : ""}
      ${src === "own" ? `<p class="muted small">Die Zeiten bearbeitest du unter Heizpläne › Räume › ${esc(r.name || "dieser Raum")}.</p>` : ""}
      ${src === "entity" ? `
      <div class="field"><span>Zeitplan oder Kalender (an bzw. Termin = Komfort, sonst Eco)</span>${this._picker("schedule_entity", r.schedule_entity ? [r.schedule_entity] : [])}</div>
      <p class="muted small">Bei einem Kalender heizt Heizwerk vor dem nächsten Termin vor.</p>` : ""}`;
  }
  // ------------------------------------------------------------ Entitätsauswahl
  _entityName(id) {
    return this._hass.states[id]?.attributes?.friendly_name || id;
  }

  /** Zustand der Entitätssuche je Feld: Reiter, Suchtext, Filter, aufgeklappt. */
  _pkState(field) {
    this._pk = this._pk || {};
    return (this._pk[field] = this._pk[field] || { tab: "suggest", q: "", dom: "", avail: false, open: false });
  }

  /** Raum einer Entität aus Home Assistant (der Entität selbst, sonst ihres Geräts). */
  _areaOf(id) {
    const ent = this._hass.entities?.[id];
    const areaId = ent?.area_id || (ent?.device_id ? this._hass.devices?.[ent.device_id]?.area_id : null);
    return areaId ? this._hass.areas?.[areaId]?.name || null : null;
  }

  /** An/aus eines Stellantriebs oder Heizkreises (switch, input_boolean, binary_sensor), sonst null. */
  _switchOf(id) {
    const d = id.split(".")[0];
    if (!["switch", "input_boolean", "binary_sensor"].includes(d)) return null;
    const st = this._hass?.states?.[id];
    if (!st || !["on", "off"].includes(st.state)) return null;
    return st.state === "on";
  }

  _floorLabel(room) {
    return room.type === "flaeche" ? "Fußbodenheizung" : "Stellantrieb";
  }

  /** Anzeige-Geräte eines Raums zusammengefasst: höchste Ventilöffnung und Fußbodenheizung an/aus. */
  _devIndicators(room) {
    const ids = [...(room.climates || []), ...(room.show_entities || [])];
    const valves = ids.map((id) => this._valveOf(id)).filter((v) => v != null);
    const sws = (room.show_entities || []).map((id) => [id, this._switchOf(id)]).filter(([, v]) => v != null);
    return {
      valve: valves.length ? Math.max(...valves) : null,
      valves: valves.length,
      floor: sws.length
        ? { on: sws.some(([, v]) => v), label: this._floorLabel(room), names: sws.map(([id, v]) => `${this._entityName(id)} ${v ? "an" : "aus"}`).join(", ") }
        : null,
    };
  }

  /** Art des Geräts als Überschrift, z. B. „Wandthermostat“, „Fensterkontakt“, „Fußbodenheizung“. */
  _devType(id) {
    const st = this._hass?.states?.[id];
    const dom = String(id).split(".")[0];
    const a = st?.attributes || {};
    const dc = a.device_class;
    const txt = `${id} ${a.friendly_name || ""}`.toLowerCase();
    if (dom === "climate" && /zone|circuit|heizkreis|vaillant|viessmann|buderus|kessel|therme|w(ä|ae)rmepumpe|heat_?pump|boiler/.test(txt)) return "Wärmeerzeuger";
    if (dom === "climate") {
      const k = this._thermoKind(id);
      return k === "wall" ? "Wandthermostat" : k === "trv" ? "Heizkörper-Thermostat" : "Thermostat";
    }
    if ((dom === "switch" || dom === "input_boolean") && /fu(ss|ß)boden|fbh|fl(ä|ae)chen|heizkreis|stellantrieb/.test(txt)) return "Fußbodenheizung";
    if (dom === "binary_sensor") {
      return { window: "Fensterkontakt", door: "Türkontakt", opening: "Öffnungskontakt", garage_door: "Garagentor", motion: "Bewegungsmelder",
        occupancy: "Präsenzmelder", presence: "Präsenzmelder", battery: "Batterie", moisture: "Wassermelder", smoke: "Rauchmelder" }[dc]
        || (/fenster|window/.test(txt) ? "Fensterkontakt" : /präsenz|presence|bewegung|motion/.test(txt) ? "Präsenzmelder" : "Melder");
    }
    if (dom === "sensor") {
      if (a.unit_of_measurement === "%" && /ventil|valve|st(ö|oe)(ß|ss)el|tappet|heating_demand|pi_heating/.test(txt)) return "Ventilöffnung";
      if (a.unit_of_measurement === "%" && /heating_power|heizleistung|_heating$/.test(txt)) return "Heizleistung";
      if (/duty_cycle/.test(txt)) return "Funk-Auslastung";
      return { temperature: "Temperatursensor", humidity: "Feuchtesensor", battery: "Batterie", distance: "Entfernung", power: "Leistung",
        energy: "Energie", illuminance: "Helligkeit", pressure: "Luftdruck", carbon_dioxide: "CO₂-Sensor" }[dc] || "Sensor";
    }
    return { switch: "Schalter", input_boolean: "Schalter-Helfer", input_number: "Zahl-Helfer", number: "Einstellwert", valve: "Ventil",
      cover: "Rollladen", light: "Licht", scene: "Szene", script: "Skript", weather: "Wetterdienst", person: "Person",
      device_tracker: "Handy / Tracker", calendar: "Kalender", schedule: "Zeitplan", zone: "Zone", sun: "Sonne", notify: "Benachrichtigung",
      fan: "Lüfter", humidifier: "Luftentfeuchter", media_player: "Medienspieler" }[dom] || DOMAIN_LABEL[dom] || "Gerät";
  }

  /** Wandthermostat („wall“), Heizkörper-Thermostat („trv“) oder unbekannt – nach Modell, sonst Name. */
  _thermoKind(id) {
    const st = this._hass?.states?.[id];
    // Modell aus dem Zustand, sonst aus dem Geräte-Register (Homematic, Bosch, tado, Netatmo, Danfoss, Aqara, AVM …)
    const dev = this._hass?.devices?.[this._hass?.entities?.[id]?.device_id];
    const model = String(st?.attributes?.model || dev?.model || "").toLowerCase();
    if (model) {
      if (TRV_MODELS.some((w) => model.includes(w))) return "trv";
      if (WALL_MODELS.some((w) => model.includes(w))) return "wall";
    }
    const txt = `${id} ${st?.attributes?.friendly_name || ""}`.toLowerCase();
    if (/wth|wandthermostat|wall_thermostat|wall thermostat|raumthermostat|room thermostat/.test(txt)) return "wall";
    if (/trv|heizk(ö|o|oe)rper|radiator|stellantrieb|ventil/.test(txt)) return "trv";
    return null;
  }

  /** Rolle der Thermostate eines Raums: stellt ein · folgt dem Wandthermostat · selbst · Zusatzheizung. */
  _rolesBlock(r) {
    const rs = this._status?.rooms?.[r.id] || {};
    const climates = r.climates || [];
    const hasWall = climates.some((id) => this._thermoKind(id) === "wall");
    const assist = new Set(r.assist_entities || []);
    const own = new Set(r.pair_exclude || []);
    const role = (id) => assist.has(id) ? "assist" : this._thermoKind(id) === "wall" ? "main"
      : !hasWall || r.pair_mode === "off" || own.has(id) ? "own" : "follow";
    const rows = climates.map((id) => {
      const ro = role(id);
      const kind = this._thermoKind(id);
      const v = this._valveOf(id);
      let state = "";
      if (ro === "follow") state = (rs.pair_broken || []).includes(id) ? "folgt nicht – Hauswerk stellt selbst" : (rs.followers || []).includes(id) ? "folgt ✓" : "";
      if (ro === "assist" && rs.assist) state = rs.assist.on ? "heizt mit" : "zu – Boden reicht";
      const sub = [this._entityName(id), state, v != null ? `Ventil ${fmt(v, 0)} %` : ""].filter(Boolean).join(" · ");
      const opts = [...(hasWall ? [["follow", "Folgt Wand", "mdi:link-variant"]] : []), ["own", "Selbst", "mdi:tune-variant"], ["assist", "Zusatz", "mdi:radiator"]];
      return `<div class="role">
        <div class="role-h"><ha-icon icon="${kind === "wall" ? "mdi:thermostat-box" : "mdi:radiator"}"></ha-icon><span class="grow"><b>${esc(this._devType(id))}</b><small>${esc(sub)}</small></span>
          ${ro === "main" ? `<em class="role-main">stellt ein</em>` : ""}</div>
        ${ro === "main" ? "" : `<div class="segs small ${hasWall ? "n3" : "n2"}">${opts.map(([k, l, i]) => `<button class="seg ${ro === k ? "on" : ""}" data-action="role-set" data-id="${esc(id)}" data-v="${k}"><ha-icon icon="${i}"></ha-icon>${l}</button>`).join("")}</div>`}
      </div>`;
    }).join("");
    const anyAssist = climates.some((id) => role(id) === "assist");
    return `<div class="field"><span><ha-icon icon="mdi:thermostat"></ha-icon> Rolle der Thermostate</span>
      <div class="roles">${rows}</div>
      ${anyAssist ? `<label class="field narrow"><span><ha-icon icon="mdi:thermometer-chevron-down"></ha-icon> Zusatz-Heizkörper helfen ab</span><div class="unit"><input type="number" step="0.1" min="0.2" max="3" data-room="assist_diff" value="${r.assist_diff ?? ""}" placeholder="0,5"><i>°C unter Soll</i></div></label>` : ""}
      <details class="role-help"><summary><ha-icon icon="mdi:help-circle-outline"></ha-icon> Was bedeuten die Rollen?</summary>
        <p><b>Folgt Wand</b> – in der CCU-Heizgruppe des Wandthermostats; Hauswerk stellt nur das Wandthermostat (spart Funk). Folgt er 15 Min. nicht, stellt Hauswerk ihn selbst.</p>
        <p><b>Selbst</b> – Hauswerk stellt ihn wie das Wandthermostat auf das Raum-Soll.</p>
        <p><b>Zusatz</b> – Mischbetrieb: zu, solange die Fußbodenheizung reicht; heizt mit ab X °C unter Soll, beim Vorheizen und Boost. In der CCU aus der Heizgruppe nehmen und auf „Manu“ stellen.</p>
      </details></div>`;
  }

  /** %-Sensoren für die Ventilöffnung am selben Gerät wie das Thermostat (Sensoren vor Zahlen-Entitäten). */
  _valveSiblings(id) {
    const reg = this._hass?.entities;
    if (!reg) return [];
    if (this._valveMapFor !== reg) {
      this._valveMapFor = reg;
      this._valveMap = {};
    }
    if (this._valveMap[id]) return this._valveMap[id];
    const dev = reg[id]?.device_id;
    let found = [];
    if (dev) {
      // Homematic „Ventilöffnungsgrad“, Bosch „Ventilstößel“ (valvetappet), Zigbee „pi_heating_demand“/„position“,
      // tado „Heizleistung“ (sensor.*_heating), Netatmo „heating_power_request“
      const words = /ventil|valve|stellung|st(ö|oe)(ß|ss)el|tappet|heating_demand|heizbedarf|pi_heating|heating_power|heizleistung|_heating$|position/i;
      const cands = Object.entries(reg)
        .map(([eid, e]) => ({ ...e, entity_id: eid }))
        .filter((e) => e.device_id === dev && e.entity_id !== id && !e.hidden && words.test(`${e.entity_id} ${e.name || ""} ${e.translation_key || ""}`));
      const ok = (e) => {
        const st = this._hass.states?.[e.entity_id];
        return st && st.attributes?.unit_of_measurement === "%" && !/max|min|limit|grenze|offset/i.test(e.entity_id);
      };
      found = cands.filter((e) => e.entity_id.startsWith("sensor.") && ok(e)).map((e) => e.entity_id);
      if (!found.length) found = cands.filter((e) => e.entity_id.startsWith("number.") && ok(e)).map((e) => e.entity_id);
    }
    this._valveMap[id] = found;
    return found;
  }

  /** Ventilöffnung in % einer Entität (Thermostat-Attribut, Ventil/Stellantrieb oder %-Sensor), sonst null. */
  _valveOf(id) {
    const st = this._hass?.states?.[id];
    if (!st || ["unavailable", "unknown"].includes(st.state)) return null;
    const a = st.attributes || {};
    const d = id.split(".")[0];
    const num = (v) => (v === null || v === undefined || v === "" || isNaN(Number(v)) ? null : Number(v));
    if (d === "climate") {
      for (const k of ["valve_position", "valve_opening", "valve_tappet", "pi_heating_demand", "heating_demand", "heating_power_request", "heating_power", "position", "valve"]) {
        if (num(a[k]) != null) return num(a[k]);
      }
      // Viele Thermostate (z. B. Homematic IP, Zigbee) melden die Ventilöffnung als eigenen Sensor am selben Gerät.
      const vals = this._valveSiblings(id).map((sid) => this._valveOf(sid)).filter((v) => v != null);
      return vals.length ? Math.max(...vals) : null;
    }
    if (d === "valve" || d === "cover") return num(a.current_position);
    if ((d === "sensor" || d === "number") && a.unit_of_measurement === "%" && a.device_class !== "battery" && a.device_class !== "humidity") return num(st.state);
    return null;
  }

  _fmtState(st) {
    if (!st) return "nicht gefunden";
    if (["unavailable", "unknown"].includes(st.state)) return "nicht erreichbar";
    const a = st.attributes || {};
    const domain = st.entity_id?.split(".")[0];
    if (domain === "climate") {
      const mode = { heat: "Heizen", off: "Aus", auto: "Auto", heat_cool: "Auto", cool: "Kühlen" }[st.state] || st.state;
      return a.current_temperature != null ? `${fmt(a.current_temperature)} °C · ${mode}` : mode;
    }
    if (domain === "binary_sensor" || domain === "input_boolean" || domain === "switch") {
      const on = st.state === "on";
      const dc = a.device_class;
      if (["window", "door", "opening", "garage_door"].includes(dc)) return on ? "offen" : "zu";
      if (["motion", "occupancy", "presence"].includes(dc)) return on ? "erkannt" : "frei";
      return on ? "an" : "aus";
    }
    if (domain === "person" || domain === "device_tracker") return st.state === "home" ? "zu Hause" : st.state === "not_home" ? "unterwegs" : st.state;
    const u = st.attributes.unit_of_measurement;
    const n = Number(st.state);
    return `${st.state !== "" && isFinite(n) ? n.toLocaleString("de-DE", { maximumFractionDigits: 2 }) : st.state}${u ? ` ${u}` : ""}`;
  }

  /** Auswahlfeld: gewählte Entitäten als Karten, darunter die Suche mit Vorschlägen, nach Raum und Filter. */
  _picker(field, selected) {
    const cfg = PICKERS[field];
    const S = this._pkState(field);
    const open = this._admin && S.open;  // erst nach „Hinzufügen“ bzw. „Ändern“
    const cards = (cfg.noCards ? [] : selected)
      .map((id) => {
        const st = this._hass.states[id];
        const area = this._areaOf(id);
        return `
        <div class="pk-sel ${st ? "" : "missing"}">
          <button class="pk-sel-b" ${this._admin && !cfg.multi ? `data-action="pk-open" data-field="${field}" title="Ändern"` : "disabled"}>
            <b>${esc(this._devType(id))}</b><small>${esc(this._entityName(id))} · ${esc(this._fmtState(st))}${area ? ` · ${esc(area)}` : ""}</small>
          </button>
          ${this._admin ? `<button class="pk-x" data-action="pick-remove" data-field="${field}" data-id="${esc(id)}" title="Entfernen" aria-label="Entfernen"><ha-icon icon="mdi:close"></ha-icon></button>` : ""}
        </div>`;
      })
      .join("");
    const more = this._admin && !open
      ? `<button class="pk-add" data-action="pk-open" data-field="${field}"><ha-icon icon="${cfg.multi || !selected.length ? "mdi:plus" : "mdi:swap-horizontal"}"></ha-icon>${!selected.length ? "Hinzufügen" : cfg.multi ? "Weitere hinzufügen" : "Andere wählen"}</button>`
      : !this._admin && !selected.length ? `<div class="pk-none muted small">Nichts gewählt</div>` : "";
    const box = open
      ? `<div class="pk-box">
          <div class="search"><ha-icon icon="mdi:magnify"></ha-icon><input type="search" data-picker-input="${field}" placeholder="Suchen: Name, Raum, Entität …" value="${esc(S.q)}" autocomplete="off"></div>
          <div class="pk-tabs">${[["suggest", "Vorschläge"], ["area", "Nach Raum"], ["filter", "Filter"]]
            .map(([k, l]) => `<button class="${S.tab === k ? "on" : ""}" data-action="pk-tab" data-field="${field}" data-v="${k}">${l}</button>`)
            .join("")}</div>
          <div class="pk-body">${this._pickerList(field)}</div>
          <button class="link tiny pk-close" data-action="pk-open" data-field="${field}">${selected.length ? "Fertig" : "Abbrechen"}</button>
        </div>`
      : "";
    return `<div class="picker" data-picker="${field}">${cards}${more}${box}</div>`;
  }

  /** Kandidaten mit Bewertung: passt die Geräteklasse, der Name, der Raum? */
  _candidates(field, query) {
    const cfg = PICKERS[field];
    const S = this._pkState(field);
    const selected = this._pickerValue(field);
    const words = (query || "").toLowerCase().trim().split(/\s+/).filter(Boolean);
    const room = cfg.scope === "room" ? this._dialog?.room : null;
    const roomWords = (room?.name || "").toLowerCase().split(/[\s\-_.:]+/).filter((w) => w.length > 2);
    const hints = PICK_HINTS[field] || [];
    const classes = PICK_CLASSES[field] || [];
    const list = [];
    for (const [id, st] of Object.entries(this._hass.states)) {
      const domain = id.split(".")[0];
      if (!cfg.domains.includes(domain)) continue;
      const sel = selected.includes(id);
      if (sel && cfg.multi) continue;
      const a = st.attributes || {};
      const dc = a.device_class;
      const unit = a.unit_of_measurement;
      if (cfg.deviceClass) {
        const ok = dc === cfg.deviceClass || (cfg.deviceClass === "temperature" && ["°C", "°F"].includes(unit)) || (cfg.deviceClass === "humidity" && unit === "%");
        if (!ok) continue;
      }
      const name = a.friendly_name || id;
      const area = this._areaOf(id);
      const hay = `${name} ${id} ${area || ""}`.toLowerCase();
      if (words.length && !words.every((w) => hay.includes(w))) continue;
      if (S.dom && S.dom !== domain && S.dom !== dc) continue;
      const bad = ["unavailable", "unknown"].includes(st.state);
      if (S.avail && bad && !sel) continue;
      let score = 35;
      const why = [];
      if (sel) why.push("jetzt gewählt");
      if (classes.includes(dc) || (field === "persons" && domain === "person")) score += 20;
      if (hints.some((h) => hay.includes(h))) {
        score += 15;
        why.push("Name passt");
      }
      if (roomWords.length && roomWords.some((w) => hay.includes(w))) {
        score += 20;
        why.push(area && roomWords.some((w) => area.toLowerCase().includes(w)) ? "Raum passt" : "passt zum Raum");
      }
      if (area) why.push(area);
      if (unit) why.push(unit);
      else if (dc) why.push(DC_LABEL[dc] || dc);
      if (bad) {
        score -= 25;
        why.push("nicht erreichbar");
      } else score += 5;
      if (sel) score += 10;
      list.push({ id, name, area, domain, dc, bad, sel, why, val: this._fmtState(st), score: Math.max(5, Math.min(99, score)) });
    }
    return list.sort((x, y) => y.sel - x.sel || y.score - x.score || x.name.localeCompare(y.name, "de"));
  }

  /** Inhalt des gewählten Reiters (wird beim Tippen allein neu gezeichnet, damit das Suchfeld den Fokus behält). */
  _pickerList(field) {
    const S = this._pkState(field);
    const cfg = PICKERS[field];
    const all = this._candidates(field, S.q);
    const card = (c) => `
      <div class="pk-card ${c.sel ? "sel" : ""}">
        <b>${esc(c.name)}</b><span class="pk-v">${esc(c.val)}</span>
        <small>${esc(c.id)}</small>
        <span class="pk-why"><em class="${c.score >= 75 ? "hi" : ""}">${c.score} %</em>${esc(c.why.join(" · "))}</span>
        ${c.sel ? `<span class="pk-ok">ist gewählt</span>` : `<button class="pk-pick" data-action="pick-add" data-field="${field}" data-id="${esc(c.id)}">Passt</button>`}
      </div>`;
    const row = (c) => `
      <div class="pk-row ${c.sel ? "sel" : ""} ${c.bad ? "bad" : ""}">
        <span class="grow"><b>${esc(c.name)}</b><small>${esc(c.id)}${c.area && S.tab !== "area" ? ` · ${esc(c.area)}` : ""}</small></span>
        <span class="pk-v">${esc(c.val)}</span>
        ${c.sel ? `<span class="pk-mini on">gewählt</span>` : `<button class="pk-mini" data-action="pick-add" data-field="${field}" data-id="${esc(c.id)}">Wählen</button>`}
      </div>`;
    if (!all.length) return `<div class="pk-empty">Nichts gefunden${S.q ? ` für „${esc(S.q)}“` : ""}${S.dom || S.avail ? " – Filter zurücksetzen?" : ""}.</div>`;
    if (S.tab === "area") {
      const groups = new Map();
      for (const c of all.slice(0, 150)) {
        const k = c.area || "";
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(c);
      }
      const keys = [...groups.keys()].sort((a, b) => (!a ? 1 : !b ? -1 : a.localeCompare(b, "de")));
      return `<div class="pk-scroll">${keys
        .map((k) => `<div class="pk-group">${esc(k || "Ohne Raum")} <span>${groups.get(k).length}</span></div>${groups.get(k).map(row).join("")}`)
        .join("")}</div>`;
    }
    if (S.tab === "filter") {
      const counts = {};
      for (const c of this._candidates(field, "")) if (c.dc) counts[c.dc] = (counts[c.dc] || 0) + 1;
      const opts = [
        ...(cfg.domains.length > 1 ? cfg.domains.map((d) => [d, DOMAIN_LABEL[d] || d]) : []),
        ...Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([dc]) => [dc, DC_LABEL[dc] || dc]),
      ];
      return `
        <div class="pk-chips">
          ${opts.map(([v, l]) => `<button class="${S.dom === v ? "on" : ""}" data-action="pk-dom" data-field="${field}" data-v="${esc(v)}">${esc(l)}</button>`).join("")}
          <button class="${S.avail ? "on" : ""}" data-action="pk-avail" data-field="${field}">Nur erreichbare</button>
        </div>
        <div class="pk-scroll">${all.slice(0, 80).map(row).join("")}${all.length > 80 ? `<div class="pk-empty">… ${all.length - 80} weitere – Suche eingrenzen</div>` : ""}</div>`;
    }
    const top = all.slice(0, S.q ? 8 : 3);
    const rest = all.length - top.length;
    return `
      <div class="pk-list">${top.map(card).join("")}</div>
      ${rest > 0 ? `<div class="pk-foot">${rest} weitere passende · <button class="link" data-action="pk-tab" data-field="${field}" data-v="area">Nach Raum suchen</button> · <button class="link" data-action="pk-tab" data-field="${field}" data-v="filter">Filtern</button></div>` : ""}`;
  }

  /** Auswahlfeld an Ort und Stelle neu zeichnen. */
  _rerenderPicker(field) {
    const el = this.shadowRoot.querySelector(`[data-picker="${field}"]`);
    if (el) el.outerHTML = this._picker(field, this._pickerValue(field));
  }

  _pickerTarget(field) {
    const scope = PICKERS[field].scope;
    return scope === "room" ? this._dialog?.room : scope === "pop" ? this._pop?.draft : scope === "plan" ? this._plan : this._settings;
  }

  _pickerValue(field) {
    if (field === "person_add") return this._settings?.persons || [];
    if (field === "plan_calendar") return this._plan?.calendar ? [this._plan.calendar] : [];
    const target = this._pickerTarget(field);
    if (!target) return [];
    const v = target[field];
    return Array.isArray(v) ? v : v ? [v] : [];
  }

  _setPickerValue(field, values) {
    const cfg = PICKERS[field];
    if (field === "person_add") {
      this._settings.persons = values;
      this._refreshSettings();
      return;
    }
    const target = this._pickerTarget(field);
    target[field] = cfg.multi ? values : values[0] || null;
    if (["temp_sensor", "presence_sensor"].includes(field) && this._dialog) {
      this._renderDialog();
      return;
    }
    if (field === "plan_calendar") {
      this._plan.calendar = values[0] || null;
      this._plan.dirty = true;
      this._renderMain();
      return;
    }
    if (["outside_sensor", "weather_entity", "sun_entity", "vacation_calendar", "import_calendar", "w_weather"].includes(field)) {
      this._refreshSettings();
      return;
    }
    this._rerenderPicker(field);
  }

  // ------------------------------------------------------------ Ereignisse
  _onInput(e, isChange = false) {
    const t = e.target;
    if (t.dataset.newp !== undefined) {
      this._newPerson = t.value;
      return;
    }
    if (t.dataset.pickerInput) {
      const field = t.dataset.pickerInput;
      this._pkState(field).q = t.value;
      const body = t.closest(".picker")?.querySelector(".pk-body");
      if (body) body.innerHTML = this._pickerList(field);
      return;
    }
    if (t.dataset.room && this._dialog) {
      const key = t.dataset.room;
      let v;
      if (t.type === "checkbox") v = t.checked;
      else if (t.type === "number") v = t.value === "" ? null : Number(t.value);
      else v = t.value;
      if (key === "plan_id") v = v || null;
      this._dialog.room[key] = v;
      if (["name", "valve_control", "calibration", "window_detect"].includes(key) && isChange) this._renderDialog();
      return;
    }
    if (t.dataset.action === "log-search") {
      this._logQuery = t.value;
      this._logLimit = 200;
      this._renderLogList();
      return;
    }
    if (t.dataset.action === "set-search") {
      // nur die Liste neu zeichnen, damit das Suchfeld den Fokus behält
      this._setQuery = t.value;
      const list = this.shadowRoot.getElementById("set-list");
      if (list) list.innerHTML = this._settingsList();
      return;
    }
    if (t.dataset.rwpos && isChange) {
      this._ws({ type: "hauswerk/rollwerk/command", entity_ids: [t.dataset.rwpos], action: "position", position: Number(t.value) });
      return;
    }
    if (t.dataset.rwpos) {
      t.style.setProperty("--v", `${t.value}%`);
      return;
    }
    if (t.dataset.cwiz && this._pop?.id === "cwiz") {
      const c = (this._pop.draft.contacts[t.dataset.cwiz] ||= {});
      c[t.dataset.k] = t.value || null;
      return;
    }
    if (t.dataset.wiz && this._pop?.id === "rwiz") {
      this._pop.draft[t.dataset.wiz] = t.value;
      // Knopf „Weiter“ freigeben, ohne das Feld neu zu zeichnen (Fokus bleibt)
      const next = this.shadowRoot.querySelector('.sheet-foot [data-action="wiz-go"].primary');
      if (next) next.disabled = !this._wizOk(this._pop.draft.step);
      return;
    }
    if (t.dataset.wizAdd && this._pop?.id === "rwiz" && isChange && t.value) {
      const d = this._pop.draft;
      d[t.dataset.wizAdd] = [...new Set([...d[t.dataset.wizAdd], t.value])];
      this._renderPop();
      return;
    }
    if (t.dataset.rwp && this._pop?.draft?.prof) {
      const k = t.dataset.rwp, kind = t.dataset.kind;
      this._pop.draft.prof[k] = kind === "bool" ? t.checked : kind === "num" ? (t.value === "" ? null : Number(t.value)) : t.value || null;
      if ((kind === "bool" || kind === "entity") && isChange) this._renderPop();
      return;
    }
    if (t.dataset.rwc && this._pop?.draft?.cfg) {
      const k = t.dataset.rwc;
      this._pop.draft.cfg[k] = t.type === "checkbox" ? t.checked : t.type === "number" ? (t.value === "" ? null : Number(t.value)) : t.value || null;
      if (t.type === "checkbox" && isChange) this._renderPop();
      return;
    }
    if (t.dataset.pop !== undefined && this._pop) {
      this._pop.draft[t.dataset.pop] = t.value;
      return;
    }
    if (t.dataset.plankw !== undefined && this._plan) {
      this._plan.keyword = t.value;
      this._plan.dirty = true;
      if (isChange) this._renderMain();
      return;
    }
    if (t.dataset.planname !== undefined && this._plan) {
      this._plan.name = t.value;
      this._plan.dirty = true;
      if (isChange) this._renderMain();
      return;
    }
    if (isChange && t.dataset.action === "room-plan") {
      const room = clone(this._data.rooms[t.dataset.id]);
      const old = this._data.plans?.[room.plan_id];
      room.plan_id = t.value || null;
      // Wechsel auf „Eigener Plan“ ohne eigene Zeiten: Zeiten des bisherigen Plans übernehmen
      if (!room.plan_id && old && !(room.schedule || []).length) room.schedule = clone(old.schedule || []);
      this._saveRoom(room).then((saved) => {
        if (!saved) return;
        this._selectPlan("room", room.id);
        this._renderMain();
        this._toast(room.plan_id ? `${room.name} nutzt jetzt „${this._data.plans[room.plan_id].name}“` : `${room.name} hat jetzt einen eigenen Plan`);
      });
      return;
    }
    if (t.dataset.plan && this._plan) {
      const i = Number(t.dataset.i);
      const b = this._plan.blocks[i];
      if (t.value) b[t.dataset.plan] = t.value;
      // Uhrzeit: nicht neu zeichnen (sonst schließt der Wähler am Handy und die Seite springt)
      if (t.value) this._planSoftUpdate(i);
      return;
    }
    if (t.dataset.lookColor !== undefined && this._settings) {
      this._settings.look_accent = t.value;
      if (isChange) this._renderPop();
      else this._applyLook(this._settings);
      return;
    }
    if (t.dataset.set && this._settings) {
      const key = t.dataset.set;
      if (t.type === "checkbox") this._settings[key] = t.checked;
      else if (t.type === "number") {
        if (t.value !== "") this._settings[key] = Number(t.value); // leer = alten Wert behalten
      } else this._settings[key] = t.value || null;
      // Andere Wetterquelle oder Zone: Werte im Pop-up sofort aktualisieren
      if (isChange && ["weather_entity", "outside_sensor", "home_zone"].includes(key)) this._refreshSettings();
      const bar = this.shadowRoot.getElementById("set-save");
      if (bar) bar.hidden = !this._settingsDirty();
      return;
    }
    if (isChange && t.dataset.action === "plan-preset" && t.value) {
      this._plan.blocks = clone(PLAN_PRESETS[t.value].blocks);
      this._plan.dirty = true;
      this._renderMain();
      return;
    }
    if (isChange && t.dataset.action === "hmode") {
      const key = t.dataset.key;
      this._ws({ type: "hauswerk/heizen/settings/save", settings: { [key]: t.checked } })
        .then((settings) => {
          this._data.settings = settings;
          if (this._settings) this._settings[key] = t.checked;
          this._renderMain();
        })
        .catch(() => this._renderMain());
      return;
    }
    if (isChange && t.dataset.action === "room-toggle") {
      const room = clone(this._data.rooms[t.dataset.id]);
      room.enabled = t.checked;
      this._saveRoom(room);
    }
  }

  async _onClick(e) {
    const path = e.composedPath();
    if (!path.some((n) => n.classList?.contains("picker"))) {
      this.shadowRoot.querySelectorAll(".pick-list").forEach((l) => (l.hidden = true));
    }
    for (const d of this.shadowRoot.querySelectorAll("details.rmenu[open]")) if (!path.includes(d) || e.target.closest?.(".rm-pop [data-action]")) d.open = false;
    const el = e.target.closest?.("[data-action]");
    if (!el) return;
    const a = el.dataset.action;
    if (a === "room-quick" && path.some((n) => n.tagName === "DETAILS" || n.tagName === "SUMMARY" || n.tagName === "INPUT")) return;
    if (["room-toggle", "plan-preset", "adv", "hmode", "room-plan", "set-search", "log-search"].includes(a)) {
      if (a === "adv" && this._dialog) setTimeout(() => (this._dialog.advanced = el.open), 0);
      return;
    }
    if (el.tagName === "BUTTON") e.preventDefault();
    // Sprung aus der Hinweis-Liste: Liste schließen, dann Ziel öffnen
    if (el.dataset.hint && this._pop) this._closePop();

    switch (a) {
      case "tab":
        this._setView(el.dataset.tab);
        break;
      case "menu":
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "room-open":
      case "room-page":
        this._roomId = el.dataset.id;
        this._setView("room");
        break;
      case "presence": {
        const m = el.dataset.mode;
        const patch = { vacation: m === "urlaub", presence_force: m === "abwesend" ? "away" : null };
        const settings = await this._ws({ type: "hauswerk/heizen/settings/save", settings: patch });
        this._data.settings = settings;
        break;
      }
      case "step":
        await this._step(el.dataset.kind, el.dataset.key, Number(el.dataset.delta));
        break;
      case "blk-comfort":
        this._plan.blocks[Number(el.dataset.i)].temp = null;
        this._plan.dirty = true;
        this._renderMain();
        break;
      case "room-new":
        this._wizOpen();
        break;
      case "wiz-go": {
        const i = Number(el.dataset.i);
        if (i > this._pop.draft.step && !this._wizOk(this._pop.draft.step)) return;
        this._pop.draft.step = i;
        this._pop.keep = false;
        this._renderPop();
        break;
      }
      case "wiz-area":
        this._wizArea(el.dataset.id);
        this._renderPop();
        break;
      case "wiz-use":
        this._wizUse(el.dataset.id);
        this._pop.draft.step = 2;
        this._pop.keep = false;
        this._renderPop();
        break;
      case "wiz-type":
        this._pop.draft.type = el.dataset.v;
        if (el.dataset.v !== "misch") this._pop.draft.assist = [];
        this._renderPop();
        break;
      case "wiz-tog": {
        const d = this._pop.draft, k = el.dataset.k, id = el.dataset.id;
        d[k] = d[k].includes(id) ? d[k].filter((x) => x !== id) : [...d[k], id];
        if (k === "climates") d.assist = d.assist.filter((x) => d.climates.includes(x));
        this._renderPop();
        break;
      }
      case "wiz-assist": {
        e.stopPropagation?.();
        const d = this._pop.draft, id = el.dataset.id;
        d.assist = d.assist.includes(id) ? d.assist.filter((x) => x !== id) : [...d.assist, id];
        this._renderPop();
        break;
      }
      case "wiz-one":
        this._pop.draft[el.dataset.k] = el.dataset.id || null;
        this._renderPop();
        break;
      case "wiz-t": {
        const d = this._pop.draft;
        d[el.dataset.k] = Math.max(5, Math.min(30, Math.round((d[el.dataset.k] + Number(el.dataset.d)) * 2) / 2));
        this._renderPop();
        break;
      }
      case "wiz-plan":
        this._pop.draft.plan = el.dataset.v;
        this._renderPop();
        break;
      case "wiz-open":
        this._pop.draft.open = !this._pop.draft.open;
        this._renderPop();
        break;
      case "wiz-expert":
        this._closePop();
        this._openRoom(null);
        break;
      case "wiz-save":
        await this._wizSave();
        break;
      case "cwiz-open":
        this._cwizOpen();
        break;
      case "cwiz-go": {
        const i = Number(el.dataset.i);
        const d = this._pop.draft;
        if (i > d.step && !this._cwizOk(d.step)) return;
        if (d.step === 0 && i > 0) {
          // Kontakte im Bereich vorschlagen (nur für neu gewählte Rollläden)
          for (const cid of d.covers) if (!d.contacts[cid]) { const f = this._cwizContacts(cid); d.contacts[cid] = { open: f.open, tilted: f.tilted }; }
        }
        if (i === 4) d.pick = null;
        d.step = i;
        this._pop.keep = false;
        this._renderPop();
        break;
      }
      case "cwiz-cover": {
        const d = this._pop.draft, id = el.dataset.id;
        d.covers = d.covers.includes(id) ? d.covers.filter((x) => x !== id) : [...d.covers, id];
        this._renderPop();
        break;
      }
      case "cwiz-nodir":
        Object.assign(this._pop.draft.prof, { window_dir: null, azimuth_start: 95, azimuth_end: 265 });
        this._renderPop();
        break;
      case "cwiz-use":
        this._pop.draft.use = el.dataset.v;
        this._renderPop();
        break;
      case "cwiz-mode":
        this._pop.draft.mode = el.dataset.v;
        this._renderPop();
        break;
      case "cwiz-shade":
        this._pop.draft.shade = el.checked;
        this._renderPop();
        break;
      case "cwiz-t":
        this._pop.draft.temp = Math.max(15, Math.min(35, this._pop.draft.temp + Number(el.dataset.d)));
        this._renderPop();
        break;
      case "cwiz-pick":
        this._pop.draft.pick = el.dataset.v;
        this._renderPop();
        break;
      case "cwiz-save":
        await this._cwizSave();
        break;
      case "rwp-step": {
        const pr = this._pop.draft.prof, k = el.dataset.k;
        const v = Number(pr[k] ?? el.dataset.def) + Number(el.dataset.d);
        pr[k] = Math.max(Number(el.dataset.min), Math.min(Number(el.dataset.max), Math.round(v * 2) / 2));
        this._renderPop();
        break;
      }
      case "room-edit":
        this._openRoom(this._data.rooms[el.dataset.id]);
        if (el.dataset.rtab && this._dialog) {
          this._dialog.tab = el.dataset.rtab;
          this._renderDialog();
        }
        break;
      case "expert":
        this._expert = !this._expertOn();
        try {
          localStorage.setItem("hauswerk.experte", this._expert ? "1" : "0");
        } catch (err) {
          /* ohne Speicher: gilt bis zum Neuladen */
        }
        this._renderDialog();
        break;
      case "hints-open":
        this._openPop("hints");
        break;
      case "plan-open":
        if (this._plan?.dirty && !confirm("Ungespeicherte Änderungen am Heizplan verwerfen?")) break;
        this._selectPlan("room", el.dataset.id);
        this._plan.dirty = false;
        this._setView("plans");
        break;
      case "plan-sel":
        if (this._plan?.dirty && !confirm("Ungespeicherte Änderungen verwerfen?")) return;
        this._selectPlan(el.dataset.kind, el.dataset.id);
        if (this._tab !== "plans") this._setView("plans");
        else this._renderMain();
        break;
      case "w-edit":
        this._wEdit = !this._wEdit;
        this._renderMain();
        break;
      case "w-add-open":
        this._openPop("widget-add");
        break;
      case "w-add": {
        const def = WIDGETS[el.dataset.type];
        const list = clone(this._widgets());
        const w = { id: Math.random().toString(16).slice(2, 10), type: el.dataset.type, size: def.size || "m", title: null, entities: [] };
        list.push(w);
        this._wEdit = true;
        await this._saveWidgets(list);
        if (def.config) this._openPop("widget", { i: list.length - 1, title: "", size: w.size, w_entities: [] });
        else this._closePop();
        this._toast(`Widget „${def.name}“ hinzugefügt`);
        break;
      }
      case "w-move": {
        const list = clone(this._widgets());
        const i = Number(el.dataset.i), j = i + Number(el.dataset.d);
        if (j < 0 || j >= list.length) break;
        [list[i], list[j]] = [list[j], list[i]];
        await this._saveWidgets(list);
        break;
      }
      case "w-del": {
        const list = clone(this._widgets());
        const w = list[Number(el.dataset.i)];
        if (!confirm(`Widget „${w.title || WIDGETS[w.type]?.name}“ entfernen?`)) break;
        list.splice(Number(el.dataset.i), 1);
        await this._saveWidgets(list);
        break;
      }
      case "w-conf": {
        const w = this._widgets()[Number(el.dataset.i)];
        this._openPop("widget", { i: Number(el.dataset.i), title: w.title || "", size: this._wSize(w), w_entities: [...(w.entities || [])], w_weather: w.type === "forecast" ? (w.entities || [])[0] || null : null, mode: w.mode || "hourly" });
        break;
      }
      case "w-mode":
        this._pop.draft.mode = el.dataset.v;
        this._renderPop();
        break;
      case "w-size":
        this._pop.draft.size = el.dataset.v;
        this._renderPop();
        break;
      case "w-save": {
        const dr = this._pop.draft;
        const list = clone(this._widgets());
        const isFc = list[dr.i].type === "forecast";
        Object.assign(list[dr.i], { title: dr.title.trim() || null, size: dr.size, entities: isFc ? (dr.w_weather ? [dr.w_weather] : []) : dr.w_entities || [] });
        if (isFc) list[dr.i].mode = dr.mode || "hourly";
        await this._saveWidgets(list);
        this._closePop();
        break;
      }
      case "w-sc": {
        const id = el.dataset.e;
        const d = id.split(".")[0];
        const [dom, svc] = { script: ["script", "turn_on"], scene: ["scene", "turn_on"], button: ["button", "press"], input_button: ["input_button", "press"], lock: [ "lock", this._hass.states[id]?.state === "locked" ? "unlock" : "lock"] }[d] || ["homeassistant", "toggle"];
        try {
          await this._hass.callService(dom, svc, { entity_id: id });
          this._toast(`${this._entityName(id)}: ${svc === "toggle" ? "umgeschaltet" : "ausgeführt"}`);
        } catch (err) {
          this._toast(err.message || "Aktion fehlgeschlagen");
        }
        setTimeout(() => this._tab === "start" && this._renderMain(), 700);
        break;
      }
      case "room-view":
        this._view = el.dataset.v;
        try {
          localStorage.setItem("hauswerk.raumansicht", this._view);
        } catch (err) {
          /* ohne Speicher: gilt bis zum Neuladen */
        }
        this._renderMain();
        break;
      case "plan-src":
        this._plan.cal = el.dataset.v === "cal";
        this._plan.dirty = true;
        this._renderMain();
        break;
      case "plan-new":
        if (this._plan?.dirty && !confirm("Ungespeicherte Änderungen verwerfen?")) return;
        this._plan = { kind: "plan", id: null, name: "Neuer Plan", blocks: clone(PLAN_PRESETS.berufstaetig.blocks), dirty: true, day: this._plan?.day ?? (new Date().getDay() + 6) % 7, cal: false, calendar: null, keyword: "" };
        this._renderMain();
        break;
      case "plan-delete": {
        const using = this._planRooms(this._plan.id);
        if (!confirm(`Plan „${this._plan.name}“ löschen?${using.length ? `\n\n${using.map((r) => r.name).join(", ")} behalten die Zeiten als eigenen Plan.` : ""}`)) break;
        const res = await this._ws({ type: "hauswerk/heizen/plan/delete", plan_id: this._plan.id });
        this._data.rooms = res.rooms;
        this._data.plans = res.plans;
        this._plan = null;
        this._renderMain();
        this._toast("Plan gelöscht");
        break;
      }
      case "plan-own": {
        // Raum bekommt eine eigene Kopie des gemeinsamen Plans
        const room = clone(this._data.rooms[el.dataset.id]);
        room.schedule = clone(this._data.plans[room.plan_id]?.schedule || []);
        room.plan_id = null;
        if (await this._saveRoom(room)) {
          this._selectPlan("room", room.id);
          this._renderMain();
          this._toast(`${room.name} hat jetzt einen eigenen Plan`);
        }
        break;
      }
      case "plan-promote": {
        // Eigenen Plan eines Raums als gemeinsamen Plan speichern und dem Raum zuordnen
        const room = clone(this._data.rooms[this._plan.id]);
        const plan = await this._ws({ type: "hauswerk/heizen/plan/save", plan: { name: `Plan ${room.name}`, schedule: this._plan.blocks.filter((b) => b.days.length) } });
        this._data.plans = { ...(this._data.plans || {}), [plan.id]: plan };
        room.plan_id = plan.id;
        if (await this._saveRoom(room)) {
          this._selectPlan("plan", plan.id);
          this._renderMain();
          this._toast(`Gemeinsamer Plan „${plan.name}“ angelegt`);
        }
        break;
      }
      case "import-open":
        this._openPop("import", { import_calendar: null, keyword: "", result: null });
        break;
      case "import-read": {
        const dr = this._pop.draft;
        try {
          const res = await this._ws({ type: "hauswerk/heizen/calendar/import", entity_id: dr.import_calendar, keyword: dr.keyword || null, days: 7 });
          dr.result = res.blocks || [];
        } catch (err) {
          dr.result = null;
        }
        this._renderPop();
        break;
      }
      case "import-apply": {
        const blocks = this._pop.draft.result || [];
        this._plan.blocks = el.dataset.mode === "replace" ? clone(blocks) : [...this._plan.blocks, ...clone(blocks)];
        this._plan.dirty = true;
        this._closePop();
        this._renderMain();
        this._toast(`${blocks.length} Zeitfenster übernommen – bitte prüfen und speichern`);
        break;
      }
      case "pop-open":
        this._openPop(el.dataset.pop);
        break;
      case "pop-close":
        this._closePop();
        break;
      case "pop-save": {
        const p = this._settings;
        if (p.vacation_from && p.vacation_to && p.vacation_from > p.vacation_to) {
          this._toast("Der Urlaub endet vor seinem Beginn.");
          return;
        }
        // Nur Geändertes schicken: alte, inzwischen ungültige Werte blockieren so nicht das Speichern
        const old = this._data.settings;
        const diff = Object.fromEntries(Object.entries(p).filter(([k, v]) => JSON.stringify(v ?? null) !== JSON.stringify(old[k] ?? null)));
        if (Object.keys(diff).length) this._data.settings = await this._ws({ type: "hauswerk/heizen/settings/save", settings: diff });
        this._closePop();
        this._renderMain();
        this._toast("Gespeichert");
        break;
      }
      case "dialog-close":
        this._dialog = null;
        this._renderDialog();
        break;
      case "room-type":
        this._dialog.room.type = el.dataset.type;
        if (el.dataset.type === "flaeche") this._dialog.room.compensation = null;
        this._renderDialog();
        break;
      case "pause-mode":
        this._dialog.room.pause_mode = el.dataset.v || null;
        this._renderDialog();
        break;
      case "room-auto": {
        const room = clone(this._data.rooms[el.dataset.id]);
        room.enabled = room.enabled === false;
        if (await this._saveRoom(room)) this._toast(`${room.name}: Automatik ${room.enabled ? "an" : "aus"}`);
        break;
      }
      case "dialog-tab":
        this._dialog.tab = el.dataset.tab;
        this._dialog.keepScroll = false;
        this._renderDialog();
        break;
      case "room-icon":
        this._dialog.room.icon = el.dataset.v || null;
        this._renderDialog();
        break;
      case "sched-src":
        this._dialog.schedSrc = el.dataset.v;
        if (el.dataset.v !== "entity") this._dialog.room.schedule_entity = null;
        if (el.dataset.v !== "plan") this._dialog.room.plan_id = null;
        else if (!this._data.plans?.[this._dialog.room.plan_id]) this._dialog.room.plan_id = this._planList()[0]?.id || null;
        this._renderDialog();
        break;
      case "preheat-mode":
        this._dialog.room.preheat_mode = el.dataset.v || null;
        this._renderDialog();
        break;
      case "preheat-reset":
        if (!confirm("Gelernte Aufheizgeschwindigkeit vergessen und neu lernen?")) break;
        await this._ws({ type: "hauswerk/heizen/preheat/reset", room_id: el.dataset.id });
        if (this._status?.rooms?.[el.dataset.id]) this._status.rooms[el.dataset.id].learned = false;
        this._renderDialog();
        if (this._pop) this._renderPop();
        this._toast("Wird beim nächsten Aufheizen neu gelernt");
        break;
      case "role-set": {
        const room = this._dialog.room;
        const id = el.dataset.id;
        const assist = new Set(room.assist_entities || []);
        // „Alle selbst stellen“ von früher in einzelne Rollen umrechnen
        const own = new Set(room.pair_mode === "off"
          ? (room.climates || []).filter((c) => this._thermoKind(c) !== "wall" && !assist.has(c)) : room.pair_exclude || []);
        room.pair_mode = null;
        assist.delete(id);
        own.delete(id);
        if (el.dataset.v === "assist") assist.add(id);
        if (el.dataset.v === "own") own.add(id);
        room.assist_entities = [...assist];
        room.pair_exclude = [...own];
        this._renderDialog();
        break;
      }
      case "presence-mode":
        this._dialog.room.presence_mode = el.dataset.v;
        this._renderDialog();
        break;
      case "room-save":
        await this._saveDialog();
        break;
      case "room-delete":
        if (confirm(`Raum „${this._dialog.room.name}“ löschen? Heizplan und Bericht des Raums gehen verloren.`)) {
          const id = this._dialog.room.id;
          await this._ws({ type: "hauswerk/heizen/room/delete", room_id: id });
          delete this._data.rooms[id];
          this._dialog = null;
          this._renderDialog();
          this._renderMain();
        }
        break;
      case "pk-open": {
        const S = this._pkState(el.dataset.field);
        S.open = !S.open;
        this._rerenderPicker(el.dataset.field);
        if (S.open) this.shadowRoot.querySelector(`[data-picker-input="${el.dataset.field}"]`)?.focus();
        break;
      }
      case "pk-tab":
        this._pkState(el.dataset.field).tab = el.dataset.v;
        this._rerenderPicker(el.dataset.field);
        break;
      case "pk-dom": {
        const S = this._pkState(el.dataset.field);
        S.dom = S.dom === el.dataset.v ? "" : el.dataset.v;
        this._rerenderPicker(el.dataset.field);
        break;
      }
      case "pk-avail":
        this._pkState(el.dataset.field).avail = !this._pkState(el.dataset.field).avail;
        this._rerenderPicker(el.dataset.field);
        break;
      case "pick-add": {
        const field = el.dataset.field;
        // Nach der Wahl: Auswahl zuklappen (auch bei mehreren – „Weitere hinzufügen“ öffnet sie wieder), Suche zurücksetzen
        const S = this._pkState(field);
        S.q = "";
        S.open = false;
        const values = PICKERS[field].multi ? [...this._pickerValue(field), el.dataset.id] : [el.dataset.id];
        this._setPickerValue(field, values);
        break;
      }
      case "pick-remove": {
        const field = el.dataset.field;
        this._setPickerValue(field, this._pickerValue(field).filter((id) => id !== el.dataset.id));
        break;
      }
      case "ovr-reset":
        await this._ws({ type: "hauswerk/heizen/override", room_id: el.dataset.id, temp: null });
        if (this._pop?.id === "rq") this._closePop();
        break;
      case "room-quick": {
        const s = this._status?.rooms?.[el.dataset.id] || {};
        const room = this._data.rooms[el.dataset.id];
        if (!room) break;
        this._openPop("rq", { id: room.id, temp: s.target ?? room.comfort ?? 21, hours: null });
        break;
      }
      case "rq-dur":
        this._pop.draft.hours = el.dataset.h === "" ? null : Number(el.dataset.h);
        this._renderPop();
        break;
      case "rq-temp":
        this._pop.draft.temp = Number(el.dataset.t);
        this._renderPop();
        break;
      case "rq-apply": {
        const d = this._pop.draft;
        const name = this._data.rooms[d.id]?.name || "";
        await this._ws({ type: "hauswerk/heizen/override", room_id: d.id, temp: d.temp, hours: d.hours });
        this._closePop();
        this._toast(`${name}: ${fmt(d.temp)} °C ${d.hours ? `für ${d.hours} h` : "bis zum nächsten Planwechsel"}`);
        break;
      }
      case "rq-boost":
        await this._ws({ type: "hauswerk/heizen/override", room_id: el.dataset.id, boost: true });
        this._closePop();
        this._toast(`Boost für ${this._data.settings.boost_minutes || 30} Minuten`);
        break;
      case "boost":
        await this._ws({ type: "hauswerk/heizen/override", room_id: el.dataset.id, boost: true });
        this._toast(`Boost für ${this._data.settings.boost_minutes || 30} Minuten`);
        break;
      case "plan-preview":
        this._plan.day = Number(el.dataset.day);
        this._renderMain();
        break;
      case "plan-day": {
        const b = this._plan.blocks[Number(el.dataset.i)];
        const day = Number(el.dataset.day);
        b.days = b.days.includes(day) ? b.days.filter((x) => x !== day) : [...b.days, day].sort();
        this._plan.dirty = true;
        this._renderMain();
        break;
      }
      case "plan-days":
        this._plan.blocks[Number(el.dataset.i)].days = el.dataset.set.split(",").map(Number);
        this._plan.dirty = true;
        this._renderMain();
        break;
      case "plan-copy": {
        const i = Number(el.dataset.i);
        this._plan.blocks.splice(i + 1, 0, clone(this._plan.blocks[i]));
        this._plan.dirty = true;
        this._renderMain();
        break;
      }
      case "plan-add":
        this._plan.blocks.push({ days: [0, 1, 2, 3, 4], start: "06:00", end: "22:00", temp: null });
        this._plan.dirty = true;
        this._renderMain();
        break;
      case "plan-del":
        this._plan.blocks.splice(Number(el.dataset.i), 1);
        this._plan.dirty = true;
        this._renderMain();
        break;
      case "plan-revert":
        if (this._plan.id) this._selectPlan(this._plan.kind, this._plan.id);
        else this._plan = null;
        this._renderMain();
        break;
      case "plan-save": {
        const P = this._plan;
        const blocks = P.blocks.filter((b) => b.days.length);
        if (P.kind === "plan") {
          if (!P.name.trim()) {
            this._toast("Bitte einen Namen für den Plan eingeben.");
            return;
          }
          if (P.cal && !P.calendar) {
            this._toast("Bitte einen Kalender wählen.");
            return;
          }
          const saved = await this._ws({ type: "hauswerk/heizen/plan/save", plan: { id: P.id, name: P.name, schedule: blocks, calendar: P.cal ? P.calendar : null, keyword: P.cal ? P.keyword || null : null } });
          this._data.plans = { ...(this._data.plans || {}), [saved.id]: saved };
          this._selectPlan("plan", saved.id);
          this._renderMain();
          this._toast(P.id ? "Plan gespeichert" : "Plan angelegt – jetzt im Raum auswählen");
        } else {
          const room = { ...clone(this._data.rooms[P.id]), schedule: blocks };
          if (await this._saveRoom(room)) {
            this._selectPlan("room", room.id);
            this._renderMain();
            this._toast("Heizplan gespeichert");
          }
        }
        break;
      }
      case "settings-go":
        // zentrale Pop-ups unter Hauswerk-Einstellungen, alle anderen unter Heizwerk › Einstellungen
        this._setView(HOUSE_POPS.includes(el.dataset.sub) ? "house" : RW_POPS.includes(el.dataset.sub) || el.dataset.sub?.startsWith("rwc:") || el.dataset.sub?.startsWith("rwp:") ? "shutset" : "settings");
        if (el.dataset.sub) this._openPop(el.dataset.sub);
        break;
      case "person-new":
        this._newPerson = this._newPerson == null ? "" : null;
        this._renderPop();
        if (this._newPerson != null) this.shadowRoot.querySelector("[data-newp]")?.focus();
        break;
      case "person-create": {
        const name = (this._newPerson || "").trim();
        if (!name) {
          this._toast("Bitte einen Namen eingeben");
          break;
        }
        try {
          await this._hass.callWS({ type: "person/create", name });
        } catch (err) {
          this._toast(`Person nicht angelegt: ${err.message || err}`);
          break;
        }
        // Die neue Entität (person.…) erscheint kurz danach in Home Assistant
        let id = null;
        for (let i = 0; i < 20 && !id; i++) {
          id = Object.keys(this._hass.states).find((e) => e.startsWith("person.") && this._hass.states[e].attributes.friendly_name === name);
          if (!id) await new Promise((res) => setTimeout(res, 150));
        }
        if (id) this._settings.persons = [...new Set([...(this._settings.persons || []), id])];
        this._newPerson = null;
        this._refreshSettings();
        this._toast(id ? `${name} angelegt und ausgewählt` : `${name} angelegt – erscheint gleich in der Liste`);
        break;
      }
      case "notify-toggle": {
        const list = new Set(this._settings.notify_targets || []);
        if (list.has(el.dataset.id)) list.delete(el.dataset.id);
        else list.add(el.dataset.id);
        this._settings.notify_targets = [...list];
        this._refreshSettings();
        break;
      }
      case "notify-test":
        await this._ws({ type: "hauswerk/notify/test" });
        this._toast("Testnachricht gesendet");
        break;
      case "person-toggle": {
        const list = new Set(this._settings.persons || []);
        if (list.has(el.dataset.id)) list.delete(el.dataset.id);
        else list.add(el.dataset.id);
        this._settings.persons = [...list];
        this._refreshSettings();
        break;
      }
      case "min-step": {
        const k = el.dataset.key;
        this._settings[k] = Math.min(240, Math.max(0, Number(this._settings[k] ?? 0) + Number(el.dataset.d)));
        this._refreshSettings();
        break;
      }
      case "help":
        this._help = { ...(this._help || {}), [el.dataset.k]: !this._help?.[el.dataset.k] };
        this._renderPop();
        break;
      case "log-room":
        this._logRoom = el.dataset.id || "";
        this._logLimit = 200;
        this._renderMain();
        break;
      case "log-cat": {
        const cats = this._logCats();
        if (cats.has(el.dataset.k)) cats.delete(el.dataset.k);
        else cats.add(el.dataset.k);
        try {
          localStorage.setItem("hauswerk.protokoll.kategorien", JSON.stringify([...cats]));
        } catch (err) {
          /* ohne Speicher: gilt bis zum Neuladen */
        }
        this._logLimit = 200;
        this._renderMain();
        break;
      }
      case "log-more":
        this._logLimit = (this._logLimit || 200) + 300;
        this._renderLogList();
        break;
      case "look-accent":
        this._settings.look_accent = el.dataset.v || null;
        this._renderPop();
        break;
      case "look-size":
        try {
          localStorage.setItem("hauswerk.groesse", el.dataset.v);
        } catch (err) {
          /* ohne Speicher: gilt bis zum Neuladen */
        }
        this.setAttribute("size", el.dataset.v);
        this._renderPop();
        break;
      case "start-edit":
        this._wEdit = true;
        this._setView("start");
        break;
      case "rw-cmd":
        await this._ws({ type: "hauswerk/rollwerk/command", entity_ids: el.dataset.ids.split(",").filter(Boolean), action: el.dataset.a });
        break;
      case "rwc-set":
        this._pop.draft.cfg[el.dataset.k] = el.dataset.v || null;
        this._renderPop();
        break;
      case "rwp-tog": {
        const pr = this._pop.draft.prof, k = el.dataset.k, v = el.dataset.v;
        const list = new Set(pr[k] || []);
        if (list.has(v)) list.delete(v); else list.add(v);
        pr[k] = [...list];
        this._renderPop();
        break;
      }
      case "rwp-set":
        this._pop.draft.prof[el.dataset.k] = el.dataset.v;
        this._renderPop();
        break;
      case "rwp-feat": {
        const pr = this._pop.draft.prof;
        const f = new Set(pr.features || []);
        if (el.type === "checkbox" ? !el.checked : f.has(el.dataset.v) && el.tagName !== "BUTTON") f.delete(el.dataset.v);
        else f.add(el.dataset.v);
        pr.features = [...f];
        this._renderPop();
        break;
      }
      case "rwp-mode": {
        const pr = this._pop.draft.prof;
        const f = new Set(pr.features || []);
        const v = el.dataset.v;
        f.delete("sun");
        if (v === "free") f.delete("time"); else f.add("time");
        if (v === "sun" || v === "free") f.add("sun");
        if (v === "time" || v === "cal") f.delete("brightness");
        pr.time_mode = v === "cal" ? "calendar" : "times";
        if (v === "time") for (const [a, b] of [["up_early", "up_late"], ["up_early_we", "up_late_we"], ["down_early", "down_late"], ["down_early_we", "down_late_we"]]) pr[b] = pr[a];
        pr.features = [...f];
        this._renderPop();
        break;
      }
      case "rwp-dir": {
        const pr = this._pop.draft.prof;
        const dir = Number(el.dataset.v);
        pr.window_dir = dir;
        pr.azimuth_start = (dir - 75 + 360) % 360;
        pr.azimuth_end = (dir + 75) % 360;
        this._renderPop();
        break;
      }
      case "rwp-lock":
        this._pop.draft.prof.pos_lockout = el.dataset.v === "" ? null : Number(el.dataset.v);
        if (el.dataset.v !== "") this._pop.draft.prof.features = [...new Set([...(this._pop.draft.prof.features || []), "ventilate"])];
        this._renderPop();
        break;
      case "rwp-man": {
        const pr = this._pop.draft.prof;
        const v = el.dataset.v;
        pr.manual_block = v === "next" ? [] : ["opening", "closing", "shading", "ventilation"];
        pr.manual_reset = v === "night" ? ["fixed"] : v === "hours" ? ["timeout"] : [];
        if (v === "night") pr.reset_time = "00:01";
        if (v === "hours" && !(pr.reset_timeout > 5)) pr.reset_timeout = 120;
        this._renderPop();
        break;
      }
      case "rw-expert":
        this._expert = !this._expertOn();
        try {
          localStorage.setItem("hauswerk.experte", this._expert ? "1" : "0");
        } catch (err) {
          /* ohne Speicher: gilt bis zum Neuladen */
        }
        this._renderPop();
        break;
      case "rwp-sec": {
        const [, pid] = this._pop.id.split(":");
        this._pop.id = `rwp:${pid}:${el.dataset.sec}`;
        this._pop.keep = false;
        this._renderPop();
        break;
      }
      case "rwp-save": {
        const d = this._pop.draft;
        if (!String(d.prof.name || "").trim()) { this._toast("Bitte einen Namen eingeben."); return; }
        const res = await this._ws({ type: "hauswerk/rollwerk/profile/save", profile_id: d.pid, profile: d.prof });
        this._data.rollwerk.profiles = res.profiles;
        this._closePop();
        this._renderMain();
        this._toast(d.pid ? "Gespeichert" : "Verhalten angelegt");
        break;
      }
      case "rwp-del": {
        const d = this._pop.draft;
        if (!d.confirm) { d.confirm = true; this._renderPop(); return; }
        const res = await this._ws({ type: "hauswerk/rollwerk/profile/delete", profile_id: d.pid });
        this._data.rollwerk.profiles = res.profiles;
        this._data.rollwerk.covers = res.covers;
        this._closePop();
        this._renderMain();
        this._toast("Verhalten gelöscht");
        break;
      }
      case "rwc-save": {
        const res = await this._ws({ type: "hauswerk/rollwerk/cover/save", entity_id: el.dataset.id, cover: this._pop.draft.cfg });
        this._data.rollwerk.covers = res.covers;
        if (res.profiles) this._data.rollwerk.profiles = res.profiles;
        this._closePop();
        this._renderMain();
        this._toast("Gespeichert");
        break;
      }
      case "set-seg":
        this._settings[el.dataset.key] = el.dataset.v;
        this._refreshSettings();
        break;
      case "report-days":
        this._reportDays = Number(el.dataset.days);
        this._renderMain();
        break;
    }
  }

  async _step(kind, key, delta) {
    if (kind === "dlg") {
      const r = this._dialog.room;
      r[key] = clampT((r[key] ?? 20) + delta);
      this._renderDialog();
    } else if (kind === "blk") {
      const room = this._planRef();
      const b = this._plan.blocks[Number(key)];
      b.temp = clampT((b.temp ?? room.comfort) + delta);
      this._plan.dirty = true;
      this._renderMain();
    } else if (kind === "set") {
      this._settings[key] = clampT((this._settings[key] ?? 17) + delta);
      this._refreshSettings();
    } else if (kind === "rq") {
      this._pop.draft.temp = clampT((this._pop.draft.temp ?? 20) + delta);
      this._renderPop();
    } else if (kind === "ovr") {
      const s = this._status?.rooms?.[key] || {};
      const base = s.target ?? this._data.rooms[key].comfort;
      const temp = clampT(base + delta);
      // sofort anzeigen, der Server bestätigt per Abo
      if (this._status?.rooms?.[key]) Object.assign(this._status.rooms[key], { target: temp, mode: "manuell", mode_label: "Manuell" });
      this._renderMain();
      await this._ws({ type: "hauswerk/heizen/override", room_id: key, temp });
    }
  }

  async _saveRoom(room) {
    try {
      const saved = await this._ws({ type: "hauswerk/heizen/room/save", room });
      this._data.rooms[saved.id] = saved;
      if (this._tab !== "plans") this._renderMain();
      return saved;
    } catch (e) {
      return null;
    }
  }

  async _saveDialog() {
    const r = this._dialog.room;
    if (!r.name || !r.name.trim()) {
      this._dialog.tab = "basis";
      this._renderDialog();
      this._toast("Bitte einen Namen eingeben.");
      return;
    }
    if (r.eco > r.comfort) {
      this._toast("Eco sollte nicht wärmer sein als Komfort.");
      return;
    }
    const saved = await this._saveRoom(r);
    if (saved) {
      this._dialog = null;
      this._renderDialog();
      this._renderMain();
    }
  }
}

/* Eigenes Zeichen: Flamme in einem Thermostat-Ring */
// Symbole der Module – gleiche Hausform wie das Hauswerk-Logo, eigene Farbe und eigenes Innenleben
const MODULE_LOGOS = {
  heizen: `<svg viewBox="0 0 48 48" aria-hidden="true">
  <defs><linearGradient id="hwlg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fdba74"/><stop offset="1" stop-color="#c2410c"/></linearGradient></defs>
  <rect width="48" height="48" rx="13" fill="url(#hwlg)"/>
  <path d="M10.5 23.5 24 11.5l13.5 12" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M14.8 21.8V34.2a2.8 2.8 0 0 0 2.8 2.8h12.8a2.8 2.8 0 0 0 2.8-2.8V21.8" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="18.6" y="22.6" width="3" height="10.8" rx="1.5" fill="#fff"/>
  <rect x="22.5" y="22.6" width="3" height="10.8" rx="1.5" fill="#fde68a"/>
  <rect x="26.4" y="22.6" width="3" height="10.8" rx="1.5" fill="#fff" opacity=".6"/>
</svg>`,
  rollwerk: `<svg viewBox="0 0 48 48" aria-hidden="true">
  <defs><linearGradient id="rwlg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7dd3fc"/><stop offset="1" stop-color="#0369a1"/></linearGradient></defs>
  <rect width="48" height="48" rx="13" fill="url(#rwlg)"/>
  <path d="M10.5 23.5 24 11.5l13.5 12" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M14.8 21.8V34.2a2.8 2.8 0 0 0 2.8 2.8h12.8a2.8 2.8 0 0 0 2.8-2.8V21.8" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="18.6" y="22.6" width="10.8" height="3" rx="1.5" fill="#fff"/>
  <rect x="18.6" y="26.6" width="10.8" height="3" rx="1.5" fill="#fff" opacity=".6"/>
  <rect x="18.6" y="30.6" width="10.8" height="3" rx="1.5" fill="#fdba74"/>
</svg>`,
};
/** ha-icon oder – bei „logo:<modul>“ – das eigene Symbol des Moduls. */
// Jede Kopie bekommt eigene IDs für den Farbverlauf: sonst bleibt sie leer, wenn die erste Kopie verborgen ist.
let logoNo = 0;
const modIcon = (icon) => {
  const svg = String(icon).startsWith("logo:") && MODULE_LOGOS[icon.slice(5)];
  if (!svg) return `<ha-icon icon="${icon}"></ha-icon>`;
  const n = ++logoNo;
  return `<span class="mlogo">${svg.replace(/id="(\w+)"/g, `id="$1${n}"`).replace(/url\(#(\w+)\)/g, `url(#$1${n})`)}</span>`;
};

const LOGO = `
<svg viewBox="0 0 48 48" aria-hidden="true">
  <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:color-mix(in srgb, var(--accent) 75%, #fff)"/><stop offset="1" style="stop-color:color-mix(in srgb, var(--accent) 65%, #000)"/></linearGradient></defs>
  <rect width="48" height="48" rx="13" fill="url(#lg)"/>
  <path d="M10.5 23.5 24 11.5l13.5 12" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M14.8 21.8V34.2a2.8 2.8 0 0 0 2.8 2.8h12.8a2.8 2.8 0 0 0 2.8-2.8V21.8" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="18.6" y="22.8" width="4.6" height="4.6" rx="1.3" fill="#fdba74"/>
  <rect x="24.8" y="22.8" width="4.6" height="4.6" rx="1.3" fill="#fff"/>
  <rect x="18.6" y="29" width="4.6" height="4.6" rx="1.3" fill="#fff"/>
  <rect x="24.8" y="29" width="4.6" height="4.6" rx="1.3" fill="#fff" opacity=".55"/>
</svg>`;

const STYLE = `
/* Farben kommen aus dem Home-Assistant-Theme: hell oder dunkel wie dort eingestellt. */
:host {
  --text:var(--primary-text-color, #1f2328); --muted:var(--secondary-text-color, #5f6670);
  --bg:var(--primary-background-color, #f3f5f7); --card:var(--card-background-color, var(--ha-card-background, #fff));
  --card2:var(--secondary-background-color, #eceff2);
  --line:var(--divider-color, rgba(0,0,0,.1)); --line2:color-mix(in srgb, var(--text) 18%, transparent);
  --track:color-mix(in srgb, var(--text) 22%, transparent);
  --accent:#0f9488; --ink:#fff; --shade:38%; --shadow:0 8px 24px rgba(0,0,0,.10); --r:18px;
  display:block; min-height:100vh; background:var(--bg); color:var(--text);
  font-family:var(--paper-font-body1_-_font-family, Inter, "Segoe UI", Roboto, system-ui, sans-serif); -webkit-font-smoothing:antialiased;
}
:host([dark]) {
  --text:var(--primary-text-color, #f1f3f4); --muted:var(--secondary-text-color, #9aa0a6);
  --bg:var(--primary-background-color, #111315); --card:var(--card-background-color, var(--ha-card-background, #1b1d20));
  --card2:var(--secondary-background-color, #24272b); --line:var(--divider-color, rgba(255,255,255,.1));
  --accent:#2dd4bf; --ink:#04211d; --shade:0%; --shadow:0 10px 30px rgba(0,0,0,.45);
}
* { box-sizing:border-box; scrollbar-color:var(--track) transparent; scrollbar-width:thin;
  --ct:color-mix(in srgb, var(--c, currentColor), var(--text) var(--shade));
  --rct:color-mix(in srgb, var(--rc, currentColor), var(--text) var(--shade)); }
ha-icon { --mdc-icon-size:18px; flex:none; }
button { font:inherit; color:inherit; }
.app { max-width:1180px; margin:0 auto; padding:16px 20px 40px; }
.grow { flex:1; }
.muted { color:var(--muted); }
.small { font-size:12px; }
code { background:var(--card2); padding:1px 6px; border-radius:6px; font-size:12px; }

/* Kopfleiste (fest oben) mit Modul-Reitern */
.top { position:sticky; top:0; z-index:6; padding:8px max(16px, calc((100% - 1180px) / 2 + 20px)) 0;
  background:linear-gradient(135deg, color-mix(in srgb, var(--accent) 20%, var(--bg)), color-mix(in srgb, #60a5fa 14%, var(--bg)));
  border-bottom:1px solid var(--line); }
.bar { display:flex; align-items:center; gap:12px; min-height:58px; }
.menu { all:unset; cursor:pointer; width:40px; height:40px; border-radius:50%; display:grid; place-items:center; flex:none; }
.menu ha-icon { --mdc-icon-size:24px; }
:host(:not([narrow])) .menu { display:none; }
.brand svg { width:44px; height:44px; display:block; }
.ttl { display:flex; flex-direction:column; min-width:0; flex:1; line-height:1.2; }
.ttl small { font-size:10.5px; letter-spacing:.14em; font-weight:800; color:var(--accent); }
.ttl b { font-size:19px; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ttl span { font-size:12px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hacts { display:flex; gap:8px; flex:none; }
.abtn { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:7px; padding:9px 15px; border-radius:99px; font-weight:600; font-size:14px;
  background:var(--card); border:1px solid var(--line); }
.abtn:hover { border-color:var(--line2); }
.abtn.active { border-color:var(--accent); color:var(--accent); }
.mtabs { display:flex; gap:10px; overflow-x:auto; padding:10px 0 12px; scrollbar-width:none; }
.mtabs::-webkit-scrollbar { display:none; }
.mtab { all:unset; cursor:pointer; flex:none; display:inline-flex; align-items:center; gap:10px; padding:9px 14px; border-radius:16px;
  background:var(--card); border:1px solid var(--line); }
.mtab > ha-icon { --mdc-icon-size:22px; color:var(--muted); }
.mtab .mt { display:flex; flex-direction:column; line-height:1.15; }
.mtab .mt small { font-size:10.5px; color:var(--muted); }
.mtab .mt b { font-size:15px; font-weight:600; }
.mtab:hover { border-color:var(--line2); }
.mtab.active { border-color:var(--accent); background:color-mix(in srgb, var(--accent) 12%, var(--card)); }
.mtab.active > ha-icon, .mtab.active .mt small { color:var(--accent); }
.mtab.soon { cursor:default; opacity:.45; border-style:dashed; }
.mtab.soon:hover { border-color:var(--line); }
.badge { font-style:normal; font-size:10px; font-weight:800; letter-spacing:.05em; padding:2px 8px; border-radius:99px; color:var(--muted); border:1px solid var(--line2); }
.badge.ok { --c:#fb923c; color:var(--ct); border-color:color-mix(in srgb, var(--c) 55%, transparent); background:color-mix(in srgb, var(--c) 12%, transparent); }
.badge.warn { --c:#06b6d4; color:var(--ct); border-color:color-mix(in srgb, var(--c) 55%, transparent); background:color-mix(in srgb, var(--c) 12%, transparent); }

/* Unterleiste im Modul Heizen */
.heatnav { display:flex; gap:4px; padding:4px; margin:0 0 16px; border-radius:16px; background:var(--card); border:1px solid var(--line); overflow-x:auto; scrollbar-width:none; }
.heatnav::-webkit-scrollbar { display:none; }
.hnav { all:unset; cursor:pointer; flex:1 0 auto; display:flex; align-items:center; justify-content:center; gap:8px; padding:10px 14px; border-radius:12px; font-weight:600; font-size:14px; color:var(--muted); white-space:nowrap; }
.hnav:hover { color:var(--text); background:var(--card2); }
.hnav.on { color:var(--text); background:color-mix(in srgb, var(--accent) 16%, var(--card)); box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--accent) 45%, transparent); }
.hnav.on ha-icon { color:var(--accent); }
.hnav em { font-style:normal; font-size:11px; font-weight:700; padding:1px 7px; border-radius:99px; color:var(--muted); background:var(--card2); }
.hnav em.ok { --c:#fb923c; color:var(--ct); background:color-mix(in srgb, var(--c) 14%, transparent); }
.hnav em.warn { --c:#06b6d4; color:var(--ct); background:color-mix(in srgb, var(--c) 14%, transparent); }

/* Status-Chips */
.schips { display:flex; gap:10px; overflow-x:auto; padding:2px 0 14px; scrollbar-width:none; }
.schips::-webkit-scrollbar { display:none; }
.schip { all:unset; flex:none; display:inline-flex; align-items:center; gap:9px; padding:8px 15px 8px 12px; border-radius:99px; background:var(--card); border:1px solid var(--line); }
.schip > ha-icon { --mdc-icon-size:20px; color:var(--ct); }
.schip:not([style]) > ha-icon { color:var(--muted); }
.schip > span { display:flex; flex-direction:column; line-height:1.15; }
.schip b { font-size:13.5px; } .schip small { font-size:10.5px; color:var(--muted); }

/* Start */
.start .stit { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
.start .stit ha-icon { --mdc-icon-size:20px; color:var(--accent); }
.hl { margin:0 0 4px; font-size:26px; font-weight:800; letter-spacing:-.01em; --c:#14b8a6; color:var(--ct); }
.hl.warn { --c:#f59e0b; }
.hsub { margin:0 0 16px; color:var(--muted); font-size:14px; }
.mtiles { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:12px; }
.mtile { all:unset; cursor:pointer; display:flex; flex-direction:column; align-items:center; gap:6px; padding:18px 10px; border-radius:18px; text-align:center;
  background:color-mix(in srgb, var(--card2) 55%, var(--card)); border:1px solid var(--line); }
.mtile:hover { border-color:var(--line2); transform:translateY(-1px); }
.mtile.warn { --c:#f59e0b !important; background:color-mix(in srgb, #f59e0b 12%, var(--card)); border-color:color-mix(in srgb, #f59e0b 60%, transparent); }
.mico { width:46px; height:46px; border-radius:14px; display:grid; place-items:center; background:color-mix(in srgb, var(--c) 18%, transparent); color:var(--ct); }
.mico ha-icon { --mdc-icon-size:26px; }
.mtile b { font-size:15px; }
.mtile small { font-size:12.5px; color:var(--muted); }
.mtile small.g { --c:#14b8a6; color:var(--ct); font-weight:600; }
.gmini { display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:10px; }
.gm { all:unset; cursor:pointer; display:flex; flex-direction:column; gap:4px; padding:12px 14px; border-radius:14px; background:color-mix(in srgb, var(--card2) 55%, var(--card));
  border:1px solid var(--line); border-left:4px solid var(--acc); }
.gm:hover { border-color:var(--line2); border-left-color:var(--acc); }
.gh { display:flex; align-items:center; gap:7px; font-weight:600; font-size:14px; }
.gh ha-icon { --mdc-icon-size:18px; color:var(--muted); }
.gh .gn { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.gh .gf { --c:#fb923c; color:var(--ct); }
.gt { font-size:26px; font-weight:800; letter-spacing:-.02em; }
.gt small { font-size:13px; font-weight:500; color:var(--muted); margin-left:2px; }
.gl { display:flex; align-items:center; gap:5px; font-size:12px; font-weight:600; color:var(--ct); }
.gl ha-icon { --mdc-icon-size:14px; }

/* Karten */
.card { background:var(--card); border:1px solid var(--line); border-radius:var(--r); padding:18px 20px; margin-bottom:14px; }
.shead { display:flex; align-items:center; gap:10px; margin-bottom:14px; }
.shead ha-icon { color:var(--accent); }
.shead h3 { margin:0; font-size:16px; font-weight:600; }
.shead.outer { margin:22px 2px 12px; }
.empty { text-align:center; padding:36px 20px; color:var(--muted); }
.empty ha-icon { --mdc-icon-size:46px; color:var(--accent); opacity:.8; }
.empty h2 { color:var(--text); margin:10px 0 6px; font-size:18px; }
.empty.small { padding:18px; }
.loading, .chart-empty { display:grid; place-items:center; padding:60px 0; }
.spinner { width:28px; height:28px; border-radius:50%; border:3px solid var(--line2); border-top-color:var(--accent); animation:spin 1s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

/* Banner */
.hero { color:#fff; position:relative; overflow:hidden; display:flex; align-items:center; gap:20px; padding:24px 28px; margin-bottom:14px; border-radius:22px;
  background:radial-gradient(120% 140% at 85% 0%, rgba(45,212,191,.55) 0%, rgba(45,212,191,0) 55%),
             linear-gradient(115deg, #0f5f63 0%, #11505a 40%, #0c3446 100%);
  box-shadow:0 10px 40px rgba(0,0,0,.35); }
.hero::after { content:""; position:absolute; inset:auto -10% -60% 30%; height:120%; background:radial-gradient(closest-side, rgba(255,255,255,.06), transparent); pointer-events:none; }
.hero-text { flex:1; min-width:0; position:relative; z-index:1; }
.hero-label { display:flex; gap:7px; align-items:center; font-size:14px; color:rgba(255,255,255,.85); }
.hero-big { font-size:64px; font-weight:800; letter-spacing:-.03em; line-height:1.05; margin-top:6px; }
.hero-big span { font-size:22px; font-weight:500; margin-left:6px; letter-spacing:0; }
.hero-date { color:rgba(255,255,255,.75); font-size:14px; margin-bottom:16px; }
.hero-chips { display:flex; gap:8px; flex-wrap:wrap; }
.hchip { display:inline-flex; align-items:center; gap:7px; padding:7px 13px; border-radius:99px; background:rgba(255,255,255,.12); backdrop-filter:blur(6px); font-size:13px; font-weight:500; }
.gauge { width:190px; flex:none; position:relative; z-index:1; }
.gauge svg { width:100%; display:block; }
.g-small { fill:rgba(255,255,255,.7); font-size:12px; }
.g-big { fill:#fff; font-size:26px; font-weight:800; }

/* Anwesenheit */
.segs { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; }
.seg { all:unset; cursor:pointer; display:flex; flex-direction:column; align-items:center; gap:6px; padding:14px 8px; border-radius:14px; border:1px solid var(--line2); color:var(--muted); font-weight:600; font-size:14px; text-align:center; }
.seg ha-icon { --mdc-icon-size:22px; }
.seg:hover { background:var(--card2); }
.seg.on { border-color:var(--accent); color:var(--text); background:color-mix(in srgb, var(--accent) 14%, var(--card)); }
.seg.on ha-icon { color:var(--accent); }
.seg[disabled] { cursor:default; }
.segs.small .seg { flex-direction:row; justify-content:center; padding:10px 8px; font-size:13px; }
.ptext { margin:14px 0 8px; color:var(--muted); line-height:1.5; }
.ptext b { color:var(--text); }
.links { display:flex; gap:20px; flex-wrap:wrap; }
.link { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:6px; color:var(--accent); font-weight:600; font-size:14px; }
.link:hover { filter:brightness(1.15); }
.link.tiny { font-size:12px; }
.tiny { font-size:12px; }

/* Kennzahlen */
.kpis { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:14px; }
.kpi { position:relative; background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px 16px 14px 20px; overflow:hidden; }
.kpi::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--k); }
.kpi-l { display:flex; gap:7px; align-items:center; color:var(--muted); font-size:13px; }
.kpi-v { font-size:28px; font-weight:800; margin:6px 0 2px; letter-spacing:-.02em; }
.kpi-v span { font-size:14px; font-weight:500; color:var(--muted); margin-left:5px; letter-spacing:0; }
.kpi-s { font-size:12px; color:var(--muted); }

/* Diagramm */
.chart-wrap { position:relative; }
.chart { width:100%; height:240px; display:block; }
.gl { stroke:var(--line2); stroke-dasharray:4 6; }
.ax { fill:var(--muted); font-size:13px; }
.ax.today { fill:var(--text); font-weight:700; }
.chart-note { position:absolute; inset:0 0 30px 44px; display:grid; place-items:center; color:var(--muted); font-size:14px; }
.legend { display:flex; flex-wrap:wrap; gap:6px 16px; margin-top:12px; font-size:13px; color:var(--muted); }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.legend i { width:10px; height:10px; border-radius:3px; }

/* Räume */
.rooms { display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:12px; }
.room { background:var(--card); border:1px solid var(--line); border-radius:var(--r); padding:16px 18px; position:relative; overflow:hidden; display:flex; flex-direction:column; }
.room::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--rc); }
.room-head { display:flex; align-items:center; gap:12px; }
.room-ic { width:40px; height:40px; border-radius:12px; display:grid; place-items:center; background:color-mix(in srgb, var(--rc) 18%, transparent); color:var(--rct); }
.room-ic { position:relative; flex:none; }
.room-ic > ha-icon { --mdc-icon-size:22px; }
.flame { position:absolute; right:-5px; bottom:-5px; width:20px; height:20px; border-radius:50%; display:grid; place-items:center; background:#fb923c; color:#fff; border:2px solid var(--card); }
.flame ha-icon { --mdc-icon-size:12px; }
.room-t small { display:inline-flex; align-items:center; gap:4px; }
.room-t small ha-icon { --mdc-icon-size:13px; }
.room.off { opacity:.62; }
.room.off .room-temp { color:var(--muted); }
.trend { display:inline-flex; align-items:center; gap:4px; margin-top:6px; font-size:12px; font-weight:600; color:var(--ct); }
.trend ha-icon { --mdc-icon-size:15px; }
.room-set small { display:inline-flex !important; align-items:center; gap:4px; }
.room-set small ha-icon { --mdc-icon-size:13px; }
.sis { display:flex; align-items:center; gap:4px; min-width:0; overflow:hidden; }
.room-foot { flex-wrap:nowrap !important; }
.si .t { white-space:nowrap; }
.si { display:inline-flex; align-items:center; gap:4px; height:28px; padding:0 7px; border-radius:9px; color:var(--ct); font-size:12px; font-weight:600; background:color-mix(in srgb, var(--c) 10%, transparent); }
.si ha-icon { --mdc-icon-size:16px; }
.acts { display:flex; align-items:center; gap:2px; padding:2px; border-radius:12px; background:var(--card2); }
.acts .icon { width:32px; height:32px; }
.acts:empty { display:none; }
.icon.auto-on { color:var(--accent); }
.icon.auto-off { color:#f87171; background:color-mix(in srgb, #f87171 14%, transparent); }
.room.off .acts { opacity:1; }
.room-t { flex:1; min-width:0; }
.room-t h4 { margin:0; font-size:16px; line-height:1.25; white-space:normal; overflow-wrap:break-word; hyphens:manual; }
.room-t small { color:var(--muted); font-size:12px; }
.mode { display:inline-flex; align-items:center; gap:5px; padding:4px 10px 4px 8px; border-radius:99px; font-size:12px; font-weight:600;
  color:var(--ct); background:color-mix(in srgb, var(--c) 15%, transparent); border:1px solid color-mix(in srgb, var(--c) 35%, transparent); white-space:nowrap; }
.mode ha-icon { --mdc-icon-size:15px; }
.room-body { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:16px 0 12px; }
.room-now small, .room-set small { display:block; color:var(--muted); font-size:12px; margin-bottom:2px; }
.room-set { text-align:right; }
.room-temp { font-size:42px; font-weight:800; letter-spacing:-.03em; line-height:1; }
.room-temp span { font-size:16px; font-weight:500; color:var(--muted); margin-left:3px; }
.tgt { font-size:20px; }
.room-note { display:flex; align-items:center; gap:7px; font-size:13px; padding:8px 10px; border-radius:10px; background:color-mix(in srgb, #a78bfa 12%, transparent); margin-bottom:10px; }
.room-note.warn { background:color-mix(in srgb, #f59e0b 14%, transparent); }
.room-foot { display:flex; align-items:center; gap:10px; flex-wrap:wrap; border-top:1px solid var(--line); padding-top:12px; margin-top:auto; }
.dot-l { display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600; color:var(--ct); }
.dot-l i { width:8px; height:8px; border-radius:50%; background:var(--c); box-shadow:0 0 0 3px color-mix(in srgb, var(--c) 25%, transparent); }
.dot-l.plain { color:var(--muted); font-weight:500; }
.icon { all:unset; cursor:pointer; width:34px; height:34px; display:grid; place-items:center; border-radius:10px; color:var(--muted); }
.icon:hover { background:var(--card2); color:var(--text); }
.icon.boxed { border:1px solid var(--line2); }

/* Stepper */
.stepper { display:inline-flex; align-items:center; gap:10px; }
.stepper b { min-width:78px; text-align:center; font-size:22px; font-weight:800; letter-spacing:-.01em; }
.stepper.small b { min-width:64px; font-size:19px; }
.sbtn { all:unset; cursor:pointer; width:38px; height:38px; display:grid; place-items:center; border-radius:50%; border:1px solid var(--line2); font-size:20px; line-height:1; }
.stepper.small .sbtn { width:32px; height:32px; font-size:18px; }
.sbtn:hover { border-color:var(--accent); color:var(--accent); }

/* Schalter */
.switch { position:relative; display:inline-block; width:46px; height:26px; flex:none; }
.switch input { opacity:0; width:0; height:0; position:absolute; }
.switch > span { position:absolute; inset:0; border-radius:99px; background:var(--track); transition:.2s; cursor:pointer; }
.switch > span::after { content:""; position:absolute; width:20px; height:20px; left:3px; top:3px; border-radius:50%; background:#fff; transition:.2s; }
.switch input:checked + span { background:var(--accent); }
.switch input:checked + span::after { transform:translateX(20px); }
.switch input:disabled + span { opacity:.4; cursor:default; }

/* Pillen */
.pills { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }
.pill { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:8px; padding:8px 14px; border-radius:99px; background:var(--card); border:1px solid var(--line); font-size:14px; font-weight:500; }
.pill i { width:8px; height:8px; border-radius:50%; background:var(--rc); }
.pill.on { border-color:var(--accent); background:color-mix(in srgb, var(--accent) 14%, var(--card)); }

/* Heizplan */
.plan-head { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:18px; }
.plan-head h2 { margin:0; font-size:22px; }
.plan-temps { display:flex; gap:8px; flex-wrap:wrap; align-items:flex-start; }
.tpill { padding:6px 12px; border-radius:99px; background:var(--card2); font-size:13px; color:var(--muted); }
.tpill b { color:var(--ct); margin-left:4px; }
.lbl { color:var(--muted); font-size:13px; margin:4px 0 8px; }
.daypills { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
.dp { all:unset; cursor:pointer; width:42px; height:36px; display:grid; place-items:center; border-radius:99px; border:1px solid var(--line2); font-size:14px; font-weight:600; color:var(--muted); }
.dp:hover { border-color:var(--accent); }
.dp.on { background:var(--accent); border-color:var(--accent); color:var(--ink); }
.dp[disabled] { cursor:default; }
.dbar { position:relative; height:22px; border-radius:99px; overflow:hidden; background:var(--card2); }
.dbar.mini { height:12px; }
.dseg { position:absolute; top:0; bottom:0; }
.dseg.eco { background:color-mix(in srgb, #60a5fa 38%, var(--card2)) !important; }
.dseg + .dseg { box-shadow:inset 2px 0 0 var(--card); }
.now { position:absolute; top:-3px; bottom:-3px; width:4px; margin-left:-2px; border-radius:2px; background:#fff; box-shadow:0 0 0 2px rgba(0,0,0,.45); }
.legend-line { display:flex; flex-wrap:wrap; gap:6px 16px; align-items:center; }
.legend-line span { display:inline-flex; align-items:center; gap:6px; }
.legend-line i { width:14px; height:8px; border-radius:4px; }
.dscale {display:flex; justify-content:space-between; color:var(--muted); font-size:12px; margin:6px 2px 4px; }
.week-mini { display:grid; gap:7px; margin-top:18px; padding-top:16px; border-top:1px solid var(--line); }
.wm-row { display:grid; grid-template-columns:28px 1fr; align-items:center; gap:8px; font-size:12px; color:var(--muted); }
.blocks { display:grid; gap:12px; }
.block { background:var(--card); border:1px solid var(--line); border-radius:var(--r); padding:16px 18px 16px 22px; position:relative; overflow:hidden; }
.block::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--tc); }
.block-top { display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin-bottom:12px; }
.times { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.dur { font-size:12px; color:var(--muted); padding:4px 10px; border-radius:99px; background:var(--card2); margin-left:4px; }
.block .dp { width:38px; height:32px; font-size:13px; }
.block .dp.on { background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent); border-color:color-mix(in srgb, var(--accent) 55%, transparent); }
.addbtn { all:unset; cursor:pointer; flex:1; display:flex; align-items:center; justify-content:center; gap:8px; padding:14px; border-radius:var(--r); border:1.5px dashed var(--line2); color:var(--accent); font-weight:600; font-size:14px; }
.addbtn:hover { border-color:var(--accent); background:color-mix(in srgb, var(--accent) 8%, transparent); }
.timebox { display:flex; align-items:center; gap:8px; padding:0 12px; border-radius:12px; border:1px solid var(--line2); background:var(--bg); }
.timebox input { all:unset; font-size:20px; font-weight:700; padding:9px 0; width:76px; color-scheme:dark; }
.timebox input::-webkit-calendar-picker-indicator { display:none; }
.timebox ha-icon { color:var(--muted); }
.block-temp { display:flex; align-items:center; gap:10px; flex:1; justify-content:flex-end; }
.quick { display:flex; gap:18px; flex-wrap:wrap; }
.plan-tools { display:flex; align-items:stretch; gap:12px; margin:12px 0 16px; flex-wrap:wrap; }
.plan-tools .ghost { border-radius:var(--r); padding:0 18px; }
.unit input { max-width:140px; }
.select-link { position:relative; }
.select-link select { position:absolute; inset:0; opacity:0; cursor:pointer; }
.savebar { position:sticky; bottom:12px; display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px; z-index:4; }
.primary, .secondary, .danger { all:unset; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; gap:8px; padding:13px 22px; border-radius:14px; font-weight:700; font-size:15px; text-align:center; }
.primary { background:var(--accent); color:var(--ink); }
.primary:hover { filter:brightness(1.08); }
.secondary { background:var(--card2); border:1px solid var(--line2); }
.danger { color:#f87171; border:1px solid color-mix(in srgb, #f87171 40%, transparent); padding:13px 16px; }
.primary[disabled], .secondary[disabled] { background:var(--card2); color:var(--muted); pointer-events:none; }
.savebar .primary, .savebar .secondary { box-shadow:var(--shadow); }

/* Bericht */
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:14px; }
th { text-align:left; color:var(--muted); font-weight:500; font-size:12px; padding:0 10px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
td { padding:12px 10px; border-bottom:1px solid var(--line); white-space:nowrap; font-weight:600; }
td small { display:block; color:var(--muted); font-weight:400; font-size:12px; margin-left:18px; }
.rdot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:8px; }

/* Formulare */
.field { display:flex; flex-direction:column; gap:7px; margin-bottom:16px; }
.field > span { font-size:13px; color:var(--muted); font-weight:500; }
.field.narrow { max-width:280px; }
.field > small { font-size:12px; }
.sub-h { display:flex; align-items:center; gap:8px; margin:22px 0 6px; padding-top:16px; border-top:1px solid var(--line); font-weight:700; font-size:14px; }
.sub-h ha-icon { color:var(--accent); }
.sub-h + p { margin-top:0; }
.sheet-body > .sub-h:first-of-type, .sheet-body > p:first-child + .sub-h { margin-top:4px; padding-top:0; border-top:none; }
.segs.small { grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); }
.savebar[hidden] { display:none; }
.subnav { display:flex; gap:6px; overflow-x:auto; scrollbar-width:none; margin-bottom:14px; padding-bottom:2px; }
.snav { all:unset; cursor:pointer; flex:none; display:inline-flex; align-items:center; gap:8px; padding:9px 14px; border-radius:12px; color:var(--muted); font-weight:600; font-size:14px; border:1px solid transparent; }
.snav:hover { color:var(--text); background:var(--card); }
.snav.on { color:var(--text); background:var(--card); border-color:var(--line2); }
.snav.on ha-icon { color:var(--accent); }
.snav em { font-style:normal; font-size:11px; font-weight:700; padding:1px 7px; border-radius:99px; background:color-mix(in srgb, var(--accent) 20%, transparent); color:var(--accent); }
.field > span ha-icon { --mdc-icon-size:14px; vertical-align:-2px; }
.seg ha-icon { --mdc-icon-size:18px; }
.rr-ic { width:36px; height:36px; border-radius:11px; display:grid; place-items:center; flex:none; background:color-mix(in srgb, var(--rc) 18%, transparent); color:var(--rct); }
.rrow small { display:inline-flex !important; align-items:center; gap:4px; }
.rrow small ha-icon { --mdc-icon-size:13px; }
.rrow.off { opacity:.55; }
.rr-extras { display:flex; gap:6px; color:var(--muted); }
.rr-extras ha-icon { --mdc-icon-size:17px; }
p ha-icon { --mdc-icon-size:16px; vertical-align:-3px; color:var(--accent); margin-right:6px; }
.presence { padding:14px; }
.heat-sub .presence { padding:0; }
.heat-sub { margin-top:18px; padding-top:16px; border-top:1px solid var(--line); }
.mnum { font-size:10.5px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); padding:2px 8px; border-radius:99px; background:var(--card2); }
.pbar { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.psegs { display:flex; flex:1 1 360px; padding:4px; gap:4px; border-radius:14px; background:var(--bg); border:1px solid var(--line); }
.pseg { all:unset; cursor:pointer; flex:1; display:flex; align-items:center; justify-content:center; gap:8px; padding:10px 12px; border-radius:11px; font-weight:600; font-size:14px; color:var(--muted); }
.pseg:hover { color:var(--text); }
.pseg.on { background:color-mix(in srgb, var(--accent) 18%, var(--card)); color:var(--text); box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--accent) 50%, transparent); }
.pseg.on ha-icon { color:var(--accent); }
.pseg[disabled] { cursor:default; }
.ptoggles { display:flex; gap:8px; }
.ptoggle { position:relative; cursor:pointer; display:inline-flex; align-items:center; gap:7px; padding:10px 14px; border-radius:14px; border:1px solid var(--line2); color:var(--muted); font-weight:600; font-size:14px; }
.ptoggle input { position:absolute; opacity:0; pointer-events:none; }
.ptoggle:hover { color:var(--text); }
.ptoggle.on { --c:#d946ef; color:var(--ct); border-color:color-mix(in srgb, #e879f9 55%, transparent); background:color-mix(in srgb, #e879f9 12%, var(--card)); }
.presence .ptext { display:flex; align-items:center; gap:8px; margin:12px 4px 0; font-size:13px; }
.presence .ptext ha-icon { --mdc-icon-size:16px; flex:none; }
.link.inline { font-size:13px; }
.count { font-size:12px; font-weight:700; color:var(--muted); background:var(--card2); border-radius:99px; padding:2px 9px; }
.hchip.warn { background:rgba(250,204,21,.22); }
.hmodes { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:14px 0; }
.hmode { display:flex; align-items:center; gap:12px; padding:12px 14px; border-radius:14px; border:1px solid var(--line2); cursor:pointer; }
.hmode > ha-icon { --mdc-icon-size:22px; color:var(--muted); }
.hmode > span:first-of-type { flex:1; min-width:0; }
.hmode b { display:block; font-size:14px; }
.hmode small { display:block; color:var(--muted); font-size:12px; }
.hmode.on { border-color:#e879f9; background:color-mix(in srgb, #e879f9 10%, var(--card)); }
.hmode.on > ha-icon { color:#e879f9; }
.notes { display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 6px; }
.note { display:inline-flex; align-items:center; gap:7px; padding:6px 12px; border-radius:99px; font-size:13px; font-weight:600; color:var(--ct); background:color-mix(in srgb, var(--c) 13%, transparent); border:1px solid color-mix(in srgb, var(--c) 30%, transparent); }
.room-note.pre { background:color-mix(in srgb, #fb923c 13%, transparent); }
.room-note small { color:var(--muted); font-size:12px; }
.learn { display:flex; flex-direction:column; gap:2px; padding:10px 13px; border-radius:12px; border:1px solid var(--line2); }
.learn b { font-size:18px; }
.learn small { font-size:12px; color:var(--muted); }
.learn.ok { border-color:color-mix(in srgb, var(--accent) 50%, transparent); }
.learn .link { align-self:flex-start; margin-top:4px; }
.tpill ha-icon { --mdc-icon-size:14px; vertical-align:-2px; margin-right:4px; }
.room-note.boost { background:color-mix(in srgb, #f43f5e 14%, transparent); }
.room-note.warmn { background:color-mix(in srgb, #f97316 13%, transparent); }
.icon.hot { color:#f43f5e; background:color-mix(in srgb, #f43f5e 14%, transparent); }
select { font:inherit; color:var(--text); background:var(--bg); border:1px solid var(--line2); border-radius:12px; padding:11px 13px; width:100%; color-scheme:dark; }
input[type=time] { font:inherit; color:var(--text); background:var(--bg); border:1px solid var(--line2); border-radius:12px; padding:10px 13px; width:100%; color-scheme:dark; }
.timebox input[type=time] { border:none; padding:9px 0; background:none; width:76px; font-size:20px; font-weight:700; box-shadow:none; }
input[type=text], input[type=number], input[type=date], input[type=search] { font:inherit; color:var(--text); background:var(--bg); border:1px solid var(--line2); border-radius:12px; padding:11px 13px; min-width:0; width:100%; color-scheme:dark; }
input:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent); }
.unit { display:flex; align-items:center; gap:8px; }
.unit i { font-style:normal; color:var(--muted); font-size:13px; min-width:30px; }
.row2 { display:grid; grid-template-columns:1fr 1fr; gap:0 14px; }
.row3 { display:grid; grid-template-columns:1fr 1fr 1.2fr; gap:0 14px; }
.check { display:flex; align-items:center; gap:14px; justify-content:space-between; padding:12px 0; border-top:1px solid var(--line); cursor:pointer; }
.check b { display:block; font-size:14px; }
.check small { display:block; color:var(--muted); font-size:12px; margin-top:3px; line-height:1.4; }
.rlist { display:grid; }
.rrow { display:flex; align-items:center; gap:10px; padding:10px 0; border-top:1px solid var(--line); }
.rrow:first-child { border-top:none; }
.rrow small { display:block; color:var(--muted); font-size:12px; }

/* Rollwerk: Tagesleiste, Kompass, Experte */
.rwday { margin:2px 0 4px; }
.rwday-bar { position:relative; height:12px; border-radius:99px; background:color-mix(in srgb, #1e293b 55%, var(--card2)); overflow:hidden; }
.rwday.small .rwday-bar { height:7px; }
.rwday-bar i { position:absolute; top:0; bottom:0; }
.rwday-bar .d-day { background:color-mix(in srgb, #38bdf8 55%, var(--card2)); }
.rwday-bar .d-shade { background:repeating-linear-gradient(135deg, #f97316 0 4px, #fb923c 4px 8px); }
.rwday-bar .d-now { position:absolute; top:-2px; bottom:-2px; width:2px; background:var(--text); border-radius:2px; }
.rwday-lab { position:relative; height:16px; font-size:11px; color:var(--muted); }
.rwday-lab span { position:absolute; transform:translateX(-50%); white-space:nowrap; }
.rw-next { display:flex; flex-direction:column; gap:4px; margin:4px 0 2px; }
.rw-next small { display:flex; align-items:center; gap:5px; color:var(--muted); font-size:12px; }
.rw-next small ha-icon { --mdc-icon-size:14px; }
.rwtop { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.rwexp { flex:none; display:inline-flex; align-items:center; gap:5px; padding:6px 11px; border-radius:99px; border:1px solid var(--line2); background:var(--card2); color:var(--muted); font:inherit; font-size:12px; cursor:pointer; }
.rwexp.on { color:#fff; background:#8b5cf6; border-color:#8b5cf6; }
.rwex { margin-top:16px; padding:12px; border-radius:14px; border:1px dashed color-mix(in srgb, #8b5cf6 45%, transparent); background:color-mix(in srgb, #8b5cf6 5%, transparent); }
.rwex-h { display:flex; align-items:center; gap:6px; font-size:12px; font-weight:700; color:#8b5cf6; text-transform:uppercase; letter-spacing:.04em; margin-bottom:6px; }
.rwex-h ha-icon { --mdc-icon-size:16px; }
.compass { display:flex; flex-direction:column; align-items:center; gap:4px; margin:4px 0 10px; }
.compass svg { width:min(250px, 100%); height:auto; }
.cp-ring { fill:var(--card2); stroke:var(--line2); stroke-width:1.5; }
.cp-sec { fill:color-mix(in srgb, #f97316 28%, transparent); stroke:#f97316; stroke-width:1.5; }
.cp-win { stroke:#0ea5e9; stroke-width:5; stroke-linecap:round; }
.cp-house { fill:var(--card); stroke:var(--text); stroke-width:1.5; }
.cp-sun { fill:#facc15; stroke:#f59e0b; stroke-width:2; }
.cp-b { cursor:pointer; }
.cp-b circle { fill:var(--card); stroke:var(--line2); stroke-width:1.5; }
.cp-b text { font-size:11px; font-weight:700; text-anchor:middle; fill:var(--text); pointer-events:none; }
.cp-b.on circle { fill:#0ea5e9; stroke:#0ea5e9; }
.cp-b.on text { fill:#fff; }
.rwsent { display:flex; gap:10px; padding:12px 14px; border-radius:16px; background:color-mix(in srgb, #f97316 8%, var(--card2)); border:1px solid color-mix(in srgb, #f97316 25%, transparent); margin-bottom:6px; }
.rwsent > ha-icon { color:#f97316; flex:none; margin-top:4px; }
.rwsent p { margin:0; line-height:2.3; font-size:15px; }
.tok { display:inline-flex; align-items:center; gap:2px; vertical-align:middle; padding:1px 3px; border-radius:99px; background:var(--card); border:1px solid color-mix(in srgb, #f97316 45%, transparent); line-height:1.4; white-space:nowrap; }
.tok b { padding:0 4px; font-weight:700; color:#c2410c; }
.tok.txt { padding:2px 10px; font-weight:700; color:#0369a1; border-color:color-mix(in srgb, #0ea5e9 45%, transparent); }
.tok.warn { color:#b45309; }
.tok-b { all:unset; cursor:pointer; width:24px; height:24px; border-radius:50%; display:grid; place-items:center; font-weight:700; color:var(--muted); background:var(--card2); }
.tok-b:active { background:var(--line2); }
.cwiz-c { padding:12px; border:1px solid var(--line2); border-radius:14px; margin-bottom:10px; }
.cwiz-c > b { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.cwiz-c > b ha-icon { color:#0ea5e9; }
.cwiz-c select { width:100%; padding:10px 12px; border-radius:12px; border:1px solid var(--line2); background:var(--card); color:var(--text); font:inherit; }
/* Raum-Assistent */
.wiz-bar { display:flex; gap:4px; margin:-2px 0 16px; overflow-x:auto; scrollbar-width:none; }
.wiz-dot { flex:1; min-width:52px; display:flex; flex-direction:column; align-items:center; gap:4px; border:0; background:none; color:var(--muted); font:inherit; font-size:11px; cursor:pointer; padding:0; }
.wiz-dot i { font-style:normal; width:26px; height:26px; border-radius:50%; display:grid; place-items:center; background:var(--card2); border:1px solid var(--line2); font-weight:700; font-size:12px; }
.wiz-dot.on { color:var(--text); font-weight:600; }
.wiz-dot.on i { background:#fb923c; border-color:#fb923c; color:#fff; }
.wiz-dot.done i { background:color-mix(in srgb, #fb923c 18%, var(--card2)); color:#c2410c; border-color:color-mix(in srgb, #fb923c 40%, transparent); }
.wiz-dot:disabled { opacity:.45; cursor:default; }
.wiz-areas { display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr)); gap:8px; margin:10px 0 14px; }
.wiz-area { display:flex; flex-direction:column; align-items:flex-start; gap:3px; text-align:left; padding:12px; border-radius:14px; border:1px solid var(--line2); background:var(--card2); color:var(--text); font:inherit; cursor:pointer; }
.wiz-area ha-icon { color:#fb923c; margin-bottom:2px; }
.wiz-area small { color:var(--muted); font-size:12px; }
.wiz-area.on { border-color:#fb923c; background:color-mix(in srgb, #fb923c 12%, var(--card2)); box-shadow:0 0 0 1px #fb923c inset; }
.wiz-area.done { opacity:.55; }
.wiz-type { width:100%; display:flex; align-items:flex-start; gap:12px; text-align:left; padding:14px; margin-bottom:8px; border-radius:14px; border:1px solid var(--line2); background:var(--card2); color:var(--text); font:inherit; cursor:pointer; }
.wiz-type ha-icon { color:#fb923c; flex:none; }
.wiz-type span { display:flex; flex-direction:column; gap:3px; }
.wiz-type small { color:var(--muted); }
.wiz-type.on { border-color:#fb923c; box-shadow:0 0 0 1px #fb923c inset; background:color-mix(in srgb, #fb923c 10%, var(--card2)); }
.wiz-dev { width:100%; display:flex; align-items:center; gap:10px; text-align:left; padding:10px 12px; margin-bottom:6px; border-radius:12px; border:1px solid var(--line2); background:var(--card); color:var(--text); font:inherit; cursor:pointer; }
.wiz-dev > ha-icon { color:var(--muted); flex:none; }
.wiz-dev .grow { display:flex; flex-direction:column; gap:2px; min-width:0; }
.wiz-dev small { color:var(--muted); font-size:12px; overflow:hidden; text-overflow:ellipsis; }
.wiz-dev.on { border-color:color-mix(in srgb, #fb923c 50%, transparent); background:color-mix(in srgb, #fb923c 7%, var(--card)); }
.wiz-dev.on > ha-icon { color:#fb923c; }
.wiz-role { font-style:normal; font-size:12px; padding:4px 10px; border-radius:99px; border:1px solid var(--line2); background:var(--card2); white-space:nowrap; }
.wiz-role.on { background:#fb923c; color:#fff; border-color:#fb923c; }
.wiz-temp { display:flex; align-items:center; gap:10px; }
.wiz-temp b { min-width:64px; text-align:center; font-size:17px; }
.wiz-sum { display:flex; flex-direction:column; gap:2px; margin-bottom:12px; }
.wiz-sum .kv { display:flex; align-items:center; gap:10px; padding:9px 2px; border-bottom:1px solid var(--line2); }
.wiz-sum .kv ha-icon { color:#fb923c; }
.wiz-sum .kv span { flex:1; color:var(--muted); }
/* Entitätsauswahl */
.picker { position:relative; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }
.echip { display:inline-flex; align-items:center; gap:7px; padding:5px 5px 5px 12px; border-radius:99px; background:color-mix(in srgb, var(--accent) 14%, var(--card2)); border:1px solid color-mix(in srgb, var(--accent) 30%, transparent); font-size:13px; font-weight:500; max-width:100%; }
.echip em { font-style:normal; color:var(--muted); font-size:12px; font-weight:400; }
.echip.missing { background:color-mix(in srgb, #f87171 15%, var(--card2)); border-color:color-mix(in srgb, #f87171 40%, transparent); }
.echip button { all:unset; cursor:pointer; width:22px; height:22px; border-radius:50%; display:grid; place-items:center; color:var(--muted); }
.echip button:hover { background:var(--line2); color:var(--text); }
.search { position:relative; }
.search ha-icon { position:absolute; left:12px; top:50%; transform:translateY(-50%); color:var(--muted); }
.search input { padding-left:38px; }
/* Entitätssuche: gewählte Karten, Vorschläge mit Trefferquote, nach Raum, Filter */
.picker { display:grid; grid-template-columns:minmax(0, 1fr); gap:8px; min-width:0; }
.pk-sel { display:flex; align-items:center; gap:6px; padding:3px 6px 3px 3px; border-radius:16px; border:2px solid color-mix(in srgb, var(--accent) 65%, transparent); background:color-mix(in srgb, var(--accent) 6%, var(--card)); }
.pk-sel.missing { border-color:color-mix(in srgb, #f87171 60%, transparent); }
.pk-sel-b { all:unset; cursor:pointer; flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; padding:8px 10px; }
.pk-sel-b[disabled] { cursor:default; }
.pk-sel-b b { font-size:15px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pk-sel-b small { font-size:12.5px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pk-x { all:unset; cursor:pointer; width:36px; height:36px; flex:none; border-radius:10px; display:grid; place-items:center; color:var(--muted); }
.pk-x:hover { background:var(--card2); color:var(--text); }
.pk-add { all:unset; cursor:pointer; justify-self:start; display:inline-flex; align-items:center; gap:6px; color:var(--accent); font-weight:600; font-size:14px; padding:2px; }
.pk-box { display:grid; grid-template-columns:minmax(0, 1fr); min-width:0; gap:10px; padding:12px; border-radius:18px; border:1px solid var(--line2); background:var(--card); }
.pk-tabs { display:grid; grid-template-columns:repeat(3, 1fr); gap:2px; padding:3px; border-radius:14px; border:1px solid var(--line2); }
.pk-tabs button { all:unset; cursor:pointer; text-align:center; padding:9px 4px; border-radius:11px; font-weight:600; font-size:14px; color:var(--muted); }
.pk-tabs button.on { background:var(--accent); color:var(--ink); }
.pk-list { display:grid; gap:8px; }
.pk-card { display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:3px 12px; padding:12px 14px; border-radius:14px; border:1px solid var(--line2); }
.pk-card.sel { border-color:var(--accent); background:color-mix(in srgb, var(--accent) 8%, var(--card)); }
.pk-card b { font-size:15px; overflow-wrap:anywhere; }
.pk-card .pk-v { font-weight:700; font-size:14px; white-space:nowrap; text-align:right; }
.pk-card small { grid-column:1 / -1; color:var(--muted); font-size:12.5px; overflow-wrap:anywhere; }
.pk-why { grid-column:1 / -1; display:flex; align-items:center; flex-wrap:wrap; gap:4px 8px; margin-top:2px; font-size:12.5px; color:var(--muted); }
.pk-why em { font-style:normal; font-weight:800; font-size:12px; padding:1px 8px; border-radius:99px; background:var(--card2); color:var(--text); }
.pk-why em.hi { background:#34d399; color:#04211d; }
.pk-pick { all:unset; cursor:pointer; grid-column:1 / -1; text-align:center; margin-top:8px; padding:9px; border-radius:12px; border:1px solid var(--line2); font-weight:700; font-size:15px; }
.pk-pick:hover { border-color:var(--accent); color:var(--accent); }
.pk-ok { grid-column:1 / -1; text-align:right; margin-top:6px; font-size:13px; color:var(--muted); }
.pk-foot { display:flex; flex-wrap:wrap; align-items:center; gap:6px; font-size:13.5px; color:var(--muted); }
.pk-foot .link { font-size:13.5px; }
.pk-scroll { max-height:340px; overflow:auto; margin-right:-6px; padding-right:6px; }
.pk-group { display:flex; justify-content:space-between; font-size:12px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); padding:12px 2px 4px; }
.pk-group span { font-weight:600; letter-spacing:0; }
.pk-row { display:flex; align-items:center; gap:10px; padding:8px 2px; border-top:1px solid var(--line); }
.pk-row .grow { min-width:0; }
.pk-row b { display:block; font-size:14px; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pk-row small { display:block; font-size:12px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pk-row .pk-v { font-size:13px; font-weight:600; white-space:nowrap; }
.pk-row.bad .pk-v { color:#f87171; }
.pk-mini { all:unset; cursor:pointer; flex:none; padding:6px 12px; border-radius:10px; border:1px solid var(--line2); font-weight:700; font-size:13px; }
.pk-mini:hover { border-color:var(--accent); color:var(--accent); }
.pk-mini.on { cursor:default; border-color:var(--accent); color:var(--accent); }
.pk-chips { display:flex; flex-wrap:wrap; gap:6px; }
.pk-chips button { all:unset; cursor:pointer; padding:6px 12px; border-radius:99px; border:1px solid var(--line2); font-size:13px; font-weight:600; color:var(--muted); }
.pk-chips button.on { color:var(--text); border-color:var(--accent); background:color-mix(in srgb, var(--accent) 14%, var(--card)); }
.pk-empty { padding:10px 2px; color:var(--muted); font-size:13.5px; }
.pk-close { justify-self:end; }
/* Anwesenheit */
.pstate { display:inline-flex; align-items:center; gap:7px; margin-bottom:12px; padding:7px 14px; border-radius:99px; font-weight:700; font-size:14px; color:var(--ct); background:color-mix(in srgb, var(--c) 14%, transparent); }
.pchips { display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }
.pchip { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:7px; padding:8px 14px; border-radius:99px; font-weight:700; font-size:14px; color:var(--muted); background:var(--card); border:1px dashed var(--line2); }
.pchip i { width:9px; height:9px; border-radius:50%; background:var(--line2); }
.pchip.on { color:var(--text); border:1px solid transparent; background:color-mix(in srgb, #f59e0b 14%, var(--card)); }
.pchip.on i { background:#f59e0b; }
.pchip.on.home { --c:#14b8a6; color:var(--ct); background:color-mix(in srgb, #14b8a6 16%, var(--card)); }
.pchip.on.home i { background:#14b8a6; }
.pchip[disabled] { cursor:default; }
.mstep { display:inline-flex; align-items:center; gap:4px; padding:4px; border-radius:99px; background:var(--card); border:1px solid var(--line); }
.mstep button { all:unset; cursor:pointer; width:38px; height:38px; border-radius:50%; display:grid; place-items:center; font-size:20px; font-weight:700; color:var(--accent); background:color-mix(in srgb, var(--accent) 12%, transparent); }
.mstep button[disabled] { cursor:default; opacity:.5; }
.mstep b { min-width:72px; text-align:center; font-size:16px; }
@media (max-width:600px) {
  .wxr.ctl .pchips { justify-content:flex-start; }
}
.pick-list { position:absolute; left:0; right:0; top:100%; margin-top:6px; max-height:270px; overflow:auto; z-index:10; background:var(--card2); border:1px solid var(--line2); border-radius:14px; box-shadow:0 16px 40px rgba(0,0,0,.5); padding:4px; }
.pick-item { all:unset; cursor:pointer; display:flex; flex-direction:column; padding:9px 12px; width:100%; box-sizing:border-box; border-radius:10px; }
.pick-item:hover { background:color-mix(in srgb, var(--accent) 14%, transparent); }
.pick-item small { color:var(--muted); font-size:11px; }
.pick-empty { padding:12px; color:var(--muted); }

/* Dialog */
.backdrop { position:fixed; inset:0; background:rgba(0,0,0,.6); backdrop-filter:blur(3px); z-index:20; }
.sheet { position:fixed; z-index:21; top:50%; left:50%; transform:translate(-50%,-50%); width:min(660px, calc(100vw - 24px)); max-height:calc(100vh - 40px);
  display:flex; flex-direction:column; background:var(--card); border:1px solid var(--line2); border-radius:24px; box-shadow:0 30px 80px rgba(0,0,0,.6); color:var(--text);
  font-family:Inter, "SF Pro Text", "Segoe UI", Roboto, system-ui, sans-serif; }
.sheet { height:min(780px, calc(100vh - 40px)); }
@supports (height:100dvh) { .sheet { max-height:calc(100dvh - 40px); height:min(780px, calc(100dvh - 40px)); } }
.sheet-head { display:flex; align-items:center; gap:14px; padding:20px 24px 12px; }
.sheet-head h2 { margin:0 0 2px; font-size:20px; }
.rr-ic.big { width:46px; height:46px; border-radius:14px; }
.rr-ic.big ha-icon { --mdc-icon-size:26px; }
.sheet-body { padding:16px 24px 8px; overflow:auto; flex:1; }
.dtabs { display:flex; gap:4px; padding:0 18px; border-bottom:1px solid var(--line); overflow-x:auto; scrollbar-width:none; flex:none; }
.dtab { all:unset; cursor:pointer; position:relative; flex:none; display:inline-flex; align-items:center; gap:7px; padding:11px 10px 12px; color:var(--muted); font-weight:600; font-size:13px; border-bottom:2px solid transparent; margin-bottom:-1px; }
.dtab:hover { color:var(--text); }
.dtab.on { color:var(--text); border-bottom-color:var(--accent); }
.dtab.on ha-icon { color:var(--accent); }
.dtab i { position:absolute; top:8px; left:24px; width:7px; height:7px; border-radius:50%; background:var(--accent); }
.icons { display:flex; flex-wrap:wrap; gap:6px; }
.ic-pick { all:unset; cursor:pointer; position:relative; width:42px; height:42px; display:grid; place-items:center; border-radius:12px; border:1px solid var(--line2); color:var(--muted); }
.ic-pick:hover { color:var(--text); border-color:var(--accent); }
.ic-pick.on { color:var(--accent); border-color:var(--accent); background:color-mix(in srgb, var(--accent) 14%, transparent); }
.ic-pick em { position:absolute; bottom:-7px; font-style:normal; font-size:9px; font-weight:700; background:var(--card); padding:0 3px; border-radius:4px; color:var(--accent); }
.check .ck-ic { --mdc-icon-size:22px; color:var(--muted); align-self:flex-start; margin-top:2px; }
.check > span:first-of-type { flex:1; }
.check:has(input:checked) .ck-ic { color:var(--accent); }
.sheet-foot { display:flex; gap:10px; padding:14px 24px 20px; border-top:1px solid var(--line); }
.sheet-foot .secondary, .sheet-foot .primary { flex:1; }
.types { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.type { all:unset; cursor:pointer; display:flex; flex-direction:column; gap:5px; padding:14px; border-radius:16px; border:1px solid var(--line2); }
.type ha-icon { --mdc-icon-size:28px; color:var(--muted); }
.type small { color:var(--muted); font-size:12px; line-height:1.4; }
.type.on { border-color:var(--accent); background:color-mix(in srgb, var(--accent) 12%, var(--card)); }
.type.on ha-icon { color:var(--accent); }
details { border-top:1px solid var(--line); padding-top:14px; margin-top:6px; }
summary { cursor:pointer; font-weight:600; margin-bottom:14px; }
/* Hinweise: Glocke, Zeile auf Start, Liste */
.bell { all:unset; cursor:pointer; position:relative; width:42px; height:42px; border-radius:14px; display:grid; place-items:center; color:var(--muted); background:var(--card); border:1px solid var(--line); }
.bell:hover { color:var(--text); border-color:var(--line2); }
.bell ha-icon { --mdc-icon-size:22px; }
.bell.warn { color:#f59e0b; }
.bell em { position:absolute; top:-5px; right:-5px; min-width:18px; height:18px; padding:0 5px; box-sizing:border-box; border-radius:99px; background:#f59e0b; color:#1f1300; font-style:normal; font-size:11px; font-weight:800; display:grid; place-items:center; }
.bell.on { color:var(--accent); border-color:var(--accent); background:color-mix(in srgb, var(--accent) 12%, var(--card)); }
.setintro { display:flex; align-items:center; flex-wrap:wrap; gap:4px; margin:0 2px 12px; }
.bell i { position:absolute; top:7px; right:8px; width:8px; height:8px; border-radius:50%; background:var(--accent); }
.hstrip { all:unset; cursor:pointer; box-sizing:border-box; width:100%; display:flex; align-items:center; gap:10px; padding:10px 14px; margin-bottom:14px; border-radius:14px; font-size:13.5px;
  background:color-mix(in srgb, #f59e0b 12%, var(--card)); border:1px solid color-mix(in srgb, #f59e0b 35%, transparent); }
.hstrip > ha-icon { color:#f59e0b; }
.hstrip .grow { min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.hs-go { display:inline-flex; align-items:center; color:var(--accent); font-weight:600; white-space:nowrap; }
.hints { display:grid; gap:6px; }
.hint { all:unset; cursor:pointer; box-sizing:border-box; display:flex; align-items:center; gap:12px; padding:9px 10px; border-radius:14px; border:1px solid var(--line); }
.hint:hover { background:var(--card2); }
.hint[disabled] { cursor:default; }
.hint.warn .sr-ic { --c:#f59e0b; }
.hint.info .sr-ic { --c:#60a5fa; }
/* Startseite: Module und Widgets */
.modtiles { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:10px; }
.modtile { all:unset; cursor:pointer; box-sizing:border-box; display:flex; align-items:center; gap:12px; padding:12px 14px; border-radius:16px; border:1px solid var(--line2); background:var(--card); min-width:0; }
.modtile:hover { border-color:var(--accent); }
.modtile .mico { width:44px; height:44px; border-radius:14px; display:grid; place-items:center; flex:none; background:color-mix(in srgb, var(--c) 18%, transparent); color:var(--ct); }
.modtile .mico ha-icon { --mdc-icon-size:24px; }
.mt-t { flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; }
.mt-t b { font-size:16px; }
.mt-t small { color:var(--muted); font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mt-go { color:var(--muted); }
.modtile.soon { cursor:default; opacity:.45; border-style:dashed; --c:#94a3b8; }
.wgrid { display:grid; grid-template-columns:repeat(auto-fill, minmax(170px, 1fr)); gap:12px; grid-auto-flow:dense; }
.wdg.sz-s { grid-column:span 1; }
.wdg.sz-m { grid-column:span 2; }
.wdg.sz-l { grid-column:1 / -1; }
.wdg.sz-s { padding:12px 13px; }
.wdg.sz-s .wh { margin-bottom:8px; }
.wdg.sz-s .wh .link span { display:none; }
.wdg.sz-s.edit .wh b, .wdg.sz-s.edit .wic { display:none; }
.wline { display:flex; align-items:center; gap:6px; margin-top:6px; font-size:12.5px; font-weight:600; color:var(--ct); --c:var(--muted); min-width:0; }
.wline ha-icon { --mdc-icon-size:15px; flex:none; }
.wsplit { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1.3fr); gap:20px; align-items:start; }
.wrooms { display:grid; gap:2px; }
.wroom { display:flex; align-items:center; gap:8px; padding:6px 8px; border-radius:10px; font-size:13px; }
.wroom:nth-child(odd) { background:var(--card2); }
.wroom > ha-icon { --mdc-icon-size:17px; }
.wroom b { font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }
.wroom span:not(.grow) { font-weight:700; }
.wroom small { color:var(--muted); }
.wroom .wm { color:var(--c); --mdc-icon-size:16px; }
.wroom .gf { color:#fb923c; --mdc-icon-size:15px; }
.wstate { font-size:18px; font-weight:700; margin-bottom:10px; }
.pqs { display:flex; gap:6px; }
.pq { all:unset; cursor:pointer; flex:1; display:grid; place-items:center; padding:9px 0; border-radius:12px; background:var(--card2); color:var(--muted); }
.pq.on { background:color-mix(in srgb, var(--accent) 18%, var(--card2)); color:var(--accent); }
.pq[disabled] { cursor:default; }
.ppl { display:grid; gap:4px; margin-top:12px; padding-top:10px; border-top:1px solid var(--line); }
.prow { display:flex; align-items:center; gap:10px; padding:5px 0; min-width:0; }
.prow b { display:block; font-size:14px; font-weight:600; }
.prow small { display:flex; align-items:center; gap:4px; color:var(--muted); font-size:12px; }
.prow small ha-icon { --mdc-icon-size:13px; }
.prow.home small { color:var(--ct); --c:#34d399; }
.prow em { font-style:normal; font-weight:700; font-size:14px; white-space:nowrap; }
.pav { position:relative; width:34px; height:34px; border-radius:50%; flex:none; display:grid; place-items:center; overflow:visible; background:var(--card2); border:2px solid var(--line2); font-weight:700; color:var(--muted); }
.pav img { width:100%; height:100%; border-radius:50%; object-fit:cover; }
.prow.home .pav, .pav.home { border-color:#34d399; }
.ppl-s { display:flex; gap:10px; flex-wrap:wrap; margin-top:10px; }
.ppl-s .pav { width:30px; height:30px; font-size:13px; }
.ppl-s .pav em { position:absolute; bottom:-8px; left:50%; transform:translateX(-50%); font-style:normal; font-size:9.5px; font-weight:700; white-space:nowrap; padding:0 4px; border-radius:6px; background:var(--card); color:var(--text); border:1px solid var(--line); }
.wdots { display:flex; flex-wrap:wrap; gap:5px; margin-top:10px; }
.wdots i { width:12px; height:12px; border-radius:4px; }
.gmini.two { grid-template-columns:repeat(2, 1fr); }
.wsc.s { grid-template-columns:repeat(auto-fill, minmax(44px, 1fr)); gap:6px; }
.wsc.s .sc { align-items:center; padding:10px 0; }
.wval b { display:block; font-size:24px; font-weight:800; letter-spacing:-.02em; line-height:1.1; word-break:break-word; }
.wval small { display:block; color:var(--muted); font-size:12px; margin-top:3px; }
.wlist.cols { grid-template-columns:repeat(auto-fill, minmax(240px, 1fr)); column-gap:24px; }
.wlist.cols .wrow:nth-child(-n+3) { border-top:none; }
.wrow.tall .dbar.mini { height:6px; margin-top:5px; }
.hbar { display:block; height:5px; border-radius:99px; background:var(--card2); margin-top:4px; overflow:hidden; }
.hbar i { display:block; height:100%; border-radius:99px; }
.rdot { width:9px; height:9px; border-radius:50%; flex:none; }
.wbar em { font-style:normal; font-size:10.5px; color:var(--muted); }
.fc.tight { grid-auto-columns:minmax(38px, 1fr); }
.fc.tight .fci { padding:5px 0; gap:2px; }
.fc.tight .fci > ha-icon { --mdc-icon-size:21px; }
.wdg { margin:0; padding:14px 16px; display:flex; flex-direction:column; min-width:0; }

.wdg.edit { outline:2px dashed color-mix(in srgb, var(--accent) 60%, transparent); outline-offset:-2px; }
.wh { display:flex; align-items:center; gap:9px; margin-bottom:12px; min-width:0; }
.wh b { font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wic { width:30px; height:30px; border-radius:10px; display:grid; place-items:center; flex:none; background:color-mix(in srgb, var(--c) 16%, transparent); color:var(--ct); }
.wic ha-icon { --mdc-icon-size:18px; }
.wtools { display:inline-flex; gap:2px; }
.wtools .icon[disabled] { opacity:.3; cursor:default; }
.danger-t { color:#f87171; }
.wb { flex:1; min-width:0; }
.wb .presence { margin:0; }
.wbig { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
.wbig > span:first-child { font-size:38px; font-weight:800; letter-spacing:-.03em; line-height:1; }
.wbig small { font-size:15px; font-weight:500; color:var(--muted); margin-left:3px; }
.wverdict { display:inline-flex; align-items:center; gap:6px; padding:6px 11px; border-radius:99px; font-size:13px; font-weight:600; color:var(--ct); background:color-mix(in srgb, var(--c) 14%, transparent); }
.wminis { display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-top:12px; }
.wmini { display:flex; flex-direction:column; align-items:flex-start; gap:1px; padding:8px 10px; border-radius:12px; background:var(--card2); }
.wmini ha-icon { --mdc-icon-size:16px; color:var(--muted); }
.wmini b { font-size:17px; }
.wmini small { font-size:11.5px; color:var(--muted); }
.wwx { display:flex; align-items:center; gap:14px; }
.wwx > ha-icon { --mdc-icon-size:48px; color:#f59e0b; }
.wwx b { display:block; font-size:30px; font-weight:800; letter-spacing:-.02em; }
.wwx span { color:var(--muted); font-size:14px; }
.wsc { display:grid; grid-template-columns:repeat(auto-fill, minmax(110px, 1fr)); gap:8px; }
.sc { all:unset; cursor:pointer; box-sizing:border-box; display:flex; flex-direction:column; gap:4px; padding:10px 12px; border-radius:14px; background:var(--card2); border:1px solid transparent; min-width:0; }
.sc ha-icon { --mdc-icon-size:22px; color:var(--muted); }
.sc span { font-size:13px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sc small { font-size:11px; color:var(--muted); }
.sc:hover { border-color:var(--line2); }
.sc.on { background:color-mix(in srgb, #f59e0b 16%, var(--card2)); }
.sc.on ha-icon { color:#f59e0b; }
.sc.missing { opacity:.5; }
.wok { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:14px; }
.wok ha-icon { color:#34d399; }
.wlist { display:grid; }
.wrow { display:flex; align-items:center; gap:10px; padding:7px 0; border-top:1px solid var(--line); min-width:0; }
.wrow:first-child { border-top:none; padding-top:0; }
.wrow > ha-icon { --mdc-icon-size:18px; color:var(--muted); }
.wrow b { display:block; font-size:13.5px; font-weight:600; }
.wrow small { display:block; font-size:11.5px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.wrow .grow { min-width:0; }
.wrow em { font-style:normal; font-size:12.5px; font-weight:600; white-space:nowrap; }
.wrow em.hot { color:var(--ct); --c:#f59e0b; }
.wbars { display:flex; align-items:flex-end; gap:8px; height:110px; }
.wbar { flex:1; height:100%; display:flex; flex-direction:column; justify-content:flex-end; align-items:center; gap:4px; }
.wbar i { width:100%; max-width:34px; border-radius:6px 6px 3px 3px; background:linear-gradient(180deg, #fb923c, color-mix(in srgb, #fb923c 45%, var(--card2))); }
.wbar small { font-size:11px; color:var(--muted); }
.wcat { display:grid; gap:6px; }
.fchints { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
.fchint { --c:#94a3b8; display:inline-flex; align-items:center; gap:6px; padding:5px 11px; border-radius:99px; font-size:12.5px; font-weight:600; color:var(--ct); background:color-mix(in srgb, var(--c) 14%, transparent); }
.fchint ha-icon { --mdc-icon-size:15px; }
.fc { display:grid; grid-auto-flow:column; grid-auto-columns:minmax(52px, 1fr); gap:4px; overflow-x:auto; scrollbar-width:thin; padding-bottom:4px; }
.fci { display:flex; flex-direction:column; align-items:center; gap:4px; padding:8px 2px; border-radius:12px; text-align:center; }
.fci:first-child { background:var(--card2); }
.fci > small { font-size:11.5px; color:var(--muted); white-space:nowrap; }
.fci > ha-icon { --mdc-icon-size:26px; color:#f59e0b; }
.fci b { font-size:15px; }
.fci em { font-style:normal; font-size:12.5px; color:var(--muted); }
.fcr { position:relative; width:6px; height:46px; border-radius:99px; background:var(--card2); }
.fci:first-child .fcr { background:var(--line2); }
.fcr i { position:absolute; left:0; right:0; border-radius:99px; background:linear-gradient(0deg, #60a5fa, #fb923c); }
.fcp { display:inline-flex; align-items:center; gap:1px; }
.fcp ha-icon { --mdc-icon-size:12px; }
.fcp.wet { color:#60a5fa !important; font-weight:600; }
.wcat-i { all:unset; cursor:pointer; box-sizing:border-box; display:flex; align-items:center; gap:12px; padding:10px; border-radius:14px; border:1px solid var(--line); }
.wcat-i:hover { border-color:var(--accent); background:var(--card2); }
.sr-t small.wrap { white-space:normal; }
@media (max-width:700px) {
  .wgrid { grid-template-columns:1fr 1fr; gap:10px; }
  .wdg.sz-m, .wdg.sz-l { grid-column:1 / -1; }
  .wsplit { grid-template-columns:1fr; }
  .modtiles { grid-template-columns:1fr 1fr; gap:8px; }
  .modtile { padding:10px; gap:9px; }
  .modtile .mico { width:36px; height:36px; border-radius:11px; }
  .modtile .mt-go { display:none; }
}
/* Banner der Raumübersicht */
.hero { flex-direction:column; align-items:stretch; gap:18px; }
.hero-row { display:flex; align-items:center; gap:22px; position:relative; z-index:1; }
.verdict { display:inline-flex; align-items:center; gap:8px; margin-top:12px; padding:8px 14px; border-radius:99px; font-size:14px; font-weight:600;
  background:color-mix(in srgb, var(--c) 26%, rgba(255,255,255,.08)); border:1px solid color-mix(in srgb, var(--c) 55%, transparent); }
.verdict ha-icon { color:var(--c); filter:brightness(1.3); }
.wx { display:flex; align-items:center; gap:12px; padding:12px 16px; border-radius:18px; background:rgba(255,255,255,.1); backdrop-filter:blur(6px); flex:none; }
.wx > ha-icon { --mdc-icon-size:40px; color:#fde68a; }
.wx b { display:block; font-size:22px; font-weight:700; }
.wx small { display:block; font-size:12px; color:rgba(255,255,255,.8); }
.hstats { display:grid; grid-template-columns:repeat(auto-fit, minmax(128px, 1fr)); gap:8px; position:relative; z-index:1; }
.hstat { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:14px; background:rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.1); min-width:0; }
.hstat > ha-icon { --mdc-icon-size:22px; color:var(--c, rgba(255,255,255,.85)); flex:none; }
.hstat span { display:flex; flex-direction:column; min-width:0; }
.hstat small { font-size:11px; color:rgba(255,255,255,.7); text-transform:uppercase; letter-spacing:.04em; }
.hstat b { font-size:16px; font-weight:700; white-space:nowrap; }
.hstat em { font-style:normal; font-size:11.5px; color:rgba(255,255,255,.72); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
/* Ansicht der Raumkacheln */
.vtog { display:inline-flex; padding:3px; border-radius:12px; background:var(--card); border:1px solid var(--line); margin-right:6px; }
.vtog button { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:6px; padding:6px 10px; border-radius:9px; font-size:13px; font-weight:600; color:var(--muted); }
.vtog button.on { background:color-mix(in srgb, var(--accent) 16%, var(--card)); color:var(--text); }
.vtog button.on ha-icon { color:var(--accent); }
/* Zeitplan in der Raumkarte */
.rsched { margin:0 0 12px; padding:9px 11px 10px; border-radius:12px; background:var(--card2); }
.rs-top { display:flex; align-items:center; gap:7px; font-size:12.5px; margin-bottom:7px; min-width:0; }
.rs-top > ha-icon { --mdc-icon-size:15px; color:var(--muted); }
.rs-src { color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }
.rs-top b { font-weight:600; white-space:nowrap; }
.rsched.on .rs-top b { color:var(--ct); --c:#f59e0b; }
.rsched .dbar.mini { height:8px; }
/* Kompakte Raumkacheln */
.rooms.compact { grid-template-columns:repeat(auto-fill, minmax(210px, 1fr)); gap:10px; }
.room.tap, .rmini.tap { cursor:pointer; }
.room.tap:active, .rmini.tap:active { transform:scale(.99); }
.rq-facts { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
.rq-facts span { display:inline-flex; align-items:center; gap:5px; padding:6px 10px; border-radius:99px; background:var(--card2); font-size:13px; font-weight:600; }
.rq-facts ha-icon { --mdc-icon-size:17px; color:var(--c); }
.rq-temp { display:grid; justify-items:center; gap:10px; padding:16px; border-radius:18px; background:var(--card2); margin-bottom:14px; }
.rq-temp > small { color:var(--muted); font-weight:600; }
.rq-temp .stepper { transform:scale(1.25); margin:8px 0; }
.rq-quick { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; }
.segs.small.rq-dur { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:6px; }
.segs.small.rq-dur .seg { padding:10px 2px; font-size:12.5px; white-space:nowrap; }
.rw-sum-h { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.rw-sum-h h2 { margin:2px 0 0; font-size:22px; }
.rw-all { display:flex; gap:8px; }
.kv2s { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:8px; margin-top:14px; }
.kv2 { display:flex; align-items:center; gap:10px; background:var(--card2); border-radius:14px; padding:10px 12px; }
.kv2 > ha-icon { color:var(--c, var(--accent)); --mdc-icon-size:22px; }
.kv2 span { display:flex; flex-direction:column; }
.kv2 b { font-size:15px; }
.kv2 small { color:var(--muted); font-size:12px; }
.rw-area h3 { margin:18px 4px 8px; font-size:15px; color:var(--muted); font-weight:700; }
.rw-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:12px; }
.rw-c { padding:14px; display:flex; flex-direction:column; gap:10px; margin:0; }
.rw-c.bad { opacity:.6; }
.rw-top { display:flex; align-items:center; gap:12px; }
.rw-top .grow { display:flex; flex-direction:column; min-width:0; }
.rw-top b { font-size:15.5px; }
.rw-top small { color:var(--muted); font-size:12.5px; }
.rw-flags { display:flex; flex-wrap:wrap; gap:6px; }
.rw-flags span { display:inline-flex; align-items:center; gap:5px; font-size:12px; font-weight:600; padding:3px 9px; border-radius:99px; color:var(--c); background:color-mix(in srgb, var(--c) 14%, var(--card)); }
.rw-flags ha-icon { --mdc-icon-size:15px; }
.rw-ctl { display:flex; align-items:center; gap:8px; }
.rw-ctl .sbtn { width:40px; height:40px; flex:none; }
.rw-ctl .sbtn ha-icon { --mdc-icon-size:20px; }
.rw-range { flex:1; min-width:60px; accent-color:var(--accent); height:28px; }
.segs.small.rw-fac { display:grid; grid-template-columns:repeat(9, minmax(0, 1fr)); gap:4px; }
.segs.small.rw-fac .seg { padding:8px 0; font-size:12.5px; justify-content:center; }
.rwchecks { display:flex; flex-direction:column; gap:4px; margin:6px 0 10px; }
.rwck { display:flex; align-items:flex-start; gap:10px; text-align:left; padding:9px 10px; border-radius:12px; border:1px solid var(--line2); background:var(--card); color:var(--text); font:inherit; cursor:pointer; }
.rwck ha-icon { --mdc-icon-size:20px; color:var(--muted); flex:none; }
.rwck.on { border-color:color-mix(in srgb, var(--accent) 45%, transparent); background:color-mix(in srgb, var(--accent) 8%, var(--card)); }
.rwck.on ha-icon { color:var(--accent); }
.rwchips { margin:4px 0 8px; }
.rwchips .chip { display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:99px; border:1px solid var(--line2); background:var(--card2); color:var(--text); font:inherit; font-size:13px; cursor:pointer; }
.rwchips .chip.on { background:color-mix(in srgb, var(--accent) 16%, var(--card2)); border-color:color-mix(in srgb, var(--accent) 45%, transparent); font-weight:600; }
.rwsecs { display:flex; gap:6px; overflow-x:auto; margin:0 -4px 14px; padding:2px 4px 6px; scrollbar-width:none; }
.rwsecs::-webkit-scrollbar { display:none; }
.rwsec { flex:none; display:inline-flex; align-items:center; gap:6px; padding:7px 12px; border-radius:99px; border:1px solid var(--line2); background:var(--card2); color:var(--text); font:inherit; font-size:13px; cursor:pointer; white-space:nowrap; }
.rwsec ha-icon { --mdc-icon-size:16px; color:var(--c); }
.rwsec.on { background:color-mix(in srgb, var(--c) 18%, var(--card2)); border-color:color-mix(in srgb, var(--c) 50%, transparent); font-weight:600; }
.rwsec.off { opacity:.55; }
select.rwsel { width:100%; padding:10px 12px; border-radius:12px; border:1px solid var(--line2); background:var(--card); color:var(--text); font:inherit; }
button.danger { color:#ef4444; }
select[data-rwc] { width:100%; padding:10px 12px; border-radius:12px; border:1px solid var(--line2); background:var(--card); color:var(--text); font:inherit; }
@media (max-width:600px) { .rw-grid { grid-template-columns:1fr; } .segs.small.rw-fac { grid-template-columns:repeat(5, minmax(0, 1fr)); } }
.mlogo { display:inline-flex; width:24px; height:24px; flex:none; border-radius:7px; filter:drop-shadow(0 1px 2px rgba(0,0,0,.18)); }
.mlogo svg { width:100%; height:100%; display:block; }
.mtab .mlogo { width:22px; height:22px; }
.mtab.active .mlogo { filter:drop-shadow(0 1px 3px rgba(0,0,0,.28)); }
.sr-ic.logo { background:none !important; box-shadow:none; }
.sr-ic.logo .mlogo { width:100%; height:100%; border-radius:12px; }
.vh { display:flex; flex-direction:column; gap:6px; margin-top:4px; }
.vh-row { display:grid; grid-template-columns:110px minmax(0, 1fr); gap:10px; align-items:center; }
.vh-name { font-size:13px; font-weight:600; display:flex; flex-direction:column; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.vh-name .rdot { display:none; }
.vh-name small { color:var(--muted); font-weight:500; font-size:11.5px; }
.vh-cells { display:grid; grid-template-columns:repeat(24, minmax(0, 1fr)); gap:2px; }
.vh-cells i { height:22px; border-radius:4px; }
.vh-axis b { font-size:10.5px; color:var(--muted); font-weight:600; }
@media (max-width:600px) { .vh-row { grid-template-columns:78px minmax(0, 1fr); } .vh-cells i { height:18px; border-radius:3px; } }
.roles { display:flex; flex-direction:column; gap:8px; }
.role { background:var(--card2); border-radius:14px; padding:10px 12px; display:flex; flex-direction:column; gap:8px; }
.role-h { display:flex; align-items:center; gap:10px; }
.role-h > ha-icon { --mdc-icon-size:22px; color:var(--accent); }
.role-h .grow { display:flex; flex-direction:column; min-width:0; }
.role-h b { font-size:14.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.role-h small { color:var(--muted); font-size:12.5px; }
.role-main { font-style:normal; font-size:12px; font-weight:700; padding:3px 9px; border-radius:99px; background:color-mix(in srgb, var(--accent) 16%, var(--card)); color:var(--accent); white-space:nowrap; }
.role .segs.small { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:6px; margin:0; }
.role .segs.small.n2 { grid-template-columns:repeat(2, minmax(0, 1fr)); }
.role .segs.small .seg { padding:8px 4px; font-size:12.5px; white-space:nowrap; justify-content:center; gap:5px; }
.role .segs.small .seg ha-icon { --mdc-icon-size:16px; }
.role-help { margin-top:8px; font-size:13px; color:var(--muted); }
.role-help summary { cursor:pointer; display:inline-flex; align-items:center; gap:6px; color:var(--accent); font-weight:600; list-style:none; }
.role-help summary::-webkit-details-marker { display:none; }
.role-help p { margin:8px 0 0; line-height:1.4; }
.rq-more { display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }
.rq-more .qbtn { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:6px; padding:10px 14px; border-radius:12px; background:var(--card2); font-size:13.5px; font-weight:600; color:var(--text); }
.rq-more .qbtn ha-icon { --mdc-icon-size:18px; color:var(--accent); }
.rq-more .qbtn.hot ha-icon { color:#fb923c; }
.rm-dev { display:inline-flex; align-items:center; gap:2px; font-size:11px; font-weight:700; color:var(--muted); }
.rm-dev ha-icon { --mdc-icon-size:16px; }
.rm-dev.on { color:#f97316; }
.rmini { position:relative; overflow:hidden; display:flex; flex-direction:column; gap:8px; padding:12px 12px 12px 15px; border-radius:16px; background:var(--card); border:1px solid var(--line); }
.rmini::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--rc); }
.rmini.off { opacity:.62; }
.rm-head { display:flex; align-items:center; gap:8px; min-width:0; }
.rm-ic { width:28px; height:28px; border-radius:9px; display:grid; place-items:center; flex:none; background:color-mix(in srgb, var(--rc) 18%, transparent); color:var(--rct); }
.rm-ic ha-icon { --mdc-icon-size:17px; }
.rm-name { flex:1; min-width:0; font-size:15px; line-height:1.25; text-align:left; white-space:normal; overflow-wrap:break-word; hyphens:manual; }
.rm-ind { display:flex; align-items:center; flex-wrap:wrap; gap:8px; min-height:0; }
.rm-ind:empty { display:none; }
.rm-fire { color:#fb923c; --mdc-icon-size:16px; }
.rm-win { color:#22d3ee; --mdc-icon-size:16px; }
.icon.tiny { width:28px; height:28px; }
.icon.tiny ha-icon { --mdc-icon-size:16px; }
.rm-body { display:flex; align-items:flex-end; justify-content:space-between; gap:6px; }
.rm-tgt { display:flex; flex-direction:column; align-items:flex-end; line-height:1.15; }
.rm-tgt small { font-size:11px; color:var(--muted); }
.rm-tgt b { font-size:16px; }
.rm-temp { font-size:28px; font-weight:800; letter-spacing:-.02em; line-height:1; }
.rm-temp small { font-size:13px; font-weight:500; color:var(--muted); margin-left:2px; }
.rm-mode { display:flex; align-items:center; gap:6px; font-size:12px; font-weight:600; color:var(--ct); min-width:0; }
.rm-mode ha-icon { --mdc-icon-size:14px; }
.rm-mode small { color:var(--muted); font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.rmini .dbar.mini { height:6px; }
.link.back { margin:0 0 10px; }
@media (max-width:600px) {
  .hero-row { flex-wrap:wrap; }
  .hero .gauge { display:none; }
  .wx { flex:1 1 100%; }
  .hstats { grid-template-columns:1fr 1fr; }
  .vtog span { display:none; }
  .rooms.compact { grid-template-columns:1fr 1fr; }
  .rm-mode small { display:none; }

}
/* Einstellungen: flache Liste, Details im Pop-up */
.setsearch { margin-bottom:14px; }
.setsearch input { width:100%; }
.sgroup { padding:8px 10px; }
.sg-h { display:flex; align-items:center; gap:8px; padding:8px 10px 6px; font-size:12px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
.srow { all:unset; cursor:pointer; box-sizing:border-box; width:100%; display:flex; align-items:center; gap:12px; padding:10px; border-radius:14px; }
.srow + .srow { border-top:1px solid var(--line); border-radius:0 0 14px 14px; }
.srow:hover { background:var(--card2); border-radius:14px; }
.srow[disabled] { cursor:default; }
.srow.off { opacity:.6; }
.sr-ic { width:38px; height:38px; border-radius:12px; display:grid; place-items:center; flex:none; background:color-mix(in srgb, var(--c) 16%, transparent); color:var(--ct); }
.sr-ic ha-icon { --mdc-icon-size:21px; }
.sr-ic.big { width:46px; height:46px; border-radius:14px; }
.sr-ic.big ha-icon { --mdc-icon-size:26px; }
.sr-t { flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; }
.sr-t b { font-size:15px; font-weight:600; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.sr-t small { color:var(--muted); font-size:12.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.srow.warn .sr-t small { color:var(--ct); --c:#f59e0b; }
.sr-go { color:var(--muted); }
.sheet.pop { height:auto; width:min(580px, calc(100vw - 24px)); z-index:23; }
#pop .backdrop { z-index:22; }
.note.warn { --c:#f59e0b; border-radius:12px; display:flex; margin:4px 0 12px; }
.evlist { display:grid; gap:6px; margin-bottom:12px; }
.ev { display:flex; align-items:center; gap:10px; padding:9px 12px; border-radius:12px; background:var(--card2); }
.ev > ha-icon { color:var(--muted); }
.ev.live > ha-icon { color:#34d399; }
.ev b { display:block; font-size:14px; font-weight:600; }
.ev small { color:var(--muted); font-size:12px; }
.wide { width:100%; display:flex; align-items:center; justify-content:center; gap:8px; }
/* Heizpläne */
.plangroups { padding:14px 16px 4px; }
.pg { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
.pg + .pg { border-top:1px solid var(--line); padding-top:12px; }
.pg-l { display:inline-flex; align-items:center; gap:6px; min-width:150px; font-size:12px; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); }
.pg .pills { flex:1; margin-bottom:10px; }
.pill em { font-style:normal; font-size:11px; font-weight:700; padding:0 7px; border-radius:99px; background:var(--card2); color:var(--muted); }
.pill .pi { --mdc-icon-size:14px; color:var(--muted); }
.pill.add { border-style:dashed; color:var(--accent); }
.plan-name { font-size:20px; font-weight:700; width:100%; max-width:420px; margin-bottom:6px; }
.uchip { display:inline-flex; align-items:center; gap:5px; padding:2px 9px; border-radius:99px; background:var(--card2); margin:2px 2px 0 0; }
.uchip i { width:7px; height:7px; border-radius:50%; background:var(--rc); }
.row-btns { display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end; justify-content:center; margin-top:8px; }
.plan-head + p, .plan-head + .row-btns { margin-top:-6px; margin-bottom:14px; }
.card:not(.empty) .row-btns { justify-content:flex-start; }
.inline-sel { margin:0; min-width:240px; text-align:left; }
.empty .inline-sel { max-width:320px; margin:8px auto 0; }
@media (max-width:600px) {
  .pg-l { min-width:0; width:100%; }
  .row-btns > * { flex:1 1 100%; }
}
/* Plakativer Hintergrund je Bereich: Heizen = Glut und aufsteigende Wärme, Start = Zuhause */
:host { background-color:var(--bg); background-image:var(--deco, none); background-attachment:fixed; background-repeat:no-repeat; }
:host([view="heat"]) {
  --deco:radial-gradient(110% 55% at 50% 118%, rgba(249,115,22,.30), transparent 70%),
         radial-gradient(50% 45% at 102% -5%, rgba(239,68,68,.20), transparent 70%),
         radial-gradient(40% 40% at -5% 40%, rgba(251,191,36,.12), transparent 70%),
         url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 160 160'%3E%3Cg fill='none' stroke='%23fb923c' stroke-opacity='0.13' stroke-width='3' stroke-linecap='round'%3E%3Cpath d='M30 150c-14-16 14-28 0-44s14-28 0-44'/%3E%3Cpath d='M80 118c-14-16 14-28 0-44s14-28 0-44'/%3E%3Cpath d='M130 158c-14-16 14-28 0-44s14-28 0-44'/%3E%3C/g%3E%3C/svg%3E");
  background-size:100% 100%, 100% 100%, 100% 100%, 160px 160px; background-repeat:no-repeat, no-repeat, no-repeat, repeat; }
:host([dark][view="heat"]) {
  --deco:radial-gradient(110% 55% at 50% 118%, rgba(249,115,22,.28), transparent 70%),
         radial-gradient(50% 45% at 102% -5%, rgba(239,68,68,.22), transparent 70%),
         radial-gradient(40% 40% at -5% 40%, rgba(251,191,36,.08), transparent 70%),
         url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 160 160'%3E%3Cg fill='none' stroke='%23fb923c' stroke-opacity='0.08' stroke-width='3' stroke-linecap='round'%3E%3Cpath d='M30 150c-14-16 14-28 0-44s14-28 0-44'/%3E%3Cpath d='M80 118c-14-16 14-28 0-44s14-28 0-44'/%3E%3Cpath d='M130 158c-14-16 14-28 0-44s14-28 0-44'/%3E%3C/g%3E%3C/svg%3E"); }
:host([view="start"]) {
  --deco:radial-gradient(60% 50% at 0% 0%, rgba(45,212,191,.22), transparent 70%),
         radial-gradient(55% 50% at 100% 100%, rgba(251,146,60,.18), transparent 70%),
         radial-gradient(rgba(45,212,191,.16) 1.2px, transparent 1.6px);
  background-size:100% 100%, 100% 100%, 22px 22px; background-repeat:no-repeat, no-repeat, repeat; }
:host([dark][view="start"]) {
  --deco:radial-gradient(60% 50% at 0% 0%, rgba(45,212,191,.20), transparent 70%),
         radial-gradient(55% 50% at 100% 100%, rgba(251,146,60,.14), transparent 70%),
         radial-gradient(rgba(45,212,191,.12) 1.2px, transparent 1.6px); }
/* Heizen-Banner: schmal und dezent */
.hero { color:var(--text); padding:14px 18px; gap:12px; border-radius:var(--r); border:1px solid var(--line); box-shadow:none;
  background:linear-gradient(100deg, color-mix(in srgb, #fb923c 10%, var(--card)) 0%, var(--card) 55%); }
.hero::after { display:none; }
.hero .hero-label { color:var(--muted); font-size:12.5px; }
.hero-line { display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin-top:2px; }
.hero .hero-big { font-size:38px; margin-top:0; }
.hero .hero-big span { font-size:16px; color:var(--muted); }
.hero .verdict { margin-top:0; padding:5px 12px; font-size:13px; color:var(--ct); background:color-mix(in srgb, var(--c) 13%, transparent); border-color:color-mix(in srgb, var(--c) 35%, transparent); }
.hero .verdict ha-icon { filter:none; }
.hero .wx { background:var(--card2); padding:8px 12px; border-radius:14px; backdrop-filter:none; }
.hero .wx > ha-icon { --mdc-icon-size:30px; color:#f59e0b; }
.hero .wx b { font-size:17px; }
.hero .wx small { color:var(--muted); }
.hero .hstats { grid-template-columns:repeat(auto-fit, minmax(118px, 1fr)); gap:6px; }
.hero .hstat { background:var(--card2); border:none; padding:7px 10px; border-radius:12px; }
.hero .hstat > ha-icon { --mdc-icon-size:18px; color:var(--ct); --c:var(--muted); }
.hero .hstat[style] > ha-icon { color:var(--ct); }
.hero .hstat small { color:var(--muted); font-size:10.5px; }
.hero .hstat b { font-size:14.5px; }
.hero .hstat em { color:var(--muted); font-size:11px; }
@media (max-width:600px) {
  .hero { padding:12px 14px; }
  .hero .hero-big { font-size:32px; }
}
/* Untere Navigationsleiste (nur Handy) */
.bnav { display:none; }
@media (max-width:600px) {
  .bnav { display:flex; position:fixed; left:0; right:0; bottom:0; z-index:8; padding:6px 8px calc(6px + env(safe-area-inset-bottom)); gap:4px;
    background:color-mix(in srgb, var(--card) 92%, transparent); backdrop-filter:blur(12px); border-top:1px solid var(--line); }
  .bn { all:unset; cursor:pointer; flex:1; display:flex; flex-direction:column; align-items:center; gap:2px; padding:5px 0; border-radius:12px; font-size:11px; font-weight:600; color:var(--muted); }
  .bn .bi { position:relative; display:grid; place-items:center; width:54px; height:28px; border-radius:99px; }
  .bn ha-icon { --mdc-icon-size:22px; }
  .bn .mlogo { width:26px; height:26px; }
  .bn.on { color:var(--text); }
  .bn.on .bi { background:color-mix(in srgb, var(--accent) 18%, transparent); color:var(--accent); }
  .bn em { position:absolute; top:-3px; right:6px; min-width:16px; height:16px; padding:0 4px; box-sizing:border-box; border-radius:99px; font-style:normal; font-size:10px; font-weight:800; display:grid; place-items:center; background:#fb923c; color:#1f1300; }
  .bn em.warn { background:#22d3ee; color:#001b20; }
  .app { padding-bottom:calc(84px + env(safe-area-inset-bottom)); }
  /* Speicherleisten über der unteren Navigationsleiste halten */
  .savebar { bottom:calc(78px + env(safe-area-inset-bottom)); z-index:9; }
  .mtabs { display:none !important; }
  .heatnav { margin-bottom:12px; }
  .hnav { padding:9px 10px; font-size:13px; }
  .top { padding-bottom:6px; }
  :host .top.slim .bar { display:flex; min-height:44px; }
  :host .top.slim .ttl { display:flex; order:2; flex:1; }
  :host .top.slim .ttl b { font-size:15px; }
  :host .top.slim .ttl small { display:none; }
}
/* Raum-Detailseite */
.rlink { all:unset; cursor:pointer; display:block; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.rlink:hover { color:var(--accent); text-decoration:underline; text-underline-offset:3px; }
.rm-name.rlink, .room-t .rlink { white-space:normal; overflow:visible; text-overflow:clip; overflow-wrap:break-word; hyphens:manual; }
.rpage .room { margin-bottom:14px; }
.rp-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:14px; }
.rp-grid .card { margin:0; }
.kvs { display:grid; }
.kv { display:flex; justify-content:space-between; gap:12px; padding:8px 0; border-top:1px solid var(--line); font-size:13.5px; }
.kv:first-child { border-top:none; }
.kv span { color:var(--muted); }
.kv b { font-weight:600; text-align:right; }
.wrow em.bad { color:#f87171; }
.wminis.four { grid-template-columns:repeat(2, 1fr); }
.rlegend { display:inline-flex; gap:12px; flex-wrap:wrap; font-size:12px; color:var(--muted); }
.rlegend span { display:inline-flex; align-items:center; gap:5px; }
.rlegend i { display:inline-block; width:14px; height:3px; border-radius:2px; }
.rlegend .lt { background:var(--accent); }
.rlegend .ls { background:repeating-linear-gradient(90deg, #fb923c 0 4px, transparent 4px 7px); }
.rlegend .lh { background:#fb923c; opacity:.55; height:8px; }
.rlegend .lw { background:#22d3ee; opacity:.55; height:8px; }
.chart.hist { height:240px; }
.hwrap { position:relative; }
.hy { position:absolute; left:0; top:0; height:240px; width:6.5%; pointer-events:none; }
.hy span { position:absolute; right:4px; transform:translateY(-50%); font-size:11px; color:var(--muted); }
.hx { display:flex; justify-content:space-between; margin:-18px 0 0 7%; font-size:11px; color:var(--muted); }
@media (max-width:600px) { .chart.hist, .hy { height:190px; } .rlegend { gap:8px; } }
.chart.hist .pt { fill:none; stroke:var(--accent); stroke-width:2.5; vector-effect:non-scaling-stroke; stroke-linejoin:round; }
.chart.hist .ps { fill:none; stroke:#fb923c; stroke-width:2; stroke-dasharray:6 5; vector-effect:non-scaling-stroke; }
.chart.hist .bh { fill:#fb923c; opacity:.45; }
.chart.hist .bw { fill:#22d3ee; opacity:.45; }
/* Kopfzeile beim Scrollen: eine Zeile mit Logo, Reitern und Glocke */
:host { position:relative; }
#sentinel { position:absolute; top:0; left:0; width:1px; height:48px; pointer-events:none; }
.top.slim { display:flex; align-items:center; gap:10px; padding-top:6px; padding-bottom:6px; }
.top.slim .bar { display:contents; }
.top.slim .ttl { display:none; }
.top.slim .menu { order:0; width:34px; height:34px; }
.top.slim .brand { order:1; }
.top.slim .brand svg { width:32px; height:32px; }
.top.slim .mtabs { order:2; flex:1; min-width:0; padding:0; gap:6px; }
.top.slim .mtab { padding:6px 12px; }
.top.slim .mtab > ha-icon { --mdc-icon-size:18px; }
.top.slim .mtab .mlogo { width:18px; height:18px; border-radius:5px; }
.top.slim .mtab .mt b { font-size:14px; }
.top.slim .hacts { order:3; }
.top.slim .bell { width:36px; height:36px; border-radius:12px; }
/* Räume ohne Thermostat */
.room.setup, .rmini.setup { background:transparent; border-style:dashed; box-shadow:none; }
.room.setup::before, .rmini.setup::before { background:var(--line2); }
.room.setup .room-ic, .rmini.setup .rm-ic { opacity:.6; }
.room.setup .room-t small { color:var(--muted); }
.setup-b { display:flex; flex-direction:column; align-items:flex-start; gap:10px; margin-top:14px; }
.setup-b p { display:flex; align-items:center; gap:8px; margin:0; color:var(--muted); font-size:13.5px; }
.setup-b p ha-icon { --mdc-icon-size:20px; }
.setup-b .secondary { display:inline-flex; align-items:center; gap:7px; }
.rmini .setup-b { margin-top:6px; }
.rmini .setup-b .secondary { padding:7px 11px; font-size:13px; }
.wroom.setup { opacity:.6; }
.wroom.setup small { font-style:italic; }
/* Gleichmäßiges Widget-Raster: klein und mittel gleich hoch, groß nach Inhalt */
.wdg.sz-s, .wdg.sz-m { height:236px; }
.wdg .wb { min-height:0; overflow-y:auto; overflow-x:hidden; scrollbar-width:thin; margin-right:-6px; padding-right:6px; }
.wdg.sz-s .wb, .wdg.sz-m .wb { padding-bottom:16px; mask-image:linear-gradient(180deg, #000 calc(100% - 14px), transparent); -webkit-mask-image:linear-gradient(180deg, #000 calc(100% - 14px), transparent); }
@media (max-width:700px) {
  .wdg.sz-s { height:176px; }
  .wdg.sz-m { height:auto; max-height:340px; }
}
/* Experten-Schalter im Raum-Dialog */
.xtog { all:unset; cursor:pointer; flex:none; display:inline-flex; align-items:center; gap:6px; margin:6px 0; padding:5px 10px; border-radius:99px; font-size:12.5px; font-weight:600; color:var(--muted); border:1px solid var(--line2); }
.xtog ha-icon { --mdc-icon-size:16px; }
.xtog i { width:26px; height:14px; border-radius:99px; background:var(--track); position:relative; }
.xtog i::after { content:""; position:absolute; top:2px; left:2px; width:10px; height:10px; border-radius:50%; background:#fff; transition:left .15s; }
.xtog.on { color:var(--accent); border-color:var(--accent); }
.xtog.on i { background:var(--accent); }
.xtog.on i::after { left:14px; }
.xhint { all:unset; cursor:pointer; box-sizing:border-box; width:100%; display:flex; align-items:center; gap:8px; margin-top:18px; padding:10px 12px; border-radius:12px; border:1px dashed var(--line2); color:var(--muted); font-size:13px; }
.xhint:hover { border-color:var(--accent); color:var(--text); }
.xhint > span:not(.grow) { color:var(--text); font-weight:600; }
@media (max-width:600px) { .xtog span { display:none; } }
/* Ruhigere Farben: Raumfarbe nur als Streifen, Symbole einheitlich */
.room-ic, .rm-ic { background:var(--card2) !important; color:var(--text) !important; }
.wic, .sr-ic { --c:var(--accent) !important; }
.hint.warn .sr-ic { --c:#f59e0b !important; }
.hint.info .sr-ic { --c:#60a5fa !important; }
.room-head { gap:8px; }
.room-head .icon { width:34px; height:34px; flex:none; }
.room-t small { flex-wrap:wrap; }
.room-t .sis { display:inline-flex; gap:7px; margin-left:8px; }
.rmenu { border:none !important; padding:0 !important; margin:0 !important; }
.room-head .icon { width:30px; height:30px; }
.room-head .rmenu summary { width:30px; height:30px; }
.room-head .mode { padding:4px 9px; font-size:12px; }
.room-head .mode ha-icon { --mdc-icon-size:14px; }
.room-t .si { display:inline-flex; align-items:center; gap:3px; color:var(--ct); font-size:12px; padding:0; background:none; }
.room-t .si ha-icon { --mdc-icon-size:14px; }
.rmenu { position:relative; flex:none; }
.rmenu summary { list-style:none; display:grid; place-items:center; width:34px; height:34px; border-radius:11px; cursor:pointer; color:var(--muted); }
.rmenu summary::-webkit-details-marker { display:none; }
.rmenu summary:hover, .rmenu[open] summary { background:var(--card2); color:var(--text); }
.rm-pop { position:absolute; right:0; top:calc(100% + 6px); z-index:6; min-width:210px; padding:6px; border-radius:14px; background:var(--card); border:1px solid var(--line2); box-shadow:var(--shadow); display:grid; }
.rm-pop button { all:unset; cursor:pointer; display:flex; align-items:center; gap:10px; padding:9px 10px; border-radius:10px; font-size:14px; }
.rm-pop button:hover { background:var(--card2); }
.rm-pop ha-icon { --mdc-icon-size:18px; color:var(--muted); }
.room .room-note:last-child { margin-bottom:0; }
.room .rsched:last-child { margin-bottom:0; }
@media (max-width:600px) {
  .room-head .mode { max-width:120px; }
}
/* Einheitliche Schrift: Wert groß, Titel, Nebeninfo */
:host { --fs-val:34px; --fs-title:15px; --fs-sub:12.5px; }
.room-temp, .wbig > span:first-child, .wval b, .wwx b, .hero .hero-big, .kpi-v, .rm-temp { font-size:var(--fs-val) !important; letter-spacing:-.02em; }
.rm-temp, .wdg.sz-s .wbig > span:first-child, .wdg.sz-s .wval b, .wdg.sz-s .wwx b { font-size:28px !important; }
.room-t h4, .wh b, .sr-t b, .stit b, .shead h3, .rm-name, .prow b, .wrow b, .mt-t b, .ev b { font-size:var(--fs-title) !important; }
.room-t small, .sr-t small, .wrow small, .prow small, .wmini small, .ev small, .kv, .rs-top, .room-note, .muted.small, .trend, .gm .gl, .rm-mode { font-size:var(--fs-sub) !important; }
.room-temp span, .wbig small, .hero .hero-big span, .rm-temp small { font-size:14px !important; }
/* Darstellung: Himmel nach Tageszeit, schlichter Hintergrund, Größe, Uhrzeit und Wetter oben rechts */
:host {
  --sky-night:radial-gradient(1.5px 1.5px at 12% 30%, #fff, transparent), radial-gradient(1px 1px at 32% 62%, #fffc, transparent),
    radial-gradient(1.5px 1.5px at 58% 22%, #fff, transparent), radial-gradient(1px 1px at 76% 52%, #fffb, transparent),
    radial-gradient(1px 1px at 90% 18%, #fffc, transparent), linear-gradient(165deg, #0b1026 0%, #1b2557 60%, #34386f 100%);
  --sky-dawn:radial-gradient(60% 120% at 80% 120%, rgba(253,186,116,.9), transparent 70%), linear-gradient(165deg, #3b2c5f 0%, #a8507a 60%, #f39b62 100%);
  --sky-day:radial-gradient(18% 60% at 88% 20%, rgba(255,247,200,.95), transparent 70%), linear-gradient(165deg, #3b82f6 0%, #7cb7fb 55%, #cfe6ff 100%);
  --sky-dusk:radial-gradient(60% 120% at 20% 120%, rgba(251,146,60,.9), transparent 70%), linear-gradient(165deg, #251b48 0%, #873c69 60%, #ef8547 100%);
}
:host([sky]) .top { border-bottom-color:transparent; color:var(--text); }
:host([sky="night"]) .top { background:var(--sky-night); }
:host([sky="dawn"]) .top { background:var(--sky-dawn); }
:host([sky="day"]) .top { background:var(--sky-day); }
:host([sky="dusk"]) .top { background:var(--sky-dusk); }
:host([sky="night"]) .top, :host([sky="dawn"]) .top, :host([sky="dusk"]) .top {
  --text:#fff; --muted:rgba(255,255,255,.78); --card:rgba(255,255,255,.13); --line:rgba(255,255,255,.2); --line2:rgba(255,255,255,.35); }
:host([sky="day"]) .top { --text:#0b2545; --muted:rgba(11,37,69,.72); --card:rgba(255,255,255,.6); --line:rgba(255,255,255,.7); --line2:rgba(255,255,255,.9); }
:host([sky]) .top .ttl small { color:var(--text); opacity:.85; }
:host([sky]) .top .mtab, :host([sky]) .top .bell, :host([sky]) .top .hinfo { backdrop-filter:blur(8px); }
:host([bg="plain"]) { background-image:none !important; }
:host([size="s"]) .top, :host([size="s"]) .app, :host([size="s"]) .bnav, :host([size="s"]) .sheet, :host([size="s"]) .toast { zoom:.9; }
:host([size="l"]) .top, :host([size="l"]) .app, :host([size="l"]) .bnav, :host([size="l"]) .sheet, :host([size="l"]) .toast { zoom:1.15; }
.hinfo { display:flex; align-items:center; gap:10px; padding:0 12px; height:42px; box-sizing:border-box; border-radius:14px; background:var(--card); border:1px solid var(--line); font-weight:700; font-size:15px; white-space:nowrap; }
.hwx { display:inline-flex; align-items:center; gap:5px; }
.hwx ha-icon { --mdc-icon-size:20px; color:#f59e0b; }
.hclock { font-variant-numeric:tabular-nums; }
.hclock + .hwx { padding-left:10px; border-left:1px solid var(--line2); }
.top.slim .hinfo { height:36px; border-radius:12px; font-size:13.5px; }
.bell.gear ha-icon { --mdc-icon-size:21px; }
.swatches { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:6px; }
.sw { all:unset; cursor:pointer; position:relative; width:38px; height:38px; border-radius:50%; background:var(--c); box-shadow:inset 0 0 0 1px rgba(0,0,0,.12); display:grid; place-items:center; }
.sw.on { box-shadow:0 0 0 3px var(--card), 0 0 0 5px var(--c); }
.sw.on::after { content:""; width:12px; height:12px; border-radius:50%; background:#fff; box-shadow:0 0 0 2px rgba(0,0,0,.25); }
.sw.custom { background:conic-gradient(#ef4444, #f59e0b, #84cc16, #0ea5e9, #8b5cf6, #ec4899, #ef4444); }
.sw.custom input { position:absolute; inset:0; width:100%; height:100%; opacity:0; cursor:pointer; padding:0; border:none; }
.sw[disabled] { cursor:default; opacity:.6; }
.skies { display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; margin:4px 0 8px; }
.skyc { display:flex; flex-direction:column; gap:4px; min-width:0; }
.skyc small { font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sky { position:relative; height:58px; border-radius:12px; border:2px solid transparent; }
.sky.on { border-color:var(--accent); }
.sky em { position:absolute; left:6px; top:5px; font-style:normal; font-size:10px; font-weight:800; padding:1px 7px; border-radius:99px; background:var(--accent); color:var(--ink); }
@media (max-width:600px) {
  .hclock { display:none; }
  .hclock + .hwx { border:none; padding:0; }
  .hinfo { padding:0 9px; height:38px; font-size:14px; }
  .skies { grid-template-columns:repeat(2, 1fr); }
}
/* Wetter: Zeilen mit Wert rechts und Erklärung per „?“ */
.wxrows { display:grid; gap:2px; margin-bottom:6px; }
.wxr { display:flex; align-items:center; gap:14px; padding:12px 14px; border-radius:14px; }
.wxr:nth-child(odd) { background:var(--card2); }
.wxr-l { flex:1; min-width:0; }
.wxr-l b { display:flex; align-items:center; gap:8px; font-size:15px; font-weight:600; }
.wxr-l small { display:block; color:var(--muted); font-size:12.5px; margin-top:2px; line-height:1.35; }
.wxr-h { margin:8px 0 0 !important; font-size:12.5px; line-height:1.45; color:var(--text) !important; padding:8px 10px; border-radius:10px; background:color-mix(in srgb, var(--accent) 10%, var(--card)); }
.wxr-v { flex:none; max-width:55%; text-align:right; font-weight:700; font-size:15px; }
.wxr-v select { max-width:260px; font-weight:600; }
.wxsrcs { display:grid; gap:8px; margin-bottom:6px; }
.wxsrc { background:var(--card2); border-radius:14px; }
.wxr-pk { padding:0 14px 12px; }
.newp { display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap; }
.newp input { flex:1; min-width:160px; }
.wxsrc .segs { margin-top:2px; }
.wxsrc .segs.small.n4 { grid-template-columns:repeat(4, minmax(0, 1fr)); gap:6px; }
.wxsrc .segs.small.n4 .seg { padding:9px 4px; font-size:12.5px; gap:4px; }
@media (max-width:420px) { .wxsrc .segs.small.n4 .seg ha-icon { display:none; } }
.nrow { display:flex; align-items:center; gap:10px; justify-content:flex-end; }
.nrow .unit input { width:76px; }
.nrow input[type=time] { width:auto; }
.pk-none { padding:4px 2px; }
.wxr-v .unit { justify-content:flex-end; }
.wxr-v .unit input { width:96px; text-align:right; font-weight:700; }
.wxr-v .link { font-size:15px; }
.qm { all:unset; cursor:pointer; width:22px; height:22px; flex:none; border-radius:50%; border:1.5px solid var(--line2); display:grid; place-items:center; font-size:12px; font-weight:700; color:var(--muted); }
.qm:hover, .qm.on { border-color:var(--accent); color:var(--accent); }
@media (max-width:600px) {
  .wxr { flex-wrap:wrap; gap:8px 12px; }
  .wxr.ctl .wxr-v { width:100%; max-width:none; }
  .wxr.ctl .wxr-v select { max-width:none; width:100%; }
}
/* Protokoll */
.card.lg { padding:20px 22px; }
.lg-head { display:flex; align-items:flex-start; gap:12px; margin-bottom:16px; }
.lg-ic { width:44px; height:44px; flex:none; border-radius:14px; display:grid; place-items:center; background:var(--card2); color:var(--muted); }
.lg-ic ha-icon { --mdc-icon-size:24px; }
.lg-head h2 { margin:0 0 2px; font-size:20px; }
.lg-head small { color:var(--muted); font-size:13px; }
.lg-live { display:inline-flex; align-items:center; gap:6px; font-size:13px; font-weight:600; color:var(--muted); white-space:nowrap; padding-top:4px; font-variant-numeric:tabular-nums; }
.lg-live i { width:10px; height:10px; border-radius:50%; background:var(--line2); }
.lg-live.on i { background:#22c55e; box-shadow:0 0 0 3px color-mix(in srgb, #22c55e 25%, transparent); }
.lg-chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
.lg-room, .lg-cat { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:7px; padding:8px 14px; border-radius:99px; font-size:14px; font-weight:600;
  color:var(--muted); background:color-mix(in srgb, var(--c) 7%, var(--card)); border:1px solid color-mix(in srgb, var(--c) 16%, transparent); opacity:.62; }
.lg-room i { width:8px; height:8px; border-radius:50%; background:var(--c); }
.lg-cat ha-icon { --mdc-icon-size:17px; color:var(--ct); }
.lg-room.on, .lg-cat.on { opacity:1; color:var(--text); background:color-mix(in srgb, var(--c) 15%, var(--card)); border-color:color-mix(in srgb, var(--c) 38%, transparent); }
.lg-search { margin:4px 0 6px; }
.lg-day { font-size:12px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); padding:18px 0 8px; border-bottom:1px solid var(--line); }
.lg-row { display:grid; grid-template-columns:48px 40px minmax(0, 1fr); gap:12px; padding:12px 0; border-bottom:1px solid var(--line); align-items:start; }
.lg-row time { font-size:13.5px; font-weight:600; color:var(--muted); padding-top:10px; font-variant-numeric:tabular-nums; }
.lg-i { width:40px; height:40px; border-radius:12px; display:grid; place-items:center; background:color-mix(in srgb, var(--c) 15%, transparent); color:var(--ct); }
.lg-i ha-icon { --mdc-icon-size:21px; }
.lg-t { display:flex; flex-wrap:wrap; align-items:center; gap:4px 8px; padding-top:2px; }
.lg-t b { font-size:15px; font-weight:700; }
.lg-badge { font-size:12px; font-weight:600; padding:2px 9px; border-radius:99px; color:var(--ct); background:color-mix(in srgb, var(--c) 14%, transparent); }
.lg-b p { margin:4px 0 0; font-size:13.5px; color:var(--muted); line-height:1.45; overflow-wrap:anywhere; }
.lg-b p b { color:var(--text); font-weight:600; }
.lg-more { margin-top:14px; box-sizing:border-box; }
@media (max-width:600px) {
  .card.lg { padding:14px; }
  .lg-row { grid-template-columns:40px 34px minmax(0, 1fr); gap:10px; }
  .lg-i { width:34px; height:34px; border-radius:10px; }
  .lg-row time { padding-top:7px; font-size:12.5px; }
  .lg-room, .lg-cat { padding:7px 11px; font-size:13px; }
}
.toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:var(--text); color:var(--bg); padding:11px 20px; border-radius:12px; z-index:30; font-size:14px; font-weight:600; box-shadow:0 10px 30px rgba(0,0,0,.4); }

@media (max-width:820px) {
  .kpis { grid-template-columns:1fr 1fr; }
  .gauge { width:130px; }
  .hero-big { font-size:52px; }
}
@media (max-width:600px) {
  /* unten Platz für die Navigationsleiste lassen, sonst verdeckt sie das Ende der letzten Kachel */
  .app { padding:10px 12px calc(96px + env(safe-area-inset-bottom)); }
  .hmodes { grid-template-columns:1fr; }
  .top { padding:6px 10px 0; }
  .bar { gap:8px; }
  .brand svg { width:36px; height:36px; }
  .ttl b { font-size:16px; }
  .ttl span { display:none; }
  .abtn span { display:none; }
  .abtn { padding:9px; }
  .mtab { padding:8px 12px; gap:8px; }
  .mtiles { grid-template-columns:repeat(2, 1fr); gap:8px; }
  .mtile { padding:12px 8px; gap:4px; }
  .mico { width:38px; height:38px; border-radius:12px; }
  .gmini { grid-template-columns:1fr 1fr; }
  .hl { font-size:22px; }
  .hero { flex-direction:column; align-items:stretch; padding:20px; }
  .gauge { position:absolute; right:10px; top:10px; width:96px; opacity:.95; }
  .hero-big { font-size:46px; }
  .row2, .row3, .types { grid-template-columns:1fr; }
  .rooms { grid-template-columns:1fr; }
  .card { padding:16px; }
  .chart { height:180px; }
  .dp { width:38px; }
  .block-temp { justify-content:flex-start; flex-basis:calc(100% - 60px); }
  .block .daypills { display:grid; grid-template-columns:repeat(7, 1fr); gap:5px; }
  .block .dp { width:auto; }
  .plan-tools .addbtn { flex-basis:100%; }
  .plan-tools .ghost { padding:12px 18px; justify-content:center; flex:1; }
  .sheet { top:auto; bottom:0; left:0; transform:none; width:100vw; height:92vh; max-height:92vh; border-radius:24px 24px 0 0; }
  /* sichtbare Höhe statt 100vh (in der App und im Browser liegen sonst Leisten über dem Fuß) */
  @supports (height:100dvh) { .sheet { height:92dvh; max-height:92dvh; } .sheet.pop { height:auto; } }
  .sheet-foot { padding-bottom:calc(16px + env(safe-area-inset-bottom)); }
  .dtabs { padding:0 10px; justify-content:space-between; }
  .dtab:not(.on) span { display:none; }
  .dtab { padding:11px 8px 12px; }
  .pseg span { font-size:13px; }
  .ptoggles { width:100%; }
  .ptoggle { flex:1; justify-content:center; }
  .snav:not(.on) span { display:none; }
  .si .t { display:none; }
  .si { padding:0 6px; }
}
`;

customElements.get("hauswerk-panel") || customElements.define("hauswerk-panel", HauswerkPanel);
