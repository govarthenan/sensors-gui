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
 * Its outline is to scale, 280 x 140 mm: the card is the SUPRIM LIQUID X (Gova,
 * 2026-09-23), and the size is from MSI's own specification of it.
 *
 * **A dot sits on the card only where a source places the part.** Two do:
 * the power connector, seen in photographs 02 and 06, and the graphics chip,
 * inferred from the cross-shaped plate and its four screws on the backplate.
 * The coolant tubes and the card's one fan are drawn where photographs 05 to
 * 07 show them; they carry no dot, because no reading belongs to them alone. The rest
 * — the memory, the VRM, the PCIe fingers, the fans and the hotspot — are in
 * a row under the card that says their position is not established.
 * `docs/diagram-positions.md` holds every claim and its source.
 */

import { Dots, make } from "./dots.js";

const MM = 2.6; // drawing units per millimetre
const LENGTH = 280; // mm, MSI specification of the SUPRIM LIQUID X
const HEIGHT = 140; // mm, the same
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
    along: 0.45,
    across: 0.47,
    basis:
      "Inferred: under the cross-shaped plate and its four screws on the backplate, photographs 02 and 06 " +
      "(0.44 to 0.46 of the length).",
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
    along: 0.88,
    across: 1.0,
    basis: "Seen: the cable enters the card's edge here, photographs 02 and 06 (0.84 to 0.91 of the length).",
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
    name: "Memory",
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
    name: "VRM",
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
    basis:
      "The card has one fan and its radiator two. Its board, MS-V510 (label, photograph 06), has two fan " +
      "headers, A and B, one on each GPU fan channel; which fans each drives is not established.",
    rows: [
      ["Speed", "fan0_rpm"],
      ["Duty", "fan0_percent"],
    ],
  },
  {
    id: "fan2",
    name: "Fan channel 2",
    basis:
      "The card has one fan and its radiator two. Its board, MS-V510 (label, photograph 06), has two fan " +
      "headers, A and B, one on each GPU fan channel; which fans each drives is not established.",
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

  const dots = new Dots(element, svg, width, height, stream);
  /** The rows of a part, with each NVML key turned into its channel. */
  const resolve = (part) => ({
    ...part,
    rows: part.rows.map(([label, key, format, missing]) => ({
      label,
      channel: key ? find(key) : null,
      format,
      missing,
    })),
  });

  drawCard(svg);

  for (const part of PLACED) {
    const [x, y] = at(part.along, part.across);
    dots.add(resolve(part), x, y);
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
    dots.add(resolve(part), x, boxTop + 52);
    svg.appendChild(make("text", { x, y: boxTop + 84, class: "wire-dot-name", "text-anchor": "middle" }, part.name));
  });

  return { element, update: () => dots.update() };
}

/** Draw the card: the backplate outline, the bracket, the plate, the edges and the sizes. */
function drawCard(svg) {
  const [x0, y0] = at(0, 0);
  const [x1, y1] = at(1, 1);
  svg.appendChild(
    make("text", { x: LEFT, y: 24, class: "wire-caption" }, "MSI GeForce RTX 4090 SUPRIM LIQUID X · backplate side"),
  );
  svg.appendChild(
    make(
      "text",
      { x: LEFT, y: 44, class: "wire-note" },
      "As photographs 02 and 06 show it through the side glass. Outline to scale; dots only where a source places the part.",
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
    make("text", { x: x0 - 22, y: y1 + 40, class: "wire-edge" }, "bracket: 3 DisplayPort, 1 HDMI"),
  );
  // The cross-shaped plate and its four screws, seen in photograph 02.
  const [cx, cy] = at(0.45, 0.47);
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
  // The power connector on the near edge, seen in photograph 02.
  const [px, py] = at(0.88, 1.0);
  svg.appendChild(make("rect", { x: px - 22, y: py - 2, width: 44, height: 14, rx: 3, class: "wire-line" }));
  // The two coolant tubes, which leave the near edge for the radiator at the
  // bottom of the case: seen in photographs 05, 06 and 07.
  for (const along of [0.35, 0.44]) {
    const [tx, ty] = at(along, 1.0);
    svg.appendChild(make("rect", { x: tx - 9, y: ty - 2, width: 18, height: 30, rx: 8, class: "wire-tube" }));
  }
  const [tubeX, tubeY] = at(0.395, 1.0);
  svg.appendChild(
    make("text", { x: tubeX, y: tubeY + 44, class: "wire-edge", "text-anchor": "middle" }, "tubes to the radiator"),
  );
  // The card's one fan is on the far face, seen in photograph 07. Drawn
  // dashed, because it is on the other side of the card from this view.
  const [fx, fy] = at(0.73, 0.5);
  svg.appendChild(make("circle", { cx: fx, cy: fy, r: 45 * MM, class: "wire-fan" }));
  svg.appendChild(
    make("text", { x: fx, y: fy + 45 * MM + 16, class: "wire-edge", "text-anchor": "middle" },
      "fan, on the far face"),
  );
  // The words on the two long edges.
  svg.appendChild(
    make("text", { x: (x0 + x1) / 2, y: y0 - 10, class: "wire-edge", "text-anchor": "middle" },
      "this edge goes into the motherboard slot"),
  );
  svg.appendChild(
    make("text", { x: x0 + 70, y: y1 + 20, class: "wire-edge", "text-anchor": "middle" },
      "this edge faces the side glass"),
  );
  // The size, from MSI's specification.
  svg.appendChild(make("line", { x1: x0, y1: y1 + 52, x2: x1, y2: y1 + 52, class: "wire-dim" }));
  svg.appendChild(
    make("text", { x: (x0 + x1) / 2, y: y1 + 68, class: "wire-edge", "text-anchor": "middle" },
      "280 mm, and 140 mm across; one fan on the far face, two more on the radiator below the card"),
  );
}
