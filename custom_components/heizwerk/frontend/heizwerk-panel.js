// Heizwerk – Ersatz-Panel (Wiederherstellung).
// Schlichte Raumübersicht mit ±0,5 °C und Boost über die WebSocket-API.
// Das vollständige Original-Panel (Widgets, Raumseite, Einstellungen, Hinweise)
// war nicht unter den gesicherten Dateien und sollte diese Datei ersetzen.

class HeizwerkPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._status = null;
    this._unsub = null;
    this._error = null;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._init();
  }

  set narrow(v) { this._narrow = v; }
  set panel(v) { this._panel = v; }

  async _init() {
    try {
      this._data = await this._hass.callWS({ type: "heizwerk/get" });
      this._status = this._data.status;
      this._unsub = await this._hass.connection.subscribeMessage(
        (status) => { this._status = status; this._render(); },
        { type: "heizwerk/subscribe" }
      );
    } catch (err) {
      this._error = err.message || String(err);
    }
    this._render();
  }

  disconnectedCallback() {
    if (this._unsub) { this._unsub(); this._unsub = null; }
  }

  async _override(roomId, delta, boost = false) {
    const r = (this._status.rooms || {})[roomId] || {};
    const msg = { type: "heizwerk/override", room_id: roomId, boost };
    if (!boost) {
      const base = r.target ?? 20;
      msg.temp = Math.min(30, Math.max(5, Math.round((base + delta) * 2) / 2));
    }
    try { await this._hass.callWS(msg); } catch (err) { alertless(this, err); }
  }

  async _reset(roomId) {
    try { await this._hass.callWS({ type: "heizwerk/override", room_id: roomId, temp: null }); }
    catch (err) { alertless(this, err); }
  }

  _fmt(v, unit = "°C") {
    return v === null || v === undefined ? "–" : `${Number(v).toLocaleString("de-DE", { maximumFractionDigits: 1 })} ${unit}`;
  }

  _render() {
    const root = this.shadowRoot;
    const css = `
      :host { display:block; padding:16px; color:var(--primary-text-color); background:var(--primary-background-color); min-height:100vh; box-sizing:border-box; font-family:var(--paper-font-body1_-_font-family, sans-serif); }
      h1 { font-size:22px; font-weight:500; margin:0 0 4px; }
      .sub { color:var(--secondary-text-color); margin-bottom:16px; font-size:14px; }
      .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:12px; }
      .card { background:var(--card-background-color); border-radius:12px; padding:14px; box-shadow:var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.15)); }
      .name { font-weight:500; font-size:16px; }
      .mode { font-size:13px; color:var(--secondary-text-color); margin-top:2px; }
      .row { display:flex; align-items:center; justify-content:space-between; margin-top:12px; }
      .temp { font-size:28px; font-weight:300; }
      .small { font-size:13px; color:var(--secondary-text-color); }
      button { border:none; border-radius:8px; padding:8px 12px; background:var(--secondary-background-color); color:var(--primary-text-color); font-size:15px; cursor:pointer; }
      button.accent { background:var(--primary-color); color:var(--text-primary-color, #fff); }
      .chips span { display:inline-block; font-size:12px; padding:2px 8px; border-radius:10px; background:var(--secondary-background-color); margin:6px 4px 0 0; }
      .heat { color:var(--state-climate-heat-color, #ff8100); }
      .err { color:var(--error-color); }
      .note { margin-top:20px; font-size:12px; color:var(--secondary-text-color); }
    `;
    if (this._error) {
      root.innerHTML = `<style>${css}</style><h1>Heizwerk</h1><p class="err">${esc(this._error)}</p>`;
      return;
    }
    if (!this._data) {
      root.innerHTML = `<style>${css}</style><h1>Heizwerk</h1><p class="sub">Lade …</p>`;
      return;
    }
    const st = this._status || {};
    const rooms = this._data.rooms || {};
    const flags = [];
    if (st.away) flags.push("Abwesend");
    if (st.vacation) flags.push("Urlaub");
    if (st.party) flags.push("Party");
    if (st.guest) flags.push("Gäste");
    if (st.summer) flags.push("Sommerpause");
    if (st.eco_force) flags.push("Eco erzwungen");
    const outside = st.outside_temp != null ? ` · Außen ${this._fmt(st.outside_temp)}` : "";

    const cards = Object.values(rooms).map((room) => {
      const r = (st.rooms || {})[room.id] || {};
      const chips = [];
      if (r.windows_open) chips.push("Fenster offen");
      if (r.humidity != null) chips.push(`${Math.round(r.humidity)} % rF`);
      if (r.override_until) chips.push(`bis ${new Date(r.override_until).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`);
      return `
        <div class="card">
          <div class="name">${esc(room.name)} ${r.heating ? '<span class="heat">●</span>' : ""}</div>
          <div class="mode">${esc(r.mode_label || "–")}</div>
          <div class="row">
            <div><div class="temp">${this._fmt(r.room_temp)}</div><div class="small">Soll ${this._fmt(r.target)}</div></div>
            <div>
              <button data-act="minus" data-id="${room.id}">−</button>
              <button data-act="plus" data-id="${room.id}">+</button>
            </div>
          </div>
          <div class="row">
            <div class="chips">${chips.map((c) => `<span>${esc(c)}</span>`).join("")}</div>
            <div>
              ${r.override_until ? `<button data-act="reset" data-id="${room.id}">Plan</button>` : ""}
              <button class="accent" data-act="boost" data-id="${room.id}">Boost</button>
            </div>
          </div>
        </div>`;
    }).join("");

    root.innerHTML = `
      <style>${css}</style>
      <h1>Heizwerk</h1>
      <div class="sub">${flags.length ? esc(flags.join(" · ")) : "Normalbetrieb"}${esc(outside)}</div>
      <div class="grid">${cards || '<p class="sub">Noch keine Räume angelegt.</p>'}</div>
      <div class="note">Ersatz-Panel – Räume, Pläne und Einstellungen sind hier nicht bearbeitbar.</div>
    `;
    root.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const act = btn.dataset.act;
        if (act === "plus") this._override(id, 0.5);
        else if (act === "minus") this._override(id, -0.5);
        else if (act === "boost") this._override(id, 0, true);
        else if (act === "reset") this._reset(id);
      });
    });
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function alertless(panel, err) {
  panel._error = err.message || String(err);
  panel._render();
  setTimeout(() => { panel._error = null; panel._render(); }, 4000);
}

customElements.define("heizwerk-panel", HeizwerkPanel);
