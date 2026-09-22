/*
 * The core topology of this machine, read from it and not inferred.
 *
 * Source: `data/probes/2026-09-22-cpu-topology.txt`, taken from
 * `/sys/devices/system/cpu/cpuN/topology/` on 2026-09-22. The table is in
 * `docs/hardware-inventory.md`.
 *
 * The one thing a guess would get wrong: a thread's sibling is **12 away**,
 * not next to it. `cpu0` and `cpu12` are one core.
 */

/** Each core of this processor, in hardware order. */
export const CORES = [
  { core: 0, die: 1, threads: [0, 12] },
  { core: 1, die: 1, threads: [1, 13] },
  { core: 2, die: 1, threads: [2, 14] },
  { core: 3, die: 1, threads: [3, 15] },
  { core: 4, die: 1, threads: [4, 16] },
  { core: 5, die: 1, threads: [5, 17] },
  { core: 8, die: 2, threads: [6, 18] },
  { core: 9, die: 2, threads: [7, 19] },
  { core: 10, die: 2, threads: [8, 20] },
  { core: 11, die: 2, threads: [9, 21] },
  { core: 12, die: 2, threads: [10, 22] },
  { core: 13, die: 2, threads: [11, 23] },
];

/** The name of each die, as the temperature channels name them. */
export const DIE_NAME = { 1: "CCD 1 — Tccd1", 2: "CCD 2 — Tccd2" };

/**
 * Return one column for each thread, in hardware order.
 *
 * The two threads of a core are next to each other and the two dies are
 * apart, so the shape of the processor is the shape of the display.
 *
 * @param {import("./stream.js").Catalogue} catalogue the channels
 * @returns {Array<object>} the columns, ready for `CoreBars`
 */
export function threadColumns(catalogue) {
  const columns = [];
  for (const core of CORES) {
    for (const [position, thread] of core.threads.entries()) {
      const channel = catalogue.byLabel(`CPU${thread} use`);
      if (channel === null) continue;
      columns.push({
        label: `core ${core.core}, thread ${thread}`,
        channel,
        group: DIE_NAME[core.die],
        // Only the first thread of a core is labelled, or the axis is a wall
        // of numbers. The tooltip names both.
        tick: position === 0 ? String(core.core) : false,
      });
    }
  }
  return columns;
}

/**
 * Return one column for each core's power, in the same hardware order.
 *
 * The same display, a different measure: `exp-0012` reads one energy counter
 * for each core, and those twelve channels line up with the columns above.
 *
 * @param {import("./stream.js").Catalogue} catalogue the channels
 * @returns {Array<object>} the columns, ready for `CoreBars`
 */
export function corePowerColumns(catalogue) {
  const columns = [];
  for (const core of CORES) {
    const channel = catalogue.byLabel(`CPU Core ${core.core} Power`);
    if (channel === null) continue;
    columns.push({
      label: `core ${core.core} power`,
      channel,
      group: DIE_NAME[core.die],
      tick: String(core.core),
    });
  }
  return columns;
}
