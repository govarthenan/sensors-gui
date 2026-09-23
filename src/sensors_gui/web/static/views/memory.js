/*
 * The memory view: the two DDR5 modules, and what the system does with them.
 *
 * It keeps the rules the graphics card view set at checkpoint 3: every
 * channel on screen with the tooltip of `docs/gui-goal.md` 4.2, a meter only
 * where the spec carries a scale, related values together.
 *
 * Two kinds of reading live here and are kept apart on screen. The module
 * temperatures are sensors on the hardware, one on each module. The rest is
 * the kernel's account of memory use across both modules together; no
 * channel says how much of it is on one module.
 */

import { formatValue, setText } from "../widgets.js";
import { memoryDiagram } from "./memory-diagram.js";
import { builders, card, factLine } from "./parts.js";

/** The fixed facts of the memory, each from a file in this repository. */
const IDENTITY = [
  ["Modules", "2 x 32 GB TEAM GROUP UD5-6400, DDR5", "docs/hardware-inventory.md"],
  ["Slots", "DIMMA2 and DIMMB2; A1 and B1 empty", "docs/hardware-inventory.md"],
  ["Speed", "6400 MT/s configured, 5200 MT/s rated: an EXPO or XMP profile is on", "docs/hardware-inventory.md"],
  ["Voltage", "1.1 V configured", "docs/hardware-inventory.md"],
  ["Rank", "2 per module", "docs/hardware-inventory.md"],
  ["Sensor of each module", "SPD hub, i2c 0-0051 (A2) and 0-0053 (B2)", "docs/hardware-inventory.md"],
];

/**
 * Build the memory view.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the view
 */
export function memoryView(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "view view-detail";
  const painters = [];
  const build = builders(stream, painters);
  const byLabel = (label) => catalogue.byLabel(label);

  // --- the drawing ---------------------------------------------------------
  const drawing = card("The modules", "hover a module for its reading; every value is also in the cards");
  drawing.element.classList.add("card-diagram");
  const diagram = memoryDiagram(catalogue, stream);
  drawing.body.appendChild(diagram.element);
  painters.push(() => diagram.update());
  const identity = document.createElement("div");
  identity.className = "identity";
  const heading = document.createElement("h4");
  heading.textContent = "Fixed facts about the memory — hover a line for its source";
  identity.appendChild(heading);
  for (const [label, value, source] of IDENTITY) {
    const { row, value: target } = factLine(label, `source: ${source}`);
    target.textContent = value;
    identity.appendChild(row);
  }
  drawing.body.appendChild(identity);

  // --- module temperatures -------------------------------------------------
  const heat = card("Module temperature", "one sensor on each module");
  const a2 = byLabel("DIMM A2");
  const b2 = byLabel("DIMM B2");
  build.show(heat.body, a2, "DIMM A2");
  build.show(heat.body, b2, "DIMM B2");
  build.chart(heat.body, a2, "Both modules, on one axis", {
    firstLabel: "A2",
    others: [{ channel: b2, label: "B2", token: "--series-2" }],
  });

  // --- system memory ------------------------------------------------------
  const system = card("System memory", "the kernel's account, across both modules");
  build.show(system.body, byLabel("Memory use"), "Memory use");
  for (const label of [
    "Memory total",
    "Memory used",
    "Memory available",
    "Memory free",
    "Memory cached",
    "Memory buffers",
    "Memory shared",
  ]) {
    build.fact(system.body, byLabel(label), label);
  }
  build.chart(system.body, byLabel("Memory used"), "Memory used");

  // --- swap ---------------------------------------------------------------
  const swap = card("Swap", "space on the drive the kernel can move memory to");
  const swapTotal = byLabel("Swap total");
  build.show(swap.body, byLabel("Swap use"), "Swap use");
  for (const label of ["Swap total", "Swap used", "Swap free", "Swap in", "Swap out"]) {
    build.fact(swap.body, byLabel(label), label);
  }
  // A machine with no swap reads 0 on every one of these, and a row of
  // zeros must say why rather than look like an idle swap.
  const swapNote = document.createElement("p");
  swapNote.className = "absent";
  swap.body.appendChild(swapNote);
  painters.push(() => {
    const total = stream.value(swapTotal);
    setText(
      swapNote,
      total === 0
        ? "Swap total reads 0 B: this machine has no swap now, so every swap reading is 0."
        : total === null
          ? ""
          : `${formatValue(total, swapTotal)} of swap is set up.`,
    );
  });

  for (const built of [drawing, heat, system, swap]) element.appendChild(built.element);

  return {
    element,
    update() {
      for (const paint of painters) paint();
    },
  };
}
