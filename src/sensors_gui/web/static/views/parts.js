/*
 * The small parts every view is built from: a card, a line of label and
 * value, and a note that a value is not on this machine.
 *
 * They were in the summary view first. The graphics card view needs the same
 * ones, and two copies would drift.
 */

/** Build one card with a title and a note beside it. */
export function card(title, extra = "") {
  const element = document.createElement("section");
  element.className = "card view-card";
  element.innerHTML = `<h3 class="card-title"><span></span><span class="card-note"></span></h3>
    <div class="card-body"></div>`;
  element.querySelector(".card-title > span:first-child").textContent = title;
  element.querySelector(".card-note").textContent = extra;
  return { element, body: element.querySelector(".card-body") };
}

/** Build one line of "label ... value", for a fact with no meter. */
export function factLine(label, note = "") {
  const row = document.createElement("div");
  row.className = "fact";
  row.innerHTML = `<span class="fact-label"></span><span class="fact-value">—</span>`;
  row.querySelector(".fact-label").textContent = label;
  if (note) row.title = note;
  return { row, value: row.querySelector(".fact-value") };
}

/** Say that a channel this view expected is not on this machine. */
export function missing(body, label) {
  const line = document.createElement("p");
  line.className = "absent";
  line.textContent = `${label}: not found on this machine`;
  body.appendChild(line);
}
