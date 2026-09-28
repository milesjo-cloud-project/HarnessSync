// HarnessSync Session - a climbing session timer for Meta Ray-Ban Display.
//
// Input needs no custom key handling: the glasses spatially navigate native
// <button>s and activate the focused one, and the same build works with a
// mouse or keyboard in a desktop browser.
//
// Times are stored as timestamps, not tick counts, so the clocks stay correct
// if the app is backgrounded or relaunched mid-session.

const STORAGE_KEY = "harnesssync-session";
const REST_LENGTHS = [60, 120, 180, 300]; // seconds
const RESET_CONFIRM_MS = 3000;

const DEFAULT_STATE = {
  running: false,
  startedAt: null,   // timestamp of the current running stretch
  elapsedMs: 0,      // time banked from earlier stretches (before pauses)
  attempts: 0,
  sends: 0,
  restEndsAt: null,
  restLengthIndex: 2,
};

const $ = (id) => document.getElementById(id);

let state = loadState();
let resetArmedUntil = 0;
let restAnnounced = state.restEndsAt !== null && state.restEndsAt <= Date.now();

// Storage can be unavailable or cleared, so the app must work without it.
function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return saved ? { ...DEFAULT_STATE, ...saved } : { ...DEFAULT_STATE };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Not fatal: the session just won't survive a relaunch.
  }
}

function sessionMs(now) {
  return state.elapsedMs + (state.running ? now - state.startedAt : 0);
}

function formatClock(totalSeconds, withHours) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = String(s % 60).padStart(2, "0");
  if (withHours) return `${hours}:${String(minutes).padStart(2, "0")}:${seconds}`;
  return `${hours * 60 + minutes}:${seconds}`;
}

function restLength() {
  return REST_LENGTHS[state.restLengthIndex] ?? REST_LENGTHS[2];
}

function announce(text) {
  // Speech is a bonus; the same message is always shown on screen.
  if ("speechSynthesis" in window) {
    try {
      speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    } catch {
      // Unsupported on this runtime - the visible readout is enough.
    }
  }
}

function render() {
  const now = Date.now();

  $("session-clock").textContent = formatClock(sessionMs(now) / 1000, true);
  $("attempt-count").textContent = state.attempts;
  $("send-count").textContent = state.sends;
  $("attempt-label").textContent = state.attempts === 1 ? "attempt" : "attempts";
  $("send-label").textContent = state.sends === 1 ? "send" : "sends";
  $("start-btn").textContent = state.running ? "Pause" : (state.elapsedMs ? "Resume" : "Start");
  $("rest-length-btn").textContent = `Length ${formatClock(restLength(), false)}`;

  let status = state.running ? "Climbing" : (state.elapsedMs ? "Paused" : "Ready");
  const restReadout = $("rest-readout");
  if (state.restEndsAt !== null) {
    const remaining = (state.restEndsAt - now) / 1000;
    restReadout.classList.remove("hidden");
    if (remaining > 0) {
      status = "Resting";
      restReadout.classList.remove("done");
      $("rest-clock").textContent = formatClock(Math.ceil(remaining), false);
      $("rest-btn").textContent = "Skip rest";
    } else {
      restReadout.classList.add("done");
      restReadout.textContent = "Rest over - climb!";
      $("rest-btn").textContent = "Start rest";
      if (!restAnnounced) {
        restAnnounced = true;
        announce("Rest over. Climb!");
      }
    }
  } else {
    restReadout.classList.add("hidden");
    $("rest-btn").textContent = "Start rest";
  }
  $("status").textContent = status;

  const armed = now < resetArmedUntil;
  $("reset-btn").textContent = armed ? "Confirm reset" : "Reset";
  $("reset-btn").classList.toggle("armed", armed);
}

// The rest readout's inner <span> is replaced by "Rest over" text, so rebuild
// it whenever a new rest starts.
function resetRestReadout() {
  $("rest-readout").innerHTML = 'Rest <span id="rest-clock"></span>';
}

function startSession() {
  if (!state.running) {
    state.running = true;
    state.startedAt = Date.now();
  }
}

function update(change) {
  change();
  saveState();
  render();
}

$("attempt-btn").addEventListener("click", () => update(() => {
  startSession();
  state.attempts += 1;
}));

$("send-btn").addEventListener("click", () => update(() => {
  startSession();
  state.sends += 1;
}));

$("rest-btn").addEventListener("click", () => update(() => {
  const resting = state.restEndsAt !== null && state.restEndsAt > Date.now();
  if (resting) {
    state.restEndsAt = null;
  } else {
    startSession();
    resetRestReadout();
    restAnnounced = false;
    state.restEndsAt = Date.now() + restLength() * 1000;
  }
}));

$("start-btn").addEventListener("click", () => update(() => {
  if (state.running) {
    state.elapsedMs = sessionMs(Date.now());
    state.running = false;
    state.startedAt = null;
  } else {
    startSession();
  }
}));

$("rest-length-btn").addEventListener("click", () => update(() => {
  state.restLengthIndex = (state.restLengthIndex + 1) % REST_LENGTHS.length;
}));

// Reset wipes the session, so it takes a second press within 3 seconds.
$("reset-btn").addEventListener("click", () => {
  if (Date.now() < resetArmedUntil) {
    resetArmedUntil = 0;
    resetRestReadout();
    update(() => {
      state = { ...DEFAULT_STATE, restLengthIndex: state.restLengthIndex };
    });
  } else {
    resetArmedUntil = Date.now() + RESET_CONFIRM_MS;
    render();
  }
});

if (state.restEndsAt !== null && state.restEndsAt > Date.now()) resetRestReadout();
render();
setInterval(render, 250);
