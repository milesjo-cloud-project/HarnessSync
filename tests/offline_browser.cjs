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
  page.setDefaultTimeout(60000);
  const errors = [];
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
  assert.equal(new URL(page.url()).hash, "");
  await context.setOffline(true);
  await page.reload();
  await page.getByText("Offline page downloaded.", {exact: false}).waitFor();
  await page.locator("#grade").selectOption("V3");
  await page.getByLabel("Route or problem name").fill("Offline fictional send");
  await page.getByRole("button", {name: "Save on this device"}).click();
  await page.locator("#pending").getByText("Offline fictional send", {exact: false}).waitFor();
  await page.getByRole("button", {name: "Add attempt", exact: true}).click();
  await page.waitForFunction(() => document.querySelectorAll("#pending li").length === 2);
  await page.reload();
  await page.waitForFunction(() => document.querySelectorAll("#pending li").length === 2);
  assert.match(await page.locator("#progress").textContent(), /1 logged climbs/);
  await context.setOffline(false);
  await page.waitForFunction(() => document.getElementById("status").textContent.includes("Up to date"), null, {timeout: 60000});
  assert.match(await page.locator("#progress").textContent(), /2 logged climbs/);
  assert.match(await page.locator("#projects").textContent(), /2 attempts/);
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
  console.log("PASS: offline reopening, durable sends/attempts, downloaded progress, reconnect sync, and lost-response deduplication.");
})().catch(async error => {
  console.error(error);
  if (page) {
    console.error(await page.locator("body").innerText());
    await page.screenshot({path: path.join(folder, "failure.png"), fullPage: true});
  }
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  server.kill();
});
