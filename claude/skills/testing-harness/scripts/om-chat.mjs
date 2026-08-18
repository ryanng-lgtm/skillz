#!/usr/bin/env node
/**
 * testing-harness — a browser harness for the OM Chat GUI.
 *
 * Drives a real Chromium against two surfaces of the same product:
 *
 *   cloud  https://openmarket.xyz/chat/#/…      the parity baseline
 *   local  http://127.0.0.1:31417/rooms#/…      the daemon, serving your branch
 *
 * Both talk to the SAME production rooms backend (packages/cli/src/constants.ts:
 * ROOM_CHAT_API_URL / ROOMS_WS_URL point at chat.openmarket.xyz), so a visual
 * diff between them isolates the GUI build: same account, same rooms, same
 * messages, different frontend code.
 *
 * The report is a single self-contained HTML file — images inlined as data
 * URIs, no external requests — so it opens over file:// from anywhere.
 */

import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { existsSync, lstatSync, mkdirSync, readFileSync, readlinkSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const HOME = homedir();

// Saved browser profiles and run scratch. The skill was once called
// "om-chat-web"; a profile directory left at the old path is still honoured so
// an existing cloud login survives the rename.
const LEGACY_STATE_DIR = join(HOME, ".claude", "state", "om-chat-web");
const DEFAULT_STATE_DIR = join(HOME, ".claude", "state", "testing-harness");
const STATE_DIR =
  process.env.OM_CHAT_STATE ??
  (existsSync(DEFAULT_STATE_DIR) || !existsSync(LEGACY_STATE_DIR)
    ? DEFAULT_STATE_DIR
    : LEGACY_STATE_DIR);
const PROFILE_DIR = join(STATE_DIR, "profiles");
const RUN_DIR = join(STATE_DIR, "runs");

const CREDS_FILE =
  process.env.OM_CHAT_CREDS ??
  join(HOME, "Library", "Mobile Documents", "com~apple~CloudDocs", "Obsidian", "Local", "creds.md");

const REPORT_DIR =
  process.env.OM_CHAT_REPORTS ??
  join(HOME, "Library", "Mobile Documents", "com~apple~CloudDocs", "Obsidian", "UI Updates");

// The daemon's port. 31417 is the usual source-run rig; the installed daemon
// listens on 31337, and a second session can hold either. Override to capture
// against whichever daemon is actually serving the branch under test.
const LOCAL_PORT = process.env.OM_CHAT_LOCAL_PORT ?? "31417";

const REPOS = {
  chat: process.env.OM_CHAT_REPO ?? join(HOME, "Documents", "GitLab", "openmarket-chat"),
  // Only openmarket-internal is live; the openmarket and openmarket-main
  // checkouts of the same remote are stale and must never be read here.
  internal: process.env.OM_REPO ?? join(HOME, "Documents", "GitLab", "openmarket-internal"),
};

const TARGETS = {
  cloud: {
    key: "cloud",
    label: "cloud — openmarket.xyz/chat",
    role: "baseline",
    base: "https://openmarket.xyz/chat/",
    origin: "https://openmarket.xyz",
    // The public deployment has no daemon to inject a key: real login required.
    needsLogin: true,
    // Logins are routed through the chart app, and the redirect back to /chat/
    // is broken, so the flow ends with a manual navigation. A logged-out hit on
    // /chat/ bounces to /chart/, which is exactly how we detect "needs login".
    loginUrl: "https://openmarket.xyz/chart/",
    loginBouncePath: "/chart",
  },
  local: {
    key: "local",
    label: `local — daemon :${LOCAL_PORT}/rooms`,
    role: "candidate",
    base: `http://127.0.0.1:${LOCAL_PORT}/rooms`,
    origin: `http://127.0.0.1:${LOCAL_PORT}`,
    // The daemon stamps an operator-session cookie and injects the API key
    // into its /api/rooms and /ws/rooms proxies.
    needsLogin: false,
  },
};

/** Emitted by the daemon's placeholder shell when no real GUI bundle is present. */
const STUB_MARKER = "__OM_ROOMS_GUI_STUB__";

/** Recipients that never require an explicit confirmation flag. */
const TEST_ACCOUNT_HINTS = ["plus", "guest"];

const DEFAULT_VIEWPORT = { width: 1440, height: 900 };

// Selectors, all read off the real components and the live pages rather than
// guessed. The `chart*` ones belong to the platform shell that owns cloud
// login; the rest belong to the chat GUI itself.
const SEL = {
  // Chat GUI's own login form (src/components/Login.tsx) — the local daemon
  // and any deployment that does not detour through the chart app.
  loginIdentity: "#login-identity",
  loginPassword: "#login-password",
  loginTwoFa: "#login-twofa",
  loginSubmit: "button[type=submit]",
  // Chat GUI proper.
  composer: "textarea[data-composer-input]",
  messageRow: ".message-row",
  // Platform shell (cloud login detour).
  chartRebrandClose: '[data-testid="rebrand-close-btn"]',
  chartGuestPill: '[data-testid="profile-guest-mode-btn"]',
  chartEmail: "input[name=email]:visible",
  chartPassword: "input[type=password]:visible",
};

// ---------------------------------------------------------------------------
// Small utilities
// ---------------------------------------------------------------------------

const log = (...parts) => console.log(...parts);
const warn = (...parts) => console.warn(...parts);

function fail(message) {
  console.error(`testing-harness: ${message}`);
  process.exit(1);
}

function ensureDir(path) {
  mkdirSync(path, { recursive: true });
  return path;
}

function stamp() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return {
    iso: now.toISOString(),
    slug: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`,
    human: now.toLocaleString(),
  };
}

function parseArgs(argv) {
  const out = { _: [], flags: {} };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      out._.push(token);
      continue;
    }
    const eq = token.indexOf("=");
    if (eq !== -1) {
      out.flags[token.slice(2, eq)] = token.slice(eq + 1);
      continue;
    }
    const name = token.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) {
      out.flags[name] = true;
    } else {
      out.flags[name] = next;
      i += 1;
    }
  }
  return out;
}

function splitList(value, fallback) {
  if (value === undefined || value === true) return fallback;
  return String(value)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function parseViewport(value) {
  if (!value || value === true) return DEFAULT_VIEWPORT;
  const match = /^(\d+)x(\d+)$/.exec(String(value));
  if (!match) fail(`--viewport wants WIDTHxHEIGHT, got "${value}"`);
  return { width: Number(match[1]), height: Number(match[2]) };
}

/** Quiet `git` read. Returns null outside a repo rather than throwing. */
function git(repo, args) {
  try {
    return execFileSync("git", ["-C", repo, ...args], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

function repoState(path) {
  if (!existsSync(path)) return { path, present: false };
  const status = git(path, ["status", "--porcelain"]);
  return {
    path,
    present: true,
    branch: git(path, ["branch", "--show-current"]),
    commit: git(path, ["rev-parse", "--short", "HEAD"]),
    subject: git(path, ["log", "-1", "--format=%s"]),
    dirty: status !== null && status.length > 0,
    dirtyCount: status ? status.split("\n").filter(Boolean).length : 0,
  };
}

// ---------------------------------------------------------------------------
// Credentials
// ---------------------------------------------------------------------------

/**
 * Parse the creds markdown: a label line ending in ':', then a fenced block
 * holding an email on one line and a password on the next.
 *
 *   prod user:
 *   ```
 *   someone@example.com
 *   secret
 *   ```
 *
 * Keyed by the label's first word, so "prod user" is reachable as "prod".
 */
function loadCreds(file = CREDS_FILE) {
  if (!existsSync(file)) fail(`no credentials file at ${file} (set OM_CHAT_CREDS)`);
  const lines = readFileSync(file, "utf8").split("\n");
  const accounts = {};
  let label = null;
  let fence = null;

  for (const raw of lines) {
    const line = raw.trim();
    if (line.startsWith("```")) {
      if (fence === null) {
        fence = [];
      } else {
        if (label && fence.length >= 2) {
          accounts[label] = { label, email: fence[0], password: fence[1] };
        }
        fence = null;
        label = null;
      }
      continue;
    }
    if (fence !== null) {
      if (line) fence.push(line);
      continue;
    }
    if (line.endsWith(":") && line.length > 1) {
      label = line.slice(0, -1).trim().toLowerCase().split(/\s+/)[0];
    }
  }
  return accounts;
}

function pickAccount(accounts, name) {
  const key = String(name ?? "prod").toLowerCase();
  const found = accounts[key];
  if (!found) {
    fail(`no account "${key}" in ${CREDS_FILE} — found: ${Object.keys(accounts).join(", ") || "none"}`);
  }
  return { key, ...found };
}

// ---------------------------------------------------------------------------
// Browser
// ---------------------------------------------------------------------------

function targetFor(name) {
  const found = TARGETS[String(name ?? "local").toLowerCase()];
  if (!found) fail(`unknown target "${name}" — expected cloud or local`);
  return found;
}

function urlFor(target, route = "#/") {
  const path = route.startsWith("#") ? route : `#${route.startsWith("/") ? "" : "/"}${route}`;
  return `${target.base}${path}`;
}

async function openContext(target, accountKey, options = {}) {
  const viewport = options.viewport ?? DEFAULT_VIEWPORT;
  const dir = ensureDir(join(PROFILE_DIR, `${target.key}-${accountKey}`));
  const context = await chromium.launchPersistentContext(dir, {
    headless: Boolean(options.headless),
    viewport,
    deviceScaleFactor: 2,
    colorScheme: options.colorScheme ?? "dark",
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const page = context.pages()[0] ?? (await context.newPage());
  await page.setViewportSize(viewport);
  return { context, page };
}

/** Let the app finish painting: fonts, a couple of frames, then a settle beat. */
async function settle(page, ms = 900) {
  await page.waitForLoadState("domcontentloaded").catch(() => {});
  await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
  await page.evaluate(() => document.fonts?.ready).catch(() => {});
  await page
    .evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
    .catch(() => {});
  await page.waitForTimeout(ms);
}

/**
 * Hash routes do not fire a navigation, so we set the hash and wait on
 * rendered state rather than on a load event.
 */
async function goRoute(page, target, route) {
  const url = urlFor(target, route);
  if (page.url().split("#")[0] === url.split("#")[0]) {
    await page.evaluate((next) => {
      window.location.hash = next;
    }, route.startsWith("#") ? route.slice(1) : route);
  } else {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
  }
  await settle(page);
  return url;
}

async function isLoginVisible(page) {
  return page
    .locator(SEL.loginPassword)
    .first()
    .isVisible({ timeout: 2500 })
    .catch(() => false);
}

/** True once the chat GUI shell has actually rendered. */
async function isChatShell(page) {
  return page
    .evaluate(() => {
      if (document.querySelector("textarea[data-composer-input]")) return true;
      if (document.querySelector(".message-row")) return true;
      const text = document.body?.innerText ?? "";
      return text.includes("Search messages") || text.includes("Pick a channel");
    })
    .catch(() => false);
}

/** The platform shell greets first-time profiles with a multi-stage overlay
 *  that swallows every click until it is closed. */
async function dismissRebrand(page) {
  const close = page.locator(SEL.chartRebrandClose).first();
  if (await close.isVisible({ timeout: 3000 }).catch(() => false)) {
    await close.click({ force: true }).catch(() => {});
    await page.waitForTimeout(800);
  }
}

/**
 * Cloud login: openmarket.xyz routes chat logins through the chart app. Sign in
 * there, then navigate to /chat/ by hand because the redirect back is broken.
 */
async function chartLogin(page, target, account) {
  await page.goto(target.loginUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
  await settle(page, 2500);
  await dismissRebrand(page);

  await page.locator(SEL.chartGuestPill).first().click({ timeout: 20000 });
  await page.waitForTimeout(2000);

  await page.locator(SEL.chartEmail).first().fill(account.email);
  await page.locator(SEL.chartPassword).first().fill(account.password);
  await page.getByRole("button", { name: /^log in$/i }).last().click();

  // Success shows as the password field going away.
  await page
    .waitForFunction(() => !document.querySelector("input[type=password]"), null, { timeout: 45000 })
    .catch(() => {});
  if (await page.locator(SEL.chartPassword).first().isVisible().catch(() => false)) {
    throw new Error("chart login did not complete — the password field is still on screen");
  }
  await page.waitForTimeout(2500);
}

/**
 * Ensure the page holds a live session. Returns whether a login was performed,
 * so callers can report "reused session" versus "logged in".
 */
async function ensureSession(page, target, account) {
  await page.goto(urlFor(target, "#/"), { waitUntil: "domcontentloaded", timeout: 60000 });
  await settle(page, 2000);

  // Cloud bounces a logged-out visitor to the chart app; that bounce is the
  // most reliable "not signed in" signal this deployment offers.
  const bounced =
    Boolean(target.loginBouncePath) && new URL(page.url()).pathname.startsWith(target.loginBouncePath);

  if (!bounced && !(await isLoginVisible(page)) && (await isChatShell(page))) {
    return { loggedIn: true, didLogin: false };
  }

  if (!account) {
    throw new Error(`${target.key} is not signed in and no account was supplied`);
  }

  if (bounced) {
    await chartLogin(page, target, account);
    await page.goto(urlFor(target, "#/"), { waitUntil: "domcontentloaded", timeout: 60000 });
    await settle(page, 3000);
    if (new URL(page.url()).pathname.startsWith(target.loginBouncePath)) {
      throw new Error("signed in on the chart app but /chat/ still bounces back — session not accepted");
    }
  } else if (await isLoginVisible(page)) {
    // The chat GUI's own form (local daemon, or a deployment without the detour).
    await page.fill(SEL.loginIdentity, account.email);
    await page.fill(SEL.loginPassword, account.password);
    await page.click(SEL.loginSubmit);
    await page.waitForTimeout(1500);
    if (await page.locator(SEL.loginTwoFa).first().isVisible({ timeout: 2000 }).catch(() => false)) {
      throw new Error(
        "2FA is enabled on this account — unattended login cannot complete. " +
          "Run `login --headed` and pass the code by hand once; the profile keeps the session.",
      );
    }
    await page
      .waitForFunction(() => !document.querySelector("#login-password"), null, { timeout: 40000 })
      .catch(() => {});
    if (await isLoginVisible(page)) {
      const formError = await page.locator(".field-error").first().textContent().catch(() => null);
      throw new Error(`login failed${formError ? `: ${formError.trim()}` : " (still on the login form)"}`);
    }
  }

  await settle(page, 2000);
  if (!(await isChatShell(page))) {
    throw new Error("signed in, but the chat shell never rendered");
  }
  return { loggedIn: true, didLogin: true };
}

/**
 * Identity, without ever surfacing a bearer token.
 *
 * Two deployments store it two ways. The chat GUI's own login writes
 * `om.chat.identity` (src/lib/config.ts). The cloud build authenticates through
 * the platform and keeps only tokens — `om.chat.voucher.chatToken` carries the
 * handle in its claims, and the platform `jwt` carries username and email. JWT
 * payloads are plain base64url, so reading claims needs no secret.
 */
async function readIdentity(page) {
  return page
    .evaluate(() => {
      const claims = (token) => {
        try {
          const part = String(token).split(".")[1];
          return JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
        } catch {
          return null;
        }
      };

      try {
        const direct = JSON.parse(localStorage.getItem("om.chat.identity") ?? "null");
        if (direct?.username) {
          return { username: direct.username, handle: direct.handle, userId: direct.userId, source: "om.chat.identity" };
        }
      } catch {
        /* fall through */
      }

      try {
        const voucher = JSON.parse(localStorage.getItem("om.chat.voucher") ?? "null");
        const payload = voucher?.chatToken ? claims(voucher.chatToken) : null;
        if (payload?.handle) {
          const platform = claims(localStorage.getItem("jwt") ?? "");
          return {
            username: payload.handle,
            handle: payload.handle,
            userId: payload.sub,
            role: payload.roleName,
            email: platform?.email,
            expiresAt: voucher.chatTokenExpiresAt
              ? new Date(voucher.chatTokenExpiresAt).toISOString()
              : undefined,
            source: "om.chat.voucher",
          };
        }
      } catch {
        /* fall through */
      }

      const platform = claims(localStorage.getItem("jwt") ?? "");
      if (platform?.username) {
        return {
          username: platform.username,
          userId: platform.id,
          role: platform.roleName,
          email: platform.email,
          source: "jwt",
        };
      }

      // Daemon-served builds keep no voucher at all — the API key lives with the
      // daemon and rides its proxies — so the handle the shell paints is the
      // only client-side evidence of who we are.
      for (const node of document.querySelectorAll("div,span,a")) {
        const text = (node.textContent ?? "").trim();
        if (/^@[A-Za-z0-9_.-]{2,32}$/.test(text)) {
          return { username: text.slice(1), handle: text.slice(1), source: "dom" };
        }
      }
      return null;
    })
    .catch(() => null);
}

// ---------------------------------------------------------------------------
// Doctor — verify the wiring before trusting any capture
// ---------------------------------------------------------------------------

async function probeLocal() {
  const out = { reachable: false, devProxy: false, stub: false, detail: "" };
  try {
    const response = await fetch(`${TARGETS.local.origin}/rooms`, {
      redirect: "follow",
      signal: AbortSignal.timeout(8000),
    });
    out.reachable = response.ok;
    const body = await response.text();
    // A vite-served document carries the dev client; a bundle never does.
    out.devProxy = body.includes("/@vite/client") || body.includes("@react-refresh");
    out.stub = body.includes(STUB_MARKER);
    out.detail = out.devProxy
      ? "serving your working tree through the vite dev proxy"
      : out.stub
        ? "serving the PLACEHOLDER SHELL — no real GUI bundle is installed"
        : "serving a built bundle (OM_ROOMS_GUI_DIR or an embedded build)";
  } catch (error) {
    out.detail = `unreachable: ${error.message}`;
  }
  return out;
}

async function probeCloud() {
  try {
    const response = await fetch(TARGETS.cloud.base, {
      redirect: "follow",
      signal: AbortSignal.timeout(12000),
    });
    return { reachable: response.ok, detail: `HTTP ${response.status}` };
  } catch (error) {
    return { reachable: false, detail: error.message };
  }
}

function probeRoomsClient() {
  const pkg = join(REPOS.chat, "node_modules", "@openmarket", "rooms-client");
  if (!existsSync(pkg)) return { state: "missing", detail: "not installed" };
  let linked = false;
  let target = null;
  try {
    linked = lstatSync(pkg).isSymbolicLink();
    if (linked) target = resolve(dirname(pkg), readlinkSync(pkg));
  } catch {
    /* fall through to the registry-copy reading */
  }
  let version = null;
  try {
    version = JSON.parse(readFileSync(join(pkg, "package.json"), "utf8")).version;
  } catch {
    /* unreadable package.json is reported as an unknown version */
  }
  if (!linked) return { state: "registry", version, detail: `registry copy, version ${version}` };
  const stale = target && !target.includes("openmarket-internal");
  return {
    state: stale ? "linked-stale" : "linked",
    version,
    target,
    detail: stale
      ? `linked to ${target} — that checkout is STALE, relink with OM_REPO=${REPOS.internal}`
      : `linked to ${target}`,
  };
}

async function cmdDoctor() {
  const local = await probeLocal();
  const cloud = await probeCloud();
  const roomsClient = probeRoomsClient();
  const chat = repoState(REPOS.chat);
  const internal = repoState(REPOS.internal);
  const problems = [];

  log("\ntesting-harness doctor\n");

  log(`  cloud    ${cloud.reachable ? "ok" : "FAIL"}  ${TARGETS.cloud.base}  (${cloud.detail})`);
  if (!cloud.reachable) problems.push("cloud baseline is unreachable");

  log(`  local    ${local.reachable ? "ok" : "FAIL"}  ${TARGETS.local.base}  (${local.detail})`);
  if (!local.reachable) problems.push("local daemon is unreachable — is `om run` up?");
  if (local.stub) {
    problems.push(
      "local /rooms is the placeholder shell: the dev proxy is off and no bundle is installed. " +
        "Either export OM_ROOMS_GUI_DEV_URL=http://127.0.0.1:8097 on a SOURCE run, or point " +
        "OM_ROOMS_GUI_DIR at openmarket-chat/dist.",
    );
  }
  if (local.reachable && !local.devProxy && !local.stub) {
    warn(
      "  note     local is serving a BUILT bundle, not your working tree — " +
        "edits will not appear until it is rebuilt",
    );
  }

  log(`  rooms-client  ${roomsClient.detail}`);
  if (roomsClient.state === "linked-stale") problems.push("rooms-client is linked to a stale checkout");

  for (const [name, state] of [
    ["openmarket-chat", chat],
    ["openmarket-internal", internal],
  ]) {
    if (!state.present) {
      log(`  ${name.padEnd(20)} not found at ${state.path}`);
      continue;
    }
    log(
      `  ${name.padEnd(20)} ${state.branch} @ ${state.commit}` +
        `${state.dirty ? `  (${state.dirtyCount} uncommitted)` : ""}`,
    );
  }

  if (problems.length === 0) {
    log("\n  wiring looks good — a capture can be trusted\n");
    return { ok: true, local, cloud, roomsClient, chat, internal };
  }
  log("");
  for (const problem of problems) warn(`  PROBLEM  ${problem}`);
  log("");
  return { ok: false, problems, local, cloud, roomsClient, chat, internal };
}

// ---------------------------------------------------------------------------
// Capture
// ---------------------------------------------------------------------------

async function captureRoutes({ target, account, routes, viewport, headless, fullPage }) {
  const { context, page } = await openContext(target, account?.key ?? "anon", { viewport, headless });
  const shots = [];
  try {
    const session = await ensureSession(page, target, target.needsLogin ? account : account ?? null);
    const identity = await readIdentity(page);
    for (const route of routes) {
      const url = await goRoute(page, target, route);
      const buffer = await page.screenshot({ fullPage: Boolean(fullPage) });
      shots.push({ route, url, png: buffer.toString("base64") });
      log(`  captured ${target.key}  ${route}`);
    }
    return { shots, identity, session };
  } finally {
    await context.close();
  }
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderReport({ title, note, when, left, right, pairs, context }) {
  const panes = pairs
    .map((pair, index) => {
      const id = `pair-${index}`;
      return `
      <section class="pair" data-pair="${id}">
        <header class="pair-head">
          <h2>${escapeHtml(pair.route)}</h2>
          <div class="modes" role="tablist">
            <button class="mode is-on" data-mode="side">Side by side</button>
            <button class="mode" data-mode="slider">Slider</button>
            <button class="mode" data-mode="blink">Blink</button>
            <button class="mode" data-mode="diff">Diff</button>
          </div>
        </header>
        <div class="stage" data-view="side">
          <div class="side">
            <figure>
              <figcaption><span class="tag tag-a">A</span> ${escapeHtml(left.label)}</figcaption>
              <img class="src-a" src="data:image/png;base64,${pair.a}" alt="${escapeHtml(left.label)} ${escapeHtml(pair.route)}">
            </figure>
            <figure>
              <figcaption><span class="tag tag-b">B</span> ${escapeHtml(right.label)}</figcaption>
              <img class="src-b" src="data:image/png;base64,${pair.b}" alt="${escapeHtml(right.label)} ${escapeHtml(pair.route)}">
            </figure>
          </div>
          <!-- The slider and blink views borrow the two images above at runtime.
               Repeating the data URIs here would triple the file size. -->
          <div class="slider">
            <div class="slider-frame">
              <img class="under" alt="">
              <div class="over"><img alt=""></div>
              <div class="handle"></div>
            </div>
            <input type="range" min="0" max="100" value="50" aria-label="Compare position">
          </div>
          <div class="blink">
            <img class="blink-a" alt="">
            <img class="blink-b" alt="">
          </div>
          <div class="diff">
            <canvas></canvas>
            <p class="diff-stat">computing…</p>
          </div>
        </div>
      </section>`;
    })
    .join("\n");

  const contextRows = context
    .map(({ label, value }) => `<div class="meta"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff; --panel: #f6f7f9; --line: #d8dce3;
    --ink: #14171c; --muted: #5b6472;
    --a: #6b7cff; --b: #14b87a; --warn: #d1682b;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0e1014; --panel: #171a21; --line: #2a2f3a;
      --ink: #e8ebf0; --muted: #949dad;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 32px 28px 80px;
    background: var(--bg); color: var(--ink);
    font: 15px/1.55 ui-sans-serif, -apple-system, "SF Pro Text", system-ui, sans-serif;
  }
  h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); margin: 0 0 22px; }
  .note {
    background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--a);
    border-radius: 8px; padding: 10px 14px; margin: 0 0 22px;
  }
  .context {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 10px 22px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 10px; padding: 16px 18px; margin: 0 0 30px;
  }
  .meta dt { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
  .meta dd { margin: 2px 0 0; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12.5px; word-break: break-all; }
  .pair { border: 1px solid var(--line); border-radius: 12px; margin-bottom: 26px; overflow: hidden; background: var(--panel); }
  .pair-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 16px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
  .pair-head h2 { font-size: 14px; margin: 0; font-family: ui-monospace, Menlo, monospace; }
  .modes { display: flex; gap: 4px; }
  .mode { font: inherit; font-size: 12.5px; padding: 5px 12px; border-radius: 999px; border: 1px solid var(--line); background: transparent; color: var(--muted); cursor: pointer; }
  .mode.is-on { background: var(--ink); color: var(--bg); border-color: var(--ink); }
  .stage { padding: 16px; }
  .stage > div { display: none; }
  .stage[data-view="side"] .side,
  .stage[data-view="slider"] .slider,
  .stage[data-view="blink"] .blink,
  .stage[data-view="diff"] .diff { display: block; }
  .side { display: none; grid-template-columns: 1fr 1fr; gap: 16px; }
  .stage[data-view="side"] .side { display: grid; }
  figure { margin: 0; }
  figcaption { font-size: 12px; color: var(--muted); margin-bottom: 7px; display: flex; align-items: center; gap: 7px; }
  .tag { font-size: 10px; font-weight: 700; color: #fff; border-radius: 4px; padding: 1px 6px; }
  .tag-a { background: var(--a); } .tag-b { background: var(--b); }
  img { max-width: 100%; display: block; border: 1px solid var(--line); border-radius: 6px; }
  .slider-frame { position: relative; max-width: 100%; }
  .slider-frame .over { position: absolute; inset: 0; width: 50%; overflow: hidden; border-right: 2px solid var(--b); }
  .slider-frame .over img { max-width: none; border-radius: 6px 0 0 6px; }
  .slider input { width: 100%; margin-top: 12px; }
  .blink { position: relative; }
  .blink img { position: relative; }
  .blink .blink-b { position: absolute; inset: 0; animation: blink 1.6s steps(1) infinite; }
  @keyframes blink { 0%, 49% { opacity: 0; } 50%, 100% { opacity: 1; } }
  .diff canvas { max-width: 100%; border: 1px solid var(--line); border-radius: 6px; }
  .diff-stat { color: var(--muted); font-size: 13px; margin: 10px 0 0; }
  .empty { color: var(--muted); }
</style>
</head>
<body>
  <h1>${escapeHtml(title)}</h1>
  <p class="sub">${escapeHtml(left.label)} <strong>(A, baseline)</strong> vs ${escapeHtml(right.label)} <strong>(B, candidate)</strong> · ${escapeHtml(when)}</p>
  ${note ? `<p class="note">${escapeHtml(note)}</p>` : ""}
  <div class="context">${contextRows}</div>
  ${panes || '<p class="empty">No routes were captured.</p>'}
<script>
(function () {
  for (const stage of document.querySelectorAll(".pair")) {
    const view = stage.querySelector(".stage");

    // One copy of each PNG lives in the side-by-side figures; every other view
    // points at the same data URI rather than carrying its own.
    const srcA = stage.querySelector(".src-a").getAttribute("src");
    const srcB = stage.querySelector(".src-b").getAttribute("src");
    stage.querySelector(".slider .under").src = srcA;
    stage.querySelector(".slider .over img").src = srcB;
    stage.querySelector(".blink-a").src = srcA;
    stage.querySelector(".blink-b").src = srcB;

    for (const button of stage.querySelectorAll(".mode")) {
      button.addEventListener("click", function () {
        for (const other of stage.querySelectorAll(".mode")) other.classList.remove("is-on");
        button.classList.add("is-on");
        view.dataset.view = button.dataset.mode;
        if (button.dataset.mode === "diff") drawDiff(stage);
        // A hidden pane measures 0 wide, so the overlay can only be pinned
        // once its view is actually on screen.
        if (button.dataset.mode === "slider") stage.dispatchEvent(new Event("sync-slider"));
      });
    }
    const range = stage.querySelector(".slider input");
    const over = stage.querySelector(".slider .over");
    const under = stage.querySelector(".slider .under");
    const overImg = stage.querySelector(".slider .over img");
    // The overlay is clipped by its parent, so its image must be pinned to the
    // full rendered width of the one underneath or the two halves misalign.
    const syncWidth = function () {
      if (under.clientWidth) overImg.style.width = under.clientWidth + "px";
    };
    under.addEventListener("load", syncWidth);
    window.addEventListener("resize", syncWidth);
    stage.addEventListener("sync-slider", syncWidth);
    syncWidth();
    if (range && over) {
      range.addEventListener("input", function () {
        over.style.width = range.value + "%";
      });
    }
  }

  // Pixel diff, computed in the page so the report needs no image library.
  const done = new WeakSet();
  function drawDiff(stage) {
    if (done.has(stage)) return;
    const canvas = stage.querySelector(".diff canvas");
    const stat = stage.querySelector(".diff-stat");
    const images = stage.querySelectorAll(".side img");
    const [a, b] = images;
    if (!a || !b || !a.naturalWidth || !b.naturalWidth) return;
    done.add(stage);

    const width = Math.min(a.naturalWidth, b.naturalWidth);
    const height = Math.min(a.naturalHeight, b.naturalHeight);
    const read = function (img) {
      const scratch = document.createElement("canvas");
      scratch.width = width; scratch.height = height;
      scratch.getContext("2d").drawImage(img, 0, 0);
      return scratch.getContext("2d").getImageData(0, 0, width, height);
    };
    const one = read(a), two = read(b);
    canvas.width = width; canvas.height = height;
    const out = canvas.getContext("2d").createImageData(width, height);
    let changed = 0;
    for (let i = 0; i < one.data.length; i += 4) {
      const delta =
        Math.abs(one.data[i] - two.data[i]) +
        Math.abs(one.data[i + 1] - two.data[i + 1]) +
        Math.abs(one.data[i + 2] - two.data[i + 2]);
      if (delta > 24) {
        changed += 1;
        out.data[i] = 255; out.data[i + 1] = 40; out.data[i + 2] = 110; out.data[i + 3] = 255;
      } else {
        const grey = 235 - (one.data[i] + one.data[i + 1] + one.data[i + 2]) / 3 * 0.72;
        out.data[i] = out.data[i + 1] = out.data[i + 2] = grey;
        out.data[i + 3] = 255;
      }
    }
    canvas.getContext("2d").putImageData(out, 0, 0);
    const total = width * height;
    const percent = (changed / total) * 100;
    stat.textContent =
      changed === 0
        ? "Identical at this viewport — no pixels differ."
        : changed + " of " + total + " pixels differ (" + percent.toFixed(2) + "%). " +
          (a.naturalWidth !== b.naturalWidth || a.naturalHeight !== b.naturalHeight
            ? "Sizes differ; compared over the shared region."
            : "");
  }
})();
</script>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

async function cmdLogin(args) {
  const target = targetFor(args.flags.target ?? "cloud");
  const accounts = loadCreds();
  const account = pickAccount(accounts, args.flags.account ?? "prod");
  const { context, page } = await openContext(target, account.key, {
    headless: args.flags.headless === true,
    viewport: parseViewport(args.flags.viewport),
  });
  try {
    const result = await ensureSession(page, target, account);
    const identity = await readIdentity(page);
    log(
      `${target.label}: ${result.didLogin ? "logged in" : "reused saved session"}` +
        `${identity?.username ? ` as @${identity.username}` : ""}`,
    );
    return identity;
  } finally {
    await context.close();
  }
}

async function cmdWhoami(args) {
  const target = targetFor(args.flags.target ?? "cloud");
  const accounts = loadCreds();
  const account = pickAccount(accounts, args.flags.account ?? "prod");
  const { context, page } = await openContext(target, account.key, {
    headless: args.flags.headless !== false,
    viewport: parseViewport(args.flags.viewport),
  });
  try {
    await ensureSession(page, target, account);
    // Daemon-served builds only paint the handle on the home view, so land
    // there before reading rather than reporting a false blank.
    await goRoute(page, target, "#/home");
    const identity = await readIdentity(page);
    log(identity ? JSON.stringify(identity, null, 2) : "no identity found");
  } finally {
    await context.close();
  }
}

/**
 * List DM candidates. Uses the app's own API from inside the page, so it
 * inherits the session rather than re-implementing auth.
 */
async function cmdPeople(args) {
  const target = targetFor(args.flags.target ?? "cloud");
  const accounts = loadCreds();
  const account = pickAccount(accounts, args.flags.account ?? "prod");
  const { context, page } = await openContext(target, account.key, {
    headless: args.flags.headless !== false,
    viewport: parseViewport(args.flags.viewport),
  });
  try {
    await ensureSession(page, target, account);
    await goRoute(page, target, "#/connections");

    const found = await page.evaluate(async () => {
      const results = { api: null, dom: [], errors: [] };
      const base =
        localStorage.getItem("om.chat.api") ??
        `${window.location.protocol}//${window.location.host}/api/rooms`;
      let token = null;
      try {
        token = JSON.parse(localStorage.getItem("om.chat.identity") ?? "null")?.token ?? null;
      } catch {
        token = null;
      }
      for (const path of ["/dms", "/friends", "/connections", "/me/dms"]) {
        try {
          const response = await fetch(base + path, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            credentials: "include",
          });
          if (response.ok) {
            results.api = { path, body: await response.json() };
            break;
          }
          results.errors.push(`${path} ${response.status}`);
        } catch (error) {
          results.errors.push(`${path} ${error.message}`);
        }
      }
      const seen = new Set();
      for (const node of document.querySelectorAll("[title], a, button, li, div")) {
        const text = (node.textContent ?? "").trim();
        const match = /^@([A-Za-z0-9_.-]{2,32})$/.exec(text);
        if (match && !seen.has(match[1])) {
          seen.add(match[1]);
          results.dom.push(match[1]);
        }
      }
      return results;
    });

    if (found.api) {
      log(`api ${found.api.path}:`);
      log(JSON.stringify(found.api.body, null, 2).slice(0, 4000));
    } else {
      log(`no list endpoint answered (${found.errors.join(", ")})`);
    }
    if (found.dom.length) log(`\nhandles visible on #/connections:\n  ${found.dom.join("\n  ")}`);
    if (args.flags.screenshot) {
      const out = String(args.flags.screenshot);
      writeFileSync(out, await page.screenshot({ fullPage: true }));
      log(`\nscreenshot ${out}`);
    }
  } finally {
    await context.close();
  }
}

async function cmdRead(args) {
  const target = targetFor(args.flags.target ?? "cloud");
  const to = args.flags.to;
  if (!to || to === true) fail("read needs --to <handle>");
  const count = Number(args.flags.n ?? 15);
  const accounts = loadCreds();
  const account = pickAccount(accounts, args.flags.account ?? "prod");
  const { context, page } = await openContext(target, account.key, {
    headless: args.flags.headless !== false,
    viewport: parseViewport(args.flags.viewport),
  });
  try {
    await ensureSession(page, target, account);
    await goRoute(page, target, `#/dm/${encodeURIComponent(to)}`);
    const rows = await page.evaluate(
      (selector) =>
        [...document.querySelectorAll(selector)].map((node) =>
          (node.textContent ?? "").replace(/\s+/g, " ").trim(),
        ),
      SEL.messageRow,
    );
    const tail = rows.slice(-count);
    if (tail.length === 0) log("(no messages rendered)");
    for (const row of tail) log(`  ${row}`);
    return tail;
  } finally {
    await context.close();
  }
}

async function cmdSend(args) {
  const target = targetFor(args.flags.target ?? "local");
  const to = args.flags.to;
  const text = args.flags.text;
  if (!to || to === true) fail("send needs --to <handle>");
  if (!text || text === true) fail("send needs --text <message>");

  const accounts = loadCreds();
  const account = pickAccount(accounts, args.flags.account ?? "prod");

  // Guardrail: this harness drives a real identity against the production
  // rooms backend. Anything that is not one of the known throwaway accounts
  // needs an explicit flag, so an unattended run cannot message a person.
  const testHandles = TEST_ACCOUNT_HINTS.map((key) => accounts[key]?.email?.split("@")[0]).filter(Boolean);
  const isTestRecipient = testHandles.some((handle) => handle && handle.includes(String(to)));
  if (!isTestRecipient && args.flags["confirm-real"] !== true) {
    fail(
      `refusing to message "${to}" — not a known test account.\n` +
        "  This sends to a real person on the production backend.\n" +
        "  Re-run with --confirm-real once you have approved the text.",
    );
  }

  const { context, page } = await openContext(target, account.key, {
    headless: args.flags.headless === true,
    viewport: parseViewport(args.flags.viewport),
  });
  try {
    await ensureSession(page, target, account);
    await goRoute(page, target, `#/dm/${encodeURIComponent(to)}`);

    const composer = page.locator(SEL.composer).first();
    await composer.waitFor({ state: "visible", timeout: 20000 });
    await composer.click();
    await composer.fill(String(text));
    await composer.press("Enter");
    await settle(page, 2000);

    // "Sent" means observed in the rendered thread, not "the click threw nothing".
    const present = await page.evaluate(
      ({ selector, needle }) =>
        [...document.querySelectorAll(selector)].some((node) =>
          (node.textContent ?? "").includes(needle),
        ),
      { selector: SEL.messageRow, needle: String(text) },
    );
    if (!present) throw new Error("message was typed but never appeared in the thread");
    log(`sent on ${target.key} to @${to} and confirmed in the thread`);
    return true;
  } finally {
    await context.close();
  }
}

async function cmdCompare(args) {
  const routes = splitList(args.flags.routes, ["#/home"]);
  const viewport = parseViewport(args.flags.viewport);
  const headless = args.flags.headless !== false && args.flags.headed !== true;
  const note = args.flags.note === true ? "" : String(args.flags.note ?? "");
  const accounts = loadCreds();
  const account = pickAccount(accounts, args.flags.account ?? "prod");

  const health = await cmdDoctor();
  if (!health.ok && args.flags.force !== true) {
    fail("doctor found problems above — fix them, or pass --force to capture anyway");
  }

  const left = TARGETS.cloud;
  const right = TARGETS.local;

  log(`capturing ${routes.length} route(s) at ${viewport.width}x${viewport.height}\n`);
  const a = await captureRoutes({ target: left, account, routes, viewport, headless, fullPage: args.flags["full-page"] === true });
  const b = await captureRoutes({ target: right, account, routes, viewport, headless, fullPage: args.flags["full-page"] === true });

  const pairs = routes.map((route, index) => ({
    route,
    a: a.shots[index]?.png ?? "",
    b: b.shots[index]?.png ?? "",
  }));

  const when = stamp();
  const context = [
    { label: "captured", value: when.human },
    { label: "viewport", value: `${viewport.width}x${viewport.height} @2x, dark` },
    { label: "account", value: a.identity?.username ? `@${a.identity.username}` : account.key },
    { label: "A · baseline", value: left.base },
    { label: "B · candidate", value: right.base },
    {
      label: "local serving",
      value: health.local.devProxy ? "vite dev proxy (working tree)" : health.local.detail,
    },
    {
      label: "openmarket-chat",
      value: health.chat.present
        ? `${health.chat.branch} @ ${health.chat.commit}${health.chat.dirty ? ` +${health.chat.dirtyCount} dirty` : ""}`
        : "not found",
    },
    {
      label: "openmarket-internal",
      value: health.internal.present
        ? `${health.internal.branch} @ ${health.internal.commit}${health.internal.dirty ? ` +${health.internal.dirtyCount} dirty` : ""}`
        : "not found",
    },
    { label: "rooms-client", value: health.roomsClient.detail },
  ];

  const title = args.flags.title === true || !args.flags.title
    ? "OM Chat — cloud vs local"
    : String(args.flags.title);

  const html = renderReport({ title, note, when: when.human, left, right, pairs, context });

  ensureDir(REPORT_DIR);
  const outPath =
    args.flags.out && args.flags.out !== true
      ? String(args.flags.out)
      : join(REPORT_DIR, `${when.slug}-om-chat-cloud-vs-local.html`);
  ensureDir(dirname(outPath));
  writeFileSync(outPath, html);
  ensureDir(RUN_DIR);

  log(`\nreport  ${outPath}`);
  if (args.flags.open === true) {
    execFileSync("open", [outPath]);
  }
  return outPath;
}

async function cmdSnap(args) {
  const target = targetFor(args.flags.target ?? "local");
  const routes = splitList(args.flags.routes, ["#/home"]);
  const viewport = parseViewport(args.flags.viewport);
  const accounts = loadCreds();
  const account = pickAccount(accounts, args.flags.account ?? "prod");
  const out = ensureDir(
    args.flags.out && args.flags.out !== true ? String(args.flags.out) : join(RUN_DIR, stamp().slug),
  );
  const captured = await captureRoutes({
    target,
    account,
    routes,
    viewport,
    headless: args.flags.headless !== false && args.flags.headed !== true,
    fullPage: args.flags["full-page"] === true,
  });
  captured.shots.forEach((shot, index) => {
    const name = `${target.key}-${String(index).padStart(2, "0")}-${shot.route.replace(/[^a-z0-9]+/gi, "_")}.png`;
    writeFileSync(join(out, name), Buffer.from(shot.png, "base64"));
    log(`  ${join(out, name)}`);
  });
  return out;
}

const USAGE = `testing-harness — browser harness for the OM Chat GUI

  doctor                       verify the wiring before trusting a capture
  login    [--target cloud]    establish or refresh the saved session
  whoami   [--target cloud]    print the stored identity
  people   [--target cloud]    list DM candidates
  read     --to <handle>       print the tail of a DM thread
  send     --to <handle> --text "..."   send, then confirm it rendered
  snap     --routes '#/home'   capture one target to PNGs
  compare  --routes '#/home'   cloud vs local, into an HTML report

Common flags
  --target cloud|local   which surface (default: local for send/snap, cloud for reads)
  --account prod|plus|guest
  --routes '#/home,#/dm/someone'
  --viewport 1440x900    --full-page    --headed    --note "what changed"
  --out <path>           --open         --force     --confirm-real
`;

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const command = args._[0];
  switch (command) {
    case "doctor":
      await cmdDoctor();
      return;
    case "login":
      await cmdLogin(args);
      return;
    case "whoami":
      await cmdWhoami(args);
      return;
    case "people":
      await cmdPeople(args);
      return;
    case "read":
      await cmdRead(args);
      return;
    case "send":
      await cmdSend(args);
      return;
    case "snap":
      await cmdSnap(args);
      return;
    case "compare":
      await cmdCompare(args);
      return;
    default:
      log(USAGE);
      if (command) process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(`testing-harness: ${error.message}`);
  process.exit(1);
});
