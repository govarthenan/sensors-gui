/*
 * The alerts view: every reading that left the scale its spec publishes.
 *
 * Gova, 2026-09-23: "Log an alert on a seperate screen." The log is kept by
 * the Python service (`web/alerts.py`), on every pass, so an alert is caught
 * whatever view is on screen. This view only shows it.
 *
 * The ceiling is the spec's `high` and the floor its `low`. A channel that
 * publishes neither is not watched, and the view lists which channels are, so
 * a reader knows what an empty log means.
 */

import { STATES, formatValue, scaleLabel, setText } from "../widgets.js";
import { attachTooltip } from "../tooltip.js";
import { card } from "./parts.js";

const COLUMNS = ["", "Channel", "What", "Limit", "Furthest", "Past by", "Last", "Started", "Lasted", "Passes"];
const SUMMARY_COLUMNS = ["Channel", "What", "Limit", "Alerts", "Furthest", "Past by", "Last seen"];

/**
 * Return the distance past the limit, with enough decimals to be seen.
 *
 * A limit of 5662.016 MHz and a reading of 5676.627 MHz both read "5.7 GHz"
 * in the unit's own format, so the difference is shown on its own, scaled
 * for itself: "+14.6 MHz".
 */
function pastBy(alert, spec) {
  const gap = Math.abs(alert.peak - alert.limit);
  return `${alert.kind === "above ceiling" ? "+" : "−"}${formatValue(gap, spec)}`;
}

/** Return a time of day, from seconds since the epoch. */
function clock(seconds) {
  return new Date(seconds * 1000).toLocaleTimeString();
}

/** Return a duration as short text: 4 s, 2 min 5 s, 1 h 3 min. */
function lasted(seconds) {
  const whole = Math.max(0, Math.round(seconds));
  if (whole < 60) return `${whole} s`;
  if (whole < 3600) return `${Math.floor(whole / 60)} min ${whole % 60} s`;
  return `${Math.floor(whole / 3600)} h ${Math.floor((whole % 3600) / 60)} min`;
}

/** Fetch the log from the service. */
async function fetchLog() {
  const response = await fetch("/api/alerts");
  return response.json();
}

/**
 * Build the alerts view.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the view
 */
export function alertsView(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "view view-alerts";

  const log = card("Alert log", "readings outside their published scale · in memory, newest first");
  log.element.classList.add("card-full");
  log.body.innerHTML = `
    <p class="alerts-count">—</p>
    <p class="absent">
      An alert opens when a reading goes above its ceiling or below its floor, and closes when it comes back.
      A return within 5 s reopens the same alert. The log is kept in memory only: a restart empties it, and
      nothing is written to disk. The newest 500 alerts are kept.
    </p>
    <h4 class="alerts-sub">By channel</h4>
    <table class="alerts-table alerts-summary"><thead><tr></tr></thead><tbody></tbody></table>
    <h4 class="alerts-sub">Every alert, newest first</h4>
    <table class="alerts-table alerts-every"><thead><tr></tr></thead><tbody></tbody></table>
    <p class="alerts-empty absent">No reading has left its scale since the application started.</p>`;
  for (const [selector, names] of [
    [".alerts-every", COLUMNS],
    [".alerts-summary", SUMMARY_COLUMNS],
  ]) {
    const head = log.body.querySelector(`${selector} thead tr`);
    for (const name of names) {
      const cell = document.createElement("th");
      cell.textContent = name;
      head.appendChild(cell);
    }
  }
  const body = log.body.querySelector(".alerts-every tbody");
  const summaryBody = log.body.querySelector(".alerts-summary tbody");
  const count = log.body.querySelector(".alerts-count");
  const empty = log.body.querySelector(".alerts-empty");

  // --- what is watched, so an empty log can be read ---------------------------
  const watched = catalogue.where(
    (channel) => !channel.hidden && ((channel.high ?? null) !== null || (channel.low ?? null) !== null),
  );
  const scope = card("What is watched", `${watched.length} channels publish a scale`);
  scope.element.classList.add("card-full");
  const list = document.createElement("div");
  list.className = "alerts-watched";
  for (const channel of watched) {
    const item = document.createElement("span");
    item.className = "alerts-watched-item";
    const floor = (channel.low ?? null) === null ? "—" : scaleLabel(channel.low, channel);
    const ceiling = (channel.high ?? null) === null ? "—" : scaleLabel(channel.high, channel);
    item.innerHTML = "<b></b><em></em>";
    item.querySelector("b").textContent = channel.label;
    item.querySelector("em").textContent = `${floor} to ${ceiling} ${channel.symbol}`.trim();
    attachTooltip(item, channel, stream);
    list.appendChild(item);
  }
  const note = document.createElement("p");
  note.className = "absent";
  note.textContent =
    "A channel with no published scale is not watched: the application does not invent a limit. " +
    "Tctl, for example, publishes none. A published critical threshold is a different thing, and is shown " +
    "by the state colour on every view.";
  scope.body.append(list, note);

  element.append(log.element, scope.element);

  let seen = null;
  let busy = false;

  /** Draw one row per channel and kind: how often, and how far at worst. */
  function renderSummary(alerts) {
    summaryBody.replaceChildren();
    const groups = new Map();
    for (const alert of alerts) {
      const id = `${alert.key}|${alert.kind}`;
      const group = groups.get(id) ?? { first: alert, count: 0, worst: alert, last: alert.started };
      group.count += 1;
      if (Math.abs(alert.peak - alert.limit) > Math.abs(group.worst.peak - group.worst.limit)) group.worst = alert;
      group.last = Math.max(group.last, alert.ended ?? alert.started);
      groups.set(id, group);
    }
    const ordered = [...groups.values()].sort((a, b) => b.count - a.count);
    for (const group of ordered) {
      const alert = group.worst;
      const spec = { unit: alert.unit, symbol: alert.symbol, decimals: alert.decimals };
      const row = document.createElement("tr");
      for (const text of [
        alert.label,
        alert.kind,
        formatValue(alert.limit, spec),
        String(group.count),
        formatValue(alert.peak, spec),
        pastBy(alert, spec),
        clock(group.last),
      ]) {
        const cell = document.createElement("td");
        cell.textContent = text;
        row.appendChild(cell);
      }
      const channel = catalogue.channels.find((candidate) => candidate.key === alert.key);
      if (channel) attachTooltip(row.children[0], channel, stream);
      summaryBody.appendChild(row);
    }
  }

  /** Draw the rows from one copy of the log. */
  function render(data) {
    renderSummary(data.alerts);
    body.replaceChildren();
    empty.hidden = data.alerts.length > 0;
    setText(
      count,
      `${data.open} open now · ${data.total} logged since the application started` +
        (data.total > data.alerts.length ? ` · the oldest ${data.total - data.alerts.length} are no longer kept` : ""),
    );
    const now = Date.now() / 1000;
    for (const alert of data.alerts) {
      const row = document.createElement("tr");
      row.dataset.state = alert.ended === null ? "over" : "closed";
      const spec = { unit: alert.unit, symbol: alert.symbol, decimals: alert.decimals };
      const icon = alert.kind === "above ceiling" ? STATES.over.icon : STATES.under.icon;
      const cells = [
        alert.ended === null ? `${icon} open` : "closed",
        alert.label,
        alert.kind,
        formatValue(alert.limit, spec),
        formatValue(alert.peak, spec),
        pastBy(alert, spec),
        formatValue(alert.last, spec),
        clock(alert.started),
        lasted((alert.ended ?? now) - alert.started) + (alert.ended === null ? " so far" : ""),
        String(alert.passes),
      ];
      for (const text of cells) {
        const cell = document.createElement("td");
        cell.textContent = text;
        row.appendChild(cell);
      }
      const channel = catalogue.channels.find((candidate) => candidate.key === alert.key);
      if (channel) attachTooltip(row.children[1], channel, stream);
      body.appendChild(row);
    }
  }

  return {
    element,
    async update() {
      // Fetch when the counts change, and every frame while an alert is open,
      // so its "furthest" and "lasted" stay live. Never two fetches at once.
      const counts = stream.latest?.alerts ?? { open: 0, total: 0 };
      const key = `${counts.open}/${counts.total}`;
      if (busy || (key === seen && counts.open === 0)) return;
      busy = true;
      try {
        render(await fetchLog());
        seen = key;
      } finally {
        busy = false;
      }
    },
  };
}
