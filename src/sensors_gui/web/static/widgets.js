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
  // Gova, 2026-09-23: a reading past the scale its spec publishes must say
  // so. The ceiling is the spec's `high`, the floor its `low`.
  over: { word: "above ceiling", icon: "⤒" },
  under: { word: "below floor", icon: "⤓" },
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
  const has = (at) => at !== null && at !== undefined;
  if (has(spec.critical) && value >= spec.critical) return "critical";
  const warm = has(spec.warn) && value >= spec.warn;
  // Two thirds of the way from the warning to the critical threshold, the
  // state moves on, so the last part of the range is not one flat colour.
  if (warm && has(spec.critical) && value >= spec.warn + (spec.critical - spec.warn) * 0.66) return "serious";
  // Past the published scale. Weaker than a published critical or serious
  // threshold, because those name a danger and a ceiling only names the end
  // of the scale; stronger than a warning, because the meter can no longer
  // show the value inside its track.
  if (has(spec.high) && value > spec.high) return "over";
  if (has(spec.low) && value < spec.low) return "under";
  if (warm) return "warning";
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

/**
 * Return the axis with no part below the bottom of the spec's scale.
 *
 * A fan at rest reads 0 RPM, and an axis centred on it ran from -1 to 1: a
 * speed below zero, drawn as if it could happen. Where the spec publishes a
 * low end, the axis does not go under it; the ticks keep their step.
 *
 * @param {{low: number, high: number, step: number, ticks: number[]}} axis
 * @param {number|null|undefined} bottom the spec's `low`
 * @param {number|null} lowest the lowest value in the data, if any
 * @returns {{low: number, high: number, step: number, ticks: number[]}}
 */
export function floorAt(axis, bottom, lowest = null) {
  if (bottom === null || bottom === undefined || axis.low >= bottom) return axis;
  // A reading below the floor is the thing to see, never to cut off.
  if (lowest !== null && lowest !== undefined && lowest < bottom) return axis;
  const span = axis.high - axis.low;
  const low = bottom;
  const high = Math.max(axis.high, bottom + span / 2);
  const ticks = axis.ticks.filter((tick) => tick >= low && tick <= high);
  return { ...axis, low, high, ticks };
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
  over: "--warning",
  under: "--warning",
  stale: "--unavailable",
  unavailable: "--unavailable",
};

/** Return the one colour that belongs to a state. */
export function colourOf(state) {
  return token(COLOUR_OF_STATE[state] ?? "--series");
}

// --- Meter geometry -------------------------------------------------------------

/**
 * Return where a meter's fill, its ceiling and its overflow sit, as fractions
 * of the track.
 *
 * Inside the scale the ceiling is the end of the track. Past it, the track is
 * stretched so the ceiling moves inward to a mark the reader can see, and the
 * fill runs across that mark: a bar that simply stops at its end would hide
 * the one fact that matters. Gova, 2026-09-23.
 *
 * @param {number|null} value the reading
 * @param {object} spec the channel
 * @returns {{fill: number, ceiling: number, over: number, top: number}}
 *   `fill` up to the ceiling, `ceiling` where the ceiling mark sits, `over`
 *   the length past it, and `top` the value at the end of the track
 */
export function meterGeometry(value, spec) {
  const low = spec.low ?? 0;
  const top = scaleTop(spec);
  if (top === null || top <= low) return { fill: 0, ceiling: 1, over: 0, top };
  const span = top - low;
  if (value === null || value === undefined || value <= top) {
    const fill = value === null || value === undefined ? 0 : Math.min(Math.max((value - low) / span, 0), 1);
    return { fill, ceiling: 1, over: 0, top };
  }
  // The end of the stretched track: a little past the value, and never so
  // close to the ceiling that the mark sits on the end of the track.
  const end = Math.max(value + span * 0.05, low + span / 0.88);
  const ceiling = span / (end - low);
  return { fill: 1, ceiling, over: (value - top) / (end - low), top: end };
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
      <div class="meter-track">
        <div class="meter-fill"></div><div class="meter-over"></div><div class="meter-marks"></div>
        <i class="meter-ceiling" hidden></i>
      </div>
      <div class="meter-flag" hidden></div>
      <div class="meter-scale"><span></span><span class="meter-top"></span></div>
    `;
    this.element.querySelector(".meter-label").textContent = spec.label;
    // The ends are scaled like the value, so 24 GiB never reads 25757220864.
    const ends = this.element.querySelectorAll(".meter-scale span");
    ends[0].textContent = scaleLabel(spec.low ?? 0, spec);
    ends[1].textContent = top === null ? "" : scaleLabel(top, spec);
    this.fill = this.element.querySelector(".meter-fill");
    this.overflow = this.element.querySelector(".meter-over");
    this.ceilingMark = this.element.querySelector(".meter-ceiling");
    this.flag = this.element.querySelector(".meter-flag");
    this.topLabel = ends[1];
    this.topText = ends[1].textContent;
    this.marks = [];
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
      this.marks.push({ mark, at });
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
    const geometry = meterGeometry(value, this.spec);
    const over = geometry.over > 0;
    this.fill.style.width = `${(over ? geometry.ceiling : geometry.fill) * 100}%`;
    this.overflow.style.left = `${geometry.ceiling * 100}%`;
    this.overflow.style.width = `${geometry.over * 100}%`;
    this.ceilingMark.hidden = !over;
    this.ceilingMark.style.left = `${geometry.ceiling * 100}%`;
    // The thresholds keep their place on the stretched track.
    if (geometry.top !== null) {
      for (const { mark, at } of this.marks) mark.style.left = `${((at - low) / (geometry.top - low)) * 100}%`;
    }
    // The label under the track follows the ceiling, and names it.
    const ceilingText = over ? `ceiling ${this.topText}` : this.topText;
    setText(this.topLabel, ceilingText);
    this.topLabel.style.right = over ? `${(1 - geometry.ceiling) * 100}%` : "0";
    this.topLabel.classList.toggle("is-over", over);
    const top = scaleTop(this.spec);
    this.flag.hidden = state !== "over" && state !== "under";
    if (state === "over") {
      setText(this.flag, `${STATES.over.icon} ${formatValue(value - top, this.spec)} above the ceiling`);
    } else if (state === "under") {
      setText(this.flag, `${STATES.under.icon} ${formatValue(low - value, this.spec)} below the floor`);
    }
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
    // More series on the same axis: [{label, token}]. The dataviz skill:
    // one axis only, so a second series is only for the same measure, and
    // with two series a legend is present and each line is labelled.
    this.others = options.others ?? [];
    this.otherValues = this.others.map(() => []);
    this.firstLabel = options.firstLabel ?? spec.label;

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
    if (this.others.length) this.addLegend();
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

  /** A legend with a line key for each series, under the title. */
  addLegend() {
    const legend = document.createElement("div");
    legend.className = "trace-legend";
    for (const [label, name] of [[this.firstLabel, "--series"], ...this.others.map((o) => [o.label, o.token])]) {
      const item = document.createElement("span");
      item.className = "trace-key";
      const key = document.createElement("i");
      key.style.background = `var(${name})`;
      item.append(key, document.createTextNode(label));
      legend.appendChild(item);
    }
    this.element.querySelector("figcaption").after(legend);
  }

  /** The inset that leaves room for the tick labels and the end label. */
  get padding() {
    // The end label needs room: "570.0 MHz" is wider than "34.0 °C".
    const scaled = UNIT_SCALING[this.spec.unit] !== undefined;
    return { left: 52, right: this.others.length ? 110 : scaled ? 78 : 62, top: 10, bottom: 18 };
  }

  /**
   * Replace the series and redraw.
   *
   * @param {Array<number|null>} values oldest first
   * @param {number} seconds how much time the series covers
   */
  update(values, seconds, others = []) {
    this.values = values;
    this.otherValues = others;
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
    const every = [values, ...this.otherValues].flat();
    const seen = values.filter((value) => value !== null && value !== undefined);
    const seenAll = every.filter((value) => value !== null && value !== undefined);
    const magnitude = seenAll.length ? Math.max(...seenAll.map(Math.abs)) : 1;
    const floor = this.spec.unit === "percent" ? 5 : Math.max(1, magnitude * 0.1);
    // Past the ceiling, the axis must hold the ceiling too, so the reader sees
    // the line cross it rather than a line with no reference at all.
    const ceiling = this.spec.high ?? null;
    const crossed = ceiling !== null && seenAll.some((value) => value > ceiling);
    this.crossed = crossed;
    const lowest = seenAll.length ? Math.min(...seenAll) : null;
    this.axis = floorAt(niceAxis(crossed ? [...every, ceiling] : every, this.axis, floor), this.spec.low, lowest);
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
    // Past the scale, only the part of the line past the ceiling changes
    // colour (`strokeAboveCeiling`); the rest keeps the series colour, so the
    // crossing itself is what the eye finds.
    const colour = colourOf(state === "over" || state === "under" ? "normal" : state);

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

    this.drawCeiling(context, pad, plotWidth, yOf, low, high);

    const pointsOf = (series) =>
      series
        .map((value, index) => (value === null || value === undefined ? null : [xOf(index), yOf(value)]))
        .filter(Boolean);
    const points = pointsOf(values);
    if (points.length < 2) return;
    if (this.others.length) {
      this.drawSeries(context, pointsOf, colour);
      this.drawCrosshair(context, pad, plotWidth, plotHeight, xOf, yOf);
      return;
    }

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
    this.strokeAboveCeiling(context, points, pad, plotWidth, yOf);

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

  /**
   * Draw the ceiling, the spec's `high`, as a reference line with its word.
   *
   * It is drawn whenever it falls inside the axis. Where the data has crossed
   * it, the line turns the colour of the "above ceiling" state, the space
   * above it takes a faint wash of that colour, and its word says it was
   * exceeded: Gova, 2026-09-23, "the dataviz should clearly show that the
   * reading exceeds the ceiling marker on the plot".
   */
  drawCeiling(context, pad, plotWidth, yOf, low, high) {
    const ceiling = this.spec.high;
    if (ceiling === null || ceiling === undefined || ceiling < low || ceiling > high) return;
    // A ceiling that is also the critical threshold is drawn once, as critical.
    if (ceiling === this.spec.critical && !this.crossed) return;
    const y = Math.round(yOf(ceiling)) + 0.5;
    const over = token("--warning");
    if (this.crossed) {
      context.fillStyle = over;
      context.globalAlpha = 0.08;
      context.fillRect(pad.left, pad.top, plotWidth, y - pad.top);
      context.globalAlpha = 1;
    }
    context.save();
    context.strokeStyle = this.crossed ? over : token("--ink-muted");
    context.lineWidth = this.crossed ? 1.5 : 1;
    context.setLineDash([5, 4]);
    context.beginPath();
    context.moveTo(pad.left, y);
    context.lineTo(pad.left + plotWidth, y);
    context.stroke();
    context.restore();
    // The word sits at the left end, where the line starts: the right end
    // belongs to the label of the newest value.
    context.textAlign = "left";
    context.textBaseline = "middle";
    context.font = `${this.crossed ? 600 : 400} 11px ${token("--sans")}`;
    context.fillStyle = this.crossed ? over : token("--ink-muted");
    const words = `${this.crossed ? `${STATES.over.icon} exceeded · ` : ""}ceiling ${scaleLabel(ceiling, this.spec)}`;
    const nearTop = y - pad.top < 14;
    context.fillText(words, pad.left + 4, nearTop ? y + 9 : y - 8);
  }

  /** Stroke again, in the "above ceiling" colour, every part of the line above the ceiling. */
  strokeAboveCeiling(context, points, pad, plotWidth, yOf) {
    if (!this.crossed) return;
    const y = yOf(this.spec.high);
    context.save();
    context.beginPath();
    context.rect(pad.left - 6, 0, plotWidth + 12, y);
    context.clip();
    context.beginPath();
    context.moveTo(...points[0]);
    for (const [x, py] of points) context.lineTo(x, py);
    context.strokeStyle = token("--warning");
    context.lineWidth = 2.5;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.stroke();
    context.restore();
  }

  /**
   * Draw every series as a 2 px line with an end marker and a direct label.
   *
   * No wash under the lines: two washes over each other hide both. The end
   * labels are moved apart when they would collide, so each value stays
   * readable and its name travels with it.
   */
  drawSeries(context, pointsOf, colour) {
    const all = [
      { label: this.firstLabel, values: this.values, colour },
      ...this.others.map((other, index) => ({
        label: other.label,
        values: this.otherValues[index] ?? [],
        colour: token(other.token),
      })),
    ];
    const ends = [];
    for (const series of all) {
      const points = pointsOf(series.values);
      if (points.length < 2) continue;
      context.beginPath();
      context.moveTo(...points[0]);
      for (const [x, y] of points) context.lineTo(x, y);
      context.strokeStyle = series.colour;
      context.lineWidth = 2;
      context.lineJoin = "round";
      context.lineCap = "round";
      context.stroke();
      const [endX, endY] = points[points.length - 1];
      context.beginPath();
      context.arc(endX, endY, 4, 0, Math.PI * 2);
      context.fillStyle = series.colour;
      context.fill();
      context.lineWidth = 2;
      context.strokeStyle = token("--surface");
      context.stroke();
      const last = [...series.values].reverse().find((value) => value !== null && value !== undefined);
      ends.push({ x: endX, y: endY, text: `${series.label} ${formatValue(last ?? null, this.spec)}` });
    }
    ends.sort((a, b) => a.y - b.y);
    for (let index = 1; index < ends.length; index += 1) {
      ends[index].y = Math.max(ends[index].y, ends[index - 1].y + 15);
    }
    context.fillStyle = token("--ink");
    context.textAlign = "left";
    context.textBaseline = "middle";
    context.font = `600 12px ${token("--sans")}`;
    for (const end of ends) context.fillText(end.text, end.x + 9, end.y);
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
    const when = ago < 1 ? "now" : `${ago.toFixed(0)} s ago`;
    // One tooltip, every series: the reader never has to land on a line.
    const readout = [
      this.others.length ? `${this.firstLabel} ${formatValue(value, this.spec)}` : formatValue(value, this.spec),
      ...this.others.map((other, at) => `${other.label} ${formatValue(this.otherValues[at]?.[index] ?? null, this.spec)}`),
    ];
    this.tip.textContent = `${readout.join(" · ")} · ${when}`;
    this.tip.style.left = `${Math.min(x + 10, this.width - 120)}px`;
    this.tip.style.top = `${Math.max(y - 30, 0)}px`;
  }

  /**
   * Return a tick of a prefixed unit with as many decimals as its step needs.
   *
   * With one fixed decimal, ticks 0.05 GiB apart read "1.3 GiB, 1.3 GiB,
   * 1.2 GiB": two ticks with one label. The prefix comes from the top of the
   * axis, so every tick on it shares one prefix.
   */
  scaledTick(tick, scaling) {
    const step = scaling === "si" ? 1000 : 1024;
    const prefixes = scaling === "si" ? SI_PREFIXES : BINARY_PREFIXES;
    let divisor = 1;
    let index = 0;
    const top = Math.max(Math.abs(this.axis?.high ?? tick), Math.abs(this.axis?.low ?? tick));
    while (top / divisor >= step && index < prefixes.length - 1) {
      divisor *= step;
      index += 1;
    }
    const scaledStep = (this.axis?.step ?? 1) / divisor;
    const decimals = scaledStep >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(scaledStep) - 1e-9));
    return `${fixed(tick / divisor, decimals)} ${prefixes[index]}${this.spec.symbol}`.trimEnd();
  }

  /** Return a short tick label. A large number keeps its prefix, not its zeros. */
  tickText(tick) {
    const scaling = UNIT_SCALING[this.spec.unit];
    if (scaling) return this.scaledTick(tick, scaling);
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
    this.axis = floorAt(niceAxis(values, this.axis, floor), this.spec.low, Math.min(...seen));
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

// --- CoreBars -----------------------------------------------------------------

/**
 * One column for each core or thread, side by side, like a level meter.
 *
 * Gova's idea, 2026-09-22. It answers a question 24 rows of numbers cannot:
 * is the load spread across the cores, or pinned to one? It is a bar chart
 * comparing one measure across a category, which is the right form for that
 * question, so the usual rules apply and they matter more here than usual.
 *
 *   - **One scale for every column**, from the spec, never from the largest
 *     value on screen. A column half full means half of 100 %, always.
 *   - **The order is the hardware's order and never the values' order.** A
 *     display that re-sorted itself by magnitude would flicker and would
 *     destroy the identity of each column.
 *   - **No rainbow.** The reference picture runs a spectrum across the
 *     columns, which paints position as if it were meaning. Every column here
 *     carries the same hue, and colour is left free to carry state.
 *   - **The grouping is read from the machine.** The two threads of a core sit
 *     together and the two dies are apart, from
 *     `data/probes/2026-09-22-cpu-topology.txt`. A guess would put two
 *     different cores side by side.
 */
const MAX_BAR = 16; // the widest a column may be, so the leftover of a slot is air
const MAX_SLOT = 26; // the furthest apart two columns may stand

export class CoreBars {
  /**
   * @param {object} options the shape of the display
   * @param {Array<{label: string, channel: object, group: string}>} options.columns
   *   one entry for each column, in hardware order
   * @param {number} options.high the top of the scale, the same for every column
   * @param {string} options.unit the symbol to show after a value
   * @param {number} [options.height] the height of the plot in pixels
   */
  constructor(options) {
    this.columns = options.columns;
    this.high = options.high;
    this.unit = options.unit ?? "";
    this.height = options.height ?? 150;
    this.width = 640;
    this.values = this.columns.map(() => null);
    this.hoverAt = null;

    this.element = document.createElement("figure");
    this.element.className = "cores";
    this.element.innerHTML = `
      <div class="cores-plot">
        <canvas class="cores-canvas"></canvas>
        <div class="cores-tip" hidden></div>
      </div>
      `;
    this.canvas = this.element.querySelector(".cores-canvas");
    this.tip = this.element.querySelector(".cores-tip");
    this.plot = this.element.querySelector(".cores-plot");

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

  /** Take one set of values, in column order, and redraw. */
  update(values) {
    this.values = values;
    this.draw();
  }

  /** Where each column sits, and how wide it is. */
  layout(width) {
    const pad = { left: 34, right: 6, top: 14, bottom: 30 };
    const plotWidth = width - pad.left - pad.right;
    // A gap of one column's slot between blocks, so the two dies read apart.
    const blocks = [...new Set(this.columns.map((column) => column.group))].length;
    const slots = this.columns.length + (blocks - 1);
    // A slot is capped too. On a 2500 px screen an uncapped slot is 100 px
    // wide, and twenty-four columns that far apart stop reading as one
    // display. What is left over becomes margin, and the block is centred.
    const slot = Math.min(plotWidth / slots, MAX_SLOT);
    const used = slot * slots;
    const start = pad.left + (plotWidth - used) / 2;
    const positions = [];
    let cursor = start;
    let previous = null;
    for (const column of this.columns) {
      if (previous !== null && column.group !== previous) cursor += slot;
      positions.push(cursor);
      cursor += slot;
      previous = column.group;
    }
    return { pad, plotWidth, slot, positions, start, used };
  }

  /** Draw the whole display. */
  draw() {
    const measured = this.plot.clientWidth;
    if (measured > 0) this.width = Math.max(measured, 260);
    const { width, height } = this;
    const context = prepare(this.canvas, width, height);
    const { pad, plotWidth, slot, positions, start, used } = this.layout(width);
    const plotHeight = height - pad.top - pad.bottom;
    // A column is capped rather than filling its slot: the leftover is air,
    // and 24 columns filling a 2500 px screen read as blocks, not as a level
    // meter. A 2 px gap of surface does the separating, so no column needs a
    // border drawn around it.
    const barWidth = Math.max(Math.min(slot - 2, MAX_BAR), 2);
    const inset = (slot - barWidth) / 2;

    context.strokeStyle = token("--grid");
    context.lineWidth = 1;
    context.fillStyle = token("--ink-muted");
    context.font = `11px ${token("--sans")}`;
    context.textAlign = "right";
    context.textBaseline = "middle";
    for (const fraction of [0, 0.25, 0.5, 0.75, 1]) {
      const y = Math.round(pad.top + plotHeight * (1 - fraction)) + 0.5;
      context.beginPath();
      context.moveTo(start, y);
      context.lineTo(start + used, y);
      context.stroke();
      context.fillText(scaleLabel(this.high * fraction, { symbol: "", decimals: 0, unit: "none" }), start - 7, y);
    }

    const colour = token("--series");
    for (const [index, column] of this.columns.entries()) {
      const value = this.values[index];
      if (value === null || value === undefined) continue;
      const fraction = Math.min(Math.max(value / this.high, 0), 1);
      const barHeight = Math.max(fraction * plotHeight, fraction > 0 ? 1 : 0);
      context.fillStyle = colour;
      context.fillRect(positions[index] + inset, pad.top + plotHeight - barHeight, barWidth, barHeight);
      // Past the top of the shared scale, the column cannot grow, so a cap in
      // the "above ceiling" colour sits on it. Gova, 2026-09-23.
      if (value > this.high) {
        const middle = positions[index] + inset + barWidth / 2;
        context.fillStyle = token("--warning");
        context.beginPath();
        context.moveTo(middle - barWidth / 2, pad.top - 1);
        context.lineTo(middle + barWidth / 2, pad.top - 1);
        context.lineTo(middle, pad.top - 9);
        context.closePath();
        context.fill();
      }
    }

    context.fillStyle = token("--ink-muted");
    context.font = `10px ${token("--sans")}`;
    context.textAlign = "center";
    context.textBaseline = "top";
    for (const [index, column] of this.columns.entries()) {
      if (column.tick === false) continue;
      context.fillText(column.tick ?? "", positions[index] + slot / 2, pad.top + plotHeight + 3);
    }

    this.drawBlockNames(context, positions, slot, pad, plotHeight);
    this.drawHover(context, positions, barWidth, slot, inset, pad, plotHeight);
  }

  /**
   * Name each block of columns, under the middle of the block it names.
   *
   * This says what the gap between the blocks means, so the display needs no
   * legend: the reader sees two dies because there are two groups.
   */
  drawBlockNames(context, positions, slot, pad, plotHeight) {
    context.fillStyle = token("--ink-muted");
    context.font = `11px ${token("--sans")}`;
    context.textAlign = "center";
    context.textBaseline = "top";
    const seen = new Map();
    for (const [index, column] of this.columns.entries()) {
      const at = seen.get(column.group) ?? { first: positions[index], last: positions[index] };
      at.last = positions[index];
      seen.set(column.group, at);
    }
    for (const [name, at] of seen) {
      context.fillText(name, (at.first + at.last + slot) / 2, pad.top + plotHeight + 16);
    }
  }

  /** Show which column the pointer is on, and what it reads. */
  drawHover(context, positions, barWidth, slot, inset, pad, plotHeight) {
    if (this.hoverAt === null) {
      this.tip.hidden = true;
      return;
    }
    let found = -1;
    for (const [index, x] of positions.entries()) {
      // The whole slot is the target, not the column: a 14 px column is a
      // hard thing to put a pointer on.
      if (this.hoverAt >= x && this.hoverAt <= x + slot) found = index;
    }
    if (found < 0) {
      this.tip.hidden = true;
      return;
    }
    const column = this.columns[found];
    const value = this.values[found];
    context.strokeStyle = token("--ink-muted");
    context.lineWidth = 1;
    context.strokeRect(positions[found] + inset - 1.5, pad.top - 0.5, barWidth + 3, plotHeight + 1);
    this.tip.hidden = false;
    this.tip.textContent = `${column.label}: ${value === null ? "—" : `${value.toFixed(0)} ${this.unit}`}`;
    this.tip.style.left = `${Math.min(positions[found] + inset, this.width - 160)}px`;
    this.tip.style.top = "0px";
  }
}
