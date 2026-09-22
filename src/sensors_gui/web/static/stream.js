/*
 * The catalogue and the frame stream, shared by every view.
 *
 * The catalogue is fetched once and never changes until a re-scan, so a frame
 * carries only an array of values in catalogue order. `Stream` keeps a ring
 * buffer of those frames and hands each view the series it asks for.
 *
 * Nothing here can write to hardware. The server offers no route that could.
 */

const HISTORY = 600; // 60 s at 10 Hz, 40 min at 0.25 Hz

/** The static description of every channel, with ways to find one. */
export class Catalogue {
  /**
   * @param {object} payload what `GET /api/catalogue` returned
   */
  constructor(payload) {
    this.machine = payload.machine;
    this.hz = payload.hz;
    this.shown = payload.shown;
    this.hidden = payload.hidden;
    this.channels = payload.channels;
    this._byLabel = new Map(this.channels.map((channel) => [channel.label, channel]));
  }

  /**
   * Return the channel with this label, or null.
   *
   * A view asks for a channel by the name a person reads. When the machine
   * does not have it, the view says so rather than showing a zero: a label
   * that is missing is a fact about the machine, not a fault to hide.
   *
   * @param {string} label the label to look for
   * @returns {object|null} the channel
   */
  byLabel(label) {
    return this._byLabel.get(label) ?? null;
  }

  /** Return every channel in one group, in catalogue order. */
  byGroup(group) {
    return this.channels.filter((channel) => channel.group === group);
  }

  /** Return every channel carrying one unit. */
  byUnit(unit) {
    return this.channels.filter((channel) => channel.unit === unit);
  }

  /** Return every channel a test function accepts. */
  where(accepts) {
    return this.channels.filter(accepts);
  }

  /** Return every channel read through the root helper. */
  helperChannels() {
    return this.channels.filter((channel) => channel.source === "privileged");
  }
}

/** The live frames: the newest one, and a ring buffer of the recent ones. */
export class Stream {
  /**
   * @param {Catalogue} catalogue the channels, in frame order
   */
  constructor(catalogue) {
    this.catalogue = catalogue;
    this.frames = [];
    this.latest = null;
    this.socket = null;
    this._listeners = [];
  }

  /** Register a function called with every frame. */
  onFrame(listener) {
    this._listeners.push(listener);
  }

  /** Open the stream and keep it open. */
  connect() {
    this.socket = new WebSocket(`ws://${location.host}/ws`);
    this.socket.onmessage = (event) => this._take(JSON.parse(event.data));
    this.socket.onclose = () => {
      for (const listener of this._listeners) listener(this.latest, { closed: true });
    };
  }

  /** Record one frame and pass it on. */
  _take(frame) {
    this.latest = frame;
    this.frames.push(frame);
    if (this.frames.length > HISTORY) this.frames.shift();
    for (const listener of this._listeners) listener(frame, { closed: false });
  }

  /** Return the current value of one channel, or null. */
  value(channel) {
    if (!channel || !this.latest) return null;
    return this.latest.v[channel.i] ?? null;
  }

  /** Return what the frame said about one channel beyond its value. */
  extra(channel) {
    if (!channel || !this.latest) return {};
    return { error: this.latest.errors[String(channel.i)], age: this.latest.ages[String(channel.i)] };
  }

  /** Return the ring buffer of one channel, oldest first. */
  series(channel) {
    if (!channel) return [];
    return this.frames.map((frame) => frame.v[channel.i] ?? null);
  }

  /** Return how many seconds the ring buffer covers. */
  get seconds() {
    const hz = this.latest?.hz ?? this.catalogue.hz;
    return this.frames.length / hz;
  }

  /**
   * Return whether the root helper is answering.
   *
   * ADR 0005 rule 3: when the helper is absent its 32 channels still appear,
   * each carrying the reason instead of a value. So the helper's state is
   * read from the channels themselves, and is never guessed.
   *
   * @returns {{present: boolean, answering: number, total: number}}
   */
  helperState() {
    const channels = this.catalogue.helperChannels();
    if (!this.latest) return { present: false, answering: 0, total: channels.length };
    const answering = channels.filter((channel) => this.latest.v[channel.i] !== null).length;
    return { present: answering > 0, answering, total: channels.length };
  }
}

/** Fetch the catalogue and open the stream. */
export async function start() {
  const catalogue = new Catalogue(await (await fetch("/api/catalogue")).json());
  const stream = new Stream(catalogue);
  return { catalogue, stream };
}

/** Ask the server to change the sample rate. */
export async function setRate(hz) {
  const response = await fetch("/api/rate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hz }),
  });
  return response.json();
}

/** Ask the server to pause or resume sampling. */
export async function setPaused(paused) {
  const response = await fetch("/api/pause", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paused }),
  });
  return response.json();
}
