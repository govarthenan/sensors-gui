/*
 * The graphics card, drawn as a schematic with every reading placed on the
 * part it belongs to.
 *
 * `docs/gui-goal.md` section 4.3 asks for a diagram with each sensor placed
 * where it physically sits, and for honesty where that is not known. What is
 * known about this card, and where each claim comes from, is written down in
 * `docs/diagram-positions.md`. In short:
 *
 *   - Which PART a reading belongs to is established: NVIDIA names each field
 *     (the chip, the memory, the whole board), and the probe names the chip,
 *     the link and the outputs.
 *   - Where each part SITS on the board is not: there is no photograph or
 *     drawing of the bare board in this repository. So the regions are laid
 *     out by function, and the drawing says so in its own title.
 *   - Where each FAN sits is not established either, so both fans are in a
 *     separate, dashed area that says so.
 *
 * Each row is a tooltip target, so the diagram explains itself on hover.
 */

import { STATES, colourOf, formatValue, setText, stateOf } from "../widgets.js";
import { attachTooltip } from "../tooltip.js";

const SVG = "http://www.w3.org/2000/svg";

/**
 * The regions of the schematic. `rows` name a card channel by its NVML key,
 * a missing value by its label, or give fixed text with its source.
 */
const REGIONS = [
  {
    id: "memory",
    title: "Memory · 24 GiB GDDR6X",
    box: [50, 96, 220, 160],
    rows: [
      { name: "Used", channel: "memory_used" },
      { name: "Bus use", channel: "memory_utilization" },
      { name: "Clock", channel: "clock_memory" },
      { name: "Temperature", missing: "GPU memory (GDDR6X)" },
    ],
  },
  {
    id: "chip",
    title: "Graphics chip · AD102",
    box: [290, 96, 240, 214],
    rows: [
      { name: "Temperature (edge)", channel: "temperature" },
      { name: "Use", channel: "utilization" },
      { name: "SM clock", channel: "clock_sm" },
      { name: "Performance state", channel: "performance_state", format: (value) => `P${value}` },
      { heading: "Video engines" },
      { name: "NVENC", channel: "encoder_utilization" },
      { name: "NVDEC", channel: "decoder_utilization" },
    ],
  },
  {
    id: "vrm",
    title: "Voltage regulators (VRM)",
    box: [550, 96, 220, 70],
    rows: [{ name: "Temperature", missing: "GPU VRM" }],
  },
  {
    id: "power",
    title: "Power in · 12VHPWR, 600 W cable",
    box: [550, 182, 220, 128],
    rows: [
      { name: "Whole card", channel: "power" },
      { name: "Energy since load", channel: "energy" },
      { text: "Limit 480 W, enforced by the card" },
    ],
  },
  {
    id: "outputs",
    title: "Display outputs",
    box: [50, 272, 220, 98],
    rows: [
      { text: "DP-1, DP-2, DP-3, HDMI-A-1" },
      { text: "Both monitors: HDMI-A-1, DP-1" },
      { text: "The iGPU drives no monitor" },
    ],
  },
  {
    id: "pcie",
    title: "PCIe edge · x16, PCIe 4.0 at most",
    box: [290, 396, 240, 82],
    rows: [
      { name: "Transmit", channel: "pcie_tx" },
      { name: "Receive", channel: "pcie_rx" },
    ],
  },
];

/** The area for readings whose place on the card is not established. */
const UNPLACED = {
  title: "Position on the card not established",
  box: [30, 504, 760, 100],
  columns: [
    [
      { name: "Fan 1", channel: "fan0_rpm" },
      { name: "Fan 1 duty", channel: "fan0_percent" },
    ],
    [
      { name: "Fan 2", channel: "fan1_rpm" },
      { name: "Fan 2 duty", channel: "fan1_percent" },
    ],
    [
      { name: "Hotspot", missing: "GPU hotspot" },
      { text: "NVML reports 2 fans." },
      { text: "Where each sits: not established." },
    ],
  ],
};

/** Make one SVG element with attributes. */
function make(tag, attributes = {}, text = null) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  if (text !== null) node.textContent = text;
  return node;
}

/**
 * Build the diagram.
 *
 * @param {(key: string) => object|null} find returns a card channel by its NVML key
 * @param {(label: string) => object|null} findMissing returns a missing value by its label
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: SVGElement, update: Function}} the diagram
 */
export function cardDiagram(find, findMissing, stream) {
  const svg = make("svg", { viewBox: "0 0 820 620", class: "diagram", role: "img" });
  svg.appendChild(make("title", {}, "Schematic of the MSI RTX 4090 SUPRIM with its live readings"));
  const painters = [];

  svg.appendChild(make("text", { x: 30, y: 22, class: "dg-caption" }, "MSI GeForce RTX 4090 SUPRIM · PCI 01:00.0"));
  svg.appendChild(
    make(
      "text",
      { x: 30, y: 42, class: "dg-note" },
      "A schematic by function. The regions are not where the parts sit on the board: no picture of the bare " +
        "board is in this repository.",
    ),
  );
  svg.appendChild(make("rect", { x: 30, y: 60, width: 760, height: 336, rx: 14, class: "dg-board" }));

  /** Put one row at (x, y), across `width`, and return nothing. */
  function row(spec, x, y, width) {
    if (spec.heading) {
      svg.appendChild(make("text", { x, y, class: "dg-heading" }, spec.heading));
      return;
    }
    if (spec.text) {
      svg.appendChild(make("text", { x, y, class: "dg-fixed" }, spec.text));
      return;
    }
    const group = make("g", { class: "dg-row" });
    group.appendChild(make("rect", { x: x - 6, y: y - 14, width: width + 12, height: 20, rx: 4, class: "dg-hit" }));
    group.appendChild(make("text", { x, y, class: "dg-name" }, spec.name));
    const value = make("text", { x: x + width, y, class: "dg-value", "text-anchor": "end" }, "—");
    group.appendChild(value);
    svg.appendChild(group);

    if (spec.missing) {
      const entry = findMissing(spec.missing);
      value.textContent = "○ not readable";
      group.classList.add("dg-missing");
      if (entry) attachTooltip(group, entry, stream);
      return;
    }
    const channel = find(spec.channel);
    if (channel === null) {
      value.textContent = "not on this machine";
      group.classList.add("dg-missing");
      return;
    }
    attachTooltip(group, channel, stream);
    painters.push(() => {
      const reading = stream.value(channel);
      const extra = stream.extra(channel);
      const state = stateOf(reading, channel, extra);
      const shown = spec.format ? spec.format(reading) : formatValue(reading, channel);
      let text = shown;
      if (reading === null) text = `${STATES[state].icon} ${extra.error ? "unavailable" : "—"}`;
      else if (state !== "normal") text = `${STATES[state].icon} ${shown}`;
      setText(value, text);
      // A state other than normal also says so in words, in the tooltip, and
      // carries its icon here: colour never carries it alone.
      const colour = state === "normal" ? "" : colourOf(state);
      if (value.style.fill !== colour) value.style.fill = colour;
    });
  }

  for (const region of REGIONS) {
    const [x, y, width, height] = region.box;
    svg.appendChild(make("rect", { x, y, width, height, rx: 8, class: `dg-region dg-${region.id}` }));
    svg.appendChild(make("text", { x: x + 12, y: y + 22, class: "dg-title" }, region.title));
    region.rows.forEach((spec, index) => row(spec, x + 12, y + 46 + index * 22, width - 24));
  }

  const [ux, uy, uwidth, uheight] = UNPLACED.box;
  svg.appendChild(make("rect", { x: ux, y: uy, width: uwidth, height: uheight, rx: 10, class: "dg-unplaced" }));
  svg.appendChild(make("text", { x: ux + 14, y: uy + 22, class: "dg-title" }, UNPLACED.title));
  const columnWidth = (uwidth - 28) / UNPLACED.columns.length;
  UNPLACED.columns.forEach((column, at) => {
    column.forEach((spec, index) =>
      row(spec, ux + 14 + at * columnWidth, uy + 46 + index * 22, columnWidth - 28),
    );
  });

  return {
    element: svg,
    update() {
      for (const paint of painters) paint();
    },
  };
}
