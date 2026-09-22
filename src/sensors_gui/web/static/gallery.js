/*
 * The component review page.
 *
 * It fetches the catalogue once, then keeps a ring buffer of the frames and
 * hands the values to each widget. Every channel it shows is chosen by label
 * from this machine's real catalogue; a label that is not found is skipped
 * rather than faked.
 */

import { Meter, STATES, StatTile, Trace, colourOf, hasScale } from "/static/widgets.js";

const HISTORY = 300;

/** Channels with a real scale, for the meters. */
const WITH_SCALE = ["GPU edge", "GPU power", "GPU use", "DIMM A2", "CPU use", "SSD Wear"];

/** Channels with no published scale, for the stat tiles. */
const WITHOUT_SCALE = ["Tctl", "CPU Package Power", "CPU Fan", "EZ Conn Fan", "+12V", "Unsafe Shutdowns"];

/** Channels worth a full chart. */
const CHARTED = ["Tctl", "CPU Package Power", "GPU edge", "CPU use"];

const $ = (id) => document.getElementById(id);

const state = {
  catalogue: null,
  byLabel: new Map(),
  history: [],
  widgets: [],
  frames: 0,
  paintTotal: 0,
};

/** Return the ring buffer of one channel, oldest first. */
function seriesOf(index) {
  return state.history.map((frame) => frame.v[index] ?? null);
}

/** Build every widget once the catalogue is known. */
function build() {
  for (const label of WITH_SCALE) {
    const channel = state.byLabel.get(label);
    if (!channel || !hasScale(channel)) continue;
    const meter = new Meter(channel);
    const card = document.createElement("div");
    card.className = "card";
    card.appendChild(meter.element);
    $("meters").appendChild(card);
    state.widgets.push((frame) => meter.update(frame.v[channel.i], extraOf(frame, channel.i)));

  }

  for (const label of WITHOUT_SCALE) {
    const channel = state.byLabel.get(label);
    if (!channel) continue;
    const hero = label === "Tctl";
    const tile = new StatTile(channel, { hero });
    $(hero ? "hero" : "tiles").appendChild(tile.element);
    state.widgets.push((frame) => tile.update(frame.v[channel.i], seriesOf(channel.i), extraOf(frame, channel.i)));
  }

  for (const label of CHARTED) {
    const channel = state.byLabel.get(label);
    if (!channel) continue;
    const trace = new Trace(channel, { width: 460, height: 170 });
    $("traces").appendChild(trace.element);
    state.widgets.push(() => trace.update(seriesOf(channel.i), state.history.length / state.catalogue.hz));
  }

  const legend = $("legend");
  for (const [name, meaning] of Object.entries(STATES)) {
    const item = document.createElement("span");
    item.innerHTML = `<i></i>${meaning.word}`;
    item.querySelector("i").textContent = meaning.icon;
    item.querySelector("i").style.color = colourOf(name);
    legend.appendChild(item);
  }
}

/** Return what the frame said about one channel beyond its value. */
function extraOf(frame, index) {
  return { error: frame.errors[String(index)], age: frame.ages[String(index)] };
}

/** Take one frame: record it, then redraw every widget. */
function onFrame(frame) {
  const began = performance.now();
  state.history.push(frame);
  if (state.history.length > HISTORY) state.history.shift();
  for (const paint of state.widgets) paint(frame);

  state.frames += 1;
  state.paintTotal += performance.now() - began;
  $("hz").textContent = frame.hz.toFixed(2);
  $("p50").textContent = frame.pass.median_ms.toFixed(2);
  $("pmax").textContent = frame.pass.max_ms.toFixed(2);
  $("frames").textContent = state.frames;
  $("paint").textContent = (state.paintTotal / state.frames).toFixed(2);
}

/** Fetch the catalogue, build the page and open the stream. */
async function start() {
  state.catalogue = await (await fetch("/api/catalogue")).json();
  for (const channel of state.catalogue.channels) state.byLabel.set(channel.label, channel);
  $("shown").textContent = state.catalogue.shown;
  $("hidden").textContent = state.catalogue.hidden;

  // The helper owns 32 channels. Whether it answers is a fact the status bar
  // must show, not hide: ADR 0005 rule 3.
  const helper = state.catalogue.channels.filter((channel) => channel.source === "privileged");
  $("helper").textContent = helper.length ? `${helper.length} channels` : "not present";

  build();

  const socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onmessage = (event) => onFrame(JSON.parse(event.data));
  socket.onclose = () => {
    $("helper").textContent = "stream closed";
  };
}

start();
