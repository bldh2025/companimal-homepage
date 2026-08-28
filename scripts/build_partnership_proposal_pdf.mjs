#!/usr/bin/env node

/** Export the 12-page ZERO LABS B2B partnership proposal as a 16:9 PDF. */

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = path.join(root, "output/proposal/zerolabs-b2b-partnership-proposal-ko-2026.html");
const outputPath = path.join(root, "output/pdf/zerolabs-b2b-partnership-proposal-ko-2026.pdf");
const stagedOutput = `${outputPath}.new`;
const expectedLabels = [
  "01 표지", "02 제안 요약", "03 사업 근거", "04 주력 제품", "05 확장 제품", "06 도입 시나리오",
  "07 공개 거래 기준", "08 수익성 기준", "09 운영과 이슈 대응", "10 파일럿 KPI", "11 증빙과 출처", "12 다음 단계와 문의",
];
const chrome = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
].find((candidate) => candidate && existsSync(candidate));

function assert(condition, message) { if (!condition) throw new Error(message); }
function delay(milliseconds) { return new Promise((resolve) => setTimeout(resolve, milliseconds)); }
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
  const exitPromise = new Promise((resolve) => child.once("exit", resolve));
  child.kill("SIGTERM");
  await Promise.race([exitPromise, delay(3_000)]);
  if (child.exitCode === null && child.signalCode === null) {
    child.kill("SIGKILL");
    await Promise.race([exitPromise, delay(3_000)]);
  }
}
function mimeType(filePath) {
  return {
    ".html": "text/html; charset=utf-8", ".jpg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
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
    if (message.error) reject(new Error(JSON.stringify(message.error))); else resolve(message.result);
  });
  socket.addEventListener("close", () => {
    closed = true;
    for (const { reject } of pending.values()) reject(new Error("Chrome DevTools socket closed"));
    pending.clear();
  });
  return new Promise((resolve, reject) => {
    socket.addEventListener("open", () => resolve({
      call(method, params = {}) {
        if (closed) return Promise.reject(new Error("Chrome DevTools socket is closed"));
        const id = nextId++;
        socket.send(JSON.stringify({ id, method, params }));
        return new Promise((resolveCall, rejectCall) => pending.set(id, { resolve: resolveCall, reject: rejectCall }));
      },
      close() { socket.close(); },
    }), { once:true });
    socket.addEventListener("error", reject, { once:true });
  });
}

const server = createServer((request, response) => {
  try {
    const requestPath = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    const relative = requestPath === "/" ? "output/proposal/zerolabs-b2b-partnership-proposal-ko-2026.html" : requestPath.slice(1);
    const filePath = path.resolve(root, relative);
    const insideRoot = filePath === root || filePath.startsWith(`${root}${path.sep}`);
    if (!insideRoot || !existsSync(filePath) || !statSync(filePath).isFile()) {
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
const profile = mkdtempSync(path.join(tmpdir(), "zerolabs-proposal-pdf-"));
let browser;
let cdp;
try {
  assert(chrome, "Chrome is unavailable; set CHROME_PATH to a Chrome/Chromium executable");
  assert(existsSync(sourcePath), `Source HTML is missing: ${sourcePath}`);
  browser = spawn(chrome, [
    "--headless=new", "--disable-background-networking", "--disable-extensions", "--disable-gpu",
    "--no-first-run", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
    "--window-size=1280,720", "about:blank",
  ], { stdio:"ignore" });
  const portFile = path.join(profile, "DevToolsActivePort");
  await waitFor(() => existsSync(portFile), 15_000, "Chrome DevTools port");
  const cdpPort = readFileSync(portFile, "utf8").split("\n", 1)[0];
  const targets = await fetch(`http://127.0.0.1:${cdpPort}/json/list`).then((response) => response.json());
  const page = targets.find((item) => item.type === "page");
  assert(page, "Chrome page target is unavailable");
  cdp = await connect(page.webSocketDebuggerUrl);
  await cdp.call("Page.enable");
  await cdp.call("Runtime.enable");
  await cdp.call("Page.navigate", { url:`http://127.0.0.1:${address.port}/output/proposal/zerolabs-b2b-partnership-proposal-ko-2026.html` });
  await waitFor(async () => {
    const result = await cdp.call("Runtime.evaluate", {
      expression:`document.readyState === 'complete' && document.querySelectorAll('section.slide').length === ${expectedLabels.length}`,
      returnByValue:true,
    });
    return result.result.value;
  }, 30_000, "proposal document");
  await cdp.call("Runtime.evaluate", {
    expression:"Promise.all([document.fonts.ready, ...Array.from(document.images, image => image.decode())])",
    awaitPromise:true,
    returnByValue:true,
  });
  const audit = await cdp.call("Runtime.evaluate", {
    expression:`(() => {
      const expected = ${JSON.stringify(expectedLabels)};
      const pages = Array.from(document.querySelectorAll('section.slide'));
      const overflow = pages.map((page, index) => ({
        page:index + 1,
        width:page.scrollWidth,
        height:page.scrollHeight,
        clientWidth:page.clientWidth,
        clientHeight:page.clientHeight,
      })).filter((item) => item.width > item.clientWidth + 1 || item.height > item.clientHeight + 1);
      const brokenImages = Array.from(document.images).filter(image => !image.complete || image.naturalWidth === 0).map(image => image.getAttribute('src'));
      const visibleTextElements = Array.from(document.querySelectorAll('body *')).filter(element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && element.childNodes.length > 0 && Array.from(element.childNodes).some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
      });
      const fontSizes = visibleTextElements.map(element => Number.parseFloat(getComputedStyle(element).fontSize)).filter(Number.isFinite);
      const links = Array.from(document.querySelectorAll('a[href]')).map(anchor => anchor.href);
      return {
        count:pages.length,
        labels:pages.map(page => page.dataset.label),
        overflow,
        brokenImages,
        minFontPx:Math.min(...fontSizes),
        links,
        title:document.title,
        lang:document.documentElement.lang,
      };
    })()`,
    returnByValue:true,
  });
  const metrics = audit.result.value;
  assert(metrics.count === expectedLabels.length, `Expected 12 pages, found ${metrics.count}`);
  assert(JSON.stringify(metrics.labels) === JSON.stringify(expectedLabels), `Page labels differ: ${JSON.stringify(metrics.labels)}`);
  assert(metrics.overflow.length === 0, `Page overflow detected: ${JSON.stringify(metrics.overflow)}`);
  assert(metrics.brokenImages.length === 0, `Broken images: ${JSON.stringify(metrics.brokenImages)}`);
  assert(metrics.minFontPx >= 13.3, `Visible text is smaller than 10pt print size: ${metrics.minFontPx}px`);
  for (const target of ["mailto:ceo@companimal.kr", "mailto:bldh2025@naver.com", "https://companimal.kr/", "https://pf.kakao.com/_xnyDcs"]) {
    assert(metrics.links.includes(target), `Required clickable link is missing: ${target}`);
  }
  assert(metrics.lang === "ko-KR", `Unexpected language: ${metrics.lang}`);
  assert(metrics.title === "ZERO LABS B2B 파트너십 제안서 2026", `Unexpected title: ${metrics.title}`);
  const printed = await cdp.call("Page.printToPDF", {
    landscape:true, displayHeaderFooter:false, printBackground:true, preferCSSPageSize:true,
    marginTop:0, marginBottom:0, marginLeft:0, marginRight:0,
    generateTaggedPDF:true, generateDocumentOutline:true, transferMode:"ReturnAsBase64",
  });
  const rawData = Buffer.from(printed.data, "base64");
  assert(rawData.length > 500_000, `Generated proposal PDF is unexpectedly small: ${rawData.length}`);
  const rawText = rawData.toString("latin1");
  const datePattern = /\/(CreationDate|ModDate) \(D:\d{14}[+-]\d{2}'\d{2}'\)/g;
  const dateFields = rawText.match(datePattern) || [];
  assert(dateFields.length === 2, `Expected two PDF date fields, found ${dateFields.length}`);
  const normalizedText = rawText.replace(datePattern, (_, field) => `/${field} (D:20260828000000+09'00')`);
  const data = Buffer.from(normalizedText, "latin1");
  assert(data.length === rawData.length, "PDF metadata normalization changed file length");
  rmSync(stagedOutput, { force:true });
  writeFileSync(stagedOutput, data);
  renameSync(stagedOutput, outputPath);
  process.stdout.write(`${JSON.stringify({ status:"ok", pages:expectedLabels.length, bytes:data.length, output:path.relative(root, outputPath) })}\n`);
} finally {
  rmSync(stagedOutput, { force:true });
  if (cdp) cdp.close();
  await stopBrowser(browser);
  await new Promise((resolve) => server.close(resolve));
  rmSync(profile, { recursive:true, force:true });
}
