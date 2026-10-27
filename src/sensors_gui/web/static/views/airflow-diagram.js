/*
 * The case from the side, with every fan, the way the air goes, and a dot
 * where a reading belongs.
 *
 * The fans and the air are Gova's own trace with a string (2026-09-23), in
 * the CORRECTION table of `docs/physical-build.md`: 3 in at the front, 1 out
 * at the rear, 3 out through the top on the CPU cooler's radiator, 2 on the
 * card's radiator at the bottom blowing down, and 1 on the card's underside.
 * The drawing looks in through the side glass, as photograph 04 does: the
 * rear is on the left, where the card's output bracket is, and the front is
 * on the right. It is a schematic, not to scale.
 *
 * **A dot sits on a group of fans only where a source says which reading it
 * is.** The card's two NVML channels drive the card's three fans
 * (`exp-0017`), so one dot sits between them, with both channels. Which board
 * header drives which fans is Q20, not established, so the four live headers
 * are in a dashed box under the case. When Gova settles Q20, a header's
 * `fans` names its group and its dot moves onto the drawing.
 * `docs/diagram-positions.md` holds every claim and its source.
 *
 * Gova, 2026-09-25: values on the drawing, so it says something without a
 * hover. Every value here is also in the cards of the view.
 */

import { colourOf, formatValue, setText, stateOf } from "../widgets.js";
import { Dots, make } from "./dots.js";

/**
 * The fans of the case, one row for each row of the CORRECTION table in
 * `docs/physical-build.md`, with the same words. A test holds the two equal.
 */
export const AIRFLOW = [
  { id: "front", count: 3, where: "front", air: "in", serves: "the case" },
  { id: "rear", count: 1, where: "rear", air: "out", serves: "the case" },
  { id: "top", count: 3, where: "top, on the CPU cooler's radiator", air: "out", serves: "the CPU" },
  {
    id: "card-radiator",
    count: 2,
    where: "bottom, on the graphics card's radiator",
    air: "out",
    serves: "the graphics card",
  },
  { id: "card", count: 1, where: "on the graphics card, underside", air: "down", serves: "the graphics card" },
  { id: "pump", count: 0, where: "the CPU cooler's pump", air: null, serves: "the CPU" },
];

/**
 * The board's fan headers that read a fan, and the fans each one drives.
 * `fans` is null while Q20 is open: no source says which fans are on which
 * header (`lab/exp-0020-case-cooler-identity/README.md`).
 */
export const HEADERS = [
  { header: "CPU_FAN1", label: "CPU Fan", fans: null },
  { header: "PUMP_SYS1", label: "Pump Fan", fans: null },
  { header: "SYS_FAN1", label: "System Fan #1", fans: null },
  { header: "JAF_1", label: "EZ Conn Fan", fans: null },
];

/** The files the drawing's claims rest on; a test checks each one exists. */
export const SOURCES = [
  "docs/physical-build.md",
  "docs/photos/04-full-interior.jpg",
  "lab/exp-0017-gpu-fan-channels/README.md",
  "lab/exp-0020-case-cooler-identity/README.md",
  "docs/diagram-positions.md",
];

const WIDTH = 1000;
const HEIGHT = 830;
// The case, inside the margin the arrows need.
const X0 = 110;
const X1 = 880;
const Y0 = 120;
const Y1 = 640;

/** Where each group of fans is drawn, and where its dot goes when it has one. */
const PLACES = {
  front: { dot: [864, 375] },
  rear: { dot: [126, 245] },
  top: { dot: [534, 158] },
  "card-radiator": { dot: [500, 502] },
  card: { dot: [520, 427] },
  pump: { dot: [330, 250] },
};

/**
 * Build the drawing.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the drawing
 */
export function airflowDiagram(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "wireframe";
  const svg = make("svg", { viewBox: `0 0 ${WIDTH} ${HEIGHT}`, class: "wire", role: "img" });
  svg.appendChild(make("title", {}, "The case from the side: every fan, the way the air goes, and the fan readings"));
  element.appendChild(svg);
  const dots = new Dots(element, svg, WIDTH, HEIGHT, stream);
  const values = [];

  /** Write a reading on the drawing, in the colour of its state. */
  const plate = (x, y, channel, prefix, anchor = "start") => {
    const text = make("text", { x, y, class: "wire-value wire-value-small", "text-anchor": anchor }, "—");
    svg.appendChild(text);
    values.push({ text, channel, prefix });
  };

  drawCase(svg);

  // --- the card's fans: one dot for its two channels ------------------------
  const fan1 = catalogue.byLabel("GPU fan 1");
  const fan2 = catalogue.byLabel("GPU fan 2");
  const [cx, cy] = [530, 462];
  dots.add(
    {
      id: "card-fans",
      name: "The graphics card's 3 fans, on 2 channels",
      basis:
        "The card's two NVML fan channels drive its three fans: one on its underside and two on its radiator " +
        "(lab/exp-0017-gpu-fan-channels, docs/physical-build.md). Which channel drives which fans is not " +
        "established (Q14), so the dot sits between the two groups, not on one.",
      rows: [
        { label: "GPU fan 1", channel: fan1 },
        { label: "GPU fan 1 duty", channel: catalogue.byLabel("GPU fan 1 duty") },
        { label: "GPU fan 2", channel: fan2 },
        { label: "GPU fan 2 duty", channel: catalogue.byLabel("GPU fan 2 duty") },
      ],
    },
    cx,
    cy,
  );
  plate(cx + 18, cy - 4, fan1, "fan 1 ");
  plate(cx + 18, cy + 14, fan2, "fan 2 ");

  // --- the board's headers: on a group when Q20 says which, else in the box -
  const boxTop = Y1 + 30;
  const unplaced = HEADERS.filter((entry) => entry.fans === null);
  if (unplaced.length > 0) {
    svg.appendChild(make("rect", { x: X0, y: boxTop, width: X1 - X0, height: 140, rx: 10, class: "wire-unplaced" }));
    svg.appendChild(
      make("text", { x: X0 + 14, y: boxTop + 22, class: "wire-title" },
        "Board fan headers: which fans each one drives is not established (Q20)"),
    );
    svg.appendChild(
      make("text", { x: X0 + 14, y: boxTop + 128, class: "wire-edge" },
        "SYS_FAN2 to SYS_FAN6 read 0 RPM: nothing is on them, and the BIOS agrees. Hover a dot for its reading."),
    );
  }
  const step = (X1 - X0) / Math.max(unplaced.length, 1);
  HEADERS.forEach((entry) => {
    const channel = catalogue.byLabel(entry.label);
    const part = {
      id: entry.header,
      name: `${entry.header} · ${entry.label}`,
      basis:
        entry.fans === null
          ? "One tachometer on this board header. Which fans it drives is not established (Q20); the readings " +
            "of lab/exp-0020-case-cooler-identity do not fit the cooler's manual well."
          : `The fans on this header, settled in Q20: ${entry.fans}.`,
      rows: [{ label: "Speed", channel }],
    };
    if (entry.fans !== null) {
      const [x, y] = PLACES[entry.fans].dot;
      dots.add(part, x, y);
      plate(x + 14, y + 20, channel, `${entry.header} `);
      return;
    }
    const x = X0 + step * (unplaced.indexOf(entry) + 0.5);
    dots.add(part, x, boxTop + 52);
    svg.appendChild(
      make("text", { x, y: boxTop + 82, class: "wire-dot-name", "text-anchor": "middle" }, part.name),
    );
    plate(x, boxTop + 102, channel, "", "middle");
  });

  return {
    element,
    update() {
      dots.update();
      for (const { text, channel, prefix } of values) {
        const value = stream.value(channel);
        setText(text, channel ? `${prefix}${formatValue(value, channel)}` : `${prefix}not found`);
        const state = channel ? stateOf(value, channel, stream.extra(channel)) : "unavailable";
        if (text.dataset.state !== state) {
          text.dataset.state = state;
          text.style.fill = colourOf(state);
        }
      }
    },
  };
}

/** One fan seen edge-on: a box with its hub. */
function fan(svg, x, y, width, height) {
  svg.appendChild(make("rect", { x, y, width, height, rx: 4, class: "wire-fanbox" }));
  const across = width > height;
  svg.appendChild(
    make("line", across
      ? { x1: x + width / 2, y1: y + 3, x2: x + width / 2, y2: y + height - 3, class: "wire-line" }
      : { x1: x + 3, y1: y + height / 2, x2: x + width - 3, y2: y + height / 2, class: "wire-line" }),
  );
}

/** One arrow of air, from one point to another. */
function air(svg, x1, y1, x2, y2) {
  svg.appendChild(make("line", { x1, y1, x2, y2, class: "wire-air", "marker-end": "url(#air-head)" }));
}

/** Draw the case, its parts, its fans and the air. */
function drawCase(svg) {
  const defs = make("defs");
  const marker = make("marker", {
    id: "air-head",
    viewBox: "0 0 10 10",
    refX: 9,
    refY: 5,
    markerWidth: 7,
    markerHeight: 7,
    orient: "auto-start-reverse",
  });
  marker.appendChild(make("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "wire-air-head" }));
  defs.appendChild(marker);
  svg.appendChild(defs);

  svg.appendChild(make("text", { x: 20, y: 24, class: "wire-caption" }, "The case from the side · every fan and the air"));
  svg.appendChild(
    make("text", { x: 20, y: 44, class: "wire-note" },
      "Gova's trace of the air, docs/physical-build.md. Seen through the side glass as in photograph 04; not to scale."),
  );

  svg.appendChild(make("rect", { x: X0, y: Y0, width: X1 - X0, height: Y1 - Y0, rx: 10, class: "wire-card" }));
  svg.appendChild(make("text", { x: X0 + 4, y: Y1 + 18, class: "wire-edge" }, "rear"));
  svg.appendChild(make("text", { x: X1 - 4, y: Y1 + 18, class: "wire-edge", "text-anchor": "end" }, "front"));

  // The motherboard behind everything, and the pump on the processor.
  svg.appendChild(make("rect", { x: 180, y: 180, width: 420, height: 340, rx: 4, class: "wire-board" }));
  svg.appendChild(make("text", { x: 190, y: 198, class: "wire-edge" }, "motherboard"));
  svg.appendChild(make("circle", { cx: 330, cy: 250, r: 30, class: "wire-line" }));
  svg.appendChild(make("text", { x: 370, y: 248, class: "wire-dot-name" }, "pump, on the processor"));
  svg.appendChild(make("text", { x: 370, y: 264, class: "wire-edge" }, "tubes to the top radiator"));

  // Top: the CPU cooler's radiator under the top panel, its 3 fans under it.
  svg.appendChild(make("rect", { x: 300, y: 126, width: 470, height: 20, rx: 3, class: "wire-radiator" }));
  for (const x of [305, 460, 615]) fan(svg, x, 148, 148, 20);
  svg.appendChild(make("text", { x: 300, y: 186, class: "wire-dot-name" }, "3 fans on the CPU radiator · out, through the top"));
  for (const x of [379, 534, 689]) air(svg, x, 118, x, 70);

  // Rear: 1 fan, out.
  fan(svg, 116, 170, 20, 150);
  svg.appendChild(make("text", { x: 142, y: 336, class: "wire-dot-name" }, "rear fan · out"));
  air(svg, 108, 245, 44, 245);

  // Front: 3 fans, in.
  for (const y of [140, 300, 460]) fan(svg, 854, y, 20, 150);
  svg.appendChild(make("text", { x: 996, y: 295, class: "wire-dot-name", "text-anchor": "end" }, "3 front fans · in"));
  for (const y of [215, 375, 535]) air(svg, 960, y, 886, y);

  // The graphics card, its output bracket at the rear, and its fan underneath.
  svg.appendChild(make("rect", { x: 160, y: 370, width: 8, height: 60, rx: 2, class: "wire-line" }));
  svg.appendChild(make("rect", { x: 170, y: 380, width: 470, height: 40, rx: 4, class: "wire-card" }));
  svg.appendChild(make("text", { x: 185, y: 405, class: "wire-dot-name" }, "graphics card"));
  fan(svg, 470, 422, 100, 10);
  svg.appendChild(make("text", { x: 465, y: 436, class: "wire-edge", "text-anchor": "end" }, "its fan · down"));
  air(svg, 450, 440, 450, 486);

  // Bottom: the card's radiator on the shroud, 2 fans on it, blowing down.
  for (const x of [360, 505]) fan(svg, x, 492, 135, 20);
  svg.appendChild(make("rect", { x: 355, y: 514, width: 290, height: 20, rx: 3, class: "wire-radiator" }));
  svg.appendChild(
    make("text", { x: 350, y: 528, class: "wire-edge", "text-anchor": "end" }, "card's radiator, 2 fans · down"),
  );
  svg.appendChild(make("line", { x1: X0, y1: 545, x2: 830, y2: 545, class: "wire-line" }));
  svg.appendChild(make("rect", { x: 130, y: 560, width: 200, height: 64, rx: 4, class: "wire-line" }));
  svg.appendChild(make("text", { x: 140, y: 596, class: "wire-edge" }, "power supply, NZXT C1200"));
  svg.appendChild(make("text", { x: 700, y: 596, class: "wire-edge", "text-anchor": "middle" }, "drive bay, under the shroud"));
  for (const x of [430, 570]) air(svg, x, 538, x, 600);
}
