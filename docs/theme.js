// Light/dark theme switch.
//
// With no JavaScript the page still themes itself from the OS setting via
// prefers-color-scheme, and the button stays hidden rather than sitting there
// doing nothing. The pre-paint snippet inlined in each page's <head> applies
// a saved choice before the first paint, so there's no flash of the wrong
// theme; this file only handles the button and later OS changes.

const STORAGE_KEY = "harnesssync-theme";
const root = document.documentElement;
const toggle = document.getElementById("theme-toggle");
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

function savedTheme() {
  // Storage throws in some privacy modes, and may hold anything.
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "light" || saved === "dark" ? saved : null;
  } catch {
    return null;
  }
}

function activeTheme() {
  return root.getAttribute("data-theme") || (systemDark.matches ? "dark" : "light");
}

function apply(theme) {
  root.setAttribute("data-theme", theme);
  const next = theme === "dark" ? "light" : "dark";
  // The icon is decorative; the label is what assistive tech announces, and
  // it names the action rather than the current state.
  toggle.setAttribute("aria-label", `Switch to ${next} theme`);
  toggle.querySelector(".theme-icon").textContent = theme === "dark" ? "☀" : "☾";
}

if (toggle) {
  toggle.hidden = false;
  apply(activeTheme());

  toggle.addEventListener("click", () => {
    const next = activeTheme() === "dark" ? "light" : "dark";
    apply(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not fatal: the choice just won't survive a reload.
    }
  });

  // Keep following the OS for anyone who hasn't overridden it here.
  systemDark.addEventListener("change", (event) => {
    if (!savedTheme()) apply(event.matches ? "dark" : "light");
  });
}
