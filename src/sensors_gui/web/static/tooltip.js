/*
 * The tooltip panel: what a value is, where it comes from, and how far to
 * trust it.
 *
 * `docs/gui-goal.md` section 4.2 lists five things hovering any value must
 * show. `explain` builds them from the catalogue and the newest frame, with
 * no page, so `tests/test_web_tooltip.py` runs the real file in node:
 *
 *   1. what it measures           the description, written in Python
 *   2. where it is read from      the library or driver, and the call or path
 *   3. how it differs from its neighbours
 *   4. the safe range, and where the value sits in it
 *   5. the read interval, and the age of the value
 *
 * The text of 1 and 3 comes from `src/sensors_gui/descriptions.py`, where
 * every sentence names its source. Nothing is written here about the
 * hardware; this file only arranges it. A channel with no description says
 * so, and nothing is guessed.
 *
 * One panel serves the whole page. It follows the frames while it is open, so
 * the value and its age in it are live.
 */

import { STATES, colourOf, formatValue, scaleLabel, scaleTop, setText, stateOf } from "./widgets.js";

/** How each source reads the machine, in words a person knows. */
const SOURCE_NAMES = {
  nvidia: "NVML, the NVIDIA driver's library",
  privileged: "sensors-guid, the root helper, over /run/sensors-gui.sock",
  system: "psutil and /proc",
  power_supply: "the kernel's power_supply class",
  proc: "the kernel, through /proc",
  derived: "made in this page from other channels, not read from the machine",
};

/** Return a number of seconds as short text: 0.5, 2, 0.25. */
function seconds(value) {
  return String(Number(value.toFixed(2)));
}

/** Return the ends of a scale as one phrase: "0 to 480 W", "0 to 24.0 GiB". */
function scalePhrase(low, top, channel) {
  const from = scaleLabel(low, channel);
  const to = scaleLabel(top, channel);
  // `scaleLabel` keeps a prefixed unit ("24.0 GiB") and drops a plain one.
  return to.includes(" ") ? `${from} to ${to}` : `${from} to ${to} ${channel.symbol}`.trimEnd();
}

/** Part 2: the library or driver, and the call or path. */
function whereFrom(channel) {
  const call = channel.description?.call;
  if (channel.source === "hwmon") {
    const driver = channel.key.split(":")[1]?.split("@")[0] ?? "hwmon";
    return `the ${driver} kernel driver, ${channel.origin}`;
  }
  const name = SOURCE_NAMES[channel.source] ?? channel.source;
  return `${name}: ${call ?? channel.origin}`;
}

/** Part 4: the safe range, and where the value sits in it. */
function range(channel, value) {
  const { warn, critical } = channel;
  const hasWarn = warn !== null && warn !== undefined;
  const hasCritical = critical !== null && critical !== undefined;
  if (hasWarn || hasCritical) {
    const named = [];
    if (hasWarn) named.push(`warning at ${formatValue(warn, channel)}`);
    if (hasCritical) named.push(`critical at ${formatValue(critical, channel)}`);
    let text = `${named.join(", ")}, published by the hardware.`;
    text = text.charAt(0).toUpperCase() + text.slice(1);
    if (value === null || value === undefined) return text;
    const ceiling = channel.high ?? null;
    if (ceiling !== null && ceiling !== critical && value > ceiling) {
      return `${text} Now ${formatValue(value - ceiling, channel)} above the ceiling of the scale.`;
    }
    const first = hasWarn ? warn : critical;
    const word = hasWarn ? "warning" : "critical threshold";
    return value < first
      ? `${text} Now ${formatValue(first - value, channel)} below the ${word}.`
      : `${text} Now past the ${word}.`;
  }
  const top = scaleTop(channel);
  if (channel.low !== null && channel.low !== undefined && top !== null) {
    let text = `Scale ${scalePhrase(channel.low, top, channel)}, from the spec.`;
    if (value !== null && value !== undefined && value > top) {
      text += ` Now ${formatValue(value - top, channel)} above the ceiling; the reading is in the alert log.`;
    } else if (value !== null && value !== undefined && value < channel.low) {
      text += ` Now ${formatValue(channel.low - value, channel)} below the floor; the reading is in the alert log.`;
    } else if (value !== null && value !== undefined && top > channel.low) {
      const share = Math.round(((value - channel.low) / (top - channel.low)) * 100);
      text += ` Now at ${share} % of the scale.`;
    }
    text += " The hardware publishes no threshold, so no state is judged.";
    if (channel.alert_margin) {
      text += ` The alert log records a reading only past ${Math.round((1 + channel.alert_margin) * 100)} % of the ceiling or below ${Math.round((1 - channel.alert_margin) * 100)} % of the floor (Gova, 2026-09-23).`;
    }
    return text;
  }
  return "The hardware publishes no scale and no threshold, so the value is shown and not judged.";
}

/** Part 5: how often the channel is read, and how old this value is. */
function readNote(channel, extra, hz) {
  const how =
    channel.min_interval > 0
      ? `Read at most once every ${seconds(channel.min_interval)} s; between reads the last value is kept.`
      : `Read on every pass, every ${seconds(1 / hz)} s.`;
  if (extra.error) return `${how} Not read now: ${extra.error}.`;
  if (extra.age !== undefined && extra.age !== null) return `${how} The value is ${extra.age.toFixed(1)} s old.`;
  return `${how} The value is from this pass.`;
}

/**
 * Return the five parts of the tooltip for one channel, as text.
 *
 * @param {object} channel the channel, as the catalogue sends it
 * @param {number|null} value the newest value
 * @param {{error?: string, age?: number}} extra what the frame said beyond the value
 * @param {number} hz the sample rate now
 * @returns {object} the parts, each one a string, and the list of sources
 */
export function explain(channel, value, extra = {}, hz = 2) {
  if (channel.missing) return explainMissing(channel);
  const description = channel.description ?? null;
  return {
    label: channel.label,
    value: formatValue(value, channel),
    state: stateOf(value, channel, extra),
    measures:
      description?.measures ??
      "This channel is not described yet. Its group is described at a later checkpoint; nothing is guessed.",
    neighbours: description?.neighbours ?? "",
    where: whereFrom(channel),
    range: range(channel, value),
    read: readNote(channel, extra, hz),
    sources: description?.sources ?? [],
  };
}

/**
 * Return the parts for a value the application does not show.
 *
 * `docs/gui-goal.md` 4.2: a value that cannot be read is shown with its
 * reason, never as a silent gap. The entry comes from the catalogue's
 * `unreachable` or `not_collected` list, written in Python with its sources.
 *
 * @param {{label: string, reason: string, sources: string[], missing: string}} entry
 * @returns {object} the same parts as `explain`
 */
export function explainMissing(entry) {
  const unreachable = entry.missing === "unreachable";
  return {
    label: entry.label,
    value: unreachable ? "not readable" : "not collected",
    state: "unavailable",
    measures: entry.reason,
    neighbours: "",
    where: unreachable ? "No route that only reads exists on this machine." : "Not read by this application.",
    range: "",
    read: "Never read.",
    sources: entry.sources ?? [],
  };
}

// --- the panel ----------------------------------------------------------------

const SECTIONS = [
  ["measures", "What it measures"],
  ["neighbours", "Beside it"],
  ["where", "Where it is read from"],
  ["range", "Safe range"],
  ["read", "Read"],
];

/** The one panel on the page. It is built the first time it is needed. */
class Panel {
  constructor() {
    this.element = document.createElement("aside");
    this.element.className = "tip";
    this.element.hidden = true;
    this.element.setAttribute("role", "tooltip");
    this.element.innerHTML = `
      <div class="tip-head">
        <span class="tip-label"></span>
        <span class="tip-value"></span>
        <span class="tip-state"><i></i><span></span></span>
      </div>
      <dl class="tip-body"></dl>
      <div class="tip-sources"></div>`;
    this.label = this.element.querySelector(".tip-label");
    this.value = this.element.querySelector(".tip-value");
    this.icon = this.element.querySelector(".tip-state i");
    this.word = this.element.querySelector(".tip-state span");
    this.sources = this.element.querySelector(".tip-sources");
    this.parts = new Map();
    const body = this.element.querySelector(".tip-body");
    for (const [key, title] of SECTIONS) {
      const term = document.createElement("dt");
      term.textContent = title;
      const detail = document.createElement("dd");
      detail.className = `tip-${key}`;
      body.append(term, detail);
      this.parts.set(key, { term, detail });
    }
    document.body.appendChild(this.element);
    this.anchor = null;
    this.channel = null;
    this.stream = null;
  }

  /** Open the panel beside `anchor`, for one channel. */
  open(anchor, channel, stream) {
    this.anchor = anchor;
    this.channel = channel;
    this.stream = stream;
    this.element.hidden = false;
    this.refresh();
    this.place();
  }

  /** Close the panel, but only if it still belongs to `anchor`. */
  close(anchor) {
    if (anchor !== this.anchor) return;
    this.anchor = null;
    this.element.hidden = true;
  }

  /** Write the newest value into the open panel. Called on every frame. */
  refresh() {
    if (this.anchor === null) return;
    const { channel, stream } = this;
    const hz = stream.latest?.hz ?? stream.catalogue.hz;
    const parts = explain(channel, stream.value(channel), stream.extra(channel), hz);
    setText(this.label, parts.label);
    setText(this.value, parts.value);
    setText(this.icon, STATES[parts.state].icon);
    this.icon.style.color = colourOf(parts.state);
    // "normal" is a judgement, and the hardware made none where it publishes
    // no threshold. The summary's rule, kept here: say so, do not judge.
    const judged = (channel.warn ?? null) !== null || (channel.critical ?? null) !== null;
    setText(this.word, parts.state === "normal" && !judged ? "not judged" : STATES[parts.state].word);
    for (const [key, { term, detail }] of this.parts) {
      setText(detail, parts[key]);
      term.hidden = parts[key] === "";
      detail.hidden = parts[key] === "";
    }
    setText(this.sources, parts.sources.length ? `Sources: ${parts.sources.join(" · ")}` : "");
  }

  /** Put the panel beside the anchor, inside the window. */
  place() {
    const box = this.anchor.getBoundingClientRect();
    const own = this.element.getBoundingClientRect();
    const margin = 12;
    let left = box.right + margin;
    if (left + own.width > window.innerWidth - margin) left = box.left - own.width - margin;
    if (left < margin) left = Math.min(box.left, window.innerWidth - own.width - margin);
    let top = box.top;
    if (top + own.height > window.innerHeight - margin) top = window.innerHeight - own.height - margin;
    this.element.style.left = `${Math.max(left, margin)}px`;
    this.element.style.top = `${Math.max(top, margin)}px`;
  }
}

let panel = null;

/** Return the one panel, building it on first use. */
function thePanel() {
  panel ??= new Panel();
  return panel;
}

/**
 * Give an element the tooltip of one channel, on hover and on keyboard focus.
 *
 * The dataviz skill: the same details on focus as on hover, so the element
 * takes a place in the tab order.
 *
 * A line whose channel changes, such as "the hottest sensor", passes a
 * function instead of a channel; it is asked each time the panel opens.
 *
 * @param {HTMLElement|SVGElement} element what the pointer or the focus lands on
 * @param {object|function(): (object|null)} channel the channel it shows, or a function that returns it
 * @param {import("./stream.js").Stream} stream the live frames
 */
export function attachTooltip(element, channel, stream) {
  if (!channel) return;
  element.classList.add("has-tip");
  // A native `title` would open a second box over the panel.
  element.removeAttribute("title");
  if (!element.hasAttribute("tabindex")) element.setAttribute("tabindex", "0");
  const open = () => {
    const shown = typeof channel === "function" ? channel() : channel;
    if (shown) thePanel().open(element, shown, stream);
  };
  const close = () => thePanel().close(element);
  element.addEventListener("pointerenter", open);
  element.addEventListener("pointerleave", close);
  element.addEventListener("focus", open);
  element.addEventListener("blur", close);
}

/**
 * Open the panel for one channel beside `anchor`, from code and not an event.
 *
 * For a display that draws many values on one canvas, such as `CoreBars`:
 * the canvas knows which column is under the pointer, and the anchor is any
 * object with `getBoundingClientRect`.
 *
 * @param {{getBoundingClientRect: function(): object}} anchor where the panel goes
 * @param {object} channel the channel to explain
 * @param {import("./stream.js").Stream} stream the live frames
 */
export function openTooltip(anchor, channel, stream) {
  if (channel) thePanel().open(anchor, channel, stream);
}

/** Close the panel, if `anchor` opened it. */
export function closeTooltip(anchor) {
  panel?.close(anchor);
}

/** Keep the open panel live. The shell calls this on every frame. */
export function refreshTooltip() {
  panel?.refresh();
}
