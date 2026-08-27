#!/usr/bin/env node

/**
 * End-to-end company-profile release check.
 * Requires Node.js 22+ with fetch/WebSocket support and Google Chrome. Run after
 * `python3 scripts/finalize_brochure_release.py`; override Chrome with
 * `CHROME_PATH=/path/to/chrome` when it is not installed at the macOS default.
 * Usage: `node scripts/validate_company_profile_runtime.mjs [optional-screenshot.png]`.
 */

import { spawn } from "node:child_process";
import {
  existsSync,
  copyFileSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const chrome = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
].find((candidate) => candidate && existsSync(candidate));
const screenshotPath = process.argv[2] ? path.resolve(process.argv[2]) : null;
const screenshotPage = Number.parseInt(process.env.COMPANY_PROFILE_SCREENSHOT_PAGE || "8", 10);
assert(Number.isInteger(screenshotPage) && screenshotPage >= 1 && screenshotPage <= 13, "Screenshot page must be between 1 and 13");
const expectedAllChannelCards = [
  ["고기가득", "11,659건"],
  ["영양가득", "6,473건"],
  ["베리가득", "10,906건"],
  ["치카하개", "1,886건"],
  ["굽빵", "54건"],
  ["미트리스", "433건"],
  ["멍스", "477건"],
  ["프레쉬링", "869건"],
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function mimeType(filePath) {
  return {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".jpg": "image/jpeg",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
  }[path.extname(filePath).toLowerCase()] || "application/octet-stream";
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

function connect(webSocketDebuggerUrl) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  const pending = new Map();
  let nextId = 1;
  let closed = false;
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result);
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
        close() {
          socket.close();
        },
      });
    }, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
}

async function readSectionLayout(cdp, pageNumber) {
  await cdp.call("Runtime.evaluate", {
    expression: `location.hash = '#${pageNumber}'`,
    returnByValue: true,
  });
  await delay(300);
  const result = await cdp.call("Runtime.evaluate", {
    expression: `(() => {
      const section = Array.from(document.querySelectorAll('section'))[${pageNumber - 1}];
      const rect = section.getBoundingClientRect();
      return {
        label: section.getAttribute('data-label'),
        clientWidth: section.clientWidth,
        clientHeight: section.clientHeight,
        rectWidth: rect.width,
        rectHeight: rect.height,
        overflow: section.scrollWidth > section.clientWidth || section.scrollHeight > section.clientHeight,
      };
    })()`,
    returnByValue: true,
  });
  return result.result.value;
}

const server = createServer((request, response) => {
  try {
    const requestPath = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    const relative = requestPath === "/" ? "index.html" : requestPath.slice(1);
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
const profile = mkdtempSync(path.join(tmpdir(), "company-profile-runtime-"));
const standaloneDirectory = mkdtempSync(path.join(tmpdir(), "company-profile-standalone-"));
let browser;
let cdp;

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
    "--window-size=1920,1080",
    "about:blank",
  ], { stdio: "ignore" });
  const portFile = path.join(profile, "DevToolsActivePort");
  await waitFor(() => existsSync(portFile), 15_000, "Chrome DevTools port");
  const cdpPort = readFileSync(portFile, "utf8").split("\n", 1)[0];
  const pages = await fetch(`http://127.0.0.1:${cdpPort}/json/list`).then((response) => response.json());
  const page = pages.find((item) => item.type === "page");
  assert(page, "Chrome page target is unavailable");
  cdp = await connect(page.webSocketDebuggerUrl);
  await cdp.call("Page.enable");
  await cdp.call("Runtime.enable");
  await cdp.call("Emulation.setDeviceMetricsOverride", {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false,
  });
  const url = `http://127.0.0.1:${address.port}/output/brochure/zerolabs-company-profile-ko-2026.html#8`;
  await cdp.call("Page.navigate", { url });
  await waitFor(async () => {
    const result = await cdp.call("Runtime.evaluate", {
      expression: "document.querySelectorAll('section').length === 13",
      returnByValue: true,
    });
    return result.result.value;
  }, 45_000, "13-page enhanced company profile");
  await cdp.call("Runtime.evaluate", {
    expression: "Promise.all([document.fonts.ready, ...Array.from(document.images, image => image.decode().catch(() => {}))])",
    awaitPromise: true,
    returnByValue: true,
  });
  await delay(500);
  const idempotentResult = await cdp.call("Runtime.evaluate", {
    expression: "window.enhanceCompanyProfile(document); document.querySelectorAll('section').length",
    returnByValue: true,
  });
  assert(idempotentResult.result.value === 13, "Company profile enhancer is not idempotent");
  const changedPageLayouts = {
    page2: await readSectionLayout(cdp, 2),
    page7: await readSectionLayout(cdp, 7),
    page8: await readSectionLayout(cdp, 8),
    page9: await readSectionLayout(cdp, 9),
  };
  const result = await cdp.call("Runtime.evaluate", {
    expression: `(() => {
      const sections = Array.from(document.querySelectorAll('section'));
      const page8 = sections[7];
      const contents = sections[1];
      const eyebrow = (section) => Array.from(section.querySelectorAll('span')).find((span) => /^\\d{2} — /.test(span.textContent.trim()));
      return {
        labels: sections.map((section) => section.getAttribute('data-label')),
        screenLabels: sections.map((section) => section.getAttribute('data-screen-label')),
        eyebrows: sections.slice(2).map((section) => eyebrow(section)?.textContent.trim() || ''),
        allChannelMarker: sections[6].getAttribute('data-review-proof'),
        deprecatedCoupangMarkers: document.querySelectorAll('[data-channel-review-proof="coupang"]').length,
        page7Text: sections[6].textContent,
        page8Text: page8.textContent,
        page9Text: sections[8].textContent,
        page8Overflow: page8.scrollWidth > page8.clientWidth || page8.scrollHeight > page8.clientHeight,
        page7Cards: Array.from(sections[6].querySelectorAll('article')).map((card) => ({
          name: card.querySelector('h3')?.textContent.trim() || '',
          count: card.querySelector('strong')?.textContent.trim() || '',
          imageAlt: card.querySelector('img')?.getAttribute('alt') || '',
        })),
        contentsRows: Array.from(contents.children[1].children).filter((child) => child.tagName === 'DIV').length,
        contentsNumbers: Array.from(contents.children[1].children)
          .filter((child) => child.tagName === 'DIV')
          .map((row) => row.querySelector('span')?.textContent.trim() || ''),
        contentsText: contents.textContent,
        decorativeOrdinals: [3, 5, 9].map((index) => Array.from(sections[index].querySelectorAll('span'))
          .map((span) => span.textContent.trim())
          .filter((text) => /^0[1-8]$/.test(text))),
        enhancerError: window.__companyProfileEnhancementError || null,
        contactText: sections[12].textContent,
      };
    })()`,
    returnByValue: true,
  });
  const metrics = result.result.value;
  assert(metrics.labels.length === 13, "Runtime slide count is not 13");
  assert(metrics.labels.every((label, index) => label.startsWith(String(index + 1).padStart(2, "0") + " ")), `Runtime data-label sequence is invalid: ${JSON.stringify(metrics.labels)}`);
  // The enhancer authors a number-only data-screen-label. The presentation
  // runtime then prefixes that ordinal to data-label for the final sidebar
  // display, yielding values such as "08 08 제품 선택 가이드" in the live DOM.
  assert(metrics.screenLabels.every((label, index) => label === `${String(index + 1).padStart(2, "0")} ${metrics.labels[index]}`), `Rendered screen-label sequence is invalid: ${JSON.stringify(metrics.screenLabels)}`);
  assert(metrics.eyebrows.every((label, index) => label.startsWith(String(index + 1).padStart(2, "0") + " — ")), `Runtime eyebrow sequence is invalid: ${JSON.stringify(metrics.eyebrows)}`);
  assert(metrics.labels[6].endsWith("리뷰 데이터"), "Page 7 is not the all-channel review page");
  assert(metrics.labels[7].endsWith("제품 선택 가이드"), "Page 8 is not the product guide after removing the duplicate page");
  assert(metrics.labels[8].endsWith("채널"), "Page 9 is not the channels page after removing the duplicate page");
  assert(metrics.allChannelMarker === "true", "The all-channel review page marker is invalid");
  assert(metrics.deprecatedCoupangMarkers === 0, "The deprecated Coupang review page marker remains");
  assert(metrics.page7Text.includes("전체 판매채널 누적 리뷰 32,757건"), "Page 7 does not preserve the all-channel total");
  assert(metrics.page7Cards.length === expectedAllChannelCards.length, `Page 7 has ${metrics.page7Cards.length} product cards instead of 8`);
  metrics.page7Cards.forEach((card, index) => {
    const [expectedName, expectedCount] = expectedAllChannelCards[index];
    assert(card.name === expectedName && card.count === expectedCount, `All-channel card ${index + 1} is ${card.name}/${card.count}, expected ${expectedName}/${expectedCount}`);
    assert(card.imageAlt.includes(expectedName), `All-channel card ${index + 1} image alt does not match ${expectedName}: ${card.imageAlt}`);
  });
  assert(!metrics.page8Text.includes("31,169건") && !metrics.labels.some((label) => label.includes("쿠팡 리뷰")), "The duplicate Coupang review page remains");
  assert(metrics.page9Text.includes("판매 채널") || metrics.page9Text.includes("채널"), "Page 9 channels content is missing");
  assert(metrics.contentsRows === 11, `Contents page has ${metrics.contentsRows} rows instead of 11`);
  assert(metrics.contentsNumbers.every((value, index) => value === String(index + 1).padStart(2, "0")), `Contents numbering regressed: ${JSON.stringify(metrics.contentsNumbers)}`);
  assert(!metrics.contentsText.includes("쿠팡 채널 · 누적 리뷰"), `Contents page still lists the deleted Coupang review page: ${JSON.stringify(metrics.contentsText)}`);
  assert(metrics.decorativeOrdinals.every((values) => values.length === 0), `Decorative card ordinals remain: ${JSON.stringify(metrics.decorativeOrdinals)}`);
  assert(!metrics.page8Overflow, "Product guide page overflows at 1920×1080");
  Object.entries(changedPageLayouts).forEach(([page, layout]) => {
    assert(layout.clientWidth === 1920 && layout.clientHeight === 1080, `${page} layout is ${layout.clientWidth}×${layout.clientHeight}, expected 1920×1080`);
    assert(layout.rectWidth > 0 && layout.rectHeight > 0 && !layout.overflow, `${page} is hidden or overflows at 1920×1080`);
  });
  assert(!metrics.enhancerError, `Company profile enhancer failed: ${metrics.enhancerError}`);
  assert(metrics.contactText.includes("ceo@companimal.kr"), "Company contact email regressed");

  if (screenshotPath) {
    const screenshotUrl = url.replace(/#.*$/, `#${screenshotPage}`);
    await cdp.call("Page.navigate", { url: screenshotUrl });
    await waitFor(async () => {
      const state = await cdp.call("Runtime.evaluate", {
        expression: `document.querySelectorAll('section').length === 13 && location.hash === '#${screenshotPage}'`,
        returnByValue: true,
      });
      return state.result.value;
    }, 45_000, `company profile screenshot page ${screenshotPage}`);
    await cdp.call("Runtime.evaluate", {
      expression: "Promise.all([document.fonts.ready, ...Array.from(document.images, image => image.decode().catch(() => {}))])",
      awaitPromise: true,
      returnByValue: true,
    });
    await cdp.call("Runtime.evaluate", { expression: "document.body.focus()", returnByValue: true });
    for (const key of ["Home", ...Array.from({ length: screenshotPage - 1 }, () => "ArrowRight")]) {
      await cdp.call("Input.dispatchKeyEvent", { type: "keyDown", key, code: key });
      await cdp.call("Input.dispatchKeyEvent", { type: "keyUp", key, code: key });
      await delay(120);
    }
    await delay(500);
    const visiblePageResult = await cdp.call("Runtime.evaluate", {
      expression: `(() => {
        const section = document.elementFromPoint(innerWidth / 2, innerHeight / 2)?.closest('section');
        return Array.from(document.querySelectorAll('section')).indexOf(section) + 1;
      })()`,
      returnByValue: true,
    });
    assert(visiblePageResult.result.value === screenshotPage, `Screenshot navigation landed on page ${visiblePageResult.result.value}, expected ${screenshotPage}`);
    const screenshot = await cdp.call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    writeFileSync(screenshotPath, Buffer.from(screenshot.data, "base64"));
  }

  const standaloneCopy = path.join(standaloneDirectory, "zerolabs-company-profile-ko-2026.html");
  copyFileSync(path.join(root, "output/brochure/zerolabs-company-profile-ko-2026.html"), standaloneCopy);
  const standaloneUrl = pathToFileURL(standaloneCopy).href + "#8";
  await cdp.call("Page.navigate", { url: standaloneUrl });
  await waitFor(async () => {
    const state = await cdp.call("Runtime.evaluate", {
      expression: "document.querySelectorAll('section').length === 13",
      returnByValue: true,
    });
    return state.result.value;
  }, 45_000, "13-page standalone file company profile");
  const standalone = await cdp.call("Runtime.evaluate", {
    expression: `(() => ({
      pages: document.querySelectorAll('section').length,
      protocol: location.protocol,
      allChannelMarker: document.querySelectorAll('section')[6]?.getAttribute('data-review-proof'),
      page8IsGuide: document.querySelectorAll('section')[7]?.getAttribute('data-label')?.endsWith('제품 선택 가이드'),
      deprecatedCoupangMarkers: document.querySelectorAll('[data-channel-review-proof="coupang"]').length,
      externalRuntimeScripts: document.querySelectorAll('script[src*="brochure-review-data"],script[src*="company-contact-patch"]').length,
    }))()`,
    returnByValue: true,
  });
  assert(standalone.result.value.pages === 13 && standalone.result.value.allChannelMarker === "true" && standalone.result.value.page8IsGuide, "Standalone downloaded company profile does not have the expected 13-page order");
  assert(standalone.result.value.deprecatedCoupangMarkers === 0, "Standalone company profile still contains the deleted Coupang page");
  assert(standalone.result.value.protocol === "file:", `Standalone company profile did not load through file://: ${standalone.result.value.protocol}`);
  assert(standalone.result.value.externalRuntimeScripts === 0, "Standalone company profile still requests external runtime scripts");

  await cdp.call("Page.addScriptToEvaluateOnNewDocument", {
    source: "window.__FORCE_COMPANY_PROFILE_ENHANCER_FAILURE__ = true;",
  });
  await cdp.call("Page.reload", { ignoreCache: true });
  const fallback = await waitFor(async () => {
    const state = await cdp.call("Runtime.evaluate", {
      expression: "({count: document.querySelectorAll('section').length, error: window.__companyProfileEnhancementError || null})",
      returnByValue: true,
    });
    return state.result.value.error ? state.result.value : null;
  }, 45_000, "fail-open base deck");
  assert(fallback.count === 12, `Enhancer fail-open deck has ${fallback.count} pages instead of 12`);
  console.log(JSON.stringify({
    status: "ok",
    pages: 13,
    removedCoupangPage: true,
    screenshot: screenshotPath,
    screenshotPage,
    labels: metrics.labels,
    screenLabels: metrics.screenLabels,
    changedPageLayouts,
    standaloneFilePages: standalone.result.value.pages,
    failOpenPages: 12,
  }));
} finally {
  if (cdp) cdp.close();
  if (browser && browser.exitCode === null) {
    browser.kill("SIGTERM");
    await Promise.race([
      new Promise((resolve) => browser.once("exit", resolve)),
      delay(3_000),
    ]);
    if (browser.exitCode === null) {
      browser.kill("SIGKILL");
      await Promise.race([
        new Promise((resolve) => browser.once("exit", resolve)),
        delay(1_000),
      ]);
    }
  }
  await new Promise((resolve) => server.close(resolve));
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  rmSync(standaloneDirectory, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
}
