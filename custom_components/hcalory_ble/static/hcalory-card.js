const DEFAULT_ENTITIES = {
  heating: ["switch.hcalory_ble_heating", "switch.hcalory_power", "switch.hcalory_heating"],
  autoMode: ["switch.hcalory_ble_auto_mode", "input_boolean.hcalory_auto_mode"],
  ventilation: ["switch.hcalory_ble_ventilation", "switch.hcalory_ventilation"],
  highland: ["switch.hcalory_ble_highland_mode", "switch.hcalory_highland_mode"],
  heaterState: ["sensor.hcalory_ble_heater_state", "sensor.hcalory_heater_state"],
  heaterMode: ["sensor.hcalory_ble_heater_mode", "sensor.hcalory_heater_mode"],
  heaterSetting: ["sensor.hcalory_ble_heater_setting", "sensor.hcalory_heater_setting"],
  bodyTemperature: ["sensor.hcalory_ble_body_temperature", "sensor.hcalory_body_temperature"],
  ambientTemperature: ["sensor.hcalory_ble_ambient_temperature", "sensor.hcalory_ambient_temperature"],
  voltage: ["sensor.hcalory_ble_voltage", "sensor.hcalory_voltage"],
  protocolVersion: ["sensor.hcalory_ble_protocol_version", "sensor.hcalory_protocol_version"],
  errorCode: "sensor.hcalory_ble_heater_error_code",
  errorMessage: "sensor.hcalory_ble_heater_error",
  lastSuccessAge: ["sensor.hcalory_ble_last_success_age", "sensor.hcalory_last_success_age"],
  consecutiveFailures: ["sensor.hcalory_ble_consecutive_failures", "sensor.hcalory_consecutive_failures"],
  lastError: ["sensor.hcalory_ble_last_error", "sensor.hcalory_last_error"],
  serviceOnline: ["binary_sensor.hcalory_ble_service_online", "binary_sensor.hcalory_daemon_online_bin"],
  bleConnected: ["binary_sensor.hcalory_ble_ble_connected", "binary_sensor.hcalory_heater_connected_bin"],
  dataOk: ["binary_sensor.hcalory_ble_data_ok", "binary_sensor.hcalory_data_ok_bin"],
  running: ["binary_sensor.hcalory_ble_running", "binary_sensor.hcalory_running_bin"],
  cooldown: ["binary_sensor.hcalory_ble_cooldown", "binary_sensor.hcalory_cooldown_bin"],
  preheating: ["binary_sensor.hcalory_ble_preheating", "binary_sensor.hcalory_preheating_bin"],
  gearMode: ["button.hcalory_ble_gear_mode", "button.hcalory_gear"],
  thermostatMode: ["button.hcalory_ble_thermostat_mode", "button.hcalory_thermostat"],
  up: ["button.hcalory_ble_increase_setting", "button.hcalory_up"],
  down: ["button.hcalory_ble_decrease_setting", "button.hcalory_down"],
  requestedSetting: "number.hcalory_ble_requested_setting",
  targetTemperature: "input_number.hcalory_target_temperature",
  hysteresis: "input_number.hcalory_hysteresis",
};

const STATE_LABELS = {
  unknown: "Unknown",
  unavailable: "Unavailable",
  off: "Off",
  standby: "Standby",
  cooldown: "Cooldown",
  cooldown_starting: "Cooldown starting",
  cooldown_received: "Cooldown requested",
  ignition_received: "Start requested",
  ignition_starting: "Starting",
  igniting: "Igniting",
  running: "Running",
  heating: "Heating",
  fan_starting: "Fan starting",
  fan_only: "Ventilation",
  error26: "Error 26",
  error255: "Error 255",
};

const MODE_LABELS = {
  unknown: "Unknown",
  unavailable: "Unavailable",
  off: "Off",
  gear: "Power",
  thermostat: "Thermostat",
  ventilation: "Ventilation",
  ignition_failed: "Ignition failed",
};

class HCaloryCard extends HTMLElement {
  constructor() {
    super();
    this._lastInteraction = 0;
    this.addEventListener("pointerdown", (event) => {
      const target = event.composedPath().find((el) => el?.dataset?.action);
      if (!target) return;
      event.preventDefault();
      event.stopPropagation();
      this._lastInteraction = Date.now();
      this.handleAction(target.dataset.action);
    });
    this.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const target = event.composedPath().find((el) => el?.dataset?.action);
      if (!target) return;
      event.preventDefault();
      event.stopPropagation();
      this._lastInteraction = Date.now();
      this.handleAction(target.dataset.action);
    });
  }

  setConfig(config) {
    this.config = {
      entities: { ...DEFAULT_ENTITIES, ...(config.entities || {}) },
      initiallyExpanded: config.initially_expanded || false,
    };
    this._settingsOpen = Boolean(this.config.initiallyExpanded);
    this._detailsOpen = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (Date.now() - this._lastInteraction < 250) return;
    this.render();
  }

  getCardSize() {
    return this._settingsOpen || this._detailsOpen ? 8 : 5;
  }

  entityId(keyOrEntity) {
    const configured = this.config.entities[keyOrEntity] || keyOrEntity;
    const candidates = Array.isArray(configured) ? configured : [configured];
    return candidates.find((entityId) => this._hass?.states?.[entityId]) || candidates[0];
  }

  state(keyOrEntity) {
    const entityId = this.entityId(keyOrEntity);
    return entityId ? this._hass?.states?.[entityId] : undefined;
  }

  value(key) {
    return this.state(key)?.state;
  }

  isOn(key) {
    return this.value(key) === "on";
  }

  availability(key) {
    const state = this.value(key);
    return state !== undefined && state !== "unavailable" && state !== "unknown";
  }

  statusColor(kind) {
    if (kind === "online") {
      return this.isOn("serviceOnline") && this.isOn("bleConnected") && this.isOn("dataOk") ? "ok" : "error";
    }
    if (kind === "service") return this.isOn("serviceOnline") ? "ok" : "error";
    if (kind === "ble") return this.isOn("bleConnected") ? "ok" : "error";
    if (kind === "data") return this.isOn("dataOk") ? "ok" : "warn";
    return "muted";
  }

  formatState(key, labels = undefined) {
    const state = this.value(key);
    if (!state) return "-";
    return labels?.[state] || state;
  }

  formatSetting() {
    const mode = this.value("heaterMode");
    const setting = this.value("heaterSetting");
    if (!this.availability("heaterSetting")) return "-";
    if (mode === "ventilation") return `Fan: level ${setting}`;
    if (mode === "gear") return `Power: level ${setting}`;
    if (mode === "thermostat") return `Thermostat: ${setting} C`;
    return String(setting);
  }

  async callEntity(entityId, action = "toggle") {
    if (!entityId) return;
    const [domain] = entityId.split(".");
    if (domain === "button") {
      await this._hass.callService("button", "press", { entity_id: entityId });
      return;
    }
    await this._hass.callService(domain, action, { entity_id: entityId });
  }

  async setNumber(entityId, delta) {
    const entity = this.state(entityId);
    if (!entity) return;
    let current = Number(entity.state);
    if (!Number.isFinite(current)) current = Number(entity.attributes.actual_value);
    if (!Number.isFinite(current)) current = Number(entity.attributes.min ?? 0);
    const step = Number(entity.attributes.step || 1);
    const min = Number(entity.attributes.min ?? -Infinity);
    const max = Number(entity.attributes.max ?? Infinity);
    const value = Math.min(max, Math.max(min, current + delta * step));
    const [domain] = entityId.split(".");
    await this._hass.callService(domain, "set_value", { entity_id: entityId, value });
  }

  requestedSettingValue(unit = "") {
    const entity = this.state("requestedSetting");
    if (!entity) return this.value("heaterSetting") || "-";
    const target = entity.state;
    const progress = entity.attributes?.progress;
    return `${target}${unit}${progress ? ` (${progress})` : ""}`;
  }

  chip(icon, label, kind) {
    return `<div class="chip">
      <ha-icon icon="${icon}"></ha-icon>
      <span>${label}</span>
      <i class="dot ${this.statusColor(kind)}"></i>
    </div>`;
  }

  action(icon, label, key, entityKey = key) {
    const active = this.isOn(entityKey);
    return `<button type="button" class="action ${active ? "active" : ""}" data-action="${key}">
      <ha-icon icon="${icon}"></ha-icon>
      <span>${label}</span>
      <i class="mini-dot ${active ? "accent" : "muted"}"></i>
    </button>`;
  }

  row(icon, label, value, expandable = false, open = false) {
    return `<div class="row ${expandable ? "clickable" : ""}" ${expandable ? 'data-action="toggle-settings"' : ""}>
      <ha-icon icon="${icon}"></ha-icon>
      <span>${label}</span>
      <b>${value}</b>
      ${expandable ? `<ha-icon class="chevron" icon="mdi:chevron-${open ? "up" : "down"}"></ha-icon>` : ""}
    </div>`;
  }

  isHeatingContext() {
    const mode = this.value("heaterMode");
    return mode === "gear" || mode === "thermostat" || this.isOn("heating");
  }

  modeSettings() {
    const mode = this.value("heaterMode");
    const auto = this.isOn("autoMode");
    if (auto) return this.autoSettings();
    if (mode === "ventilation") return this.ventilationSettings();
    if (this.isHeatingContext()) return this.heatingSettings();
    return `<div class="settings-panel muted-panel">Turn on heating or ventilation to adjust output.</div>`;
  }

  settingLabel(icon, label) {
    return `<span class="setting-label"><ha-icon icon="${icon}"></ha-icon>${label}</span>`;
  }

  stepper(icon, label, value, downAction, upAction) {
    return `<div class="setting-line">
      ${this.settingLabel(icon, label)}
      <button type="button" class="small" data-action="${downAction}"><ha-icon icon="mdi:minus"></ha-icon></button>
      <b>${value}</b>
      <button type="button" class="small" data-action="${upAction}"><ha-icon icon="mdi:plus"></ha-icon></button>
    </div>`;
  }

  highlandToggle() {
    const active = this.isOn("highland");
    return `<div class="setting-line toggle-line">
      ${this.settingLabel("mdi:image-filter-hdr", "Highland")}
      <button type="button" class="switch-toggle ${active ? "on" : ""}" data-action="highland" aria-pressed="${active ? "true" : "false"}">
        <span></span>
      </button>
    </div>`;
  }

  ventilationSettings() {
    return `<div class="settings-panel">
      ${this.stepper("mdi:fan", "Fan", this.requestedSettingValue(), "down", "up")}
      ${this.highlandToggle()}
    </div>`;
  }

  heatingSettings() {
    const mode = this.value("heaterMode");
    const label = mode === "thermostat" ? "Heating temperature" : "Heating power";
    const value = mode === "thermostat" ? this.requestedSettingValue(" C") : this.requestedSettingValue();
    return `<div class="settings-panel">
      ${this.stepper(mode === "thermostat" ? "mdi:thermometer" : "mdi:fire", label, value, "down", "up")}
      <div class="setting-line compact">
        ${this.settingLabel("mdi:tune-variant", "Control mode")}
        <button type="button" class="mode ${this.value("heaterMode") === "gear" ? "selected" : ""}" data-action="gear">Power</button>
        <button type="button" class="mode ${this.value("heaterMode") === "thermostat" ? "selected" : ""}" data-action="thermostat">Thermostat</button>
      </div>
      ${this.highlandToggle()}
    </div>`;
  }

  autoSettings() {
    const target = this.value("targetTemperature") || "-";
    const hyst = this.value("hysteresis") || "-";
    return `<div class="settings-panel">
      ${this.stepper("mdi:fire", "Heating power", this.requestedSettingValue(), "down", "up")}
      ${this.stepper("mdi:thermometer", "Target temperature", `${target} C`, "target-down", "target-up")}
      ${this.stepper("mdi:delta", "Hysteresis", `${hyst} C`, "hysteresis-down", "hysteresis-up")}
      ${this.highlandToggle()}
    </div>`;
  }

  indicator(icon, label, key) {
    const active = this.isOn(key);
    return `<div class="indicator ${active ? "active" : ""}">
      <ha-icon icon="${icon}"></ha-icon>
      <span>${label}</span>
    </div>`;
  }

  details() {
    const age = this.value("lastSuccessAge") || this.value("last_success_age") || "-";
    const errorCode = Number(this.value("errorCode") || 0);
    const errorMessage = this.value("errorMessage");
    const heaterError = errorCode > 0
      ? `E-${String(errorCode).padStart(2, "0")} - ${errorMessage || "Unknown error"}`
      : "None";
    return `<div class="details">
      <div><span>Voltage</span><b>${this.value("voltage") || "-"} V</b></div>
      <div><span>Protocol</span><b>${this.value("protocolVersion") || "-"}</b></div>
      <div><span>Heater error</span><b>${heaterError}</b></div>
      <div><span>Last data</span><b>${age}${age === "-" ? "" : " s"}</b></div>
      <div><span>Failures</span><b>${this.value("consecutiveFailures") || this.value("consecutive_failures") || "0"}</b></div>
      <div><span>Last error</span><b>${this.value("lastError") || this.value("last_error") || "-"}</b></div>
    </div>`;
  }

  render() {
    if (!this._hass || !this.config) return;
    const html = `
      <ha-card>
        <div class="card">
          <div class="chips">
            ${this.chip("mdi:bluetooth", "BLE", "ble")}
            ${this.chip("mdi:server-network", "Service", "service")}
            ${this.chip("mdi:database-check", "Data", "data")}
            ${this.chip("mdi:check-network-outline", "Online", "online")}
          </div>
          <div class="actions">
            ${this.action("mdi:fire", "Heating", "heating")}
            ${this.action("mdi:autorenew", "Auto", "autoMode")}
            ${this.action("mdi:fan", "Ventilation", "ventilation")}
          </div>
          <section class="panel">
            ${this.row("mdi:information-outline", "Heater state", this.formatState("heaterState", STATE_LABELS))}
            ${this.row("mdi:tune-variant", "Mode", this.formatState("heaterMode", MODE_LABELS))}
            ${this.row("mdi:cog-outline", "Settings", this.formatSetting(), true, this._settingsOpen)}
            ${this._settingsOpen ? this.modeSettings() : ""}
            ${this.row("mdi:radiator", "Body", `${this.value("bodyTemperature") || "-"} °C`)}
            ${this.row("mdi:home-thermometer-outline", "Ambient", `${this.value("ambientTemperature") || "-"} °C`)}
            <div class="indicators">
              ${this.indicator("mdi:fire", "Running", "running")}
              ${this.indicator("mdi:fan", "Cooldown", "cooldown")}
              ${this.indicator("mdi:fire-alert", "Preheat", "preheating")}
            </div>
          </section>
          <section class="panel details-panel">
            <div class="row clickable" data-action="toggle-details">
              <ha-icon icon="mdi:format-list-bulleted"></ha-icon>
              <span>Details</span>
              <b></b>
              <ha-icon class="chevron" icon="mdi:chevron-${this._detailsOpen ? "up" : "down"}"></ha-icon>
            </div>
            ${this._detailsOpen ? this.details() : ""}
          </section>
        </div>
      </ha-card>
      <style>${this.styles()}</style>`;
    this.innerHTML = html;
  }

  async handleAction(action) {
    const e = (key) => this.entityId(key);
    if (action === "toggle-settings") {
      this._settingsOpen = !this._settingsOpen;
      this.render();
      return;
    }
    if (action === "toggle-details") {
      this._detailsOpen = !this._detailsOpen;
      this.render();
      return;
    }

    Promise.resolve().then(async () => {
      if (action === "heating") await this.callEntity(e("heating"), this.isOn("heating") ? "turn_off" : "turn_on");
      else if (action === "autoMode") await this.callEntity(e("autoMode"), "toggle");
      else if (action === "ventilation") await this.callEntity(e("ventilation"), this.isOn("ventilation") ? "turn_off" : "turn_on");
      else if (action === "highland") await this.callEntity(e("highland"), this.isOn("highland") ? "turn_off" : "turn_on");
      else if (action === "gear") await this.callEntity(e("gearMode"));
      else if (action === "thermostat") await this.callEntity(e("thermostatMode"));
      else if (action === "up") await (this.state("requestedSetting") ? this.setNumber(e("requestedSetting"), 1) : this.callEntity(e("up")));
      else if (action === "down") await (this.state("requestedSetting") ? this.setNumber(e("requestedSetting"), -1) : this.callEntity(e("down")));
      else if (action === "target-up") await this.setNumber(e("targetTemperature"), 1);
      else if (action === "target-down") await this.setNumber(e("targetTemperature"), -1);
      else if (action === "hysteresis-up") await this.setNumber(e("hysteresis"), 1);
      else if (action === "hysteresis-down") await this.setNumber(e("hysteresis"), -1);
    }).catch((err) => console.error("HCalory card action failed", action, err));
  }

  styles() {
    return `
      ha-card { background: linear-gradient(145deg, rgba(40, 40, 40, .95), rgba(25, 25, 25, .9)); color: var(--primary-text-color); border-radius: 12px; overflow: hidden; font-size: 16px; }
      .card { padding: 10px; display: block; }
      .card > * + * { margin-top: 15px; }
      .chips { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; }
      .chip { min-height: 34px; display: flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid rgba(255,255,255,.12); border-radius: 8px; background: rgba(255,255,255,.035); font-size: 12px; font-weight: 300; }
      ha-icon { --mdc-icon-size: 20px; color: rgba(255,255,255,.88); }
      .chip ha-icon { --mdc-icon-size: 17px; color: rgba(255,255,255,.72); }
      .dot, .mini-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; background: rgba(255,255,255,.25); }
      .dot.ok { background: #53c66b; } .dot.warn { background: #d8b24a; } .dot.error { background: #e05a5a; }
      .mini-dot.accent { background: #6eb9bd; } .mini-dot.muted { background: rgba(255,255,255,.25); }
      .actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
      button { font: inherit; color: inherit; cursor: pointer; }
      .action { min-height: 58px; border: 1px solid rgba(255,255,255,.12); border-radius: 8px; background: rgba(255,255,255,.035); display: grid; place-items: center; gap: 3px; padding: 7px 4px; }
      .action.active { border-color: rgba(110,185,189,.9); box-shadow: inset 0 0 0 1px rgba(110,185,189,.25); }
      .action span { font-size: 13px; font-weight: 500; }
      .panel { border: 1px solid rgba(255,255,255,.1); border-radius: 8px; background: rgba(0,0,0,.12); overflow: hidden; }
      .row { min-height: 38px; display: grid; grid-template-columns: 30px 1fr auto 22px; align-items: center; gap: 8px; padding: 0 12px; border-bottom: 1px solid rgba(255,255,255,.07); }
      .row:last-child { border-bottom: 0; }
      .row span { font-size: 14px; font-weight: 500; color: rgba(255,255,255,.78); }
      .row b { font-size: 14px; font-weight: 300; color: rgba(255,255,255,.84); justify-self: end; }
      .row .chevron { --mdc-icon-size: 20px; color: rgba(255,255,255,.55); }
      .clickable { cursor: pointer; }
      .settings-panel { margin: 8px; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; background: rgba(255,255,255,.025); overflow: hidden; }
      .muted-panel { padding: 12px; color: rgba(255,255,255,.62); font-size: 13px; }
      .setting-line { min-height: 40px; display: grid; grid-template-columns: minmax(0, 1fr) 40px minmax(34px, auto) 40px; align-items: center; gap: 8px; padding: 5px 10px; border-bottom: 1px solid rgba(255,255,255,.06); }
      .setting-line:last-child { border-bottom: 0; }
      .setting-line.compact { grid-template-columns: minmax(0, 1fr) auto auto; }
      .setting-line.toggle-line { grid-template-columns: minmax(0, 1fr) auto; }
      .setting-line span { font-size: 13px; color: rgba(255,255,255,.72); }
      .setting-line b { min-width: 40px; text-align: center; justify-self: center; font-size: 14px; font-weight: 600; color: rgba(255,255,255,.88); }
      .setting-label { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
      .setting-label ha-icon { --mdc-icon-size: 18px; color: rgba(255,255,255,.62); flex: 0 0 auto; }
      .small, .mode { min-height: 31px; border-radius: 7px; border: 1px solid rgba(255,255,255,.12); background: rgba(255,255,255,.035); }
      .small ha-icon { --mdc-icon-size: 18px; }
      .mode { padding: 0 12px; font-size: 13px; }
      .mode.selected { border-color: rgba(110,185,189,.9); color: rgba(255,255,255,.95); }
      .switch-toggle { width: 46px; height: 24px; border: 1px solid rgba(255,255,255,.2); border-radius: 999px; background: rgba(255,255,255,.14); padding: 2px; display: flex; align-items: center; transition: background .16s ease, border-color .16s ease; }
      .switch-toggle span { width: 18px; height: 18px; border-radius: 50%; background: rgba(255,255,255,.86); transform: translateX(0); transition: transform .16s ease; }
      .switch-toggle.on { background: rgba(110,185,189,.45); border-color: rgba(110,185,189,.9); }
      .switch-toggle.on span { transform: translateX(20px); background: #fff; }
      .indicators { display: grid; grid-template-columns: repeat(3, 1fr); min-height: 68px; }
      .indicator { display: grid; place-items: center; align-content: center; gap: 4px; border-top: 1px solid rgba(255,255,255,.07); border-right: 1px solid rgba(255,255,255,.07); color: rgba(255,255,255,.62); }
      .indicator:last-child { border-right: 0; }
      .indicator span { font-size: 12px; font-weight: 500; }
      .indicator ha-icon { --mdc-icon-size: 28px; }
      .indicator::after { content: ""; width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,.25); }
      .indicator.active ha-icon { color: #6eb9bd; }
      .indicator.active span { color: rgba(255,255,255,.95); }
      .indicator.active::after { background: #6eb9bd; }
      .details-panel .row { border-bottom: 0; }
      .details { border-top: 1px solid rgba(255,255,255,.07); padding: 4px 12px 10px; }
      .details div { min-height: 30px; display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: 13px; color: rgba(255,255,255,.68); }
      .details b { color: rgba(255,255,255,.84); font-weight: 500; text-align: right; }
    `;
  }
}

customElements.define("hcalory-card", HCaloryCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hcalory-card",
  name: "HCalory card",
  description: "Compact HCalory heater control card",
  preview: false,
});

