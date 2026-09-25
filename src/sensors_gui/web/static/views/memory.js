/*
 * The memory view: the two DDR5 modules, and what the system does with them.
 *
 * It keeps the rules the graphics card view set at checkpoint 3: every
 * channel on screen with the tooltip of `docs/gui-goal.md` 4.2, a meter only
 * where the spec carries a scale, related values together.
 *
 * Two kinds of reading live here and are kept apart on screen. The module
 * temperatures are sensors on the hardware, one on each module. The rest is
 * the kernel's account of memory across both modules together; no channel
 * says how much of it is on one module.
 *
 * Gova, 2026-09-25: the first version was "subpar". It gave the kernel's
 * account as a list of eight numbers, and nothing showed how the memory
 * divides; two thirds of the screen was empty. He chose three changes: one
 * bar that divides the memory, with large figures above it; the temperature
 * of each module on the drawing; and memory pressure, which says whether
 * tasks had to wait for memory, not only how much is in use.
 */

import { StackBar, formatValue, setText } from "../widgets.js";
import { memoryDiagram } from "./memory-diagram.js";
import { attachTooltip } from "../tooltip.js";
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
 * Return the three parts of the memory bar: in use, what the kernel can take
 * back, and free. They add up to the total.
 *
 * psutil 7.2.2 gives Memory used as total less available, so the part the
 * kernel can take back is available less free. Two readings of one pass can
 * disagree by a page, so that part never goes below 0.
 *
 * @param {number|null} used Memory used
 * @param {number|null} available Memory available
 * @param {number|null} free Memory free
 * @returns {number[]|null} the three parts, or null when a reading is missing
 */
export function memorySplit(used, available, free) {
  if ([used, available, free].some((value) => value === null || value === undefined)) return null;
  return [used, Math.max(available - free, 0), free];
}

/**
 * Build the channel-like object of the part the kernel can take back. It is
 * made from two channels; its text comes from Python (`DERIVED` in
 * `descriptions.py`), like every other tooltip.
 */
function reclaimableChannel(catalogue, available, free) {
  if (!available || !free) return null;
  return {
    label: "Memory the kernel can take back",
    key: "derived:memory:reclaimable",
    source: "derived",
    unit: available.unit,
    symbol: available.symbol,
    decimals: available.decimals,
    low: null,
    high: null,
    warn: null,
    critical: null,
    min_interval: 0,
    origin: "Memory available - Memory free",
    description: catalogue.derived.memory_reclaimable ?? null,
    derive: (stream) => memorySplit(0, stream.value(available), stream.value(free))?.[1] ?? null,
  };
}

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

  const drawing = drawingCard(catalogue, stream, painters);
  const split = splitCard(catalogue, stream, build, painters);

  // --- module temperatures -------------------------------------------------
  const heat = card("Module temperature", "one sensor on each module");
  heat.element.classList.add("card-wide");
  const a2 = byLabel("DIMM A2");
  const b2 = byLabel("DIMM B2");
  build.show(heat.body, a2, "DIMM A2");
  build.show(heat.body, b2, "DIMM B2");
  build.chart(heat.body, a2, "Both modules, on one axis", {
    firstLabel: "A2",
    others: [{ channel: b2, label: "B2", token: "--series-2" }],
  });

  const pressure = pressureCard(catalogue, build);

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

  for (const built of [drawing, split, heat, pressure, swap]) element.appendChild(built.element);

  return {
    element,
    update() {
      for (const paint of painters) paint();
    },
  };
}

/** The drawing of the four slots, with the fixed facts of the modules under it. */
function drawingCard(catalogue, stream, painters) {
  const drawing = card("The modules", "hover a module for its reading; every value is also in the cards");
  // Two cells wide and one row high: two rows left an empty space under it.
  drawing.element.classList.add("card-wide");
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
  return drawing;
}

/**
 * The card that shows how the memory divides: the large figures, the bar,
 * and the rest of the kernel's account.
 */
function splitCard(catalogue, stream, build, painters) {
  const byLabel = (label) => catalogue.byLabel(label);
  const total = byLabel("Memory total");
  const used = byLabel("Memory used");
  const available = byLabel("Memory available");
  const free = byLabel("Memory free");
  const reclaimable = reclaimableChannel(catalogue, available, free);

  const split = card("Where the memory is", "the kernel's account, across both modules");
  split.element.classList.add("card-span-3");

  const tiles = document.createElement("div");
  tiles.className = "tile-row tile-row-wide";
  split.body.appendChild(tiles);
  for (const label of ["Memory used", "Memory available", "Memory cached", "Memory free"]) {
    build.show(tiles, byLabel(label), label);
  }

  if (total && used && reclaimable && free) {
    const bar = new StackBar({
      spec: total,
      parts: [
        { label: "In use", token: "--series" },
        { label: "The kernel can take back (available less free)", token: "--series-deep" },
        { label: "Free", token: "--axis" },
      ],
    });
    split.body.appendChild(bar.element);
    [used, reclaimable, free].forEach((channel, index) => {
      attachTooltip(bar.segments[index], channel, stream);
      attachTooltip(bar.keys[index].line, channel, stream);
    });
    painters.push(() =>
      bar.update(stream.value(total), memorySplit(stream.value(used), stream.value(available), stream.value(free))),
    );
  }

  // Memory use is the first part of the bar as a percent, so it is a line
  // here and not a second bar.
  const account = document.createElement("div");
  account.className = "fact-row";
  split.body.appendChild(account);
  for (const label of ["Memory use", "Memory total", "Memory buffers", "Memory shared"]) {
    build.fact(account, byLabel(label), label);
  }
  build.chart(split.body, used, "In use and available, on one axis", {
    firstLabel: "in use",
    others: [{ channel: available, label: "available", token: "--series-2" }],
  });
  return split;
}

/** The card that says whether tasks waited for memory, and how often a page was missing. */
function pressureCard(catalogue, build) {
  const byLabel = (label) => catalogue.byLabel(label);
  const pressure = card("Memory pressure", "the part of the time tasks waited for memory, from /proc/pressure");
  pressure.element.classList.add("card-wide");
  const table = document.createElement("div");
  table.className = "cell-table";
  pressure.body.appendChild(table);
  const windows = ["10", "60", "300"];
  for (const heading of ["", ...windows.map((window) => `over ${window} s`)]) {
    const head = document.createElement("span");
    head.className = "cell-head";
    head.textContent = heading;
    table.appendChild(head);
  }
  for (const [kind, words] of [
    ["some", "some tasks waited"],
    ["full", "all tasks waited"],
  ]) {
    const name = document.createElement("span");
    name.className = "cell-name";
    name.textContent = words;
    table.appendChild(name);
    for (const window of windows) build.cell(table, byLabel(`Memory pressure, ${kind}, ${window} s`));
  }
  const some = byLabel("Memory pressure, some, 10 s");
  build.chart(pressure.body, some, "Over 10 s, both lines on one axis", {
    firstLabel: "some",
    others: [{ channel: byLabel("Memory pressure, full, 10 s"), label: "full", token: "--series-2" }],
    height: 130,
  });
  const faults = document.createElement("div");
  faults.className = "tile-row";
  pressure.body.appendChild(faults);
  build.show(faults, byLabel("Page faults"), "Page faults");
  build.show(faults, byLabel("Major page faults"), "Major page faults");
  return pressure;
}
