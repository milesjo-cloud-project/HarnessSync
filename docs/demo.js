/* Separate simulation: demo entries stay in memory; no account or data sync. */
(() => {
  "use strict";
  const grades = {
    Boulder: ["VB", ...Array.from({length: 18}, (_, i) => `V${i}`)],
    Rope: [...Array.from({length: 10}, (_, i) => `5.${i}`),
      ...Array.from({length: 6}, (_, i) => "abcd".split("").map(letter => `5.${i + 10}${letter}`)).flat()],
  };
  const sendStyles = ["Onsight", "Flash", "Redpoint", "Sent"];
  const $ = id => document.getElementById(id);
  let sends, projects, nextId;

  function seed() {
    sends = [];
    for (const [grade, count] of [["V1", 5], ["V2", 4], ["V3", 2], ["V4", 1]]) {
      for (let i = 0; i < count; i++) sends.push({discipline: "Boulder", grade, status: i ? "Sent" : "Flash", route: "Sample gym boulder", location: "Sample climbing gym"});
    }
    sends.push({discipline: "Rope", grade: "5.10a", status: "Redpoint", route: "The long corner", location: "Sample crag"});
    projects = [
      {id: 1, discipline: "Boulder", grade: "V5", route: "The green overhang", location: "Sample climbing gym", attempts: 8, notes: "Left heel before the reach. Keep the right hip close."},
      {id: 2, discipline: "Rope", grade: "5.10c", route: "The upper corner", location: "Sample crag", attempts: 3, notes: "Pause at the good hold before the crux."},
    ];
    nextId = 3;
  }
  function element(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function announce(message) { $("feedback").textContent = message; }
  function view(name, focus = true) {
    document.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === name)));
    for (const key of ["log", "projects", "progress", "history"]) $("view-" + key).hidden = key !== name;
    render();
    if (focus) $("view-" + name).querySelector("h2").focus({preventScroll: true});
  }
  function populateGrades() {
    const discipline = $("discipline").value;
    $("grade").replaceChildren(...grades[discipline].map(grade => new Option(grade, grade)));
    $("grade").value = discipline === "Boulder" ? "V3" : "5.10a";
  }
  function button(text, action, secondary = false) {
    const el = element("button", text, "button" + (secondary ? " secondary" : ""));
    el.type = "button";
    el.addEventListener("click", action);
    return el;
  }
  function renderProjects() {
    $("project-count").textContent = projects.length;
    $("projects-list").replaceChildren();
    if (!projects.length) $("projects-list").append(element("p", "All projects sent! Log a climb with Project or Attempt to start another.", "empty"));
    for (const project of projects) {
      const card = element("article", undefined, "project-card");
      card.append(element("h3", `${project.grade} / ${project.route || "Unnamed project"}`));
      card.append(element("p", `${project.discipline} · ${project.location || "No location"} · ${project.attempts} ${project.attempts === 1 ? "attempt" : "attempts"}`, "project-meta"));
      const label = element("label", "Beta / notes");
      label.htmlFor = `notes-${project.id}`;
      const notes = element("textarea");
      notes.id = label.htmlFor;
      notes.value = project.notes;
      notes.maxLength = 500;
      // Retain edits when another view is opened before Save notes.
      notes.addEventListener("input", () => { project.notes = notes.value; });
      card.append(label, notes);
      const styleLabel = element("label", "Send style");
      styleLabel.htmlFor = `style-${project.id}`;
      const style = element("select");
      style.id = styleLabel.htmlFor;
      style.append(...sendStyles.map(value => new Option(value, value)));
      style.value = project.sendStyle || "Redpoint";
      style.addEventListener("change", () => { project.sendStyle = style.value; });
      card.append(styleLabel, style);
      const actions = element("div", undefined, "actions");
      actions.append(
        button("＋ Attempt", () => {
          project.attempts++;
          announce(`Attempt added to ${project.route || project.grade}: ${project.attempts} attempts. Keep at it!`);
          renderProjects();
          $("projects-list").querySelector(`[data-attempt="${project.id}"]`).focus();
        }, true),
        button("Save notes", () => { project.notes = notes.value.trim(); announce("Beta saved for this demo session."); }, true),
        button("Sent it! ↗", () => {
          sends.push({...project, status: style.value});
          projects = projects.filter(item => item.id !== project.id);
          announce(`${project.grade} sent! Your project is now in send history. See your updated progress below.`);
          $("pyramid-discipline").value = project.discipline;
          view("progress");
        }),
      );
      actions.firstChild.dataset.attempt = project.id;
      card.append(actions);
      $("projects-list").append(card);
    }
  }
  function best(discipline) {
    const scale = grades[discipline];
    const rank = Math.max(-1, ...sends.filter(climb => climb.discipline === discipline).map(climb => scale.indexOf(climb.grade)));
    return scale[rank] || "—";
  }
  function renderProgress() {
    $("total-sends").textContent = sends.length;
    $("best-boulder").textContent = best("Boulder");
    $("best-rope").textContent = best("Rope");
    const discipline = $("pyramid-discipline").value;
    const counts = new Map();
    for (const climb of sends.filter(item => item.discipline === discipline)) counts.set(climb.grade, (counts.get(climb.grade) || 0) + 1);
    const maximum = Math.max(1, ...counts.values());
    $("pyramid").replaceChildren();
    if (!counts.size) $("pyramid").append(element("p", "No sends in this discipline yet.", "empty"));
    for (const grade of [...grades[discipline]].reverse().filter(value => counts.has(value))) {
      const count = counts.get(grade);
      const row = element("div", undefined, "pyramid-row");
      const track = element("div", undefined, "pyramid-track");
      const bar = element("div", undefined, "pyramid-bar");
      bar.style.setProperty("--bar-width", `${count / maximum * 100}%`);
      track.append(bar);
      row.append(element("span", grade), track, element("span", `${count} ${count === 1 ? "send" : "sends"}`));
      $("pyramid").append(row);
    }
  }
  function render() {
    renderProjects();
    renderProgress();
    $("send-history").replaceChildren();
    for (const climb of [...sends].reverse()) {
      const row = element("li");
      const details = element("div", climb.route || "Unnamed climb");
      details.append(element("small", `${climb.discipline} · ${climb.status} · ${climb.location || "No location"}`));
      row.append(details, element("span", climb.grade, "grade"));
      $("send-history").append(row);
    }
  }
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => view(button.dataset.view)));
  $("discipline").addEventListener("change", populateGrades);
  $("pyramid-discipline").addEventListener("change", renderProgress);
  $("climb-form").addEventListener("submit", event => {
    event.preventDefault();
    const climb = {discipline: $("discipline").value, grade: $("grade").value, status: $("result").value,
      route: $("route").value.trim(), location: $("location").value.trim()};
    if (!grades[climb.discipline]?.includes(climb.grade)) return;
    $("route").value = "";
    if (["Project", "Attempt"].includes(climb.status)) {
      const existing = projects.find(project => project.discipline === climb.discipline && project.grade === climb.grade && project.route.toLowerCase() === climb.route.toLowerCase() && project.location.toLowerCase() === climb.location.toLowerCase());
      if (existing) existing.attempts++;
      else projects.push({...climb, id: nextId++, attempts: 1, notes: ""});
      announce(`${climb.grade} ${existing ? "attempt added" : "added to projects"}. It will count as a send when you complete it.`);
      view("projects");
    } else if (sendStyles.includes(climb.status)) {
      sends.push(climb);
      $("pyramid-discipline").value = climb.discipline;
      announce(`${climb.grade} ${climb.status.toLowerCase()} saved! Your send count is now ${sends.length}. Try adding an attempt to a project next.`);
      view("progress");
    }
  });
  $("reset-demo").addEventListener("click", () => {
    seed();
    $("climb-form").reset();
    populateGrades();
    $("pyramid-discipline").value = "Boulder";
    announce("Demo reset. The original fictional climbs and projects are back.");
    view("log");
  });
  seed();
  populateGrades();
  render();
  $("demo-shell").hidden = false;
  $("reset-demo").hidden = false;
})();
