/*
 * The graphics card as a wireframe, with a pulsing dot where each part sits.
 *
 * Gova, 2026-09-23: "a wireframe of the GPU ... the sensors could be shown as
 * pulsating dots on the wireframe - where the sensors would be, which show
 * the value upon mouseover. This is purely cosmetic." Every value here is also
 * on screen permanently in the cards of the view; the wireframe only places
 * them.
 *
 * The drawing is the card as photograph 02 shows it through the side glass:
 * the backplate face, the output bracket at the left, the edge that goes into
 * the motherboard at the top and the edge that faces the glass at the bottom.
 * Its outline is to scale, 336 x 142 mm, from MSI's own specification.
 *
 * **A dot sits on the card only where a source places the part.** Two do:
 * the power connector, seen in photograph 02, and the graphics chip, inferred
 * from the cross-shaped plate and its four screws on the backplate. The rest
 * — the memory, the VRM, the PCIe fingers, the fans and the hotspot — are in
 * a row under the card that says their position is not established.
 * `docs/diagram-positions.md` holds every claim and its source.
 */

import { STATES, colourOf, formatValue, stateOf } from "../widgets.js";

const SVG = "http://www.w3.org/2000/svg";
const MM = 2.6; // drawing units per millimetre
const LENGTH = 336; // mm, MSI specification
const HEIGHT = 142; // mm, MSI specification
const LEFT = 70; // room for the bracket and the edge words
const TOP = 90;

/** Return a point on the backplate face, from fractions of its length and height. */
function at(along, across) {
  return [LEFT + along * LENGTH * MM, TOP + across * HEIGHT * MM];
}

/**
 * The parts with a dot on the card. `along` is measured from the bracket end,
 * `across` from the edge that goes into the motherboard. Both were read from
 * photograph 02, which is taken at an angle, so both are approximate.
 */
const PLACED = [
  {
    id: "chip",
    name: "Graphics chip",
    along: 0.46,
    across: 0.47,
    basis: "Inferred: under the cross-shaped plate and its four screws on the backplate, photograph 02.",
    rows: [
      ["Temperature (edge)", "temperature"],
      ["Use", "utilization"],
      ["SM clock", "clock_sm"],
      ["Performance state", "performance_state", (value) => `P${value}`],
      ["NVENC", "encoder_utilization"],
      ["NVDEC", "decoder_utilization"],
    ],
  },
  {
    id: "power",
    name: "Power connector, 12VHPWR",
    along: 0.84,
    across: 1.0,
    basis: "Seen: the cable enters the card's edge here, photograph 02.",
    rows: [
      ["Whole card", "power"],
      ["Energy since load", "energy"],
    ],
  },
];

/** The parts with a reading and no established position. */
const UNPLACED = [
  {
    id: "memory",
    name: "Memory, 24 GiB GDDR6X",
    basis: "Where the memory chips sit is not established.",
    rows: [
      ["Used", "memory_used"],
      ["Bus use", "memory_utilization"],
      ["Clock", "clock_memory"],
      ["Temperature", null, null, "GPU memory (GDDR6X)"],
    ],
  },
  {
    id: "vrm",
    name: "Voltage regulators",
    basis: "Where the VRM sits is not established.",
    rows: [["Temperature", null, null, "GPU VRM"]],
  },
  {
    id: "pcie",
    name: "PCIe fingers",
    basis: "On the edge that goes into the board; where along it is not established.",
    rows: [
      ["Generation", "pcie_link_gen", (value) => `PCIe ${value}.0`],
      ["Width", "pcie_link_width", (value) => `x${value}`],
      ["Transmit", "pcie_tx"],
      ["Receive", "pcie_rx"],
    ],
  },
  {
    id: "fan1",
    name: "Fan channel 1",
    basis: "The card has three fans on its far face; which NVML channel drives which is not established.",
    rows: [
      ["Speed", "fan0_rpm"],
      ["Duty", "fan0_percent"],
    ],
  },
  {
    id: "fan2",
    name: "Fan channel 2",
    basis: "The card has three fans on its far face; which NVML channel drives which is not established.",
    rows: [
      ["Speed", "fan1_rpm"],
      ["Duty", "fan1_percent"],
    ],
  },
  {
    id: "hotspot",
    name: "Hotspot",
    basis: "Not readable, and where on the chip the card measures it is not established.",
    rows: [["Temperature", null, null, "GPU hotspot"]],
  },
];

/** Make one SVG element with attributes. */
function make(tag, attributes = {}, text = null) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  if (text !== null) node.textContent = text;
  return node;
}

/** The order of the states, worst last, for the colour of a dot with several readings. */
const SEVERITY = ["normal", "stale", "under", "over", "warning", "serious", "critical"];

/**
 * Build the wireframe.
 *
 * @param {(key: string) => object|null} find returns a card channel by its NVML key
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the wireframe
 */
export function cardWireframe(find, stream) {
  const element = document.createElement("div");
  element.className = "wireframe";
  const width = LEFT + LENGTH * MM + 40;
  const unplacedTop = TOP + HEIGHT * MM + 90;
  const height = unplacedTop + 120;
  const svg = make("svg", { viewBox: `0 0 ${width} ${height}`, class: "wire", role: "img" });
  svg.appendChild(make("title", {}, "Wireframe of the MSI RTX 4090 SUPRIM, backplate side, with its readings"));
  element.appendChild(svg);

  const tip = document.createElement("div");
  tip.className = "wire-tip";
  tip.hidden = true;
  element.appendChild(tip);

  drawCard(svg);

  const dots = [];
  for (const part of PLACED) {
    const [x, y] = at(part.along, part.across);
    dots.push(makeDot(svg, part, x, y));
  }

  // The unplaced row: the same dots, in a dashed box that says what it is.
  const boxTop = unplacedTop;
  svg.appendChild(
    make("rect", { x: LEFT, y: boxTop, width: LENGTH * MM, height: 100, rx: 10, class: "wire-unplaced" }),
  );
  svg.appendChild(
    make("text", { x: LEFT + 14, y: boxTop + 22, class: "wire-title" }, "Position on the card not established"),
  );
  const step = (LENGTH * MM) / UNPLACED.length;
  UNPLACED.forEach((part, index) => {
    const x = LEFT + step * (index + 0.5);
    dots.push(makeDot(svg, part, x, boxTop + 52));
    svg.appendChild(make("text", { x, y: boxTop + 84, class: "wire-dot-name", "text-anchor": "middle" }, part.name));
  });

  /** Build one dot: a pulsing ring, a solid centre and a hit area. */
  function makeDot(parent, part, x, y) {
    const group = make("g", { class: "wire-dot", tabindex: 0 });
    group.appendChild(make("circle", { cx: x, cy: y, r: 7, class: "wire-pulse" }));
    group.appendChild(make("circle", { cx: x, cy: y, r: 6, class: "wire-core" }));
    group.appendChild(make("circle", { cx: x, cy: y, r: 18, class: "wire-hit" }));
    parent.appendChild(group);
    const readings = part.rows.map(([label, key, format, missing]) => ({
      label,
      channel: key ? find(key) : null,
      format,
      missing,
    }));
    const dot = { part, group, readings, x, y };
    const open = () => showTip(dot);
    const close = () => {
      tip.hidden = true;
      tip.dataset.for = "";
    };
    group.addEventListener("pointerenter", open);
    group.addEventListener("focus", open);
    group.addEventListener("pointerleave", close);
    group.addEventListener("blur", close);
    return dot;
  }

  /** Return each reading of a dot as text, and the worst state among them. */
  function read(dot) {
    let worst = "normal";
    const lines = dot.readings.map(({ label, channel, format, missing }) => {
      if (missing || channel === null) return { label, text: "○ not readable", state: "unavailable" };
      const value = stream.value(channel);
      const state = stateOf(value, channel, stream.extra(channel));
      if (SEVERITY.indexOf(state) > SEVERITY.indexOf(worst)) worst = state;
      const shown = value === null ? "—" : format ? format(value) : formatValue(value, channel);
      return { label, text: state === "normal" ? shown : `${STATES[state]?.icon ?? ""} ${shown}`, state };
    });
    const allMissing = dot.readings.every(({ missing, channel }) => missing || channel === null);
    return { lines, state: allMissing ? "unavailable" : worst };
  }

  /** Show the values of one dot beside it. */
  function showTip(dot) {
    tip.dataset.for = dot.part.id;
    tip.hidden = false;
    fillTip(dot);
    const box = svg.getBoundingClientRect();
    const scale = box.width / width;
    const left = dot.x * scale + 16;
    tip.style.left = `${Math.min(left, box.width - 280)}px`;
    tip.style.top = `${Math.max(dot.y * scale - 20, 0)}px`;
  }

  /** Write the values of one dot into the tip. */
  function fillTip(dot) {
    const { lines } = read(dot);
    tip.replaceChildren();
    const title = document.createElement("b");
    title.textContent = dot.part.name;
    tip.appendChild(title);
    for (const line of lines) {
      const row = document.createElement("div");
      row.className = "wire-tip-row";
      const name = document.createElement("span");
      name.textContent = line.label;
      const value = document.createElement("span");
      value.textContent = line.text;
      if (line.state !== "normal") value.style.color = colourOf(line.state);
      row.append(name, value);
      tip.appendChild(row);
    }
    const basis = document.createElement("p");
    basis.textContent = dot.part.basis;
    tip.appendChild(basis);
  }

  return {
    element,
    update() {
      for (const dot of dots) {
        const { state } = read(dot);
        if (dot.group.dataset.state !== state) {
          dot.group.dataset.state = state;
          dot.group.style.setProperty("--dot", colourOf(state));
        }
        if (tip.dataset.for === dot.part.id) fillTip(dot);
      }
    },
  };
}

/** Draw the card: the backplate outline, the bracket, the plate, the edges and the sizes. */
function drawCard(svg) {
  const [x0, y0] = at(0, 0);
  const [x1, y1] = at(1, 1);
  svg.appendChild(
    make("text", { x: LEFT, y: 24, class: "wire-caption" }, "MSI GeForce RTX 4090 SUPRIM · backplate side"),
  );
  svg.appendChild(
    make(
      "text",
      { x: LEFT, y: 44, class: "wire-note" },
      "As photograph 02 shows it through the side glass. Outline to scale; dots only where a source places the part.",
    ),
  );
  // The backplate.
  svg.appendChild(make("rect", { x: x0, y: y0, width: x1 - x0, height: y1 - y0, rx: 8, class: "wire-card" }));
  // The output bracket at the left end: seen in photographs 02 and 04.
  svg.appendChild(make("rect", { x: x0 - 16, y: y0 - 18, width: 12, height: y1 - y0 + 36, rx: 2, class: "wire-line" }));
  for (let port = 0; port < 4; port += 1) {
    const top = y0 + 30 + port * ((y1 - y0 - 60) / 3.4);
    svg.appendChild(make("rect", { x: x0 - 14, y: top, width: 8, height: 26, rx: 2, class: "wire-port" }));
  }
  svg.appendChild(
    make("text", { x: x0 - 22, y: y1 + 36, class: "wire-edge" }, "4 outputs: 3 DisplayPort, 1 HDMI"),
  );
  // The cross-shaped plate and its four screws, seen in photograph 02.
  const [cx, cy] = at(0.46, 0.47);
  const arm = 34 * MM;
  const plate = `M ${cx - arm} ${cy - arm * 0.7} L ${cx - arm * 0.25} ${cy - arm * 0.25} L ${cx + arm * 0.25} ${cy - arm * 0.25} ` +
    `L ${cx + arm} ${cy - arm * 0.7} M ${cx - arm} ${cy + arm * 0.7} L ${cx - arm * 0.25} ${cy + arm * 0.25} ` +
    `L ${cx + arm * 0.25} ${cy + arm * 0.25} L ${cx + arm} ${cy + arm * 0.7}`;
  svg.appendChild(make("path", { d: plate, class: "wire-line" }));
  for (const [dx, dy] of [
    [-1, -1],
    [1, -1],
    [-1, 1],
    [1, 1],
  ]) {
    svg.appendChild(make("circle", { cx: cx + dx * 9 * MM, cy: cy + dy * 7 * MM, r: 3, class: "wire-screw" }));
  }
  // The vents at the far end: the backplate runs past the circuit board
  // (WCCFTech teardown); where the board ends is not established, so no line
  // for it is drawn.
  for (let vent = 0; vent < 6; vent += 1) {
    const [vx, vy] = at(0.93, 0.16 + vent * 0.12);
    svg.appendChild(make("rect", { x: vx, y: vy, width: 12 * MM, height: 3, rx: 1.5, class: "wire-vent" }));
  }
  // The power connector on the near edge, seen in photograph 02.
  const [px, py] = at(0.84, 1.0);
  svg.appendChild(make("rect", { x: px - 22, y: py - 2, width: 44, height: 14, rx: 3, class: "wire-line" }));
  // The words on the two long edges.
  svg.appendChild(
    make("text", { x: (x0 + x1) / 2, y: y0 - 10, class: "wire-edge", "text-anchor": "middle" },
      "this edge goes into the motherboard slot"),
  );
  svg.appendChild(
    make("text", { x: (x0 + x1) / 2 - 90, y: y1 + 20, class: "wire-edge", "text-anchor": "middle" },
      "this edge faces the side glass"),
  );
  // The size, from MSI's specification.
  svg.appendChild(make("line", { x1: x0, y1: y1 + 52, x2: x1, y2: y1 + 52, class: "wire-dim" }));
  svg.appendChild(
    make("text", { x: (x0 + x1) / 2, y: y1 + 68, class: "wire-edge", "text-anchor": "middle" },
      "336 mm, and 142 mm across; the three fans are on the far face"),
  );
}
