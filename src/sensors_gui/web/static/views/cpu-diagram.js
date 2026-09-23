/*
 * The processor, drawn by its dies, with a pulsing dot on each part that has
 * a reading.
 *
 * What the drawing claims, and on what (every claim is in
 * `docs/diagram-positions.md`; the sources are in
 * `data/evidence/ryzen-9900x-package-layout-2026-09-23/`):
 *
 *   - The package is square, 40 x 40 mm (the AM5 specification, as the
 *     Socket AM5 article gives it).
 *   - The I/O die is "centrally located", and the two core dies sit "closer
 *     to each other" beside it (TechPowerUp, from annotated die shots). The
 *     I/O die above and the two core-die seats side by side below it is how a
 *     published photograph of this package shows them; that is an
 *     observation of the photograph, recorded as one, not a sentence of text.
 *   - Two core dies, with cores 0-5 on die 1 and 8-13 on die 2, and a thread
 *     pair on each core: read from this machine,
 *     `data/probes/2026-09-22-cpu-topology.txt`. `Tccd1` belongs to die 1 and
 *     `Tccd2` to die 2.
 *   - Inside a core die, the cores sit in two columns either side of the
 *     shared L3 cache (an observation of the annotated die photograph).
 *
 * What it does not claim:
 *
 *   - Which of the two seats holds die 1. The kernel numbers the dies, and no
 *     source ties a number to a seat, so they are drawn in the kernel's order.
 *   - Which core sits where on its die. Each die has 8 places and 6 cores are
 *     on; which 6 is set when the chip is made, and no source maps them. The
 *     cores are drawn in the kernel's order.
 *   - How the package turns in the socket.
 *   - Where `Tctl` is. It is "a non-physical temperature on an arbitrary
 *     scale" (the k10temp documentation), so it sits apart.
 *
 * Not to scale inside the package: dies at true size would be too small to
 * hold a dot for each core. The die areas are written on them instead.
 */

import { CORES } from "../topology.js";
import { Dots, make } from "./dots.js";

const WIDTH = 740;
const HEIGHT = 544;

/** The boxes of the drawing, in viewBox units. */
const PACKAGE = { x: 40, y: 84, width: 440, height: 440 };
const IO_DIE = { x: 150, y: 114, width: 220, height: 110 };
const DIES = {
  1: { x: 62, y: 250, width: 188, height: 245, name: "Core die 1" },
  2: { x: 270, y: 250, width: 188, height: 245, name: "Core die 2" },
};
const L3_WIDTH = 30;

/**
 * Build the drawing.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the drawing
 */
export function cpuDiagram(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "wireframe";
  const svg = make("svg", { viewBox: `0 0 ${WIDTH} ${HEIGHT}`, class: "wire", role: "img" });
  svg.appendChild(make("title", {}, "The AMD Ryzen 9 9900X by its dies, with its readings"));
  element.appendChild(svg);
  const dots = new Dots(element, svg, WIDTH, HEIGHT, stream);
  const byLabel = (label) => catalogue.byLabel(label);

  svg.appendChild(make("text", { x: 20, y: 24, class: "wire-caption" }, "AMD Ryzen 9 9900X · by its dies"));
  svg.appendChild(
    make("text", { x: 20, y: 44, class: "wire-note" }, "Die places from sources; not to scale inside the package."),
  );
  svg.appendChild(
    make("text", { x: 20, y: 62, class: "wire-note" },
      "Which seat holds die 1, and where each core sits on its die, are not established."),
  );

  // The package, and the package readings on its edge.
  svg.appendChild(make("rect", { ...PACKAGE, rx: 10, class: "wire-card" }));
  svg.appendChild(
    make("text", { x: PACKAGE.x + 12, y: PACKAGE.y + PACKAGE.height - 12, class: "wire-edge" }, "package, 40 x 40 mm"),
  );
  dots.add(
    {
      id: "package",
      name: "The whole package",
      basis: "RAPL's package domain covers the whole processor package, not one die.",
      rows: [
        ["Power", "CPU Package Power"],
        ["Energy counter", "CPU Package Energy"],
        ["Sum of the 12 cores", "CPU Cores Power"],
        ["Use, all threads", "CPU use"],
        ["Load average, 1 min", "Load average (1 min)"],
      ].map(([label, name]) => ({ label, channel: byLabel(name) })),
    },
    PACKAGE.x + PACKAGE.width - 20,
    PACKAGE.y + 20,
  );

  // The I/O die: no reading of its own on this machine.
  svg.appendChild(make("rect", { ...IO_DIE, rx: 6, class: "wire-line" }));
  svg.appendChild(
    make("text", { x: IO_DIE.x + IO_DIE.width / 2, y: IO_DIE.y + IO_DIE.height / 2, class: "wire-edge",
      "text-anchor": "middle" }, "I/O die, 6 nm, 122 mm²: no reading"),
  );

  // The two core dies, each with its temperature and its six cores.
  for (const [die, box] of Object.entries(DIES)) {
    svg.appendChild(make("rect", { ...box, rx: 6, class: "wire-line" }));
    svg.appendChild(make("text", { x: box.x + 10, y: box.y + 18, class: "wire-dot-name" }, box.name));
    const temperature = byLabel(`Tccd${die}`);
    dots.add(
      {
        id: `ccd${die}`,
        name: `${box.name}, temperature Tccd${die}`,
        basis:
          `Tccd${die} belongs to core die ${die}, which holds cores ${die === "1" ? "0-5" : "8-13"} ` +
          "(data/probes/2026-09-22-cpu-topology.txt). Which seat holds this die, and where on it the sensor " +
          "sits, are not established.",
        rows: [{ label: "Temperature", channel: temperature }],
      },
      box.x + box.width - 18,
      box.y + 14,
    );
    svg.appendChild(make("text", { x: box.x + 10, y: box.y + 36, class: "wire-edge" }, "70.6 mm², 6 of 8 cores on"));
    // The shared L3 cache down the middle, the cores either side of it.
    const middle = box.x + box.width / 2;
    svg.appendChild(
      make("rect", { x: middle - L3_WIDTH / 2, y: box.y + 48, width: L3_WIDTH, height: box.height - 58, rx: 3,
        class: "wire-cell" }),
    );
    svg.appendChild(
      make("text", { x: middle, y: box.y + box.height / 2 + 24, class: "wire-edge", "text-anchor": "middle" }, "L3"),
    );
    const cores = CORES.filter((core) => String(core.die) === die);
    cores.forEach((core, index) => {
      const side = Math.floor(index / 3);
      const row = index % 3;
      const cellWidth = (box.width - L3_WIDTH - 32) / 2;
      const cx = side === 0 ? box.x + 8 : middle + L3_WIDTH / 2 + 8;
      const cy = box.y + 48 + row * 62;
      svg.appendChild(make("rect", { x: cx, y: cy, width: cellWidth, height: 54, rx: 4, class: "wire-cell" }));
      svg.appendChild(make("text", { x: cx + 6, y: cy + 15, class: "wire-edge" }, `core ${core.core}`));
      const [first, second] = core.threads;
      dots.add(
        {
          id: `core${core.core}`,
          name: `Core ${core.core}, threads ${first} and ${second}`,
          basis:
            `Core ${core.core} is on die ${die}, and cpu${first} and cpu${second} are its two threads ` +
            "(data/probes/2026-09-22-cpu-topology.txt). Drawn in the kernel's order: which of the die's 8 places " +
            "it takes is not established.",
          rows: [
            { label: "Power", channel: byLabel(`CPU Core ${core.core} Power`) },
            ...(core.core === 0 ? [{ label: "Power, RAPL core domain", channel: byLabel("CPU Core 0 (RAPL) Power") }] : []),
            { label: `Use, cpu${first}`, channel: byLabel(`CPU${first} use`) },
            { label: `Use, cpu${second}`, channel: byLabel(`CPU${second} use`) },
            { label: `Frequency, cpu${first}`, channel: byLabel(`CPU${first} frequency`) },
            { label: `Frequency, cpu${second}`, channel: byLabel(`CPU${second} frequency`) },
          ],
        },
        cx + cellWidth / 2,
        cy + 34,
      );
    });
  }

  // Tctl: a value for control, not a place.
  const apart = { x: 510, y: 80, width: 200, height: 150 };
  svg.appendChild(make("rect", { ...apart, rx: 10, class: "wire-unplaced" }));
  svg.appendChild(make("text", { x: apart.x + 12, y: apart.y + 22, class: "wire-title" }, "Not a place"));
  dots.add(
    {
      id: "tctl",
      name: "Tctl, the control temperature",
      basis:
        "The k10temp documentation, quoting AMD: Tctl is used by the platform to control cooling systems, and " +
        "is a non-physical temperature that does not represent an actual physical temperature.",
      rows: [{ label: "Tctl", channel: byLabel("Tctl") }],
    },
    apart.x + apart.width / 2,
    apart.y + 70,
  );
  svg.appendChild(
    make("text", { x: apart.x + apart.width / 2, y: apart.y + 110, class: "wire-dot-name", "text-anchor": "middle" },
      "Tctl"),
  );

  return { element, update: () => dots.update() };
}
