/* Run with NODE_PATH pointing at Playwright, and Python with requirements-dev installed:
   node tests/offline_browser.cjs .venv/Scripts/python.exe
   Uses only a temporary SQLite database and fictional data. */
const {chromium} = require("playwright");
const {spawn} = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const tempRoot = path.join(root, ".test-tmp");
fs.mkdirSync(tempRoot, {recursive: true});
const folder = fs.mkdtempSync(path.join(tempRoot, "offline-browser-"));
const port = 18765;
const url = `http://127.0.0.1:${port}/offline/`;
const python = process.argv[2] || "python";
const server = spawn(python, [path.join(__dirname, "offline_browser_server.py"), folder, String(port)], {
  cwd: root, env: {...process.env, PYTHONPATH: root, TEMP: tempRoot, TMP: tempRoot}, stdio: ["ignore", "pipe", "pipe"]
});
let browser, page, serverError = "";
server.stderr.on("data", data => { serverError += data; });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
  for (let attempt = 0; attempt < 100; attempt++) {
    try { if ((await fetch(url)).ok) break; } catch {}
    if (attempt === 99 || server.exitCode !== null) throw new Error(`Fixture did not start: ${serverError}`);
    await pause(200);
  }
  browser = await chromium.launch({headless: true, args: [`--log-file=${path.join(folder, "browser.log")}`]});
  const context = await browser.newContext({viewport: {width: 390, height: 844}});
  page = await context.newPage();
  await page.clock.install();
  page.setDefaultTimeout(60000);
  const errors = [];
  const languageTrace = [];
  page.on("response", async response => {
    if (response.url().endsWith("/offline/api/sync") && response.ok()) {
      const request = response.request().postDataJSON();
      const result = await response.json().catch(() => ({}));
      languageTrace.push({sent: request.language || null, received: result.snapshot?.language});
    }
  });
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.getByRole("tab", {name: "📱 Phone App", exact: true}).click();
  await page.getByRole("button", {name: "Connect this device for offline use", exact: true}).click();
  const connection = await page.getByRole("link", {name: "Open offline log on this device", exact: true}).getAttribute("href");
  assert.ok(connection.startsWith(url), "Connection must point at this server’s offline page");
  await page.goto(connection);
  await page.getByText("Offline page downloaded.", {exact: false}).waitFor();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await page.waitForFunction(() => document.getElementById("status").textContent.includes("Up to date"), null, {timeout: 60000});
  await page.waitForFunction(() => !syncing);
  let idleRequests = 0;
  const countSync = request => { if (request.url().endsWith("/offline/api/sync")) idleRequests++; };
  page.on("request", countSync);
  await page.clock.fastForward(60000);
  await pause(300);
  assert.equal(idleRequests, 0, "An empty queue must not poll or download history while idle");
  const manualRefresh = page.waitForResponse("**/offline/api/sync");
  await page.getByRole("button", {name: "Sync now", exact: true}).click();
  await manualRefresh;
  await page.waitForFunction(() => !syncing);
  assert.equal(idleRequests, 1, "Manual sync must still refresh downloaded progress");
  page.off("request", countSync);
  assert.equal(new URL(page.url()).hash, "");
  await context.setOffline(true);
  await page.reload();
  await page.getByText("Offline page downloaded.", {exact: false}).waitFor();
  // Language assets must work without networking and preserve canonical form
  // values and draft text when the visible labels change.
  await page.locator("#log-details summary").click();
  await page.locator('[name="route_name"]').fill("Fictional multilingual draft");
  for (const [language, saveLabel] of [["es", "Guardar en este dispositivo"], ["fr", "Enregistrer sur cet appareil"],
      ["ja", "この端末に保存"], ["ko", "이 기기에 저장"], ["zh", "保存到此设备"]]) {
    await page.locator("#language").selectOption(language);
    await page.waitForFunction(async code => (await readLocal()).state.languagePending === code, language);
    assert.equal(await page.locator("#save").textContent(), saveLabel);
    assert.equal(await page.locator('[name="discipline"]').inputValue(), "Boulder");
    assert.equal(await page.locator('[name="status"]').inputValue(), "Sent");
    assert.equal(await page.locator('[name="route_name"]').inputValue(), "Fictional multilingual draft");
  }
  await page.reload();
  await page.getByRole("button", {name: "保存到此设备", exact: true}).waitFor();
  assert.equal(await page.locator("#language").inputValue(), "zh");
  assert.equal(await page.locator("html").getAttribute("lang"), "zh-Hans");
  await page.locator("#language").selectOption("en");
  await page.getByText("Offline page downloaded.", {exact: false}).waitFor();
  await page.waitForFunction(async () => (await readLocal()).state.languagePending === "en");
  await page.locator("#log-details summary").click();
  await page.locator("#grade").selectOption("V3");
  await page.getByLabel("Route or problem name").fill("Offline fictional send");
  await page.getByRole("button", {name: "Save on this device"}).click();
  await page.locator("#pending").getByText("Offline fictional send", {exact: false}).waitFor();
  await page.getByRole("button", {name: "Add attempt", exact: true}).click();
  await page.waitForFunction(() => document.querySelectorAll("#pending li").length === 2);
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", {name: "Export unsynced entries", exact: true}).click();
  const backupPath = path.join(folder, "backup.json");
  await (await downloadEvent).saveAs(backupPath);
  const backup = JSON.parse(fs.readFileSync(backupPath, "utf8"));
  assert.equal(backup.operations.length, 2);
  async function importFile(target, value) {
    await target.locator("#restore-file").setInputFiles({name: "backup.json", mimeType: "application/json",
      buffer: Buffer.from(typeof value === "string" ? value : JSON.stringify(value))});
    await target.getByRole("button", {name: "Restore backup", exact: true}).click();
    await target.waitForFunction(() => !document.getElementById("restore").disabled);
  }
  await importFile(page, backup);
  assert.match(await page.locator("#restore-status").textContent(), /0 entries restored/);
  await importFile(page, "{broken json");
  assert.match(await page.locator("#error").textContent(), /Could not read/);
  const wrongAccount = structuredClone(backup);
  wrongAccount.operations[0].account = "fictional:someone-else";
  await importFile(page, wrongAccount);
  assert.match(await page.locator("#error").textContent(), /another account/);
  const invalid = structuredClone(backup);
  invalid.operations[0].id = require("node:crypto").randomUUID();
  invalid.operations[1].entry.date = "2026-02-30";
  await importFile(page, invalid);
  assert.match(await page.locator("#error").textContent(), /invalid climb date/);
  const conflict = structuredClone(backup);
  conflict.operations[0].id = require("node:crypto").randomUUID();
  conflict.operations[1].entry.notes = "conflicting contents";
  await importFile(page, conflict);
  assert.match(await page.locator("#error").textContent(), /conflicts with an entry/);
  assert.equal(await page.locator("#pending li").count(), 2, "Rejected imports must not partially add entries");
  // Recover onto a fresh browser/device, preserving operation identifiers.
  const recoveryContext = await browser.newContext();
  const recovery = await recoveryContext.newPage();
  recovery.on("pageerror", error => errors.push(error.message));
  await recovery.goto(connection);
  await recovery.waitForFunction(() => !!navigator.serviceWorker.controller && !syncing && state);
  await recoveryContext.setOffline(true);
  await importFile(recovery, backup);
  assert.match(await recovery.locator("#restore-status").textContent(), /2 entries restored/);
  await recovery.reload();
  await recovery.waitForFunction(() => document.querySelectorAll("#pending li").length === 2);
  await recoveryContext.setOffline(false);
  await recovery.waitForFunction(() => document.getElementById("status").textContent.includes("Up to date"), null, {timeout: 60000});
  assert.match(await recovery.locator("#progress").textContent(), /2 logged climbs/);
  assert.match(await recovery.locator("#projects").textContent(), /2 attempts/);
  // Reimport an already-synced backup: server receipts also prevent duplicates.
  await importFile(recovery, backup);
  await recovery.waitForFunction(() => !syncing && document.getElementById("status").textContent.includes("Up to date"), null, {timeout: 60000});
  assert.match(await recovery.locator("#progress").textContent(), /2 logged climbs/);
  assert.match(await recovery.locator("#projects").textContent(), /2 attempts/);
  await recoveryContext.close();
  await page.reload();
  await page.waitForFunction(() => document.querySelectorAll("#pending li").length === 2);
  assert.match(await page.locator("#progress").textContent(), /1 logged climbs/);
  await context.setOffline(false);
  await page.waitForFunction(() => document.getElementById("status").textContent.includes("Up to date"), null, {timeout: 60000});
  assert.match(await page.locator("#progress").textContent(), /2 logged climbs/);
  assert.match(await page.locator("#projects").textContent(), /2 attempts/);
  // Defaults survive reopening without reusing a route name. Language changes
  // on the phone must reach the same account and return on a fresh device.
  assert.equal(await page.locator("#grade").inputValue(), "V3");
  assert.equal(await page.locator('[name="route_name"]').inputValue(), "");
  await page.locator("#log-details summary").click();
  await page.locator("#language").selectOption("fr");
  await page.waitForFunction(async () => !syncing && (await readLocal()).state.snapshot.language === "fr");
  const languageContext = await browser.newContext();
  const languagePage = await languageContext.newPage();
  await languagePage.goto(connection);
  await languagePage.bringToFront();
  await languagePage.waitForFunction(() => !syncing && state?.snapshot.language === "fr" && hsSelector.value === "fr");
  assert.equal(await languagePage.locator("#language").inputValue(), "fr");
  await languagePage.locator("#language").selectOption("ja");
  await languagePage.waitForFunction(async () => !syncing && (await readLocal()).state.snapshot.language === "ja");
  await languageContext.close();
  // Returning from the second device can trigger a visibility refresh. Wait
  // until it finishes: sync() deliberately skips hidden or already-syncing pages.
  await page.bringToFront();
  await page.waitForFunction(() => document.visibilityState === "visible" && !syncing);
  const languageRefresh = page.waitForResponse("**/offline/api/sync");
  await page.locator("#sync").click();
  const languageResponse = await languageRefresh;
  assert.equal(languageResponse.status(), 200);
  assert.equal((await languageResponse.json()).snapshot.language, "ja", JSON.stringify(languageTrace));
  await page.waitForFunction(() => !syncing && hsLanguage === "ja" && hsSelector.value === "ja");
  await page.locator("#language").selectOption("en");
  await page.waitForFunction(() => !syncing && state?.snapshot.language === "en");
  // Commit on the server, then lose the acknowledgement. The retry must not insert twice.
  await page.route("**/offline/api/sync", async route => {
    await route.fetch();
    await route.abort("failed");
  });
  await page.getByLabel("Route or problem name").fill("Lost acknowledgement send");
  await page.getByRole("button", {name: "Save on this device"}).click();
  await page.waitForFunction(() => document.getElementById("status").textContent.includes("Sync paused"));
  assert.match(await page.locator("#pending").textContent(), /Lost acknowledgement send/);
  await page.unroute("**/offline/api/sync");
  await page.getByRole("button", {name: "Sync now", exact: true}).click();
  await page.waitForFunction(() => document.getElementById("status").textContent.includes("Up to date"));
  assert.match(await page.locator("#progress").textContent(), /3 logged climbs/);
  assert.equal(await page.locator("#history li").filter({hasText: "Lost acknowledgement send"}).count(), 1);
  assert.deepEqual(errors, []);
  await page.screenshot({path: path.join(folder, "phone.png"), fullPage: true});
  console.log("PASS: no idle polling, manual refresh, backup recovery on a fresh device, duplicate/invalid/conflicting import protection, offline reopening, reconnect sync, and lost-response deduplication.");
})().catch(async error => {
  console.error(error);
  if (page) {
    console.error(await page.evaluate(async () => ({visibility: document.visibilityState,
      syncing, displayedLanguage: hsLanguage, selectedLanguage: hsSelector.value,
      snapshotLanguage: (await readLocal()).state?.snapshot.language,
      pendingLanguage: (await readLocal()).state?.languagePending})));
    console.error(await page.locator("body").innerText());
    await page.screenshot({path: path.join(folder, "failure.png"), fullPage: true});
  }
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  server.kill();
});
