#!/usr/bin/env node
/**
 * Scaffold for a one-off probe against a live OM Chat GUI.
 *
 * Copy this into a scratch directory, edit the QUESTION block, run it with
 * plain `node`. It is deliberately not wired into om-chat.mjs: a probe answers
 * one question once and is then thrown away, so it never has to grow flags,
 * defaults, or a report format.
 *
 * The two absolute paths below are what make it runnable from anywhere:
 * Playwright is resolved out of this skill's own node_modules (the project
 * under test never has to carry it), and the browser profile is the same
 * persistent context `om-chat.mjs login` writes, so the page is already
 * authenticated.
 */

import { join } from "node:path";
import { chromium } from "/Users/ryan/.claude/skills/testing-harness/node_modules/playwright/index.mjs";

// `local-prod` is the local daemon as the prod user; `cloud-prod` is
// openmarket.xyz. Run `om-chat.mjs login --target cloud` first if the cloud
// profile does not exist yet.
const PROFILE = join(
  process.env.HOME,
  ".claude",
  "state",
  "testing-harness",
  "profiles",
  "local-prod",
);

// 31417 is the source-run rig (`bun run dev`); the installed daemon listens on
// 31337. Point this at whichever daemon is actually serving the branch.
const BASE = process.env.OM_CHAT_BASE ?? "http://127.0.0.1:31417/rooms";

const ctx = await chromium.launchPersistentContext(PROFILE, {
  headless: true,
  viewport: { width: 1440, height: 900 },
  colorScheme: "dark",
});
const page = ctx.pages()[0] ?? (await ctx.newPage());

// Surface failures that would otherwise look like an empty page.
page.on("crash", () => console.log("!! PAGE CRASH"));
page.on("pageerror", (e) => console.log("!! PAGEERROR:", e.message));
page.on("console", (m) => {
  if (m.type() === "error") console.log("!! console.error:", m.text().slice(0, 300));
});

await page.goto(`${BASE}#/`, { waitUntil: "domcontentloaded" });
// The shell hydrates, then rooms arrive over the websocket. Wait for a real
// signal rather than a timeout wherever one exists.
await page.waitForSelector("textarea[data-composer-input], .message-row", { timeout: 20_000 });

// --- QUESTION -------------------------------------------------------------
// Read the answer out of the page with page.evaluate and print it. Keep the
// output small and greppable: this is a probe, not a report.
const answer = await page.evaluate(() => ({
  url: location.href,
  rows: document.querySelectorAll(".message-row").length,
  hasComposer: Boolean(document.querySelector("textarea[data-composer-input]")),
}));
console.log(JSON.stringify(answer, null, 2));
// --------------------------------------------------------------------------

await page.screenshot({ path: "/tmp/probe.png" });
await ctx.close();
