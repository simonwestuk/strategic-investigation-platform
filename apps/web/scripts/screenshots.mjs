// Captures README screenshots from the app running in fixture mode.
//   NEXT_PUBLIC_USE_FIXTURES=true npx next dev --port 3100   (in another terminal)
//   BASE_URL=http://localhost:3100 npm run screenshots
// Uses the locally installed Chrome (channel "chrome"); set PW_CHANNEL="" to use Playwright's Chromium.
import { chromium } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";

const BASE = process.env.BASE_URL ?? "http://localhost:3100";
const OUT = path.resolve(process.env.OUT_DIR ?? "../../docs/images");
const channel = process.env.PW_CHANNEL ?? "chrome";
const ID = JSON.parse(await readFile(new URL("../fixtures/investigation-decided.json", import.meta.url), "utf8")).summary.id;

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch(channel ? { channel } : {});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: "light" });
const page = await context.newPage();

async function stage(name, persona = "demo") {
  await page.goto(`${BASE}/`);
  await page.evaluate(
    ([s, p]) => {
      localStorage.setItem("sip.fixtureStage", s);
      localStorage.setItem("sip.persona", p);
    },
    [name, persona],
  );
}

async function shot(file, opts = {}) {
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT, file), ...opts });
  console.log("wrote", path.join(OUT, file));
}

// 1. Briefing, ready for the decision
await stage("awaiting-decision", "decision");
await page.goto(`${BASE}/investigations/${ID}`);
await page.getByRole("heading", { name: "What we found" }).waitFor();
await shot("decision-room.png");
await page.setViewportSize({ width: 1440, height: 2600 });
await shot("decision-room-full.png");
await page.setViewportSize({ width: 1440, height: 900 });

// 2. Evidence behind a finding
await page.getByRole("button", { name: "Evidence →" }).first().click();
await page.getByTestId("claim-chain").waitFor();
await shot("claim-chain.png");
await page.keyboard.press("Escape");

// 3. Full working view: hypothesis map
await page.goto(`${BASE}/investigations/${ID}#hypotheses`);
await page.reload();
await page.getByRole("heading", { name: "Hypothesis map" }).waitFor();
await page.evaluate(() => window.scrollTo(0, 0));
await shot("hypothesis-map.png");

// 4. Briefing, asking to release confidential documents
await stage("privacy-review", "privacy");
await page.goto(`${BASE}/investigations/${ID}`);
await page.reload();
await page.getByRole("heading", { name: /Can the agents read/ }).waitFor();
await shot("privacy-review.png");

await browser.close();
