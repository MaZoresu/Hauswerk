/* Hauswerk als Dashboard: eine Dashboard-Strategie „custom:hauswerk“ und eine Karte, die das Hauswerk-Panel ganzseitig zeigt.
 *
 * In einem Dashboard (Einstellungen › Dashboards) im Rohkonfigurations-Editor:
 *   strategy:
 *     type: custom:hauswerk
 * Damit steht Hauswerk in der Liste der Dashboards und lässt sich dort als Standard festlegen.
 * Diese Datei ist klein und wird auf jeder Seite geladen; das eigentliche Panel lädt erst, wenn die Karte gezeigt wird.
 */
const HW_PANEL_URL = new URL("hauswerk-panel.js", import.meta.url).href.replace(/\?.*$/, "") + new URL(import.meta.url).search;

class HauswerkDashboardStrategy extends HTMLElement {
  static async generate() {
    const card = { type: "custom:hauswerk-card" };
    return {
      title: "Hauswerk",
      views: [{ title: "Hauswerk", path: "hauswerk", icon: "mdi:home-lightning-bolt-outline", type: "panel", cards: [card] }],
    };
  }
}
customElements.get("ll-strategy-dashboard-hauswerk") || customElements.define("ll-strategy-dashboard-hauswerk", HauswerkDashboardStrategy);

class HauswerkCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }
  set hass(hass) {
    this._hass = hass;
    if (this._panel) this._panel.hass = hass;
    else this._load();
  }
  connectedCallback() {
    this.style.display = "block";
    this._onResize = this._onResize || (() => { if (this._panel) this._panel.narrow = window.innerWidth < 870; });
    window.addEventListener("resize", this._onResize);
  }
  disconnectedCallback() {
    window.removeEventListener("resize", this._onResize);
  }
  async _load() {
    if (this._loading || !this._hass) return;
    this._loading = true;
    try {
      await import(HW_PANEL_URL);
    } catch (err) {
      this.textContent = `Hauswerk konnte nicht geladen werden: ${err?.message || err}`;
      return;
    }
    const panel = document.createElement("hauswerk-panel");
    panel.setAttribute("embedded", "");
    panel.panel = { url_path: "hauswerk", config: {} };
    panel.narrow = window.innerWidth < 870;
    panel.hass = this._hass;
    this.append(panel);
    this._panel = panel;
  }
  getCardSize() {
    return 20;
  }
  getGridOptions() {
    return { columns: "full", rows: "auto" };
  }
}
customElements.get("hauswerk-card") || customElements.define("hauswerk-card", HauswerkCard);

window.customStrategies = window.customStrategies || [];
if (!window.customStrategies.some((s) => s.type === "hauswerk")) {
  window.customStrategies.push({ type: "hauswerk", strategyType: "dashboard", name: "Hauswerk", description: "Hauswerk ganzseitig als Dashboard – Heizwerk, Rollwerk, Kraftwerk.", documentationURL: "https://github.com/MaZoresu/Hauswerk" });
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "hauswerk-card")) {
  window.customCards.push({ type: "hauswerk-card", name: "Hauswerk", description: "Das Hauswerk-Panel als Karte (am besten in einer Ansicht vom Typ „Panel“)." });
}
