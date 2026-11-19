#!/usr/bin/env node
/**
 * verify-load.mjs — proves a saved board actually comes back after a refresh.
 *
 * Two real browser checks against a running WHITEBOARD instance (no test-runner
 * dependency: raw CDP over a WebSocket, headless Chrome):
 *
 *   1. LOAD      — open an existing board and assert the fabric canvas holds
 *                  exactly as many objects as the API's `doc` (WB-3 / AC-13).
 *   2. ROUNDTRIP — create a throw-away board, draw a rectangle with real mouse
 *                  events, wait for the autosave, reload, assert the shape is
 *                  back on the canvas, then delete the board.
 *
 * Usage:
 *   node scripts/verify-load.mjs --url http://127.0.0.1:8193 [--board <id>]
 *   CHROME_BIN=/path/to/chrome node scripts/verify-load.mjs --url http://${BIND_IP}:8093
 *
 * Exit codes: 0 = both checks passed, 1 = a check failed, 2 = bad setup
 * (no browser / app unreachable).
 */

import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const args = new Map();
for (let i = 2; i < process.argv.length; i += 1) {
  const arg = process.argv[i];
  if (arg.startsWith('--')) args.set(arg.slice(2), process.argv[i + 1]?.startsWith('--') ? '' : process.argv[++i]);
}
const BASE = (args.get('url') ?? 'http://127.0.0.1:8193').replace(/\/$/, '');
const BOARD_ID = args.get('board') ?? '';
const TIMEOUT_MS = Number(args.get('timeout') ?? 30000);
const LOAD_ONLY = args.has('load-only');

const log = (...a) => console.log(...a);
const fail = (msg) => {
  console.error(`✖ ${msg}`);
  process.exitCode = 1;
};
const ok = (msg) => log(`✔ ${msg}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ------------------------------------------------------------------ chrome */

function findChrome() {
  if (process.env.CHROME_BIN) return process.env.CHROME_BIN;
  const candidates = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/snap/bin/chromium',
  ];
  for (const dir of [`${process.env.HOME}/.hermes/tools`, '/opt', `${process.env.HOME}/.cache/ms-playwright`]) {
    if (!existsSync(dir)) continue;
    for (const entry of readdirSync(dir)) {
      for (const rel of ['chrome-linux64/chrome', 'chrome-linux/chrome', 'chrome-linux/headless_shell']) {
        candidates.push(join(dir, entry, rel));
      }
    }
  }
  return candidates.find((p) => existsSync(p)) ?? null;
}

async function launchChrome(bin) {
  const profile = mkdtempSync(join(tmpdir(), 'wb-verify-'));
  const port = 9500 + Math.floor(Math.random() * 400);
  const child = spawn(
    bin,
    [
      '--headless=new',
      '--no-sandbox',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-dev-shm-usage',
      '--hide-scrollbars',
      '--window-size=1440,900',
      `--user-data-dir=${profile}`,
      `--remote-debugging-port=${port}`,
      'about:blank',
    ],
    { stdio: ['ignore', 'ignore', 'pipe'] },
  );
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (res.ok) return { child, port };
    } catch {
      /* not up yet */
    }
    await sleep(200);
  }
  child.kill('SIGKILL');
  throw new Error('headless chrome did not expose a debugging port');
}

/* --------------------------------------------------------------- cdp client */

class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      const waiter = this.pending.get(msg.id);
      if (!waiter) return;
      this.pending.delete(msg.id);
      if (msg.error) waiter.reject(new Error(`${msg.error.message} (${msg.error.code})`));
      else waiter.resolve(msg.result);
    });
  }

  static async connect(wsUrl) {
    const ws = new WebSocket(wsUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener('open', resolve, { once: true });
      ws.addEventListener('error', () => reject(new Error('websocket error')), { once: true });
    });
    return new CDP(ws);
  }

  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  async eval(expression, { awaitPromise = true } = {}) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise,
      userGesture: true,
    });
    if (res.exceptionDetails) {
      throw new Error(res.exceptionDetails.exception?.description ?? res.exceptionDetails.text);
    }
    return res.result.value;
  }

  async waitFor(expression, timeout = TIMEOUT_MS) {
    const deadline = Date.now() + timeout;
    let last;
    while (Date.now() < deadline) {
      try {
        last = await this.eval(expression);
        if (last) return last;
      } catch (err) {
        last = String(err);
      }
      await sleep(150);
    }
    throw new Error(`timed out waiting for: ${expression} (last=${JSON.stringify(last)})`);
  }
}

async function newPage(port, url) {
  const res = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
  if (!res.ok) throw new Error(`cannot open tab: HTTP ${res.status}`);
  const target = await res.json();
  const cdp = await CDP.connect(target.webSocketDebuggerUrl);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  return { cdp, target };
}

/* ------------------------------------------------------------------- api */

async function api(path, init) {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error(`${init?.method ?? 'GET'} ${path} → HTTP ${res.status}`);
  return body;
}

/* ------------------------------------------------------------- check 1: load */

async function checkLoad(cdp, boardId) {
  const board = await api(`/api/boards/${boardId}`);
  const expected = (board.doc?.objects ?? []).length;
  await cdp.eval(`location.hash = ${JSON.stringify(`#/b/${boardId}`)}`);
  const report = await cdp.waitFor(`window.__wbLastLoad ? JSON.stringify(window.__wbLastLoad) : null`);
  const parsed = JSON.parse(report);
  const live = await cdp.eval(`window.__wb.canvas.getObjects().length`);

  log(`   board «${board.name}» · doc objects=${expected} · canvas objects=${live} · report=${JSON.stringify(parsed)}`);
  if (expected === 0) {
    ok('load: board is empty by design (0 objects in doc, 0 on canvas)');
    return true;
  }
  if (live !== expected) {
    fail(`load: canvas has ${live} objects but the doc holds ${expected}`);
    return false;
  }
  if (parsed.loaded !== expected) {
    fail(`load: load report says ${parsed.loaded} but doc holds ${expected}`);
    return false;
  }
  ok(`load: all ${expected} objects rendered (dropped=${parsed.dropped.length})`);
  return true;
}

/* --------------------------------------------------- check 2: draw + refresh */

async function checkRoundTrip(cdp) {
  const board = await api('/api/boards', {
    method: 'POST',
    body: JSON.stringify({ name: `verify-${Date.now()}`, color: '#6366f1', doc: { version: '6.9.1', objects: [] } }),
  });
  try {
    await cdp.eval(`location.hash = ${JSON.stringify(`#/b/${board.id}`)}`);
    await cdp.waitFor(`!!window.__wb && !!document.querySelector('.upper-canvas')`);
    await sleep(400);

    // pick the rectangle tool, then drag a real rectangle with mouse events
    const picked = await cdp.eval(`(() => {
      const btn = [...document.querySelectorAll('button')].find((b) =>
        (b.getAttribute('aria-label') || b.title || '').includes('مستطيل'));
      if (!btn) return false;
      btn.click();
      return true;
    })()`);
    if (!picked) throw new Error('rectangle tool button not found');

    const box = await cdp.eval(`(() => {
      const r = document.querySelector('.upper-canvas').getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height };
    })()`);
    const x1 = box.x + box.w * 0.35;
    const y1 = box.y + box.h * 0.35;
    const x2 = box.x + box.w * 0.6;
    const y2 = box.y + box.h * 0.6;
    await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: x1, y: y1, button: 'left', clickCount: 1 });
    for (let i = 1; i <= 5; i += 1) {
      await cdp.send('Input.dispatchMouseEvent', {
        type: 'mouseMoved',
        x: x1 + ((x2 - x1) * i) / 5,
        y: y1 + ((y2 - y1) * i) / 5,
        button: 'left',
        buttons: 1,
      });
      await sleep(30);
    }
    await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: x2, y: y2, button: 'left', clickCount: 1 });

    const drawn = await cdp.eval(`window.__wb.canvas.getObjects().length`);
    if (drawn < 1) throw new Error('drawing did not add an object to the canvas');
    ok(`roundtrip: drew 1 shape (canvas objects=${drawn})`);

    // autosave is debounced (2s) + a network round-trip
    let saved = 0;
    const deadline = Date.now() + TIMEOUT_MS;
    while (Date.now() < deadline) {
      const fresh = await api(`/api/boards/${board.id}`);
      saved = (fresh.doc?.objects ?? []).length;
      if (saved >= 1) break;
      await sleep(500);
    }
    if (saved < 1) {
      fail('roundtrip: autosave never stored the shape');
      return false;
    }
    ok(`roundtrip: autosave stored ${saved} object(s)`);

    // hard refresh, then confirm the scene came back
    await cdp.eval(`location.reload()`);
    await sleep(500);
    const report = JSON.parse(
      await cdp.waitFor(`window.__wbLastLoad ? JSON.stringify(window.__wbLastLoad) : null`),
    );
    const after = await cdp.eval(`window.__wb.canvas.getObjects().length`);
    log(`   after refresh: canvas objects=${after} · report=${JSON.stringify(report)}`);
    if (after !== saved) {
      fail(`roundtrip: after refresh the canvas has ${after} objects, expected ${saved}`);
      return false;
    }
    ok(`roundtrip: shape survived the refresh (${after}/${saved})`);
    return true;
  } finally {
    await api(`/api/boards/${board.id}`, { method: 'DELETE' }).catch(() => {});
  }
}

/* -------------------------------------------------------------------- main */

async function main() {
  const health = await api('/api/health').catch(() => null);
  if (!health) {
    console.error(`✖ ${BASE}/api/health is not reachable`);
    process.exitCode = 2;
    return;
  }
  const bin = findChrome();
  if (!bin) {
    console.error('✖ no Chrome/Chromium binary found — set CHROME_BIN');
    process.exitCode = 2;
    return;
  }
  log(`→ ${BASE} · browser ${bin}`);

  const { child, port } = await launchChrome(bin);
  let cdp;
  try {
    let boardId = BOARD_ID;
    if (!boardId) {
      const boards = await api('/api/boards');
      boardId = boards[0]?.id;
      if (!boardId) {
        console.error('✖ no board to verify — create one first or pass --board <id>');
        process.exitCode = 2;
        return;
      }
    }
    const page = await newPage(port, `${BASE}/#/b/${boardId}`);
    cdp = page.cdp;
    await cdp.waitFor(`!!window.__wb`);
    const loadOk = await checkLoad(cdp, boardId);
    if (LOAD_ONLY) {
      log(loadOk ? '\nLOAD CHECK PASSED' : '\nLOAD CHECK FAILED');
      if (!loadOk) process.exitCode = 1;
      return;
    }
    const tripOk = await checkRoundTrip(cdp);
    log(loadOk && tripOk ? '\nALL CHECKS PASSED' : '\nCHECKS FAILED');
    if (!(loadOk && tripOk)) process.exitCode = 1;
  } finally {
    try {
      cdp?.ws.close();
    } catch {
      /* ignore */
    }
    child.kill('SIGKILL');
  }
}

main().catch((err) => {
  console.error(`✖ ${err.message}`);
  process.exitCode = 1;
});
