/*
 * The memory slots, drawn in the order the board has them, with a dot on each
 * fitted module.
 *
 * The order is from the manual's "Overview of Components", page 27, in
 * `docs/reference/mobo-board-layout.png`: from the processor socket outward,
 * DIMMA1, DIMMA2, DIMMB1, DIMMB2. The modules are in A2 and B2, and the
 * temperature sensor of each is the SPD hub at address 0x51 and 0x53 on the
 * SMBus; the kernel numbers the bus itself at boot (0, then 5 on 2026-10-27)
 * (`docs/hardware-inventory.md`, from `dmidecode -t memory` and the i2c
 * devices).
 *
 * The dot marks the module, not the chip: where on the module the SPD hub
 * sits is not established, and the tooltip says so. The drawing is a
 * schematic of the order, not to scale. `docs/diagram-positions.md` holds the
 * claims.
 *
 * Gova, 2026-09-25: each module shows its temperature on it, in the colour of
 * its state, so the drawing says something without a hover.
 */

import { colourOf, formatValue, setText, stateOf } from "../widgets.js";
import { Dots, make } from "./dots.js";

/** The four slots, from the socket outward, and the channel of a fitted one. */
const SLOTS = [
  { name: "DIMMA1", fitted: false },
  { name: "DIMMA2", fitted: true, label: "DIMM A2", hub: "0x51" },
  { name: "DIMMB1", fitted: false },
  { name: "DIMMB2", fitted: true, label: "DIMM B2", hub: "0x53" },
];

const WIDTH = 820;
const HEIGHT = 330;
const SLOT_TOP = 66;
const SLOT_HEIGHT = 210;
const SLOT_WIDTH = 34;

/**
 * Build the drawing.
 *
 * @param {import("../stream.js").Catalogue} catalogue the channels
 * @param {import("../stream.js").Stream} stream the live frames
 * @returns {{element: HTMLElement, update: Function}} the drawing
 */
export function memoryDiagram(catalogue, stream) {
  const element = document.createElement("div");
  element.className = "wireframe";
  const svg = make("svg", { viewBox: `0 0 ${WIDTH} ${HEIGHT}`, class: "wire", role: "img" });
  svg.appendChild(make("title", {}, "The four memory slots of the board, with the two fitted modules and their readings"));
  element.appendChild(svg);
  const dots = new Dots(element, svg, WIDTH, HEIGHT, stream);

  svg.appendChild(make("text", { x: 20, y: 24, class: "wire-caption" }, "MSI PRO X870-P WIFI · memory slots"));
  svg.appendChild(
    make("text", { x: 20, y: 44, class: "wire-note" },
      "Order from the manual, page 27; not to scale. A dot marks a module, not the chip on it."),
  );

  // The processor socket, to the left of the slots on the manual's drawing.
  svg.appendChild(make("rect", { x: 40, y: SLOT_TOP + 30, width: 170, height: 150, rx: 6, class: "wire-card" }));
  svg.appendChild(
    make("text", { x: 125, y: SLOT_TOP + 110, class: "wire-edge", "text-anchor": "middle" }, "processor socket"),
  );

  const first = 320;
  const step = 118;
  const values = [];
  SLOTS.forEach((slot, index) => {
    const x = first + index * step;
    const middle = x + SLOT_WIDTH / 2;
    svg.appendChild(
      make("rect", { x, y: SLOT_TOP, width: SLOT_WIDTH, height: SLOT_HEIGHT, rx: 3, class: "wire-line" }),
    );
    svg.appendChild(
      make("text", { x: middle, y: SLOT_TOP + SLOT_HEIGHT + 20, class: "wire-dot-name", "text-anchor": "middle" },
        slot.name),
    );
    if (!slot.fitted) {
      svg.appendChild(
        make("text", { x: middle, y: SLOT_TOP + SLOT_HEIGHT + 36, class: "wire-edge", "text-anchor": "middle" },
          "empty"),
      );
      return;
    }
    svg.appendChild(
      make("rect", {
        x: x + 4,
        y: SLOT_TOP + 4,
        width: SLOT_WIDTH - 8,
        height: SLOT_HEIGHT - 8,
        rx: 2,
        class: "wire-module",
      }),
    );
    svg.appendChild(
      make("text", { x: middle, y: SLOT_TOP + SLOT_HEIGHT + 36, class: "wire-edge", "text-anchor": "middle" },
        "32 GB"),
    );
    const channel = catalogue.byLabel(slot.label);
    // The reading, on a plate across the module, where it is read without a hover.
    const plateY = SLOT_TOP + SLOT_HEIGHT / 2 + 14;
    svg.appendChild(make("rect", { x: middle - 44, y: plateY, width: 88, height: 30, rx: 6, class: "wire-plate" }));
    const text = make("text", { x: middle, y: plateY + 20, class: "wire-value", "text-anchor": "middle" }, "—");
    svg.appendChild(text);
    values.push({ text, channel });
    dots.add(
      {
        id: slot.name,
        name: `${slot.name}, TEAM GROUP UD5-6400, 32 GB`,
        basis:
          `The module in slot ${slot.name.slice(4)}; its sensor is the SPD hub at address ${slot.hub} on the SMBus ` +
          "(docs/hardware-inventory.md). Slot order from the manual, page 27. Where on the module the hub sits " +
          "is not established.",
        rows: [{ label: "Temperature", channel }],
      },
      middle,
      SLOT_TOP + SLOT_HEIGHT / 2 - 26,
    );
  });

  return {
    element,
    update() {
      dots.update();
      for (const { text, channel } of values) {
        const value = stream.value(channel);
        setText(text, formatValue(value, channel));
        const state = stateOf(value, channel, stream.extra(channel));
        if (text.dataset.state !== state) {
          text.dataset.state = state;
          text.style.fill = colourOf(state);
        }
      }
    },
  };
}
