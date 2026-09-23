/*
 * The pulsing dots of a drawing, and the short panel each one opens.
 *
 * Gova, 2026-09-23, of the graphics card: "the sensors could be shown as
 * pulsating dots on the wireframe - where the sensors would be, which show
 * the value upon mouseover." The same dots now serve every drawing of a part,
 * so they live here once: the card wireframe, the processor and the memory.
 *
 * A dot is a part of the machine with one or more readings. Its colour is the
 * worst state among them, and a part that cannot be read does not pulse,
 * because nothing is measured there. The pulse is an HTML element over the
 * drawing that animates in 12 steps, which costs about 0.005 cores where a
 * smooth SVG pulse cost 0.045 (`lab/exp-0015-gui-checkpoints`, 3c).
 */

import { STATES, colourOf, formatValue, stateOf } from "../widgets.js";

const SVG = "http://www.w3.org/2000/svg";

/** Make one SVG element with attributes. */
export function make(tag, attributes = {}, text = null) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  if (text !== null) node.textContent = text;
  return node;
}

/** The order of the states, worst last, for the colour of a dot with several readings. */
const SEVERITY = ["normal", "stale", "under", "over", "warning", "serious", "critical"];

/**
 * A set of dots on one drawing.
 *
 * @param {HTMLElement} element the box that holds the SVG; the pulses and the panel go in it
 * @param {SVGSVGElement} svg the drawing
 * @param {number} width the width of the SVG's viewBox
 * @param {number} height the height of the SVG's viewBox
 * @param {import("../stream.js").Stream} stream the live frames
 */
export class Dots {
  constructor(element, svg, width, height, stream) {
    this.element = element;
    this.svg = svg;
    this.width = width;
    this.height = height;
    this.stream = stream;
    this.dots = [];
    this.tip = document.createElement("div");
    this.tip.className = "wire-tip";
    this.tip.hidden = true;
    element.appendChild(this.tip);
  }

  /**
   * Add one dot.
   *
   * @param {{id: string, name: string, basis: string,
   *   rows: Array<{label: string, channel: object|null, format?: Function, missing?: string}>}} part
   *   the part, its readings, and the source of its position
   * @param {number} x where it sits, in viewBox units
   * @param {number} y the same
   * @param {SVGElement} [parent] the group to draw it in; the SVG when not given
   */
  add(part, x, y, parent = this.svg) {
    const group = make("g", { class: "wire-dot", tabindex: 0 });
    group.appendChild(make("circle", { cx: x, cy: y, r: 6, class: "wire-core" }));
    const pulse = document.createElement("i");
    pulse.className = "wire-pulse";
    pulse.style.left = `${(x / this.width) * 100}%`;
    pulse.style.top = `${(y / this.height) * 100}%`;
    this.element.appendChild(pulse);
    group.appendChild(make("circle", { cx: x, cy: y, r: 18, class: "wire-hit" }));
    parent.appendChild(group);
    const dot = { part, group, pulse, x, y };
    const open = () => this.show(dot);
    const close = () => {
      this.tip.hidden = true;
      this.tip.dataset.for = "";
    };
    group.addEventListener("pointerenter", open);
    group.addEventListener("focus", open);
    group.addEventListener("pointerleave", close);
    group.addEventListener("blur", close);
    this.dots.push(dot);
    return dot;
  }

  /** Return each reading of a dot as text, and the worst state among them. */
  read(dot) {
    let worst = "normal";
    const lines = dot.part.rows.map(({ label, channel, format, missing }) => {
      if (missing || !channel) return { label, text: "○ not readable", state: "unavailable" };
      const value = this.stream.value(channel);
      const state = stateOf(value, channel, this.stream.extra(channel));
      if (SEVERITY.indexOf(state) > SEVERITY.indexOf(worst)) worst = state;
      const shown = value === null ? "—" : format ? format(value) : formatValue(value, channel);
      return { label, text: state === "normal" ? shown : `${STATES[state]?.icon ?? ""} ${shown}`, state };
    });
    const allMissing = dot.part.rows.every(({ missing, channel }) => missing || !channel);
    return { lines, state: allMissing ? "unavailable" : worst };
  }

  /** Show the values of one dot beside it. */
  show(dot) {
    this.tip.dataset.for = dot.part.id;
    this.tip.hidden = false;
    this.fill(dot);
    const box = this.svg.getBoundingClientRect();
    const scale = box.width / this.width;
    const left = dot.x * scale + 16;
    this.tip.style.left = `${Math.max(Math.min(left, box.width - 280), 0)}px`;
    this.tip.style.top = `${Math.max(dot.y * scale - 20, 0)}px`;
  }

  /** Write the values of one dot into the panel. */
  fill(dot) {
    const { lines } = this.read(dot);
    this.tip.replaceChildren();
    const title = document.createElement("b");
    title.textContent = dot.part.name;
    this.tip.appendChild(title);
    for (const line of lines) {
      const row = document.createElement("div");
      row.className = "wire-tip-row";
      const name = document.createElement("span");
      name.textContent = line.label;
      const value = document.createElement("span");
      value.textContent = line.text;
      if (line.state !== "normal") value.style.color = colourOf(line.state);
      row.append(name, value);
      this.tip.appendChild(row);
    }
    const basis = document.createElement("p");
    basis.textContent = dot.part.basis;
    this.tip.appendChild(basis);
  }

  /** Colour each dot by its worst reading, and keep an open panel live. */
  update() {
    for (const dot of this.dots) {
      const { state } = this.read(dot);
      if (dot.group.dataset.state !== state) {
        dot.group.dataset.state = state;
        dot.pulse.dataset.state = state;
        dot.group.style.setProperty("--dot", colourOf(state));
        dot.pulse.style.setProperty("--dot", colourOf(state));
      }
      if (this.tip.dataset.for === dot.part.id) this.fill(dot);
    }
  }
}
