/*
 * The cooling view: every fan and the pump, whatever driver reads them.
 *
 * `docs/gui-goal.md` 4.1 asks for a view that "brings together every fan and
 * pump on the machine with the temperature it acts on ... This crosses the
 * groups above on purpose." So it takes its channels by unit and by label,
 * not by group: the board's headers are in the board group and the card's
 * fans in the graphics card group.
 *
 * This is the first version, for checkpoint 5a (Gova, 2026-10-27: "Stop at
 * the airflow drawing first"): the drawing of the case and every fan
 * reading. The temperature each fan acts on comes at checkpoint 5, after
 * Gova's review; for most headers it is not established yet (Q20).
 */

import { airflowDiagram } from "./airflow-diagram.js";
import { builders, card } from "./parts.js";

/** The board headers that read a fan, in the board's order; the empty ones follow. */
const LIVE_HEADERS = ["CPU Fan", "Pump Fan", "System Fan #1", "EZ Conn Fan"];

/**
 * Build the cooling view.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the view
 */
export function coolingView(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "view view-detail";
  const painters = [];
  const build = builders(stream, painters);
  const byLabel = (label) => catalogue.byLabel(label);

  // --- the drawing ------------------------------------------------------------
  const drawing = card("The case and its air", "hover a dot for its reading; every value is also in the cards");
  // Three cells wide: in two, its 12 px words drew at 9 px (checkpoint 5a, 2560 px).
  drawing.element.classList.add("card-span-3");
  const diagram = airflowDiagram(catalogue, stream);
  drawing.body.appendChild(diagram.element);
  painters.push(() => diagram.update());

  // --- the board's headers ----------------------------------------------------
  const board = card("Board fan headers", "MSI PRO X870-P WIFI, read by the Super-I/O chip");
  const live = document.createElement("div");
  live.className = "tile-row tile-row-wide";
  board.body.appendChild(live);
  for (const label of LIVE_HEADERS) build.show(live, byLabel(label), label);
  // Short line names: a name of 8 letters and its value did not fit the end of the line.
  build.chart(board.body, byLabel("CPU Fan"), "CPU_FAN1 (CPU) and PUMP_SYS1 (pump), on one axis", {
    firstLabel: "CPU",
    others: [{ channel: byLabel("Pump Fan"), label: "pump", token: "--series-2" }],
    height: 130,
  });
  build.chart(board.body, byLabel("System Fan #1"), "SYS_FAN1 (SYS1) and JAF_1, on one axis", {
    firstLabel: "SYS1",
    others: [{ channel: byLabel("EZ Conn Fan"), label: "JAF_1", token: "--series-2" }],
    height: 130,
  });
  // The empty headers stay on screen: a fan that stops must not disappear.
  const empty = catalogue
    .byUnit("rpm")
    .filter((channel) => channel.group === "board" && !LIVE_HEADERS.includes(channel.label));
  for (const channel of empty) build.fact(board.body, channel, channel.label);
  const note = document.createElement("p");
  note.className = "absent";
  note.textContent =
    "Which fans each header drives is not established (Q20). The CPU cooler's manual puts the pump on the pump " +
    "header and the 3 radiator fans on CPU_FAN1, but CPU_FAN1 turns faster than those fans can at half duty, " +
    "so the two may be the other way round (lab/exp-0020-case-cooler-identity).";
  board.body.appendChild(note);

  // --- the card's fans ----------------------------------------------------------
  const gpu = card("The graphics card's fans", "3 fans on 2 channels, read by NVML");
  const tiles = document.createElement("div");
  tiles.className = "tile-row";
  gpu.body.appendChild(tiles);
  for (const label of ["GPU fan 1", "GPU fan 2"]) build.show(tiles, byLabel(label), label);
  for (const label of ["GPU fan 1 duty", "GPU fan 2 duty", "GPU fan"]) build.show(gpu.body, byLabel(label), label);
  build.chart(gpu.body, byLabel("GPU fan 1"), "Both channels, on one axis", {
    firstLabel: "fan 1",
    others: [{ channel: byLabel("GPU fan 2"), label: "fan 2", token: "--series-2" }],
    height: 130,
  });
  const gpuNote = document.createElement("p");
  gpuNote.className = "absent";
  gpuNote.textContent =
    "The two channels drive the card's fan on its underside and the two fans on its radiator. Which channel " +
    "drives which fans is not established (Q14). When they stop is not established: lab/exp-0017-gpu-fan-channels " +
    "saw them stop at idle, and on 2026-10-27 both turned with the card at 32-33 °C and 11-20 % use " +
    "(data/probes/2026-10-27-gpu-fans-turning-when-cool.txt).";
  gpu.body.appendChild(gpuNote);

  for (const built of [drawing, board, gpu]) element.appendChild(built.element);

  return {
    element,
    update() {
      for (const paint of painters) paint();
    },
  };
}
