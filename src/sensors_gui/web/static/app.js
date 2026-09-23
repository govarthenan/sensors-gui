/*
 * The shell: the views, the navigation between them, and the status bar.
 *
 * One page holds every view. The address after `#` says which one is on
 * screen, so a view can be opened directly and the back button works.
 *
 * Only the view on screen is painted. A frame arrives up to ten times a
 * second and there is no reason to draw a view nobody is looking at.
 */

import { setPaused, setRate, start } from "./stream.js";
import { refreshTooltip } from "./tooltip.js";
import { alertsView } from "./views/alerts.js";
import { gpuView } from "./views/gpu.js";
import { summaryView } from "./views/summary.js";

/**
 * The views, in the order they appear in the navigation.
 *
 * The grouping follows the hardware, not the driver, as
 * `docs/gui-goal.md` section 4.1 requires. A view that is not built yet says
 * which checkpoint builds it, rather than showing an empty page.
 */
const VIEWS = [
  { id: "summary", name: "Summary", build: summaryView },
  { id: "gpu", name: "Graphics card", build: gpuView },
  { id: "cpu", name: "Processor", checkpoint: 4, note: "AMD Ryzen 9 9900X — temperatures, 12 core powers, clocks" },
  { id: "memory", name: "Memory", checkpoint: 4, note: "2 x 32 GB DDR5, slots A2 and B2" },
  { id: "board", name: "Motherboard", checkpoint: 5, note: "MSI PRO X870-P WIFI — 9 fans, 10 voltages, 7 temperatures" },
  { id: "cooling", name: "Cooling", checkpoint: 5, note: "every fan and the pump, beside the temperature it acts on" },
  {
    id: "igpu",
    name: "Integrated graphics",
    checkpoint: 6,
    note: "the AMD iGPU in the 9900X — both monitors run from the RTX 4090, not from this part",
  },
  { id: "storage", name: "Storage", checkpoint: 6, note: "WD_BLACK SN770 — 3 temperatures and 15 health channels" },
  { id: "network", name: "Network", checkpoint: 6, note: "Ethernet PHY temperature, Wi-Fi signal, counters" },
  { id: "peripherals", name: "Peripherals", checkpoint: 6, note: "Logitech G305 battery" },
  { id: "system", name: "System", checkpoint: 6, note: "what psutil and /proc give and nothing above fits" },
  { id: "alerts", name: "Alerts", build: alertsView },
  { id: "about", name: "About", checkpoint: 7, note: "every channel, its source, and what it cannot read" },
];

const $ = (id) => document.getElementById(id);

/** A view that is not built yet, and says so plainly. */
function placeholderView(view) {
  const element = document.createElement("div");
  element.className = "view view-placeholder";
  element.innerHTML = `
    <section class="card view-card">
      <h3 class="card-title">${view.name}</h3>
      <div class="card-body">
        <p class="absent">This view is built at checkpoint ${view.checkpoint}.</p>
        <p class="absent">${view.note}</p>
      </div>
    </section>`;
  return { element, update() {} };
}

async function main() {
  const { catalogue, stream } = await start();
  const built = new Map();
  let current = null;

  // --- navigation ---------------------------------------------------------
  const nav = $("nav");
  for (const view of VIEWS) {
    const link = document.createElement("a");
    link.href = `#${view.id}`;
    link.textContent = view.name;
    link.dataset.view = view.id;
    if (view.checkpoint) link.classList.add("nav-later");
    nav.appendChild(link);
  }
  const alertBadge = document.createElement("span");
  alertBadge.className = "nav-badge";
  nav.querySelector('a[data-view="alerts"]').appendChild(alertBadge);

  /** Show one view, building it the first time it is asked for. */
  function show(id) {
    const view = VIEWS.find((candidate) => candidate.id === id) ?? VIEWS[0];
    if (!built.has(view.id)) {
      built.set(view.id, view.build ? view.build(catalogue, stream) : placeholderView(view));
    }
    current = built.get(view.id);
    const stage = $("stage");
    stage.replaceChildren(current.element);
    for (const link of nav.querySelectorAll("a")) {
      link.classList.toggle("is-current", link.dataset.view === view.id);
    }
    document.title = `sensors-gui — ${view.name}`;
    if (stream.latest) current.update();
  }

  window.addEventListener("hashchange", () => show(location.hash.slice(1)));

  // --- the status bar -----------------------------------------------------
  $("machine").textContent = catalogue.machine;
  $("counts").textContent = `${catalogue.shown} shown, ${catalogue.hidden} hidden`;

  let frames = 0;
  let paintTotal = 0;

  stream.onFrame((frame, how) => {
    if (how.closed) {
      $("link").textContent = "stream closed";
      $("link").dataset.state = "unavailable";
      return;
    }
    const began = performance.now();
    if (current) current.update();
    refreshTooltip();
    paintTotal += performance.now() - began;
    frames += 1;

    $("rate").textContent = `${frame.hz.toFixed(2)} Hz`;
    $("pass").textContent = `${frame.pass.median_ms.toFixed(2)} median, ${frame.pass.max_ms.toFixed(2)} max ms`;
    $("paint").textContent = `${(paintTotal / frames).toFixed(2)} ms`;
    $("sampled").textContent = new Date(frame.t * 1000).toLocaleTimeString();
    const helper = stream.helperState();
    $("link").textContent = helper.present
      ? `helper answers ${helper.answering} of ${helper.total}`
      : `helper is not answering (${helper.total} channels)`;
    $("link").dataset.state = helper.present ? "normal" : "unavailable";
    $("pause").textContent = frame.paused ? "Resume" : "Pause";

    // The alert count, in the status bar and on the navigation link, so an
    // alert is seen from every view. Gova, 2026-09-23.
    const alerts = frame.alerts ?? { open: 0, total: 0 };
    const alertText =
      alerts.open > 0 ? `${alerts.open} above or below scale now` : alerts.total > 0 ? `${alerts.total} logged` : "none";
    $("alerts").textContent = alertText;
    $("alerts-link").dataset.state = alerts.open > 0 ? "over" : "normal";
    const badge = alertBadge;
    badge.textContent = alerts.open > 0 ? `${alerts.open}` : alerts.total > 0 ? `${alerts.total}` : "";
    badge.dataset.state = alerts.open > 0 ? "over" : "closed";
  });

  // --- the controls -------------------------------------------------------
  $("faster").addEventListener("click", async () => {
    const current = stream.latest?.hz ?? catalogue.hz;
    await setRate(Math.min(current * 2, 10));
  });
  $("slower").addEventListener("click", async () => {
    const current = stream.latest?.hz ?? catalogue.hz;
    await setRate(Math.max(current / 2, 0.25));
  });
  $("pause").addEventListener("click", async () => {
    await setPaused(!(stream.latest?.paused ?? false));
  });

  show(location.hash.slice(1) || "summary");
  stream.connect();
}

main();
