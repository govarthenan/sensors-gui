/*
 * The processor view: every channel of the AMD Ryzen 9 9900X, grouped, drawn
 * and explained.
 *
 * It keeps the rules the graphics card view set at checkpoint 3:
 *
 *   - Every channel is on screen, and each one has the tooltip of
 *     `docs/gui-goal.md` 4.2. `tests/test_descriptions.py` holds the count.
 *   - A meter only where the spec carries a scale; a number and a line
 *     elsewhere. A state only from a published threshold, and k10temp
 *     publishes none, so no processor temperature is ever called warm.
 *   - Related values sit together: each die's temperature beside the control
 *     value, the package beside the sum of its cores, a frequency against the
 *     processor's own lowest and highest.
 *
 * Gova, 2026-09-23: "Display at the sensor level granularity." A column is
 * one channel, never a figure made from two: use and frequency get a column
 * for each of the 24 threads, power one for each of the 12 cores.
 */

import { CORES, DIE_NAME, corePowerColumns, threadColumns } from "../topology.js";
import { formatValue, setText } from "../widgets.js";
import { attachTooltip } from "../tooltip.js";
import { cpuDiagram } from "./cpu-diagram.js";
import { builders, card, factLine } from "./parts.js";

/** The fixed facts of the processor, each from a file in this repository. */
const IDENTITY = [
  ["Model", "AMD Ryzen 9 9900X (Zen 5, Granite Ridge)", "docs/hardware-inventory.md"],
  ["Family / model / stepping", "26 / 68 / 0", "docs/hardware-inventory.md"],
  ["Cores / threads", "12 / 24, on 2 core dies", "docs/hardware-inventory.md"],
  ["Thread pairs", "cpuN and cpuN+12 are one core", "data/probes/2026-09-22-cpu-topology.txt"],
  ["Frequency range", "613.95 MHz to 5662.02 MHz, boost on", "docs/hardware-inventory.md"],
  ["Cache", "L2 12 MiB, L3 64 MiB in 2 instances", "docs/hardware-inventory.md"],
  ["Scaling driver", "amd-pstate-epp, governor performance", "docs/hardware-inventory.md"],
  ["Board fan curve source", "CPU Core, in the BIOS", "docs/hardware-inventory.md"],
];

/**
 * Return a function that finds the thread with the highest or lowest reading.
 *
 * @param {Array<object>} columns the thread columns
 * @param {import("../stream.js").Stream} stream the live frames
 * @param {number} sign 1 for the highest, -1 for the lowest
 */
function extreme(columns, stream, sign) {
  return () => {
    let found = null;
    for (const column of columns) {
      const value = stream.value(column.channel);
      if (value === null) continue;
      if (found === null || sign * value > sign * found.value) found = { column, value };
    }
    return found;
  };
}

/**
 * Build the processor view.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the view
 */
export function cpuView(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "view view-detail";
  const painters = [];
  const build = builders(stream, painters);
  const byLabel = (label) => catalogue.byLabel(label);

  // --- the drawing ---------------------------------------------------------
  const drawing = card("The processor", "hover a part for its readings; every value is also in the cards");
  drawing.element.classList.add("card-diagram");
  const diagram = cpuDiagram(catalogue, stream);
  drawing.body.appendChild(diagram.element);
  painters.push(() => diagram.update());
  const identity = document.createElement("div");
  identity.className = "identity";
  const heading = document.createElement("h4");
  heading.textContent = "Fixed facts about this processor — hover a line for its source";
  identity.appendChild(heading);
  for (const [label, value, source] of IDENTITY) {
    const { row, value: target } = factLine(label, `source: ${source}`);
    target.textContent = value;
    identity.appendChild(row);
  }
  drawing.body.appendChild(identity);

  // --- temperature --------------------------------------------------------
  const heat = card("Temperature", "the control value, and one sensor for each core die");
  const tctl = byLabel("Tctl");
  const tccd1 = byLabel("Tccd1");
  const tccd2 = byLabel("Tccd2");
  const tiles = document.createElement("div");
  tiles.className = "tile-row";
  heat.body.appendChild(tiles);
  for (const [label, channel] of [
    ["Tctl", tctl],
    ["Tccd1", tccd1],
    ["Tccd2", tccd2],
  ]) {
    build.show(tiles, channel, label);
  }
  build.chart(heat.body, tctl, "All three, on one axis", {
    others: [
      { channel: tccd1, label: "Tccd1", token: "--series-2" },
      { channel: tccd2, label: "Tccd2", token: "--series-3" },
    ],
  });
  const heatNote = document.createElement("p");
  heatNote.className = "absent";
  heatNote.textContent =
    "k10temp gives no temperature for each core: one for each die, and Tctl. It publishes no threshold for " +
    "any of the three, so no state is judged here.";
  heat.body.appendChild(heatNote);

  // --- power --------------------------------------------------------------
  const power = card("Power", "the package, the sum of its cores, and core 0 read two ways");
  const packagePower = byLabel("CPU Package Power");
  const coresPower = byLabel("CPU Cores Power");
  const powerTiles = document.createElement("div");
  powerTiles.className = "tile-row";
  power.body.appendChild(powerTiles);
  build.show(powerTiles, packagePower, "CPU Package Power");
  build.show(powerTiles, coresPower, "CPU Cores Power");
  build.chart(power.body, packagePower, "Package and cores, on one axis", {
    firstLabel: "Package",
    others: [{ channel: coresPower, label: "Cores", token: "--series-2" }],
  });
  build.fact(power.body, byLabel("CPU Core 0 (RAPL) Power"), "Core 0, from the RAPL core domain");
  build.fact(power.body, byLabel("CPU Core 0 Power"), "Core 0, from its own energy register");
  build.fact(power.body, byLabel("CPU Package Energy"), "Package energy counter");
  build.fact(power.body, byLabel("CPU Core 0 (RAPL) Energy"), "Core 0 (RAPL) energy counter");

  // --- power of each core -------------------------------------------------
  const corePower = card("Power of each core", "12 columns, one for each core's energy register");
  const powerColumns = corePowerColumns(catalogue);
  build.bars(corePower.body, powerColumns, { high: null, floor: 2, height: 170 });
  const corePowerNote = document.createElement("p");
  corePowerNote.className = "absent";
  corePowerNote.textContent =
    "One scale for every column. No limit for one core is published, so the top of the axis follows the " +
    "largest reading of the last minute and only moves when a column leaves it. Hover or tab to a column.";
  corePower.body.appendChild(corePowerNote);

  // --- use of each thread -------------------------------------------------
  const use = card("Use of each thread", "24 columns; the two threads of a core side by side");
  use.element.classList.add("card-span-3");
  build.show(use.body, byLabel("CPU use"), "CPU use");
  const useColumns = threadColumns(catalogue);
  build.bars(use.body, useColumns, { high: 100, height: 170 });

  // --- load average -------------------------------------------------------
  const load = card("Load average", "of the last 1, 5 and 15 minutes, from /proc/loadavg");
  const [load1, load5, load15] = [1, 5, 15].map((minutes) => byLabel(`Load average (${minutes} min)`));
  for (const [minutes, channel] of [
    [1, load1],
    [5, load5],
    [15, load15],
  ]) {
    build.fact(load.body, channel, `Over ${minutes} min`);
  }
  build.chart(load.body, load1, "All three, on one axis", {
    firstLabel: "1 min",
    others: [
      { channel: load5, label: "5 min", token: "--series-2" },
      { channel: load15, label: "15 min", token: "--series-3" },
    ],
  });

  // --- frequency of each thread -------------------------------------------
  const frequency = card("Frequency of each thread", "24 columns, from the lowest to the highest the processor allows");
  frequency.element.classList.add("card-span-3");
  const frequencyColumns = CORES.flatMap((core) =>
    core.threads.map((thread, position) => ({
      label: `core ${core.core}, thread ${thread}`,
      channel: byLabel(`CPU${thread} frequency`),
      group: DIE_NAME[core.die],
      tick: position === 0 ? String(core.core) : false,
    })),
  ).filter((column) => column.channel !== null);
  const scaleOf = frequencyColumns[0]?.channel ?? null;
  if (scaleOf !== null) {
    build.bars(frequency.body, frequencyColumns, { low: scaleOf.low, high: scaleOf.high, height: 170 });
  }
  for (const [name, sign] of [
    ["Fastest thread now", 1],
    ["Slowest thread now", -1],
  ]) {
    const find = extreme(frequencyColumns, stream, sign);
    const { row, value } = factLine(name);
    frequency.body.appendChild(row);
    attachTooltip(row, () => find()?.column.channel ?? null, stream);
    painters.push(() => {
      const found = find();
      setText(value, found === null ? "—" : `${formatValue(found.value, found.column.channel)} — ${found.column.label}`);
    });
  }
  const frequencyNote = document.createElement("p");
  frequencyNote.className = "absent";
  frequencyNote.textContent =
    "The kernel's reading can pass the top of the scale by a little: up to 2.23 % in 28 800 readings " +
    "(data/probes/2026-09-23-cpu-frequency-margin.txt). A column that does gets a cap. The alert log waits " +
    "for 10 % past a limit on these channels, on Gova's decision of 2026-09-23.";
  frequency.body.appendChild(frequencyNote);

  for (const built of [drawing, corePower, heat, power, frequency, use, load]) element.appendChild(built.element);

  return {
    element,
    update() {
      for (const paint of painters) paint();
    },
  };
}

