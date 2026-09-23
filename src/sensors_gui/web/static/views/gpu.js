/*
 * The graphics card view: every channel of the MSI RTX 4090 SUPRIM, grouped,
 * drawn, and explained.
 *
 * `docs/gui-goal.md` calls this view the reference for every other group, so
 * its rules are the rules the later views follow:
 *
 *   - Every channel the collector reads is on screen, and each one has the
 *     tooltip of section 4.2. `tests/test_descriptions.py` holds the count.
 *   - A meter only where the spec carries a scale; a number and a line
 *     elsewhere. A state only from a published threshold.
 *   - Related values sit together: power beside its limit, each fan's measured
 *     speed beside the speed the card asks of it, a clock beside its maximum,
 *     memory used beside the total.
 *   - What the card cannot give is on screen with its reason. Never a gap.
 *
 * The facts in the card below the diagram come from the probe of 2026-09-23
 * and `docs/hardware-inventory.md`; the source is named on screen.
 */

import { Meter, StatTile, Trace, formatValue, hasScale, setText } from "../widgets.js";
import { attachTooltip } from "../tooltip.js";
import { cardDiagram } from "./card-diagram.js";
import { card, factLine, missing } from "./parts.js";

/** The fixed facts of the card, each from a file in this repository. */
const IDENTITY = [
  ["Chip", "AD102, 10de:2684", "docs/hardware-inventory.md"],
  ["PCI address", "01:00.0", "docs/hardware-inventory.md"],
  ["Memory", "24564 MiB", "docs/hardware-inventory.md"],
  ["Driver", "595.91.07", "data/probes/2026-09-23-nvidia-smi-q.txt"],
  ["VBIOS", "95.02.3C.40.D1", "data/probes/2026-09-23-nvidia-smi-q.txt"],
  ["Power limit", "480 W (the card allows 150 to 530 W)", "data/probes/2026-09-23-nvidia-smi-q.txt"],
  ["Slowdown / shutdown", "99 °C / 104 °C", "lab/exp-0002-nvidia-access/README.md"],
  ["Target temperature", "84 °C", "data/probes/2026-09-23-nvidia-smi-q.txt"],
  ["Monitors", "both, on HDMI-A-1 and DP-1", "docs/hardware-inventory.md"],
];

/** The P-states NVIDIA defines: P0, the maximum performance, to P12, the minimum. */
const PSTATES = 13;

/**
 * Build the graphics card view.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the view
 */
export function gpuView(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "view view-gpu";
  const painters = [];

  // The card's channels, found by their NVML key. The integrated graphics
  // shares the GPU group and is not this card, so the source is checked too.
  const cardChannels = catalogue.where((channel) => channel.source === "nvidia");
  const find = (key) => cardChannels.find((channel) => channel.key.endsWith(`:${key}`)) ?? null;
  const missingEntries = [
    ...(catalogue.unreachable ?? []).map((entry) => ({ ...entry, missing: "unreachable" })),
    ...(catalogue.notCollected ?? []).map((entry) => ({ ...entry, missing: "not-collected" })),
  ].filter((entry) => entry.group === "gpu");
  const findMissing = (label) => missingEntries.find((entry) => entry.label === label) ?? null;

  /** Add a meter for a channel with a scale, or a tile for one without. */
  function show(body, key) {
    const channel = find(key);
    if (channel === null) {
      missing(body, key);
      return;
    }
    if (hasScale(channel)) {
      const meter = new Meter(channel);
      body.appendChild(meter.element);
      attachTooltip(meter.element, channel, stream);
      painters.push(() => meter.update(stream.value(channel), stream.extra(channel)));
    } else {
      const tile = new StatTile(channel);
      body.appendChild(tile.element);
      attachTooltip(tile.element, channel, stream);
      painters.push(() => tile.update(stream.value(channel), stream.series(channel), stream.extra(channel)));
    }
  }

  /** Add a line chart of one channel. */
  function chart(body, key, title) {
    const channel = find(key);
    if (channel === null) return;
    const trace = new Trace(channel, { width: 360, height: 150, title });
    body.appendChild(trace.element);
    attachTooltip(trace.element.querySelector("figcaption"), channel, stream);
    painters.push(() => trace.update(stream.series(channel), stream.seconds));
  }

  /** Add a line of label and value, with the channel's tooltip. */
  function fact(body, key, label, format = null) {
    const channel = find(key);
    if (channel === null) {
      missing(body, label);
      return;
    }
    const { row, value } = factLine(label);
    body.appendChild(row);
    attachTooltip(row, channel, stream);
    painters.push(() => {
      const reading = stream.value(channel);
      setText(value, reading !== null && format ? format(reading) : formatValue(reading, channel));
    });
  }

  /** Add a line for a value the card cannot give, with its reason on hover. */
  function absentLine(body, label) {
    const entry = findMissing(label);
    if (entry === null) return;
    const { row, value } = factLine(label);
    row.classList.add("fact-absent");
    value.textContent = entry.missing === "unreachable" ? "○ not readable" : "○ not collected";
    body.appendChild(row);
    attachTooltip(row, entry, stream);
  }

  // --- the diagram ---------------------------------------------------------
  const drawing = card("The card", "hover any reading for what it is and where it comes from");
  drawing.element.classList.add("card-diagram");
  const diagram = cardDiagram(find, findMissing, stream);
  drawing.body.appendChild(diagram.element);
  painters.push(() => diagram.update());

  // --- temperature --------------------------------------------------------
  const heat = card("Temperature", "one sensor; three more cannot be read");
  show(heat.body, "temperature");
  chart(heat.body, "temperature", "GPU edge");
  for (const label of ["GPU hotspot", "GPU memory (GDDR6X)", "GPU VRM"]) absentLine(heat.body, label);

  // --- power --------------------------------------------------------------
  const power = card("Power", "the whole card, against its 480 W limit");
  show(power.body, "power");
  chart(power.body, "power", "GPU power");
  fact(power.body, "energy", "Energy since the driver loaded");

  // --- the fans -----------------------------------------------------------
  const fans = card("Fans", "measured speed beside the speed the card asks for");
  fans.element.classList.add("card-wide");
  const pair = document.createElement("div");
  pair.className = "fan-pair";
  fans.body.appendChild(pair);
  for (const index of [0, 1]) {
    const column = document.createElement("div");
    column.className = "fan-column";
    pair.appendChild(column);
    show(column, `fan${index}_rpm`);
    show(column, `fan${index}_percent`);
  }
  const first = find("fan0_rpm");
  const second = find("fan1_rpm");
  if (first !== null && second !== null) {
    const trace = new Trace(first, {
      width: 520,
      height: 160,
      title: "Both fans, on one axis",
      firstLabel: "Fan 1",
      others: [{ label: "Fan 2", token: "--series-2" }],
    });
    fans.body.appendChild(trace.element);
    painters.push(() => trace.update(stream.series(first), stream.seconds, [stream.series(second)]));
  }
  fact(fans.body, "fan_speed", "GPU fan (the original channel, fan 1)");
  fact(fans.body, "temperature", "Edge temperature, for reference");
  const fanNote = document.createElement("p");
  fanNote.className = "absent";
  fanNote.textContent =
    "NVML reports 2 fans, and they do not turn at the same speed: exp-0013 measured 1205 and 1520 RPM under " +
    "one load. Both stop at idle. Which temperature the card's own fan curve follows is not established, and " +
    "neither is where each fan sits on the card.";
  fans.body.appendChild(fanNote);

  // --- load ---------------------------------------------------------------
  const load = card("Load", "percent of time each engine was busy");
  for (const key of ["utilization", "memory_utilization", "encoder_utilization", "decoder_utilization"]) {
    show(load.body, key);
  }
  const pstate = find("performance_state");
  if (pstate !== null) {
    const ladder = document.createElement("div");
    ladder.className = "pstate";
    ladder.innerHTML = `
      <div class="pstate-head"><span>Performance state</span><b>—</b></div>
      <div class="pstate-steps"></div>
      <div class="pstate-ends"><span>P0 fastest</span><span>P12 slowest</span></div>`;
    const steps = ladder.querySelector(".pstate-steps");
    const cells = [];
    for (let step = 0; step < PSTATES; step += 1) {
      const cell = document.createElement("i");
      cell.title = `P${step}`;
      steps.appendChild(cell);
      cells.push(cell);
    }
    const figure = ladder.querySelector("b");
    load.body.appendChild(ladder);
    attachTooltip(ladder, pstate, stream);
    painters.push(() => {
      const reading = stream.value(pstate);
      setText(figure, reading === null ? "—" : `P${reading}`);
      cells.forEach((cell, step) => cell.classList.toggle("is-on", step === reading));
    });
  }

  // --- memory -------------------------------------------------------------
  const memory = card("Memory", "24 GiB GDDR6X");
  show(memory.body, "memory_used");
  fact(memory.body, "memory_reserved", "Reserved by the driver and firmware");
  chart(memory.body, "memory_used", "VRAM used");

  // --- clocks -------------------------------------------------------------
  const clocks = card("Clocks", "each beside its maximum, where the card gives one");
  show(clocks.body, "clock_sm");
  chart(clocks.body, "clock_sm", "SM clock");
  show(clocks.body, "clock_memory");

  // --- PCIe and processes ---------------------------------------------------
  const link = card("PCIe link", "read every 2 s: each read measures the link for about 20 ms");
  show(link.body, "pcie_tx");
  show(link.body, "pcie_rx");
  absentLine(link.body, "PCIe link");

  const processes = card("Processes", "what holds a context on the card");
  fact(processes.body, "graphics_processes", "Graphics");
  fact(processes.body, "compute_processes", "Compute");
  const processNote = document.createElement("p");
  processNote.className = "absent";
  processNote.textContent =
    "Both monitors run from this card, so the desktop itself always holds a graphics context here.";
  processes.body.appendChild(processNote);

  // --- what the card is, under the drawing of it ------------------------------
  const identity = document.createElement("div");
  identity.className = "identity";
  const heading = document.createElement("h4");
  heading.textContent = "Fixed facts about this card — hover a line for its source";
  identity.appendChild(heading);
  for (const [label, value, source] of IDENTITY) {
    const { row, value: target } = factLine(label, `source: ${source}`);
    target.textContent = value;
    identity.appendChild(row);
  }
  absentLine(identity, "Clock event reasons");
  drawing.body.appendChild(identity);

  for (const built of [drawing, heat, power, fans, load, memory, clocks, link, processes]) {
    element.appendChild(built.element);
  }

  return {
    element,
    update() {
      for (const paint of painters) paint();
    },
  };
}
