/*
 * The widget set.
 *
 * Four things, and the rules they keep. The rules come from the `dataviz`
 * skill, which `docs/gui-goal.md` section 4.4 tells this project to follow.
 *
 *   formatValue  the same text the Python model produces, so the GUI and the
 *                terminal screen never disagree about a number
 *   stateOf      value + spec -> one of five states, and one colour each
 *   Meter        a value against a real limit. Gova chose this form on
 *                2026-09-22, over a dial; ADR 0012.
 *   Trace        a line over the ring buffer, with a stable axis
 *   Sparkline    the same line, small, inside a row
 *
 * Three rules are kept everywhere:
 *
 *   1. A meter is drawn ONLY where the spec carries a real scale. 66 of the
 *      175 channels on this machine do. The rest get a number and a line,
 *      because a scale that is invented is a lie.
 *   2. A vertical axis never runs from zero to "whatever it is now". It keeps
 *      a floor, so a quarter-degree wobble does not look violent, and it only
 *      moves when the data leaves it.
 *   3. Colour never carries a state on its own. Every state has an icon and a
 *      word beside it, because the validator says warning, serious and
 *      critical are not far enough apart for a colour-blind reader.
 */

// --- formatting --------------------------------------------------------------

const SI_PREFIXES = ["", "k", "M", "G", "T", "P"];
const BINARY_PREFIXES = ["", "Ki", "Mi", "Gi", "Ti", "Pi"];

// Which units grow a prefix, and on which step. This mirrors _UNIT_SCALING in
// src/sensors_gui/model.py.
const UNIT_SCALING = {
  hertz: "si",
  joule: "si",
  byte_per_second: "si",
  byte: "binary",
};

// Python's format and `Number.toFixed` agree on every number except an exact
// tie: Python rounds it to the even digit and `toFixed` rounds it away from
// zero, so 41.25 became "41.2" in one and "41.3" in the other.
// `tests/test_web_formatting.py` caught it, and it is corrected here.
//
// `Intl.NumberFormat` with `halfEven` does not fix it, because it rounds the
// shortest decimal form of the number rather than the number: it turns -40.15
// into -40.2, while the double actually holds -40.149999999999998579, which
// Python rounds to -40.1. So the tie is found in the exact expansion, and only
// then is the rule applied.

/** Return true when `value` sits exactly half way at `decimals` places. */
function isTie(value, decimals) {
  const expanded = Math.abs(value).toFixed(Math.min(decimals + 25, 100));
  const fraction = expanded.split(".")[1] ?? "";
  const rest = fraction.slice(decimals);
  return rest.startsWith("5") && /^0*$/.test(rest.slice(1));
}

/**
 * Return `value` with `decimals` decimal places, rounding a tie to the even digit.
 *
 * Away from a tie this is `toFixed`, which is already correctly rounded from
 * the exact value of the double.
 *
 * @param {number} value the number
 * @param {number} decimals how many decimal places
 * @returns {string} the number as text, with no thousands separator
 */
export function fixed(value, decimals) {
  if (!Number.isFinite(value)) return String(value);
  if (!isTie(value, decimals)) return value.toFixed(decimals);

  const sign = value < 0 ? "-" : "";
  const expanded = Math.abs(value).toFixed(Math.min(decimals + 25, 100));
  const [whole, fraction = ""] = expanded.split(".");
  const keptDigits = whole + fraction.slice(0, decimals);
  let kept = BigInt(keptDigits);
  if (kept % 2n !== 0n) kept += 1n;

  const text = kept.toString().padStart(decimals + 1, "0");
  const cut = text.length - decimals;
  return decimals === 0 ? `${sign}${text}` : `${sign}${text.slice(0, cut)}.${text.slice(cut)}`;
}

/**
 * Return the value as text with its unit, exactly as the Python model does.
 *
 * `tests/test_web_formatting.py` runs this function in node against the
 * Python one for the same inputs, so the two cannot drift apart.
 *
 * @param {number|null} value the value in the base unit
 * @param {{unit: string, decimals: number, symbol: string}} spec the channel
 * @returns {string} the text, or an em dash when there is no value
 */
export function formatValue(value, spec) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const scaling = UNIT_SCALING[spec.unit] ?? null;
  let scaled = value;
  let prefix = "";
  if (scaling !== null) {
    const step = scaling === "si" ? 1000 : 1024;
    const prefixes = scaling === "si" ? SI_PREFIXES : BINARY_PREFIXES;
    let index = 0;
    while (Math.abs(scaled) >= step && index < prefixes.length - 1) {
      scaled /= step;
      index += 1;
    }
    prefix = prefixes[index];
  }
  const decimals = scaling !== null ? 1 : spec.decimals;
  return `${fixed(scaled, decimals)} ${prefix}${spec.symbol}`.trimEnd();
}

/**
 * Return a short label for one end of a scale.
 *
 * The ends of a scale are round numbers, not measurements, so they lose the
 * decimals the unit would otherwise carry: a 480 W limit reads `480`, never
 * `480.00`.
 *
 * @param {number|null} value the value in the base unit
 * @param {object} spec the channel
 * @returns {string} the label, or an empty string when there is no value
 */
export function scaleLabel(value, spec) {
  if (value === null || value === undefined) return "";
  const shown = splitValue(value, spec);
  const number = Number(shown.text);
  if (Number.isNaN(number)) return shown.text;
  const rounded = Number.isInteger(number) ? String(number) : fixed(number, Math.abs(number) < 10 ? 1 : 0);
  return shown.unit && shown.unit !== spec.symbol ? `${rounded} ${shown.unit}` : rounded;
}

/**
 * Return the value and its unit separately, both already scaled.
 *
 * A large figure beside a small unit reads better than one long string, but
 * the two must be scaled together or the dial says `3165000000` where the
 * meter says `3.2 GHz`.
 *
 * @param {number|null} value the value in the base unit
 * @param {object} spec the channel
 * @returns {{text: string, unit: string}}
 */
export function splitValue(value, spec) {
  const whole = formatValue(value, spec);
  if (value === null || value === undefined || Number.isNaN(value)) return { text: "—", unit: spec.symbol };
  const cut = whole.lastIndexOf(" ");
  if (cut < 0) return { text: whole, unit: "" };
  return { text: whole.slice(0, cut), unit: whole.slice(cut + 1) };
}

/**
 * Write text into an element, but only when it is not already there.
 *
 * At 10 Hz with 175 channels this runs about 1750 times a second, and most
 * of those values did not change between two passes. Writing the same text
 * again still costs the browser work.
 *
 * @param {HTMLElement} element where the text goes
 * @param {string} text what it should say
 */
export function setText(element, text) {
  if (element.textContent !== text) element.textContent = text;
}

// --- state -------------------------------------------------------------------

/** Every state, with the icon and the word that must travel with its colour. */
export const STATES = {
  normal: { word: "normal", icon: "●" },
  warning: { word: "warm", icon: "▲" },
  serious: { word: "hot", icon: "◆" },
  critical: { word: "critical", icon: "■" },
  stale: { word: "stale", icon: "◔" },
  unavailable: { word: "unavailable", icon: "○" },
};

/**
 * Return the state of one reading.
 *
 * A channel with no threshold is always `normal` when it has a value. The
 * application never invents a threshold: 5 of the 175 channels on this
 * machine publish one.
 *
 * @param {number|null} value the current value
 * @param {object} spec the channel
 * @param {{error?: string, age?: number}} extra what the frame said about it
 * @returns {string} one of the keys of STATES
 */
export function stateOf(value, spec, extra = {}) {
  if (value === null || value === undefined || extra.error) return "unavailable";
  if (spec.critical !== null && spec.critical !== undefined && value >= spec.critical) return "critical";
  if (spec.warn !== null && spec.warn !== undefined && value >= spec.warn) {
    // Two thirds of the way from the warning to the critical threshold, the
    // state moves on, so the last part of the range is not one flat colour.
    const critical = spec.critical;
    if (critical !== null && critical !== undefined && value >= spec.warn + (critical - spec.warn) * 0.66) {
      return "serious";
    }
    return "warning";
  }
  return "normal";
}

/** Return true when the spec carries a scale a meter can honestly use. */
export function hasScale(spec) {
  return spec.low !== null && spec.low !== undefined && scaleTop(spec) !== null;
}

/**
 * Return the top of the scale, or null.
 *
 * `high` is the spec's own maximum. Where a channel has no maximum but does
 * publish a critical threshold, the threshold is the honest top, because
 * running to it is the whole meaning of the bar. The tooltip says which one
 * was used.
 */
export function scaleTop(spec) {
  if (spec.high !== null && spec.high !== undefined) return spec.high;
  if (spec.critical !== null && spec.critical !== undefined) return spec.critical;
  return null;
}

// --- a stable, honest vertical axis -------------------------------------------

/**
 * Return rounded bounds and a step for an axis over `values`.
 *
 * Two things this fixes, both of them defects the terminal screen had:
 *
 *   - a span floor, so a value that moves by a quarter of a degree does not
 *     fill the box and look violent;
 *   - `previous`, so the axis only moves when the data leaves it. Recomputing
 *     the bounds on every frame makes the whole line jump while the value
 *     stands still.
 *
 * @param {Array<number|null>} values the series
 * @param {{low: number, high: number}|null} previous the axis now in use
 * @param {number} floor the smallest span the axis may have
 * @returns {{low: number, high: number, step: number, ticks: number[]}}
 */
export function niceAxis(values, previous = null, floor = 1) {
  const seen = values.filter((value) => value !== null && value !== undefined && !Number.isNaN(value));
  if (seen.length === 0) return previous ?? { low: 0, high: 1, step: 0.5, ticks: [0, 0.5, 1] };

  let low = Math.min(...seen);
  let high = Math.max(...seen);

  // Keep the axis that is already on screen while the data still fits inside
  // it, and while it still fills enough of it to be worth reading. Only those
  // two failures redraw the scale, so the line does not jump every frame.
  if (previous) {
    const span = previous.high - previous.low;
    const fits = low >= previous.low && high <= previous.high;
    const tooSmall = high - low < span * 0.25;
    if (fits && !tooSmall) return previous;
  }

  const span = Math.max(high - low, floor);
  const middle = (high + low) / 2;
  low = middle - span * 0.6;
  high = middle + span * 0.6;

  const step = niceStep((high - low) / 4);
  low = Math.floor(low / step) * step;
  high = Math.ceil(high / step) * step;
  const ticks = [];
  for (let tick = low; tick <= high + step / 2; tick += step) ticks.push(Number(tick.toFixed(6)));
  return { low, high, step, ticks };
}

/** Return a round step near `rough`: 1, 2, 5 or 10 times a power of ten. */
export function niceStep(rough) {
  if (!(rough > 0)) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(rough)));
  const scaled = rough / power;
  if (scaled <= 1) return power;
  if (scaled <= 2) return 2 * power;
  if (scaled <= 5) return 5 * power;
  return 10 * power;
}

// --- shared drawing helpers ---------------------------------------------------

/** Size a canvas for this screen's pixel ratio and return its context. */
function prepare(canvas, width, height) {
  const ratio = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
  }
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  return context;
}

/** Read one CSS custom property from the document root. */
function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const COLOUR_OF_STATE = {
  normal: "--series",
  warning: "--warning",
  serious: "--serious",
  critical: "--critical",
  stale: "--unavailable",
  unavailable: "--unavailable",
};

/** Return the one colour that belongs to a state. */
export function colourOf(state) {
  return token(COLOUR_OF_STATE[state] ?? "--series");
}

// --- Meter --------------------------------------------------------------------

/**
 * A value against a real limit: the default form for a channel with a scale.
 *
 * The track is the fill's own hue at low opacity, so the state reads across
 * the whole bar. The thresholds are marked on the track, so the reader can
 * see how much room is left without reading a number.
 */
export class Meter {
  /**
   * @param {object} spec the channel
   */
  constructor(spec) {
    this.spec = spec;
    this.element = document.createElement("div");
    this.element.className = "meter";
    this.element.dataset.state = "normal";
    const top = scaleTop(spec);
    this.element.innerHTML = `
      <div class="meter-head">
        <span class="meter-label"></span>
        <span class="meter-value"></span>
      </div>
      <div class="meter-track"><div class="meter-fill"></div><div class="meter-marks"></div></div>
      <div class="meter-scale"><span>${spec.low ?? 0}</span><span class="meter-top">${top ?? ""}</span></div>
    `;
    this.element.querySelector(".meter-label").textContent = spec.label;
    this.fill = this.element.querySelector(".meter-fill");
    this.valueText = this.element.querySelector(".meter-value");
    this.drawMarks();
  }

  /** Put a hairline on the track at each threshold the hardware publishes. */
  drawMarks() {
    const { spec } = this;
    const low = spec.low ?? 0;
    const top = scaleTop(spec);
    if (top === null || top <= low) return;
    const marks = this.element.querySelector(".meter-marks");
    for (const [name, at] of [
      ["warn", spec.warn],
      ["crit", spec.critical],
    ]) {
      if (at === null || at === undefined || at <= low || at >= top) continue;
      const mark = document.createElement("i");
      mark.className = `meter-mark meter-mark-${name}`;
      mark.style.left = `${((at - low) / (top - low)) * 100}%`;
      mark.title = `${name === "warn" ? "warning" : "critical"} at ${at}`;
      marks.appendChild(mark);
    }
  }

  /**
   * Show one reading.
   *
   * @param {number|null} value the value
   * @param {{error?: string, age?: number}} extra what the frame said
   */
  update(value, extra = {}) {
    const state = stateOf(value, this.spec, extra);
    if (this.element.dataset.state !== state) this.element.dataset.state = state;
    setText(this.valueText, formatValue(value, this.spec));
    const low = this.spec.low ?? 0;
    const top = scaleTop(this.spec);
    const fraction = value === null || top === null || top <= low ? 0 : (value - low) / (top - low);
    this.fill.style.width = `${Math.min(Math.max(fraction, 0), 1) * 100}%`;
  }
}

// --- Trace --------------------------------------------------------------------

/**
 * A line over the ring buffer, with a stable axis, a crosshair and a tooltip.
 *
 * The axis does not move while the data fits inside it, and never has a span
 * below its floor. The line is 2 px with round joins, the wash under it is the
 * same hue at a tenth of its strength, the gridlines are hairlines, and only
 * the last point is labelled.
 */
export class Trace {
  /**
   * @param {object} spec the channel
   * @param {{width: number, height: number, title?: string}} options the box
   */
  constructor(spec, options = {}) {
    this.spec = spec;
    this.minWidth = options.width ?? 420;
    this.width = this.minWidth;
    this.height = options.height ?? 160;
    this.axis = null;
    this.values = [];
    this.hoverAt = null;

    this.element = document.createElement("figure");
    this.element.className = "trace";
    this.element.dataset.state = "normal";
    this.element.innerHTML = `
      <figcaption>
        <span class="trace-title"></span>
        <span class="trace-span"></span>
      </figcaption>
      <div class="trace-plot">
        <canvas class="trace-canvas"></canvas>
        <div class="trace-tip" hidden></div>
      </div>
    `;
    this.element.querySelector(".trace-title").textContent = options.title ?? spec.label;
    this.canvas = this.element.querySelector(".trace-canvas");
    this.tip = this.element.querySelector(".trace-tip");
    this.plot = this.element.querySelector(".trace-plot");

    // The card decides the width; the chart follows it. Without this a chart
    // wider than its cell runs under the next card.
    this.observer = new ResizeObserver(() => this.draw());
    this.observer.observe(this.plot);

    this.plot.addEventListener("mousemove", (event) => {
      const box = this.canvas.getBoundingClientRect();
      this.hoverAt = event.clientX - box.left;
      this.draw();
    });
    this.plot.addEventListener("mouseleave", () => {
      this.hoverAt = null;
      this.tip.hidden = true;
      this.draw();
    });
  }

  /** The inset that leaves room for the tick labels and the end label. */
  get padding() {
    return { left: 46, right: 58, top: 10, bottom: 18 };
  }

  /**
   * Replace the series and redraw.
   *
   * @param {Array<number|null>} values oldest first
   * @param {number} seconds how much time the series covers
   */
  update(values, seconds) {
    this.values = values;
    this.seconds = seconds;
    const last = [...values].reverse().find((value) => value !== null && value !== undefined);
    this.element.dataset.state = stateOf(last ?? null, this.spec);
    this.element.querySelector(".trace-span").textContent =
      seconds >= 120 ? `last ${Math.round(seconds / 60)} min` : `last ${Math.round(seconds)} s`;
    this.draw();
  }

  /** Draw the whole figure, at whatever width the box now has. */
  draw() {
    const measured = this.plot.clientWidth;
    if (measured > 0) this.width = Math.max(measured, 220);
    const { width, height, values } = this;
    const context = prepare(this.canvas, width, height);
    const pad = this.padding;
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;

    // A floor of one unit, or a tenth of the value, whichever is larger. A
    // percentage keeps a floor of five, so an idle core does not look busy.
    const seen = values.filter((value) => value !== null && value !== undefined);
    const magnitude = seen.length ? Math.max(...seen.map(Math.abs)) : 1;
    const floor = this.spec.unit === "percent" ? 5 : Math.max(1, magnitude * 0.1);
    this.axis = niceAxis(values, this.axis, floor);
    const { low, high, ticks } = this.axis;

    const xOf = (index) => pad.left + (index / Math.max(values.length - 1, 1)) * plotWidth;
    const yOf = (value) => pad.top + plotHeight - ((value - low) / Math.max(high - low, 1e-9)) * plotHeight;

    context.strokeStyle = token("--grid");
    context.lineWidth = 1;
    context.fillStyle = token("--ink-muted");
    context.font = `11px ${token("--sans")}`;
    context.textAlign = "right";
    context.textBaseline = "middle";
    for (const tick of ticks) {
      const y = Math.round(yOf(tick)) + 0.5;
      context.beginPath();
      context.moveTo(pad.left, y);
      context.lineTo(pad.left + plotWidth, y);
      context.stroke();
      context.fillText(this.tickText(tick), pad.left - 8, y);
    }

    const state = this.element.dataset.state;
    const colour = colourOf(state);

    // Any threshold that falls inside the axis is drawn as a reference line,
    // with its word beside it. A reader must not have to know that red means
    // critical.
    for (const [name, at] of [
      ["warning", this.spec.warn],
      ["critical", this.spec.critical],
    ]) {
      if (at === null || at === undefined || at < low || at > high) continue;
      const y = Math.round(yOf(at)) + 0.5;
      context.strokeStyle = name === "critical" ? token("--critical") : token("--warning");
      context.globalAlpha = 0.7;
      context.beginPath();
      context.moveTo(pad.left, y);
      context.lineTo(pad.left + plotWidth, y);
      context.stroke();
      context.globalAlpha = 1;
      context.textAlign = "left";
      context.fillStyle = name === "critical" ? token("--critical") : token("--warning");
      context.fillText(name, pad.left + 4, y - 7);
      context.fillStyle = token("--ink-muted");
      context.textAlign = "right";
    }

    const points = values
      .map((value, index) => (value === null || value === undefined ? null : [xOf(index), yOf(value)]))
      .filter(Boolean);
    if (points.length < 2) return;

    context.beginPath();
    context.moveTo(points[0][0], pad.top + plotHeight);
    for (const [x, y] of points) context.lineTo(x, y);
    context.lineTo(points[points.length - 1][0], pad.top + plotHeight);
    context.closePath();
    context.fillStyle = colour;
    context.globalAlpha = 0.1;
    context.fill();
    context.globalAlpha = 1;

    context.beginPath();
    context.moveTo(...points[0]);
    for (const [x, y] of points) context.lineTo(x, y);
    context.strokeStyle = colour;
    context.lineWidth = 2;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.stroke();

    const [endX, endY] = points[points.length - 1];
    context.beginPath();
    context.arc(endX, endY, 4, 0, Math.PI * 2);
    context.fillStyle = colour;
    context.fill();
    context.lineWidth = 2;
    context.strokeStyle = token("--surface");
    context.stroke();

    const lastValue = values[values.length - 1] ?? seen[seen.length - 1];
    context.fillStyle = token("--ink");
    context.textAlign = "left";
    context.font = `600 12px ${token("--sans")}`;
    context.fillText(formatValue(lastValue ?? null, this.spec), endX + 9, endY);

    this.drawCrosshair(context, pad, plotWidth, plotHeight, xOf, yOf);
  }

  /** Draw the crosshair and place the tooltip, when the pointer is over the plot. */
  drawCrosshair(context, pad, plotWidth, plotHeight, xOf, yOf) {
    if (this.hoverAt === null) return;
    const fraction = (this.hoverAt - pad.left) / Math.max(plotWidth, 1);
    if (fraction < 0 || fraction > 1) {
      this.tip.hidden = true;
      return;
    }
    const index = Math.round(fraction * (this.values.length - 1));
    const value = this.values[index];
    const x = Math.round(xOf(index)) + 0.5;

    context.strokeStyle = token("--axis");
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(x, pad.top);
    context.lineTo(x, pad.top + plotHeight);
    context.stroke();

    if (value === null || value === undefined) {
      this.tip.hidden = true;
      return;
    }
    const y = yOf(value);
    context.beginPath();
    context.arc(x, y, 4, 0, Math.PI * 2);
    context.fillStyle = colourOf(this.element.dataset.state);
    context.fill();
    context.lineWidth = 2;
    context.strokeStyle = token("--surface");
    context.stroke();

    const ago = ((this.values.length - 1 - index) / Math.max(this.values.length - 1, 1)) * (this.seconds ?? 0);
    this.tip.hidden = false;
    this.tip.textContent = `${formatValue(value, this.spec)} · ${ago < 1 ? "now" : `${ago.toFixed(0)} s ago`}`;
    this.tip.style.left = `${Math.min(x + 10, this.width - 120)}px`;
    this.tip.style.top = `${Math.max(y - 30, 0)}px`;
  }

  /** Return a short tick label. A large number keeps its prefix, not its zeros. */
  tickText(tick) {
    const scaling = UNIT_SCALING[this.spec.unit];
    if (scaling) return formatValue(tick, this.spec).replace(` ${this.spec.symbol}`, "");
    const step = this.axis?.step ?? 1;
    const decimals = step >= 1 ? 0 : Math.min(2, Math.ceil(-Math.log10(step)));
    return tick.toFixed(decimals);
  }
}

// --- Sparkline ----------------------------------------------------------------

/** The same line, small enough to sit in a row. No axis, no labels. */
export class Sparkline {
  /**
   * @param {object} spec the channel
   * @param {{width?: number, height?: number}} options the box
   */
  constructor(spec, options = {}) {
    this.spec = spec;
    this.width = options.width ?? 110;
    this.height = options.height ?? 26;
    this.axis = null;
    this.element = document.createElement("canvas");
    this.element.className = "sparkline";
  }

  /** Redraw from the ring buffer. */
  update(values, state = "normal") {
    const context = prepare(this.element, this.width, this.height);
    const seen = values.filter((value) => value !== null && value !== undefined);
    if (seen.length < 2) return;
    const magnitude = Math.max(...seen.map(Math.abs));
    const floor = this.spec.unit === "percent" ? 5 : Math.max(1, magnitude * 0.1);
    this.axis = niceAxis(values, this.axis, floor);
    const { low, high } = this.axis;
    const points = values
      .map((value, index) =>
        value === null || value === undefined
          ? null
          : [
              2 + (index / Math.max(values.length - 1, 1)) * (this.width - 4),
              this.height - 3 - ((value - low) / Math.max(high - low, 1e-9)) * (this.height - 6),
            ],
      )
      .filter(Boolean);
    if (points.length < 2) return;

    context.beginPath();
    context.moveTo(...points[0]);
    for (const point of points) context.lineTo(...point);
    context.strokeStyle = colourOf(state);
    context.globalAlpha = 0.85;
    context.lineWidth = 1.5;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.stroke();
    context.globalAlpha = 1;

    const [endX, endY] = points[points.length - 1];
    context.beginPath();
    context.arc(endX, endY, 2, 0, Math.PI * 2);
    context.fillStyle = colourOf(state);
    context.fill();
  }
}

// --- Stat tile ----------------------------------------------------------------

/**
 * A label, one value, its state in words, and a sparkline.
 *
 * This is the form for a channel with **no** real scale, which is 109 of the
 * 175 channels on this machine. It never draws a bar, because there is
 * nothing honest to draw one against.
 */
export class StatTile {
  /**
   * @param {object} spec the channel
   * @param {{hero?: boolean}} options hero makes the figure large
   */
  constructor(spec, options = {}) {
    this.spec = spec;
    this.element = document.createElement("div");
    this.element.className = options.hero ? "tile tile-hero" : "tile";
    this.element.dataset.state = "normal";
    this.element.innerHTML = `
      <div class="tile-label"></div>
      <div class="tile-row">
        <span class="tile-value">—</span>
        <span class="tile-state"><i class="tile-icon"></i><span class="tile-word"></span></span>
      </div>
    `;
    this.element.querySelector(".tile-label").textContent = spec.label;
    this.valueText = this.element.querySelector(".tile-value");
    this.icon = this.element.querySelector(".tile-icon");
    this.word = this.element.querySelector(".tile-word");
    this.spark = new Sparkline(spec, { width: options.hero ? 220 : 130, height: options.hero ? 40 : 26 });
    this.element.appendChild(this.spark.element);
  }

  /** Show one reading and its history. */
  update(value, values, extra = {}) {
    const state = stateOf(value, this.spec, extra);
    if (this.element.dataset.state !== state) this.element.dataset.state = state;
    setText(this.valueText, formatValue(value, this.spec));
    setText(this.icon, STATES[state].icon);
    // A state that is simply "normal" needs no word; anything else must say
    // what it is, because the colour alone is not enough. And on a channel
    // with no threshold at all, "normal" says nothing, so nothing is shown.
    const judged = this.spec.warn !== null || this.spec.critical !== null;
    setText(this.word, state === "normal" ? "" : (extra.error ?? STATES[state].word));
    this.element.classList.toggle("is-quiet", state === "normal");
    this.icon.hidden = state === "normal" && !judged;
    this.spark.update(values, state);
  }
}
