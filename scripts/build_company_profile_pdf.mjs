#!/usr/bin/env node

/** Export the enhanced 13-page company-profile HTML deck as a 16:9 PDF. */

import { spawn } from "node:child_process";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(root, "output/brochure/zerolabs-company-profile-ko-2026.html");
const outputPath = path.join(root, "output/pdf/zerolabs-company-profile-ko-2026.pdf");
const stagedOutput = `${outputPath}.new`;
const expectedSlideLabels = [
  "01 표지",
  "02 목차",
  "03 회사 개요",
  "04 브랜드 원칙",
  "05 생산·원료",
  "06 제품 라인업",
  "07 리뷰 데이터",
  "08 제품 선택 가이드",
  "09 채널",
  "10 파트너십",
  "11 연혁",
  "12 기부 캠페인",
  "13 문의",
];
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

async function waitFor(predicate, timeoutMilliseconds, description) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    const value = await predicate();
    if (value) return value;
    await delay(100);
  }
  throw new Error(`Timed out waiting for ${description}`);
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

const server = createServer((request, response) => {
  try {
    const requestPath = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    const relative = requestPath === "/" ? "index.html" : requestPath.slice(1);
    const filePath = path.resolve(root, relative);
    if (filePath !== sourcePath || !existsSync(filePath) || !statSync(filePath).isFile()) {
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
const profile = mkdtempSync(path.join(tmpdir(), "company-profile-pdf-"));
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
  const targets = await fetch(`http://127.0.0.1:${cdpPort}/json/list`).then((response) => response.json());
  const page = targets.find((item) => item.type === "page");
  assert(page, "Chrome page target is unavailable");
  cdp = await connect(page.webSocketDebuggerUrl);
  await cdp.call("Page.enable");
  await cdp.call("Runtime.enable");
  await cdp.call("Page.navigate", {
    url: `http://127.0.0.1:${address.port}/output/brochure/zerolabs-company-profile-ko-2026.html#1`,
  });
  await waitFor(async () => {
    const result = await cdp.call("Runtime.evaluate", {
      expression: `(() => {
        const expected = ${JSON.stringify(expectedSlideLabels)};
        const sections = Array.from(document.querySelectorAll('section'));
        return sections.length === expected.length
          && sections.every((section, index) => section.getAttribute('data-label') === expected[index])
          && sections[6]?.getAttribute('data-review-proof') === 'true';
      })()`,
      returnByValue: true,
    });
    return result.result.value;
  }, 45_000, "fully labeled 13-page enhanced company profile");
  await cdp.call("Runtime.evaluate", {
    expression: "Promise.all([document.fonts.ready, ...Array.from(document.images, image => image.decode().catch(() => {}))])",
    awaitPromise: true,
    returnByValue: true,
  });
  await waitFor(async () => {
    const result = await cdp.call("Runtime.evaluate", {
      expression: `(() => {
        const expected = ${JSON.stringify(expectedSlideLabels)};
        const sections = Array.from(document.querySelectorAll('section'));
        return sections.length === expected.length
          && sections.every((section, index) => section.getAttribute('data-label') === expected[index])
          && sections[6]?.getAttribute('data-review-proof') === 'true';
      })()`,
      returnByValue: true,
    });
    return result.result.value;
  }, 15_000, "stable labeled 13-page company profile");
  const prepared = await cdp.call("Runtime.evaluate", {
    expression: `(() => {
      const sections = Array.from(document.querySelectorAll('section'));
      if (sections.length !== 13) return { pages: sections.length };
      document.documentElement.lang = 'ko-KR';
      document.title = '주식회사 반려동행 회사소개서 2026';
      const exportRoot = document.createElement('main');
      exportRoot.id = 'pdf-export-root';
      sections.forEach((section) => {
        const page = document.createElement('article');
        page.className = 'pdf-export-page';
        const canvas = document.createElement('div');
        canvas.className = 'pdf-export-canvas';
        const clone = section.cloneNode(true);
        clone.removeAttribute('hidden');
        clone.setAttribute('aria-hidden', 'false');
        clone.style.setProperty('width', '1920px', 'important');
        clone.style.setProperty('height', '1080px', 'important');
        clone.style.setProperty('min-width', '1920px', 'important');
        clone.style.setProperty('min-height', '1080px', 'important');
        clone.style.setProperty('max-width', '1920px', 'important');
        clone.style.setProperty('max-height', '1080px', 'important');
        clone.style.setProperty('position', 'relative', 'important');
        clone.style.setProperty('inset', 'auto', 'important');
        clone.style.setProperty('transform', 'none', 'important');
        clone.style.setProperty('opacity', '1', 'important');
        clone.style.setProperty('visibility', 'visible', 'important');
        clone.style.setProperty('overflow', 'hidden', 'important');
        canvas.appendChild(clone);
        page.appendChild(canvas);
        exportRoot.appendChild(page);
      });
      document.body.replaceChildren(exportRoot);
      const style = document.createElement('style');
      style.textContent = \`
        @page { size: 13.333333in 7.5in; margin: 0; }
        html, body { margin: 0 !important; padding: 0 !important; width: 1280px !important; background: #fff !important; }
        body { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        #pdf-export-root { width: 1280px !important; margin: 0 !important; padding: 0 !important; }
        .pdf-export-page { position: relative !important; width: 1280px !important; height: 720px !important; margin: 0 !important; padding: 0 !important; overflow: hidden !important; break-after: page !important; page-break-after: always !important; }
        .pdf-export-page:last-child { break-after: auto !important; page-break-after: auto !important; }
        .pdf-export-canvas { width: 1920px !important; height: 1080px !important; transform: scale(0.6666666667) !important; transform-origin: 0 0 !important; }
      \`;
      document.head.appendChild(style);
      return {
        pages: exportRoot.children.length,
        labels: Array.from(exportRoot.querySelectorAll('section'), section => section.getAttribute('data-label')),
      };
    })()`,
    returnByValue: true,
  });
  assert(
    !prepared.exceptionDetails,
    `PDF preparation failed: ${prepared.exceptionDetails?.exception?.description || prepared.exceptionDetails?.text || "unknown error"}`,
  );
  assert(prepared.result.value?.pages === 13, `Prepared ${prepared.result.value?.pages} PDF pages instead of 13`);
  assert(
    JSON.stringify(prepared.result.value.labels) === JSON.stringify(expectedSlideLabels),
    `Prepared PDF slide order differs: ${JSON.stringify(prepared.result.value.labels)}`,
  );
  await cdp.call("Runtime.evaluate", {
    expression: `Promise.all([
      document.fonts.ready,
      new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    ])`,
    awaitPromise: true,
    returnByValue: true,
  });
  const printed = await cdp.call("Page.printToPDF", {
    landscape: true,
    displayHeaderFooter: false,
    printBackground: true,
    preferCSSPageSize: true,
    marginTop: 0,
    marginBottom: 0,
    marginLeft: 0,
    marginRight: 0,
    generateTaggedPDF: true,
    generateDocumentOutline: true,
    transferMode: "ReturnAsBase64",
  });
  const rawData = Buffer.from(printed.data, "base64");
  assert(rawData.length > 1_000_000, `Generated company PDF is unexpectedly small: ${rawData.length}`);
  const rawText = rawData.toString("latin1");
  const datePattern = /\/(CreationDate|ModDate) \(D:\d{14}[+-]\d{2}'\d{2}'\)/g;
  const dateFields = rawText.match(datePattern) || [];
  assert(dateFields.length === 2, `Expected two PDF date fields, found ${dateFields.length}`);
  const normalizedText = rawText.replace(
    datePattern,
    (_, field) => `/${field} (D:20260828000000+09'00')`,
  );
  const data = Buffer.from(normalizedText, "latin1");
  assert(data.length === rawData.length, "PDF metadata normalization changed the file length");
  rmSync(stagedOutput, { force: true });
  writeFileSync(stagedOutput, data);
  renameSync(stagedOutput, outputPath);
  process.stdout.write(`${JSON.stringify({ status: "ok", pages: 13, bytes: data.length, output: path.relative(root, outputPath) })}\n`);
} finally {
  rmSync(stagedOutput, { force: true });
  if (cdp) cdp.close();
  await stopBrowser(browser);
  await new Promise((resolve) => server.close(resolve));
  rmSync(profile, { recursive: true, force: true });
}
