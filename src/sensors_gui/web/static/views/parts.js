/*
 * The small parts every view is built from: a card, a line of label and
 * value, and a note that a value is not on this machine.
 *
 * They were in the summary view first. The graphics card view needs the same
 * ones, and two copies would drift.
 */

import { CoreBars, Meter, StatTile, Trace, formatValue, hasScale, setText } from "../widgets.js";
import { attachTooltip, closeTooltip, openTooltip } from "../tooltip.js";

/** Build one card with a title and a note beside it. */
export function card(title, extra = "") {
  const element = document.createElement("section");
  element.className = "card view-card";
  element.innerHTML = `<h3 class="card-title"><span></span><span class="card-note"></span></h3>
    <div class="card-body"></div>`;
  element.querySelector(".card-title > span:first-child").textContent = title;
  element.querySelector(".card-note").textContent = extra;
  return { element, body: element.querySelector(".card-body") };
}

/** Build one line of "label ... value", for a fact with no meter. */
export function factLine(label, note = "") {
  const row = document.createElement("div");
  row.className = "fact";
  row.innerHTML = `<span class="fact-label"></span><span class="fact-value">—</span>`;
  row.querySelector(".fact-label").textContent = label;
  if (note) row.title = note;
  return { row, value: row.querySelector(".fact-value") };
}

/** Say that a channel this view expected is not on this machine. */
export function missing(body, label) {
  const line = document.createElement("p");
  line.className = "absent";
  line.textContent = `${label}: not found on this machine`;
  body.appendChild(line);
}

/**
 * The builders every detail view uses, bound to one stream and one list of
 * painters: a value with the right shape, a line of text, a chart, and the
 * core columns. Each one attaches the tooltip of `docs/gui-goal.md` 4.2, so
 * a view cannot forget it.
 *
 * @param {import("../stream.js").Stream} stream the live frames
 * @param {Function[]} painters where each builder puts its paint function
 */
export function builders(stream, painters) {
  return {
    /** A meter for a channel with a scale, a tile for one without. */
    show(body, channel, label = null) {
      if (channel === null) {
        missing(body, label ?? "a channel");
        return null;
      }
      const widget = hasScale(channel) ? new Meter(channel) : new StatTile(channel);
      body.appendChild(widget.element);
      attachTooltip(widget.element, channel, stream);
      painters.push(() =>
        widget instanceof Meter
          ? widget.update(stream.value(channel), stream.extra(channel))
          : widget.update(stream.value(channel), stream.series(channel), stream.extra(channel)),
      );
      return widget;
    },

    /** One value alone, for a cell of a table; the table gives the label. */
    cell(parent, channel) {
      const value = document.createElement("span");
      value.className = "cell-value";
      value.textContent = "—";
      parent.appendChild(value);
      if (channel === null) {
        value.textContent = "not found";
        value.classList.add("absent");
        return null;
      }
      attachTooltip(value, channel, stream);
      painters.push(() => setText(value, formatValue(stream.value(channel), channel)));
      return value;
    },

    /** A line of label and value. `format` may turn the number into other text. */
    fact(body, channel, label, format = null) {
      if (channel === null) {
        missing(body, label);
        return null;
      }
      const { row, value } = factLine(label);
      body.appendChild(row);
      attachTooltip(row, channel, stream);
      painters.push(() => {
        const reading = stream.value(channel);
        setText(value, reading !== null && format ? format(reading) : formatValue(reading, channel));
      });
      return row;
    },

    /**
     * A line chart. `others` puts more channels of the same measure on the
     * same axis, each with its colour token: [{channel, label, token}].
     */
    chart(body, channel, title, { others = [], firstLabel = null, height = 160 } = {}) {
      if (channel === null) return null;
      const present = others.filter((other) => other.channel !== null);
      const trace = new Trace(channel, {
        width: 360,
        height,
        title,
        firstLabel: firstLabel ?? channel.label,
        others: present.map((other) => ({ label: other.label, token: other.token })),
      });
      body.appendChild(trace.element);
      attachTooltip(trace.element.querySelector("figcaption"), channel, stream);
      painters.push(() =>
        trace.update(
          stream.series(channel),
          stream.seconds,
          present.map((other) => stream.series(other.channel)),
        ),
      );
      return trace;
    },

    /** One column for each core or thread, each with its own tooltip. */
    bars(body, columns, options) {
      const bars = new CoreBars({
        ...options,
        columns,
        onHover: (column, anchor) =>
          column === null ? closeTooltip(anchor) : openTooltip(anchor, column.channel, stream),
      });
      body.appendChild(bars.element);
      painters.push(() => bars.update(columns.map((column) => stream.value(column.channel))));
      return bars;
    },
  };
}
