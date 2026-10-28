/* No third-party scripts: snapshots, credentials and queued writes stay on-device. */
"use strict";
const $ = id => document.getElementById(id);
const grades = {
  Boulder: ["VB", ...Array.from({length: 18}, (_, i) => `V${i}`)],
  Rope: [...Array.from({length: 10}, (_, i) => `5.${i}`),
    ...Array.from({length: 6}, (_, i) => "abcd".split("").map(s => `5.${10+i}${s}`)).flat()]
};
let db, state, syncing = false, retryTimer, offlineReady = false;
const pairingToken = new URLSearchParams(location.hash.slice(1)).get("device");
// Device tokens never enter request URLs, browser history, or referrer headers.
history.replaceState(null, "", location.pathname);

function requestValue(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
function completed(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onabort = tx.onerror = () => reject(tx.error || new Error(hsT("Device storage failed.")));
  });
}
async function readLocal() {
  const tx = db.transaction(["settings", "queue"], "readonly");
  const done = completed(tx);
  const [settings, pending] = await Promise.all([
    requestValue(tx.objectStore("settings").get("current")),
    requestValue(tx.objectStore("queue").getAll())
  ]);
  await done;
  return {state: settings, pending};
}
async function writeState(next, acknowledged = []) {
  const tx = db.transaction(["settings", "queue"], "readwrite");
  const done = completed(tx);
  const current = await requestValue(tx.objectStore("settings").get("current"));
  if (current?.snapshot.account === next.snapshot.account && current.loggingDefaults) {
    // A log can be saved while a network sync is in flight. Keep its newer defaults.
    next.loggingDefaults = current.loggingDefaults;
  }
  tx.objectStore("settings").put(next, "current");
  for (const id of acknowledged) tx.objectStore("queue").delete(id);
  await done;
  state = next;
}
function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
}
function fillGrades() {
  $("grade").replaceChildren(...grades[$("discipline").value].map(value => new Option(value, value)));
}
function describe(entry) {
  return `${entry.date} · ${hsT(entry.discipline)} ${entry.grade} · ${entry.status ? hsT(entry.status) : hsT("{count} attempts", {count: entry.attempts})} · ${entry.route_name || hsT("Unnamed")}${entry.location ? ` · ${entry.location}` : ""}`;
}
function listItem(text) {
  const li = document.createElement("li"); li.textContent = text; return li;
}
async function render(message) {
  const local = await readLocal(); state = local.state;
  const language = state?.languagePending || state?.snapshot.language;
  if (Object.hasOwn(hsLanguages, language)) {
    hsLanguage = language; hsSelector.value = language; hsApplyLanguage();
  }
  if (offlineReady) $("ready").textContent = hsT("Offline page downloaded. Bookmark this page or add it to your home screen, then test opening it in airplane mode before your trip.");
  const pending = local.pending;
  $("save").disabled = !state;
  $("restore").disabled = !state;
  $("sync").disabled = !state || syncing;
  $("account").textContent = state ? hsT("Connected account: {account}", {account: state.snapshot.account}) : hsT("Connect this device from the main app’s Phone App tab while online.");
  $("status").textContent = message || hsT("{connection} · {count} waiting to sync", {connection: hsT(navigator.onLine ? "Online" : "Offline"), count: pending.length});
  $("pending").replaceChildren(...(pending.length ? pending.map(op => listItem(describe(op.entry))) : [listItem(hsT("No entries waiting."))]));
  const snapshot = state?.snapshot;
  $("downloaded").textContent = snapshot ? hsT("Last downloaded: {date}. Pending entries are listed above.", {date: new Date(snapshot.downloaded_at).toLocaleString(hsLanguage)}) : hsT("No download yet.");
  $("projects").replaceChildren(...(snapshot?.projects || []).map(project => {
    const li = listItem(describe(project));
    const button = document.createElement("button"); button.type = "button"; button.textContent = hsT("Add attempt");
    button.addEventListener("click", () => queueEntry({
      discipline: project.discipline, grade: project.grade, status: "Attempt", date: localDate(),
      route_name: project.route_name, location: project.location, environment: project.environment,
      angle: project.angle, hold_type: project.hold_type, notes: ""
    }).catch(showError));
    li.append(document.createElement("br"), button); return li;
  }));
  const climbs = snapshot?.climbs || [];
  const best = discipline => {
    const sent = climbs.filter(c => c.discipline === discipline && ["Sent","Flash","Onsight","Redpoint"].includes(c.status));
    return sent.reduce((value, c) => grades[discipline].indexOf(c.grade) > grades[discipline].indexOf(value) ? c.grade : value, "None");
  };
  $("progress").textContent = hsT("{count} logged climbs · Best boulder: {boulder} · Best rope: {rope}", {count: climbs.length, boulder: hsT(best("Boulder")), rope: hsT(best("Rope"))});
  $("history").replaceChildren(...climbs.map(c => listItem(describe(c))));
}
function showError(error) { $("error").textContent = hsT(error.message || "Something went wrong. Your entries remain on this device."); }
const entryFields = ["discipline", "grade", "status", "date", "route_name", "location", "environment", "angle", "hold_type", "notes"];
function hasFields(value, fields) {
  return value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).length === fields.length && fields.every(key => Object.hasOwn(value, key));
}
function entryKey(entry) { return JSON.stringify(entryFields.map(key => entry[key])); }
function validateBackup(backup, account) {
  if (!hasFields(backup, ["version", "operations"]) || backup.version !== 1 || !Array.isArray(backup.operations)
      || backup.operations.length > 10000) throw new Error(hsT("Choose a HarnessSync version 1 backup with at most 10,000 entries."));
  const validated = new Map();
  for (const operation of backup.operations) {
    if (!hasFields(operation, ["id", "entry", "account"]) || typeof operation.id !== "string"
        || !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(operation.id)) throw new Error(hsT("Backup contains an invalid entry identifier."));
    if (operation.account !== account) throw new Error(hsT("This backup belongs to another account. Connect its original account to restore it."));
    const entry = operation.entry;
    if (!hasFields(entry, entryFields) || entryFields.some(key => typeof entry[key] !== "string")) throw new Error(hsT("Backup contains invalid climb fields."));
    if (!Object.hasOwn(grades, entry.discipline) || !grades[entry.discipline].includes(entry.grade)
        || !["Sent", "Flash", "Onsight", "Redpoint", "Attempt", "Project"].includes(entry.status)
        || !["Outdoor", "Gym"].includes(entry.environment)
        || !["Vertical", "Slab", "Overhang", "Roof"].includes(entry.angle)
        || !["Mixed", "Crimps", "Slopers", "Jugs", "Pinches", "Pockets"].includes(entry.hold_type)) throw new Error(hsT("Backup contains an invalid grade or climb choice."));
    const parsed = new Date(`${entry.date}T00:00:00Z`);
    const tomorrow = new Date(); tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(entry.date) || !Number.isFinite(parsed.getTime())
        || parsed.toISOString().slice(0, 10) !== entry.date || entry.date > tomorrow.toISOString().slice(0, 10)) throw new Error(hsT("Backup contains an invalid climb date."));
    for (const [field, limit] of [["route_name", 80], ["location", 80], ["notes", 500]]) {
      if (Array.from(entry[field]).length > limit) throw new Error(`Backup ${field} is too long.`);
    }
    const existing = validated.get(operation.id);
    if (existing && entryKey(existing.entry) !== entryKey(entry)) throw new Error(hsT("Backup reuses an entry identifier with different data. Nothing was restored."));
    validated.set(operation.id, operation);
  }
  return [...validated.values()];
}
async function restoreBackup(file) {
  if (!file) throw new Error(hsT("Choose your exported JSON backup first."));
  if (file.size > 10 * 1024 * 1024) throw new Error(hsT("Backup exceeds the 10 MB limit."));
  let backup;
  try { backup = JSON.parse(await file.text()); }
  catch { throw new Error(hsT("Could not read this JSON backup. Nothing was restored.")); }
  let restored = 0;
  await locked(async () => {
    const local = await readLocal();
    if (!local.state) throw new Error(hsT("Connect the original account before restoring a backup."));
    const operations = validateBackup(backup, local.state.snapshot.account);
    const tx = db.transaction(["settings", "queue"], "readwrite"), done = completed(tx);
    // Validate every conflict before adding anything; concurrent local saves serialize here.
    try {
      const current = await requestValue(tx.objectStore("settings").get("current"));
      if (!current || current.snapshot.account !== local.state.snapshot.account) throw new Error(hsT("Account changed. Reload before restoring."));
      const existing = new Map((await requestValue(tx.objectStore("queue").getAll())).map(op => [op.id, op]));
      for (const operation of operations) {
        const prior = existing.get(operation.id);
        if (prior && (prior.account !== operation.account || entryKey(prior.entry) !== entryKey(operation.entry))) throw new Error(hsT("Backup conflicts with an entry on this device. Nothing was restored."));
      }
      for (const operation of operations) {
        if (!existing.has(operation.id)) { tx.objectStore("queue").add(operation); restored++; }
      }
    } catch (error) { tx.abort(); await done.catch(() => {}); throw error; }
    await done;
  });
  $("error").textContent = "";
  $("restore-status").textContent = hsT("{count} entries restored. Existing entries were kept. Entries already saved to your account will be recognized during sync.", {count: restored});
  await render(hsT("Backup restored · ready to sync"));
  void sync();
}
async function queueEntry(entry, rememberDefaults = false) {
  if (!state) throw new Error(hsT("Connect this device before logging."));
  const tx = db.transaction(["queue", "settings"], "readwrite");
  const done = completed(tx);
  // Read and add in one transaction so another tab cannot switch accounts between them.
  const current = await requestValue(tx.objectStore("settings").get("current"));
  if (!current || current.snapshot.account !== state.snapshot.account) {
    tx.abort(); await done.catch(() => {});
    throw new Error(hsT("Account changed in another tab. Reload before logging."));
  }
  tx.objectStore("queue").add({id: crypto.randomUUID(), entry, account: current.snapshot.account});
  if (rememberDefaults) current.loggingDefaults = Object.fromEntries(["discipline", "grade", "environment", "location"].map(key => [key, entry[key]]));
  tx.objectStore("settings").put(current, "current");
  await done;
  $("error").textContent = "";
  await render(hsT("Saved on this device · waiting to sync"));
  void sync();
}
async function post(token, operations, language) {
  const response = await fetch("api/sync", {
    method: "POST", cache: "no-store", credentials: "omit",
    headers: {"Content-Type": "application/json", "Authorization": `Bearer ${token}`},
    body: JSON.stringify({operations, ...(language ? {language} : {})}), signal: AbortSignal.timeout(20000)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Sync unavailable. Entries remain on this device.");
  return result;
}
async function locked(action) {
  if (!navigator.locks) throw new Error(hsT("This browser cannot safely sync offline entries. Use a current Safari, Chrome, Edge or Firefox browser."));
  return navigator.locks.request("harnesssync-offline-sync", action);
}
async function sync({refresh = false} = {}) {
  if (!db || syncing || !navigator.onLine || document.visibilityState === "hidden") return;
  syncing = true;
  clearTimeout(retryTimer);
  try {
    await locked(async () => {
      let local = await readLocal();
      if (!local.state) return;
      do {
        const batch = local.pending.slice(0, 100);
        // Imported Unicode/control characters can need extra JSON bytes.
        while (batch.length > 1 && new TextEncoder().encode(JSON.stringify({operations: batch.map(({id, entry}) => ({id, entry}))})).length > 220000) batch.pop();
        // Refresh downloaded history on open/reconnect/manual refresh, never on idle retries.
        if (!batch.length && !refresh && !local.state.languagePending) return;
        if (batch.some(op => op.account !== local.state.snapshot.account)) throw new Error(hsT("Queued entries belong to another account. Export them before reconnecting."));
        $("status").textContent = hsT("Syncing {count} entries…", {count: batch.length});
        const result = await post(local.state.token, batch.map(({id, entry}) => ({id, entry})), local.state.languagePending);
        if (result.snapshot.account !== local.state.snapshot.account) throw new Error(hsT("Account mismatch. Entries were kept on this device."));
        await writeState({...local.state, languagePending: null, snapshot: result.snapshot}, result.acknowledged);
        local = await readLocal();
      } while (local.pending.length);
      $("error").textContent = "";
      await render(hsT("Up to date · all entries saved to your account"));
    });
  } catch (error) {
    showError(error);
    await render(hsT("Sync paused · entries kept on this device"));
  } finally {
    syncing = false;
    $("sync").disabled = !state;
    const local = await readLocal();
    if ((local.pending.length || local.state?.languagePending) && navigator.onLine) retryTimer = setTimeout(() => void sync(), 15000);
  }
}
async function boot() {
  if (!window.isSecureContext || !window.indexedDB || !navigator.serviceWorker) throw new Error(hsT("Offline logging requires HTTPS (or localhost) and device storage support."));
  const open = indexedDB.open("harnesssync-offline", 1);
  open.onupgradeneeded = () => {
    open.result.createObjectStore("settings");
    open.result.createObjectStore("queue", {keyPath: "id"});
  };
  db = await requestValue(open);
  db.onversionchange = () => { db.close(); showError(new Error(hsT("App updated. Reload this page."))); };
  state = (await readLocal()).state;
  if (pairingToken) await locked(async () => {
    const result = await post(pairingToken, []);
    const local = await readLocal();
    if (local.state && local.state.snapshot.account !== result.snapshot.account) {
      throw new Error(hsT("This browser is connected to another account. Export unsynced entries and remove local data before switching accounts."));
    }
    await writeState({...local.state, token: pairingToken, snapshot: result.snapshot});
  });
  const defaults = state?.loggingDefaults || state?.snapshot.climbs?.[0];
  if (defaults && Object.hasOwn(grades, defaults.discipline)) {
    $("discipline").value = defaults.discipline; fillGrades();
    if (grades[defaults.discipline].includes(defaults.grade)) $("grade").value = defaults.grade;
    if (["Gym", "Outdoor"].includes(defaults.environment)) $("log").elements.environment.value = defaults.environment;
    $("log").elements.location.value = defaults.location || "";
  }
  try { await navigator.storage?.persist?.(); } catch { /* Saving still works without persistence permission. */ }
  await navigator.serviceWorker.register("sw.js", {scope: "./"});
  await navigator.serviceWorker.ready;
  offlineReady = true;
  $("ready").textContent = hsT("Offline page downloaded. Bookmark this page or add it to your home screen, then test opening it in airplane mode before your trip.");
  await render();
  void sync({refresh: true});
}
$("discipline").addEventListener("change", fillGrades);
hsSelector.addEventListener("change", async () => {
  hsLanguage = hsSelector.value;
  const choice = hsLanguage;
  hsApplyLanguage();
  if (db) {
    try {
      await locked(async () => {
        const local = await readLocal();
        if (local.state) await writeState({...local.state, languagePending: choice});
      });
    } catch (error) { showError(error); }
    $("ready").textContent = hsT("Offline page downloaded. Bookmark this page or add it to your home screen, then test opening it in airplane mode before your trip.");
    await render().catch(showError);
    void sync();
  }
});
fillGrades(); $("date").value = localDate(); $("date").max = localDate();
$("log").addEventListener("submit", async event => {
  event.preventDefault();
  if ($("save").disabled) return;
  $("save").disabled = true;
  try {
    await queueEntry(Object.fromEntries(new FormData(event.target)), true);
    event.target.elements.route_name.value = ""; event.target.elements.notes.value = "";
    event.target.elements.status.value = "Sent";
    $("date").value = localDate(); $("date").max = localDate();
  } catch (error) { showError(error); }
  finally { $("save").disabled = !state; }
});
$("sync").addEventListener("click", () => void sync({refresh: true}));
addEventListener("online", () => void sync({refresh: true}));
addEventListener("offline", () => { if (db) void render(); });
document.addEventListener("visibilitychange", () => { if (!document.hidden) void sync({refresh: true}); });
$("backup").addEventListener("click", async () => {
  try {
    const local = await readLocal();
    const blob = new Blob([JSON.stringify({version: 1, operations: local.pending}, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = "harnesssync-unsynced.json"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { showError(error); }
});
$("restore").addEventListener("click", async () => {
  $("restore").disabled = true;
  $("restore-status").textContent = "";
  try { await restoreBackup($("restore-file").files[0]); }
  catch (error) { showError(error); }
  finally { $("restore").disabled = !state; }
});
$("forget").addEventListener("click", async () => {
  try {
    await locked(async () => {
      const local = await readLocal();
      if (local.pending.length) throw new Error(hsT("Sync or export your unsynced entries before removing this device’s data."));
      if (!confirm(hsT("Remove the downloaded log and device connection from this browser?"))) return;
      const tx = db.transaction(["settings", "queue"], "readwrite"), done = completed(tx);
      const count = await requestValue(tx.objectStore("queue").count());
      if (count) {
        tx.abort(); await done.catch(() => {});
        throw new Error(hsT("Another tab saved an entry. Sync or export it before removing data."));
      }
      tx.objectStore("settings").clear(); await done;
      await render(hsT("Local data removed. You can also revoke device access in the main app."));
    });
  } catch (error) { showError(error); }
});
boot().catch(async error => { showError(error); if (db) await render(hsT("Setup needs attention · existing entries kept")); });
