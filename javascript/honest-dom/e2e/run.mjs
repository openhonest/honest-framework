// honest-DOM end-to-end suite (spec §1.1): the real-browser proof. honest-DOM's src is pure over an
// injected bus and query; its collect/apply/observe have only ever run against stubs. Here a fixture
// supplies a real bus (a MutationObserver, delegated listeners, rAF batching) and a real query, and we
// assert the DATAOS round-trip in a real Chromium: collect reads real state, apply writes it, and
// observe fires — through both the event path (typing) and the mutation path (a DOM change).
//
// Requires a Chromium: set HONEST_DOM_CHROMIUM to its executable (or `npx playwright install chromium`).
// No browser is downloaded here.
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
  browser = await pw.chromium.launch({ headless: true, executablePath: process.env.HONEST_DOM_CHROMIUM });
} catch {
  console.log("e2e: SKIPPED — no Chromium available. Run `npx playwright install chromium`, or set HONEST_DOM_CHROMIUM to a Chromium executable.");
  server.close();
  process.exit(0);
}

let failed = 0;
try {
  const page = await browser.newPage();
  await page.goto(`${base}/e2e/fixture/index.html`);
  await page.waitForFunction(() => window.__ready === true);

  // collect reads real DOM state through the real query.
  const collected = await page.evaluate(() => window.__api.collect({ name: { selector: "#name", read: "value" } }, window.__api.query));
  assert.deepEqual(collected, { name: "Ada" });

  // apply writes real DOM state.
  const applied = await page.evaluate(() => {
    window.__api.apply({ name: { selector: "#name", write: "value" } }, { name: "Zed" }, window.__api.query);
    return document.querySelector("#name").value;
  });
  assert.equal(applied, "Zed");

  // observe, event path: typing fires an input event -> the real bus -> rAF -> the callback.
  await page.fill("#name", "Grace");
  await page.waitForFunction(() => window.__observedName === "Grace");

  // observe, mutation path: a DOM text change fires the MutationObserver -> the real bus -> rAF -> the callback.
  await page.evaluate(() => { document.querySelector("#tag").textContent = "omega"; });
  await page.waitForFunction(() => window.__observedTag === "omega");

  console.log("e2e: passed — collect, apply, and observe (event and mutation paths) work through a real bus in a real browser.");
} catch (error) {
  failed = 1;
  console.log(`e2e: FAILED: ${error.message.split("\n")[0]}`);
} finally {
  await browser.close();
  server.close();
}
process.exit(failed);
