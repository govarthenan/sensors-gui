/*
 * The summary view: the state of the whole machine on one screen.
 *
 * `docs/gui-goal.md` section 4.4 asks this screen to give the hottest part,
 * the measured power with the note that total system power cannot be read,
 * memory, storage health and every fan. It is the screen a team member sees
 * first.
 *
 * Every fact about the hardware here has a source under `docs/`. Where a
 * number cannot be read on this machine, the card says so and says why; it
 * never shows a zero in place of a value that does not exist.
 *
 * Checkpoint 3 is the standard for every view (`docs/gui-goal.md` 5), so
 * every value here carries the tooltip of section 4.2, as on the card view.
 * The one number that is no channel, the sum of the measured power, says in
 * its own tooltip how it is made.
 */

import {
  Meter,
  STATES,
  StatTile,
  Trace,
  colourOf,
  formatValue,
  hasScale,
  setText,
  stateOf,
} from "../widgets.js";
import { attachTooltip } from "../tooltip.js";
import { card, factLine, missing } from "./parts.js";

/**
 * The parts of the machine a temperature can belong to, for "the hottest part".
 *
 * A group is not enough: `Composite` and `DIMM A2` are both real places, and
 * the reader wants the place, not the driver. The names come from
 * `docs/hardware-inventory.md`.
 */
const WHERE = {
  Tctl: "CPU, control sensor",
  Tccd1: "CPU, core die 1",
  Tccd2: "CPU, core die 2",
  "GPU edge": "RTX 4090, edge sensor",
  edge: "Integrated graphics",
  Composite: "SN770, drive summary",
  "Sensor 1": "SN770, sensor 1",
  "Sensor 2": "SN770, sensor 2",
  "DIMM A2": "Memory, slot A2",
  "DIMM B2": "Memory, slot B2",
  "VRM MOS": "Motherboard, VRM",
  PCH: "Motherboard, chipset",
  System: "Motherboard, board sensor",
  "Ethernet PHY": "Motherboard, Ethernet",
};

/**
 * Build the summary view.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the view
 */
export function summaryView(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "view view-summary";
  const painters = [];

  // --- the hottest part, and the chart of it ------------------------------
  const temperatures = catalogue
    .byUnit("celsius")
    .filter((channel) => !channel.hidden && channel.label in WHERE);
  // Gova, 2026-09-22: the processor leads, not whichever sensor happens to be
  // hottest. At idle the hottest sensor on this machine is the drive, which
  // is true and is not what a person opens the screen to see. The hottest
  // sensor is still named, on the line below.
  const leadChannel = catalogue.byLabel("Tctl");
  const hot = card("Processor temperature", "every temperature on the machine, beside it");
  hot.element.classList.add("card-hero");
  hot.body.innerHTML = `
    <div class="hero">
      <div class="hero-value">—</div>
      <div class="hero-where">—</div>
      <div class="hero-state"><i></i><span></span></div>
    </div>
    <div class="hero-hottest">—</div>
    <div class="hero-rest"></div>`;
  const heroHottest = hot.body.querySelector(".hero-hottest");
  const heroValue = hot.body.querySelector(".hero-value");
  const heroWhere = hot.body.querySelector(".hero-where");
  const heroIcon = hot.body.querySelector(".hero-state i");
  const heroWord = hot.body.querySelector(".hero-state span");
  const heroRest = hot.body.querySelector(".hero-rest");

  const restRows = new Map();
  for (const channel of temperatures) {
    // The place is on screen, not in a `title`: the tooltip replaces the
    // title, and a channel not yet described would lose its place with it.
    const { row, value } = factLine(channel.label);
    const place = document.createElement("span");
    place.className = "fact-place";
    place.textContent = WHERE[channel.label];
    row.querySelector(".fact-label").append(" ", place);
    row.classList.add("fact-small");
    heroRest.appendChild(row);
    attachTooltip(row, channel, stream);
    restRows.set(channel.i, value);
  }
  attachTooltip(hot.body.querySelector(".hero"), leadChannel, stream);
  let hottestChannel = null;
  attachTooltip(heroHottest, () => hottestChannel, stream);
  painters.push(() => {
    let hottest = null;
    for (const channel of temperatures) {
      const reading = stream.value(channel);
      const target = restRows.get(channel.i);
      if (target) setText(target, formatValue(reading, channel));
      if (reading !== null && (hottest === null || reading > hottest.reading)) {
        hottest = { channel, reading };
      }
    }

    hottestChannel = hottest?.channel ?? null;

    const lead = leadChannel === null ? null : stream.value(leadChannel);
    if (leadChannel === null) {
      setText(heroValue, "—");
      setText(heroWhere, "Tctl is not on this machine");
    } else {
      const state = stateOf(lead, leadChannel, stream.extra(leadChannel));
      setText(heroValue, formatValue(lead, leadChannel));
      setText(heroWhere, `Tctl — ${WHERE.Tctl}`);
      if (hot.element.dataset.state !== state) hot.element.dataset.state = state;
      setText(heroIcon, STATES[state].icon);
      heroIcon.style.color = colourOf(state);
      setText(
        heroWord,
        leadChannel.warn === null && leadChannel.critical === null
          ? "k10temp publishes no threshold for this sensor"
          : STATES[state].word,
      );
    }

    setText(
      heroHottest,
      hottest === null
        ? "no temperature could be read"
        : `Hottest sensor on the machine: ${formatValue(hottest.reading, hottest.channel)} — ` +
          `${hottest.channel.label}, ${WHERE[hottest.channel.label]}`,
    );
  });

  // --- power ---------------------------------------------------------------
  const packagePower = catalogue.byLabel("CPU Package Power");
  const gpuPower = catalogue.byLabel("GPU power");
  const power = card("Power drawn", "what can be measured, and what cannot");
  const powerRows = [
    ["Processor package", packagePower],
    ["Graphics card", gpuPower],
  ];
  const powerValues = [];
  for (const [name, channel] of powerRows) {
    if (channel === null) {
      missing(power.body, name);
      continue;
    }
    const { row, value } = factLine(name);
    power.body.appendChild(row);
    attachTooltip(row, channel, stream);
    powerValues.push([channel, value]);
  }
  const { row: totalRow, value: totalValue } = factLine("Measured together");
  totalRow.classList.add("fact-strong");
  totalRow.title = "The sum of the two readings above, made here; no sensor reads it.";
  power.body.appendChild(totalRow);
  const note = document.createElement("p");
  note.className = "absent";
  note.textContent =
    "Total system power cannot be measured: the NZXT C1200 power supply has no telemetry link, " +
    "and nothing on the USB bus belongs to it (docs/physical-build.md).";
  power.body.appendChild(note);
  painters.push(() => {
    let total = 0;
    let complete = true;
    for (const [channel, target] of powerValues) {
      const reading = stream.value(channel);
      setText(target, formatValue(reading, channel));
      if (reading === null) complete = false;
      else total += reading;
    }
    setText(totalValue, complete && powerValues.length ? `${total.toFixed(2)} W` : "—");
  });

  // --- meters for the parts that publish a scale ---------------------------
  const load = card("Load", "each of these publishes a real scale");
  for (const label of ["CPU use", "GPU use", "Memory use", "VRAM bus use"]) {
    const channel = catalogue.byLabel(label);
    if (channel === null || !hasScale(channel)) {
      missing(load.body, label);
      continue;
    }
    const meter = new Meter(channel);
    load.body.appendChild(meter.element);
    attachTooltip(meter.element, channel, stream);
    painters.push(() => meter.update(stream.value(channel), stream.extra(channel)));
  }

  // --- memory ---------------------------------------------------------------
  const memory = card("Memory", "2 x 32 GB DDR5 at 6400 MT/s, slots A2 and B2");
  for (const label of ["Memory used", "Memory total", "Memory cached", "Swap total"]) {
    const channel = catalogue.byLabel(label);
    if (channel === null) {
      missing(memory.body, label);
      continue;
    }
    const { row, value } = factLine(label);
    memory.body.appendChild(row);
    attachTooltip(row, channel, stream);
    painters.push(() => setText(value, formatValue(stream.value(channel), channel)));
  }

  // --- storage health -------------------------------------------------------
  const storage = card("Storage health", "WD_BLACK SN770 1TB, read through the helper");
  for (const label of ["SSD Wear", "Spare Available"]) {
    const channel = catalogue.byLabel(label);
    if (channel === null || !hasScale(channel)) {
      missing(storage.body, label);
      continue;
    }
    const meter = new Meter(channel);
    storage.body.appendChild(meter.element);
    attachTooltip(meter.element, channel, stream);
    painters.push(() => meter.update(stream.value(channel), stream.extra(channel)));
  }
  for (const label of ["Critical Warning", "Media Errors", "Unsafe Shutdowns", "Power Cycles", "Power-On Hours"]) {
    const channel = catalogue.byLabel(label);
    if (channel === null) {
      missing(storage.body, label);
      continue;
    }
    const { row, value } = factLine(label);
    storage.body.appendChild(row);
    attachTooltip(row, channel, stream);
    painters.push(() => setText(value, formatValue(stream.value(channel), channel)));
  }

  // --- every fan ------------------------------------------------------------
  const fans = catalogue.byUnit("rpm");
  const cooling = card("Every fan", "3 front, 3 top, 1 rear, the pump; the card: 1 fan and 2 on its radiator");
  const fanNote = document.createElement("p");
  fanNote.className = "absent";
  fanNote.textContent =
    "The case has 7 fans (3 front, 3 top on the CPU radiator, 1 rear) and the pump; the board reads them on " +
    "four headers. The BIOS put case fans on the EZ Conn header, which reports as one channel (exp-0009). Which " +
    "fans each header reads is not established. Five SYS_FAN headers are empty, and the BIOS agrees. " +
    "A header that reads 0 RPM is shown, never hidden: a fan that has stopped must not disappear. " +
    "The graphics card is the SUPRIM LIQUID X: one fan on its underside, and the radiator at the bottom of the " +
    "case with its two fans is the card's own (docs/physical-build.md, corrected 2026-09-23). NVML reads two fan " +
    "channels, one for each fan header on the card's board; which fans each drives is not established. Both stop " +
    "while the card is idle; exp-0013 measured 1205 and 1520 RPM under load.";
  for (const channel of fans) {
    const { row, value } = factLine(channel.label);
    cooling.body.appendChild(row);
    attachTooltip(row, channel, stream);
    painters.push(() => {
      const reading = stream.value(channel);
      setText(value, formatValue(reading, channel));
      row.classList.toggle("fact-quiet", reading === 0);
    });
  }
  cooling.body.appendChild(fanNote);

  // --- what a colour means --------------------------------------------------
  const legend = card("What a colour means", "the same in every view");
  legend.body.className = "card-body legend-body";
  for (const [name, meaning] of Object.entries(STATES)) {
    const item = document.createElement("span");
    item.className = "legend-item";
    item.innerHTML = `<i></i><b></b><em></em>`;
    item.querySelector("i").textContent = meaning.icon;
    item.querySelector("i").style.color = colourOf(name);
    item.querySelector("b").textContent = meaning.word;
    item.querySelector("em").textContent = LEGEND_MEANING[name];
    legend.body.appendChild(item);
  }

  // --- one chart, so the summary shows movement and not only a number -------
  const charted = catalogue.byLabel("Tctl");
  const movement = card("The CPU control sensor over time", "Tctl is what the board's fan curve follows");
  movement.element.classList.add("card-wide");
  if (charted === null) {
    missing(movement.body, "Tctl");
  } else {
    const trace = new Trace(charted, { width: 420, height: 180, title: "Tctl" });
    movement.body.appendChild(trace.element);
    attachTooltip(trace.element.querySelector("figcaption"), charted, stream);
    painters.push(() => trace.update(stream.series(charted), stream.seconds));
  }

  // --- the card's power over time, on its own axis --------------------------
  const gpuMovement = card("The graphics card's power over time", "limit 480 W");
  gpuMovement.element.classList.add("card-wide");
  if (gpuPower === null) {
    missing(gpuMovement.body, "GPU power");
  } else {
    const trace = new Trace(gpuPower, { width: 420, height: 180, title: "GPU power" });
    gpuMovement.body.appendChild(trace.element);
    attachTooltip(trace.element.querySelector("figcaption"), gpuPower, stream);
    painters.push(() => trace.update(stream.series(gpuPower), stream.seconds));
  }

  // --- the one channel that needs the helper, shown as a tile --------------
  const helperTile = card("Read through the root helper", "32 channels; ADR 0005 and 0009");
  const packageTile = packagePower === null ? null : new StatTile(packagePower);
  if (packageTile === null) {
    missing(helperTile.body, "CPU Package Power");
  } else {
    helperTile.body.appendChild(packageTile.element);
    attachTooltip(packageTile.element, packagePower, stream);
    painters.push(() =>
      packageTile.update(stream.value(packagePower), stream.series(packagePower), stream.extra(packagePower)),
    );
  }

  for (const built of [hot, power, load, movement, gpuMovement, memory, storage, cooling, helperTile, legend]) {
    element.appendChild(built.element);
  }

  return {
    element,
    update() {
      for (const paint of painters) paint();
    },
  };
}

/** What each state means, in one line, for the legend. */
const LEGEND_MEANING = {
  normal: "inside the range the hardware publishes",
  warning: "past the warning threshold the hardware publishes",
  serious: "two thirds of the way from the warning to the critical threshold",
  critical: "at or past the critical threshold the hardware publishes",
  over: "past the top of the published scale; the Alerts screen logs it",
  under: "under the bottom of the published scale; the Alerts screen logs it",
  stale: "the value is older than one pass; the helper samples on its own clock",
  unavailable: "the value cannot be read now, and the reason is shown",
};
