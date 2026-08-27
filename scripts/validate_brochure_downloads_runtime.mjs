#!/usr/bin/env node

/** Verify that brochure buttons download files instead of navigating. */

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(path.join(root, "output/pdf/brochure-files.json"), "utf8"));
const chrome = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
].find((candidate) => candidate && existsSync(candidate));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function stopBrowser(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  let exited = false;
  const exitPromise = new Promise((resolve) => child.once("exit", () => {
    exited = true;
    resolve();
  }));
  child.kill("SIGTERM");
  await Promise.race([exitPromise, delay(3_000)]);
  if (!exited && child.exitCode === null && child.signalCode === null) {
    child.kill("SIGKILL");
    await Promise.race([exitPromise, delay(3_000)]);
  }
  assert(exited || child.exitCode !== null || child.signalCode !== null, "Chrome did not exit after SIGKILL");
}

async function waitFor(predicate, timeoutMilliseconds, description) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    const value = await predicate();
    if (value) return value;
    await delay(100);
  }
  throw new Error(`Timed out waiting for ${description}`);
}

function mimeType(filePath) {
  return {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".pdf": "application/pdf",
    ".webp": "image/webp",
  }[path.extname(filePath).toLowerCase()] || "application/octet-stream";
}

function connect(webSocketDebuggerUrl) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  const pending = new Map();
  const handlers = new Map();
  let nextId = 1;
  let closed = false;
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
      return;
    }
    for (const handler of handlers.get(message.method) || []) handler(message.params || {});
  });
  socket.addEventListener("close", () => {
    closed = true;
    for (const { reject } of pending.values()) reject(new Error("Chrome DevTools socket closed"));
    pending.clear();
  });
  return new Promise((resolve, reject) => {
    socket.addEventListener("open", () => {
      resolve({
        call(method, params = {}) {
          if (closed) return Promise.reject(new Error("Chrome DevTools socket is already closed"));
          const id = nextId++;
          socket.send(JSON.stringify({ id, method, params }));
          return new Promise((resolveCall, rejectCall) => pending.set(id, { resolve: resolveCall, reject: rejectCall }));
        },
        on(method, handler) {
          if (!handlers.has(method)) handlers.set(method, []);
          handlers.get(method).push(handler);
        },
        close() {
          socket.close();
        },
      });
    }, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
}

const server = createServer((request, response) => {
  try {
    const requestPath = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    const relative = requestPath.endsWith("/")
      ? `${requestPath.slice(1)}index.html`
      : requestPath.slice(1);
    const filePath = path.resolve(root, relative);
    if (!filePath.startsWith(root + path.sep) || !existsSync(filePath) || !statSync(filePath).isFile()) {
      response.writeHead(404).end("Not found");
      return;
    }
    response.writeHead(200, { "Content-Type": mimeType(filePath), "Cache-Control": "no-store" });
    response.end(readFileSync(filePath));
  } catch (error) {
    response.writeHead(500).end(String(error));
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));

const address = server.address();
const profile = mkdtempSync(path.join(tmpdir(), "brochure-download-runtime-"));
const downloadDirectory = mkdtempSync(path.join(tmpdir(), "brochure-download-files-"));
const downloadEvents = [];
let browser;
let cdp;

const pages = [
  { path: "/", code: "ko" },
  { path: "/en/", code: "en" },
  { path: "/zh/", code: "zh-hans" },
  { path: "/zh-hant/", code: "zh-hant" },
].map((entry) => ({ ...entry, product: manifest[entry.code].product, locale: manifest[entry.code].locale }));
const companyFile = manifest.ko.company;
const companyName = path.basename(companyFile.path);
const productSelections = Object.entries(manifest).map(([code, entry]) => ({
  code,
  locale: entry.locale,
  file: entry.product,
}));

async function waitForEnhancedPage(expectedPath) {
  return waitFor(async () => {
    const result = await cdp.call("Runtime.evaluate", {
      expression: `(() => {
        const links = Array.from(document.querySelectorAll('a[data-download-link]'), link => ({
          href: link.getAttribute('href'),
          download: link.getAttribute('download'),
          type: link.getAttribute('type'),
          hreflang: link.getAttribute('hreflang'),
          label: link.textContent.trim()
        }));
        const selectors = Array.from(document.querySelectorAll('.download-select'));
        const companyOptions = Array.from(selectors[0]?.options || [], option => option.value);
        const productOptions = Array.from(selectors[1]?.options || [], option => option.value);
        const enhancedMeta = Array.from(document.querySelectorAll('[data-file-size]'))
          .every(element => element.textContent.includes('MB'));
        return location.pathname === ${JSON.stringify(expectedPath)}
          && companyOptions.length === 1
          && companyOptions[0] === 'ko'
          && productOptions.length === 7
          && enhancedMeta
          && links.length === 2
          && links.every(link => link.download)
          ? { links, companyOptions, productOptions }
          : null;
      })()`,
      returnByValue: true,
    });
    return result.result.value || null;
  }, 15_000, `${expectedPath} enhanced download links`);
}

async function download(index, expectedName, expectedRelativePath) {
  const eventStart = downloadEvents.length;
  await cdp.call("Runtime.evaluate", {
    expression: `document.querySelectorAll('a[data-download-link]')[${index}].click()`,
    userGesture: true,
    returnByValue: true,
  });
  const started = await waitFor(
    () => downloadEvents.slice(eventStart).find((event) => event.method === "begin" && event.suggestedFilename === expectedName),
    15_000,
    `${expectedName} download start`,
  );
  await waitFor(
    () => downloadEvents.slice(eventStart).find((event) => event.method === "progress" && event.guid === started.guid && event.state === "completed"),
    45_000,
    `${expectedName} download completion`,
  );
  const downloaded = path.join(downloadDirectory, expectedName);
  assert(existsSync(downloaded), `Downloaded file is missing: ${downloaded}`);
  assert(readFileSync(downloaded).equals(readFileSync(path.join(root, expectedRelativePath))), `Downloaded bytes differ: ${expectedName}`);
}

try {
  assert(chrome, "Chrome is unavailable; set CHROME_PATH to a Chrome/Chromium executable");
  browser = spawn(chrome, [
    "--headless=new",
    "--disable-background-networking",
    "--disable-extensions",
    "--disable-gpu",
    "--no-first-run",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ], { stdio: "ignore" });
  const portFile = path.join(profile, "DevToolsActivePort");
  await waitFor(() => existsSync(portFile), 15_000, "Chrome DevTools port");
  const cdpPort = readFileSync(portFile, "utf8").split("\n", 1)[0];
  const targets = await fetch(`http://127.0.0.1:${cdpPort}/json/list`).then((response) => response.json());
  const page = targets.find((item) => item.type === "page");
  assert(page, "Chrome page target is unavailable");
  cdp = await connect(page.webSocketDebuggerUrl);
  await cdp.call("Page.enable");
  await cdp.call("Runtime.enable");
  await cdp.call("Browser.setDownloadBehavior", {
    behavior: "allow",
    downloadPath: downloadDirectory,
    eventsEnabled: true,
  });
  cdp.on("Browser.downloadWillBegin", (event) => downloadEvents.push({ method: "begin", ...event }));
  cdp.on("Browser.downloadProgress", (event) => downloadEvents.push({ method: "progress", ...event }));

  for (const entry of pages) {
    await cdp.call("Page.navigate", { url: `http://127.0.0.1:${address.port}${entry.path}#downloads` });
    const { links } = await waitForEnhancedPage(entry.path);
    assert(
      links[0].href === `/${companyFile.path}`
        && links[0].download === companyName
        && links[0].type === "application/pdf"
        && links[0].hreflang === "ko-KR",
      `Company download regressed on ${entry.path}`,
    );
    assert(
      links[1].href === `/${entry.product.path}`
        && links[1].download === path.basename(entry.product.path)
        && links[1].type === "application/pdf",
      `Product download regressed on ${entry.path}`,
    );
    assert(links[1].hreflang === entry.locale, `Product locale regressed on ${entry.path}`);
    assert(!/Open|打开|開啟/.test(links[0].label), `Company label still describes opening on ${entry.path}`);
  }

  await cdp.call("Page.navigate", { url: `http://127.0.0.1:${address.port}/#downloads` });
  await waitForEnhancedPage("/");
  for (const selection of productSelections) {
    const result = await cdp.call("Runtime.evaluate", {
      expression: `(() => {
        const select = document.querySelectorAll('.download-select')[1];
        select.value = ${JSON.stringify(selection.code)};
        select.dispatchEvent(new Event('change'));
        const link = document.querySelectorAll('a[data-download-link]')[1];
        return {
          href: link.getAttribute('href'),
          download: link.getAttribute('download'),
          type: link.getAttribute('type'),
          hreflang: link.getAttribute('hreflang'),
          label: link.textContent.trim()
        };
      })()`,
      returnByValue: true,
    });
    const link = result.result.value;
    assert(
      link.href === `/${selection.file.path}`
        && link.download === path.basename(selection.file.path)
        && link.type === "application/pdf"
        && link.hreflang === selection.locale
        && link.label.includes("PDF"),
      `Product selector regressed for ${selection.code}`,
    );
  }
  await cdp.call("Runtime.evaluate", {
    expression: `(() => {
      const select = document.querySelectorAll('.download-select')[1];
      select.value = 'ko';
      select.dispatchEvent(new Event('change'));
    })()`,
    returnByValue: true,
  });
  await waitForEnhancedPage("/");
  await download(0, companyName, companyFile.path);
  await download(1, path.basename(manifest.ko.product.path), manifest.ko.product.path);
  const locationResult = await cdp.call("Runtime.evaluate", { expression: "location.pathname", returnByValue: true });
  assert(locationResult.result.value === "/", `Download click navigated to ${locationResult.result.value}`);

  process.stdout.write(`${JSON.stringify({
    status: "ok",
    pages: pages.length,
    productLanguages: productSelections.length,
    downloads: [companyName, path.basename(manifest.ko.product.path)],
  })}\n`);
} finally {
  if (cdp) cdp.close();
  await stopBrowser(browser);
  await new Promise((resolve) => server.close(resolve));
  rmSync(profile, { recursive: true, force: true });
  rmSync(downloadDirectory, { recursive: true, force: true });
}
