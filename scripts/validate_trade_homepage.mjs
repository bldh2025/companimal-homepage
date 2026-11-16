#!/usr/bin/env node
/** Browser regression check for the business homepage, inquiry flow and disclosures. */
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

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

const server = createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const file = path.resolve(root, '.' + pathname + (pathname.endsWith('/') ? 'index.html' : ''));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  try {
    const mime = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.png':'image/png','.webp':'image/webp'}[path.extname(file)] || 'application/octet-stream';
    res.writeHead(200, {'Content-Type':mime}); res.end(readFileSync(file));
  } catch (_) { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = process.env.SITE_URL || `http://127.0.0.1:${server.address().port}`;
const profile = mkdtempSync(path.join(tmpdir(), 'trade-homepage-'));
const screenshots = path.join(root, 'tmp', 'trade-homepage');
mkdirSync(screenshots, {recursive:true});
let browser, cdp;
try {
  browser = spawn(chrome, ['--headless=new','--no-first-run','--disable-background-networking','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'], {stdio:'ignore'});
  await waitFor(() => existsSync(path.join(profile, 'DevToolsActivePort')), 15000, 'Chrome port');
  const port = readFileSync(path.join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0];
  const tabs = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json());
  cdp = await connect(tabs.find(t => t.type === 'page').webSocketDebuggerUrl);
  await cdp.call('Page.enable'); await cdp.call('Runtime.enable');
  await cdp.call('Emulation.setEmulatedMedia', {features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  async function evaluate(expression) {
    const r = await cdp.call('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true});
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
  async function screenshot(name) {
    const r = await cdp.call('Page.captureScreenshot', {format:'png'});
    writeFileSync(path.join(screenshots, name+'.png'), Buffer.from(r.data,'base64'));
  }
  for (const route of ['/', '/en/', '/zh/', '/zh-hant/']) {
    await cdp.call('Emulation.setDeviceMetricsOverride', {width:1440,height:1100,deviceScaleFactor:1,mobile:false});
    await cdp.call('Page.navigate', {url:base+route});
    await waitFor(async () => await evaluate(`location.pathname === ${JSON.stringify(route)} && document.readyState === 'complete' && !!document.querySelector('[data-inquiry-email]')`), 45000, 'page load');
    await evaluate(`document.fonts.ready`);
    const structure = await evaluate(`(() => {
      const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
      return {order:[...document.querySelectorAll('main>section')].map(e=>e.id||'hero'),
        nav:[...document.querySelectorAll('#navLinks .link')].map(e=>e.getAttribute('href')),
        duplicateIds:ids.filter((id,i)=>ids.indexOf(id)!==i),
        deadLinks:[...document.querySelectorAll('a[href^="#"]')].filter(e=>e.hash && !document.getElementById(e.hash.slice(1))).map(e=>e.hash),
        products:document.querySelectorAll('#products .pcard').length,samples:document.querySelectorAll('.sample-card').length,
        downloads:[...document.querySelectorAll('[data-brochure-kind] select')].map(e=>e.options.length)};
    })()`);
    assert(JSON.stringify(structure.order) === JSON.stringify(['hero','trade','products','proof','trade-process','company','contact','downloads','shopping']), route+' section order');
    assert(JSON.stringify(structure.nav) === JSON.stringify(['#products','#trade','#proof','#company']), route+' navigation');
    assert(!structure.duplicateIds.length && !structure.deadLinks.length, route+' IDs and anchors');
    assert(structure.products === 8 && structure.samples === 4, route+' product counts');
    assert(structure.downloads.length===2 && structure.downloads.every(n=>n===7), route+' download languages');
    for (const width of [1440,1024,768,390]) {
      await cdp.call('Emulation.setDeviceMetricsOverride', {width,height:1100,deviceScaleFactor:1,mobile:false});
      await delay(350);
      const layout = await evaluate(`({overflow:document.documentElement.scrollWidth>innerWidth, hero:getComputedStyle(document.querySelector('.hero-grid')).gridTemplateColumns})`);
      assert(!layout.overflow, route+' overflow at '+width);
      if (route==='/' && (width===1440 || width===390)) { await evaluate('scrollTo(0,0)'); await delay(100); await screenshot('hero-'+width); }
    }
    await evaluate(`document.getElementById('hamburger').click()`);
    assert(await evaluate(`document.getElementById('hamburger').getAttribute('aria-expanded')==='true' && document.getElementById('navLinks').classList.contains('open')`), route+' mobile menu opens');
    await evaluate(`document.querySelector('#navLinks a[href="#products"]').click()`);
    assert(await evaluate(`document.getElementById('hamburger').getAttribute('aria-expanded')==='false'`), route+' mobile menu closes');
    for (const type of ['retail','online','distribution']) {
      const ok = await evaluate(`(() => {
        const link=document.querySelector('[data-trade-type="${type}"]');link.click();
        return !document.querySelector('.inquiry-context').hidden && document.querySelector('#inquiry-selection').textContent===link.dataset.inquiryLabel && document.querySelector('#inquiry-guide').textContent===link.dataset.inquiryGuide && new URL(document.querySelector('[data-inquiry-email]').href).searchParams.get('subject')==='ZERO LABS · '+link.dataset.inquiryLabel;
      })()`);
      assert(ok, route+' inquiry type '+type);
    }
    assert(await evaluate(`(() => {const d=document.querySelector('.product-details');d.querySelector('summary').click();return d.open;})()`), route+' product disclosure');
    await evaluate(`document.querySelector('.product-details a').click()`);
    assert(await evaluate(`document.querySelector('#inquiry-selection').textContent===document.querySelector('.pcard h3').textContent`), route+' product inquiry');
    await evaluate(`document.querySelector('.sample-card').click()`);
    assert(await evaluate(`document.querySelector('#inquiry-selection').textContent.includes('30g')`), route+' sample inquiry');
    await evaluate(`document.querySelector('.history-link').click()`);
    assert(await evaluate(`document.getElementById('history').closest('details').open && document.querySelectorAll('#history .yr').length===6`), route+' history reveal');
    if (route==='/') {
      const images = await evaluate(`(async()=>{const images=[...document.querySelectorAll('.showcase-grid img,#products img')];images.forEach(i=>i.loading='eager');await Promise.all(images.map(i=>i.decode()));return images.every(i=>i.naturalWidth>0);})()`);
      assert(images, 'product and hero images');
      await cdp.call('Emulation.setDeviceMetricsOverride', {width:1440,height:1100,deviceScaleFactor:1,mobile:false});
      await evaluate(`document.getElementById('products').scrollIntoView()`); await screenshot('products-desktop');
      await evaluate(`document.querySelector('[data-trade-type="distribution"]').click()`); await screenshot('contact-desktop');
    }
    console.log(route+' passed: structure, 4 viewport widths, navigation, inquiries, disclosures, downloads');
  }
  await cdp.call('Page.navigate', {url:base+'/#history'});
  await waitFor(async () => await evaluate(`document.readyState==='complete' && !!document.getElementById('history')?.closest('details')?.open`), 45000, 'direct history bookmark');
  console.log('Direct history bookmark passed');
} finally {
  if (cdp) cdp.close();
  await stopBrowser(browser);
  await new Promise(r=>server.close(r));
  rmSync(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
