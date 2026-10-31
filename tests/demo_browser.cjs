/* Public presentation only. Run: node tests/demo_browser.cjs (Playwright required). */
const {chromium} = require("playwright");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs/promises");
const path = require("node:path");
const {pathToFileURL} = require("node:url");
const root = path.resolve(__dirname, "../docs");
const types = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".zip": "application/zip"};
const prefix = "/HarnessSync/";
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://localhost");
    if (request.method !== "GET" || !url.pathname.startsWith(prefix)) throw new Error("Not public");
    const relative = decodeURIComponent(url.pathname.slice(prefix.length)) || "index.html";
    const file = path.resolve(root, relative);
    if (!file.startsWith(root + path.sep)) throw new Error("Not public");
    const content = await fs.readFile(file);
    response.writeHead(200, {"Content-Type": types[path.extname(file)] || "application/octet-stream", "Cache-Control": "no-store"});
    response.end(content);
  } catch {
    response.writeHead(404);
    response.end("Not found");
  }
});
let browser;
(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}${prefix}`;
  browser = await chromium.launch({headless: true});
  const context = await browser.newContext({viewport: {width: 390, height: 844}});
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(base + "demo.html");
  await page.getByText("Demo downloaded for offline use.", {exact: false}).waitFor();
  await context.setOffline(true);
  await page.reload();
  await page.getByText("Demo downloaded for offline use.", {exact: false}).waitFor();
  await page.getByRole("button", {name: "Save climb →", exact: true}).click();
  await page.locator("#view-progress").waitFor({state: "visible"});
  assert.equal(await page.locator("#total-sends").textContent(), "14");
  await page.getByRole("button", {name: "↗ Projects 2", exact: true}).click();
  await page.locator("#notes-1").fill("Fictional offline beta");
  await page.getByRole("button", {name: "Save notes", exact: true}).first().click();
  await page.getByRole("button", {name: "＋ Attempt", exact: true}).first().click();
  assert.match(await page.locator(".project-card").first().textContent(), /9 attempts/);
  assert.equal(await page.locator("#notes-1").inputValue(), "Fictional offline beta");
  await page.getByRole("button", {name: "Sent it! ↗", exact: true}).first().click();
  await page.locator("#view-progress").waitFor({state: "visible"});
  assert.equal(await page.locator("#total-sends").textContent(), "15");
  assert.equal(await page.locator("#best-boulder").textContent(), "V5");
  await page.goto(base); // GitHub Pages subdirectory and directory-index routing.
  await page.getByRole("heading", {name: "Every climb adds up."}).waitFor();
  await page.getByRole("link", {name: "Try the interactive demo →", exact: true}).click();
  await page.getByRole("button", {name: "Reset demo ↺", exact: true}).waitFor();
  await page.getByRole("button", {name: "▥ Progress", exact: true}).click();
  assert.equal(await page.locator("#total-sends").textContent(), "13");
  // Unknown paths and POSTs must not be served a cached demo page.
  assert.equal(await page.evaluate(async base => {
    try { await fetch(base + "account/private"); return "unexpected response"; }
    catch { return "network unavailable"; }
  }, base), "network unavailable");
  assert.equal(await page.evaluate(async base => {
    try { await fetch(base + "demo.html", {method: "POST", body: "fictional"}); return "unexpected response"; }
    catch { return "network unavailable"; }
  }, base), "network unavailable");
  const fileContext = await browser.newContext({offline: true});
  const local = await fileContext.newPage();
  local.on("pageerror", error => errors.push(error.message));
  const remoteRequests = [];
  local.on("request", request => { if (/^https?:/.test(request.url())) remoteRequests.push(request.url()); });
  await local.goto(pathToFileURL(path.join(root, "downloads/harnesssync-demo-offline.html")).href);
  await local.getByRole("button", {name: "Save climb →", exact: true}).click();
  await local.locator("#view-progress").waitFor({state: "visible"});
  assert.equal(await local.locator("#total-sends").textContent(), "14");
  await local.getByRole("button", {name: "Reset demo ↺", exact: true}).click();
  await local.getByRole("button", {name: "▥ Progress", exact: true}).click();
  assert.equal(await local.locator("#total-sends").textContent(), "13");
  // No localhost origin, server, sibling assets, or prior online visit needed.
  assert.deepEqual(remoteRequests, []);
  assert.deepEqual(errors, []);
  await fileContext.close();
  await context.close();
  console.log("PASS: hosted demo caches under /HarnessSync/, reopens offline, logs sends, saves beta, tracks attempts, graduates projects, and serves the homepage. Downloaded single-file demo works from file:// with no network. Private paths and POSTs are not cached.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
});
