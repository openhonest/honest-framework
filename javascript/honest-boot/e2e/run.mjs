// honest-boot end-to-end suite (spec §9): the real-browser proof. A static server serves the module and
// the fixture; a headless Chromium loads the fixture, whose composition root wires the real deps and
// calls boot. We assert the whole pipeline ran in a real browser — a declared element is loaded, its
// module inits it, and hf.browser.classify is emitted — then simulate an HTMX swap and assert the shared
// observer drives a rescan of the new content.
//
// Requires a Chromium: set HONEST_BOOT_CHROMIUM to its executable (e.g. a `npx playwright install
// chromium` binary, or a cached Chrome for Testing). No browser is downloaded here.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import pw from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const rootDir = join(here, "..");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript" };

const server = createServer(async (req, res) => {
  try {
    const url = req.url.split("?")[0];
    const body = await readFile(join(rootDir, url));
    res.setHeader("Content-Type", TYPES[extname(url)] || "text/plain");
    res.end(body);
  } catch {
    res.statusCode = 404;
    res.end("not found");
  }
});

await new Promise((resolve) => server.listen(0, resolve));
const base = `http://localhost:${server.address().port}`;

let browser;
try {
  browser = await pw.chromium.launch({ headless: true, executablePath: process.env.HONEST_BOOT_CHROMIUM });
} catch {
  console.log("e2e: SKIPPED — no Chromium available. Run `npx playwright install chromium`, or set HONEST_BOOT_CHROMIUM to a Chromium executable.");
  server.close();
  process.exit(0);
}
let failed = 0;
try {
  const page = await browser.newPage();
  await page.goto(`${base}/e2e/fixture/index.html`);
  await page.waitForFunction(() => window.__booted === true);

  // Initial pass: the declared element's module loaded and inited it, and it was classified.
  assert.equal(await page.getAttribute("#first", "data-formatted"), "currency");
  assert.deepEqual(await page.evaluate(() => window.__classified), ["currency"]);

  // Simulate an HTMX swap: insert a new declared element; the observer must drive a rescan.
  await page.evaluate(() => {
    const span = document.createElement("span");
    span.id = "second";
    span.setAttribute("hf-format", "date");
    span.textContent = "5";
    document.body.appendChild(span);
  });
  await page.waitForFunction(() => document.getElementById("second")?.dataset.formatted === "date");
  assert.ok((await page.evaluate(() => window.__classified)).includes("date"));

  console.log("e2e: passed — initial load/init/classify, and rescan on swap, in a real browser.");
} catch (error) {
  failed = 1;
  console.log(`e2e: FAILED: ${error.message.split("\n")[0]}`);
} finally {
  await browser.close();
  server.close();
}
process.exit(failed);
