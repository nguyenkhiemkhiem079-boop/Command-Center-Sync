import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createServer } from 'node:net';

const args = Object.fromEntries(process.argv.slice(2).map((arg) => {
  const [key, ...rest] = arg.replace(/^--/, '').split('=');
  return [key, rest.join('=')];
}));
if (!args.url || !args.tokenFile || !args.screenshot || !args.report) throw new Error('url, tokenFile, screenshot and report are required');
const expectFallback = args.expectFallback === 'true';
const physicalGpu = args.physicalGpu === 'true';
const soakMs = Math.max(0, Math.min(Number(args.soakMs) || 0, 180000));
const browser = args.browser || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const token = (await readFile(args.tokenFile, 'utf8')).trim();
if (!token) throw new Error('Disposable staging token is empty');

async function freePort() {
  const server = createServer();
  await new Promise((ok, fail) => server.listen(0, '127.0.0.1', ok).once('error', fail));
  const { port } = server.address();
  await new Promise((ok, fail) => server.close((error) => error ? fail(error) : ok()));
  return port;
}

const port = await freePort();
const profile = await mkdtemp(join(tmpdir(), 'ktool-agent-world-chrome-'));
const chrome = spawn(browser, [
  ...(physicalGpu ? ['--enable-webgl', '--use-angle=d3d11'] : ['--headless=new', ...(expectFallback ? ['--disable-webgl'] : ['--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])]),
  '--remote-allow-origins=*', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--window-size=1600,1100', 'about:blank',
], { stdio: 'ignore', windowsHide: !physicalGpu });
let socket;
const errors = [];
const externalRequests = [];
const requests = [];
const consoleErrors = [];
const methods = new Map();
let sequence = 0;

try {
  let version;
  for (let i = 0; i < 100; i++) {
    try { version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); break; }
    catch { await delay(200); }
  }
  if (!version) throw new Error('Chrome DevTools endpoint did not start');
  const newTab = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(args.url)}`, { method: 'PUT' });
  if (!newTab.ok) throw new Error(`Chrome could not create tab: ${newTab.status}`);
  const target = await newTab.json();
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok, fail) => { socket.addEventListener('open', ok, { once: true }); socket.addEventListener('error', fail, { once: true }); });
  socket.addEventListener('message', (event) => {
    const packet = JSON.parse(event.data);
    if (packet.id && methods.has(packet.id)) {
      const { resolve: done, reject } = methods.get(packet.id);
      methods.delete(packet.id);
      packet.error ? reject(new Error(packet.error.message)) : done(packet.result);
    } else if (packet.method === 'Runtime.exceptionThrown') errors.push(packet.params.exceptionDetails?.text || 'Runtime exception');
    else if (packet.method === 'Log.entryAdded' && packet.params.entry?.level === 'error') consoleErrors.push(packet.params.entry.text);
    else if (packet.method === 'Network.requestWillBeSent') {
      const url = packet.params.request.url;
      requests.push({ url, method: packet.params.request.method });
      if (!url.startsWith('http://127.0.0.1:') && !url.startsWith('data:') && !url.startsWith('blob:')) externalRequests.push(url);
    } else if (packet.method === 'Network.responseReceived') {
      const response = packet.params.response;
      const found = requests.findLast((item) => item.url === response.url);
      if (found) found.status = response.status;
    }
  });
  const send = (method, params = {}, timeoutMs = 15000) => new Promise((ok, fail) => {
    const id = ++sequence;
    methods.set(id, { resolve: ok, reject: fail });
    socket.send(JSON.stringify({ id, method, params }));
    setTimeout(() => { if (methods.has(id)) { methods.delete(id); fail(new Error(`CDP timeout: ${method}`)); } }, timeoutMs).unref();
  });
  await Promise.all(['Page.enable', 'Runtime.enable', 'Network.enable', 'Log.enable'].map((method) => send(method)));
  await send('Page.navigate', { url: args.url });
  await delay(1500);
  const login = await send('Runtime.evaluate', {
    expression: `(async()=>{const token=${JSON.stringify(token)};const input=document.querySelector('#token');if(!input)return 'LOGIN_FORM_MISSING';input.value=token;document.querySelector('#loginForm').requestSubmit();return 'LOGIN_SUBMITTED'})()`,
    awaitPromise: true, returnByValue: true,
  });
  if (login.result?.value !== 'LOGIN_SUBMITTED') throw new Error(`Login form missing: ${login.result?.value}`);
  let loggedIn = false;
  for (let i = 0; i < 50; i++) {
    const state = await send('Runtime.evaluate', { expression: `!document.querySelector('#app')?.hidden`, returnByValue: true });
    if (state.result?.value) { loggedIn = true; break; }
    await delay(100);
  }
  if (!loggedIn) {
    const failure = await send('Runtime.evaluate', { expression: `document.querySelector('#loginError')?.textContent||'login did not complete'`, returnByValue: true });
    throw new Error(`Disposable staging login failed: ${failure.result?.value}`);
  }
  await send('Runtime.evaluate', { expression: `document.querySelector('[data-page="agentworld"]').click()` });
  let mounted = false;
  for (let i = 0; i < 80; i++) {
    const state = await send('Runtime.evaluate', { expression: `Boolean(document.querySelector('#agent-world-root'))`, returnByValue: true });
    if (state.result?.value) { mounted = true; break; }
    await delay(100);
  }
  if (!mounted) {
    const failure = await send('Runtime.evaluate', { expression: `({page:document.querySelector('.navitem.selected')?.dataset.page,content:document.querySelector('#content')?.innerText?.slice(0,500)})`, returnByValue: true });
    throw new Error(`Agent World did not mount: ${JSON.stringify(failure.result?.value)}`);
  }
  const inspection = await send('Runtime.evaluate', {
    expression: `(()=>{const root=document.querySelector('#agent-world-root');const canvas=root?.querySelector('canvas');const fallback=root?.querySelector('.aw-fallback');let gl=null;try{gl=canvas?.getContext('webgl2')}catch{};let renderer='UNKNOWN';try{const ext=gl?.getExtension('WEBGL_debug_renderer_info');renderer=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):'HIDDEN'}catch{};return {title:document.title,nav:document.querySelector('[data-page="agentworld"]')?.className,root:Boolean(root),fallback:fallback?.innerText||null,fallbackVisible:Boolean(fallback&&!fallback.hidden&&fallback.getBoundingClientRect().height>0),worldLabel:root?.innerText?.slice(0,900)||null,canvas:Boolean(canvas),webgl2:Boolean(gl),renderer,ua:navigator.userAgent,externalScripts:[...document.scripts].map(s=>s.src).filter(u=>u&&!u.startsWith(location.origin)),contentSecurityPolicy:document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content||null}})()`,
    returnByValue: true,
  });
  const result = inspection.result?.value || {};
  if (!result.root) throw new Error(`Agent World root did not mount: ${JSON.stringify({ inspection, result, errors, consoleErrors, requests })}`);
  if (!result.canvas && !result.fallback) throw new Error('Neither WebGL canvas nor the explicit fallback was rendered');
  const interaction = await send('Runtime.evaluate', {
    expression: `(()=>{const click=(s)=>document.querySelector(s)?.click();click('[data-aw-view="fleet"]');const fleetVisible=!document.querySelector('#aw-fleet-pane').hidden;click('#aw-fleet-pane button');const selected=document.querySelector('#aw-selected-title').textContent;click('[data-aw-view="timeline"]');const timelineVisible=!document.querySelector('#aw-timeline-pane').hidden;click('[data-aw-view="world"]');click('[data-camera="anti01"]');return {fleetVisible,selected,timelineVisible,worldSelected:document.querySelector('[data-aw-view="world"]').getAttribute('aria-selected'),anti01Camera:document.querySelector('[data-camera="anti01"]').textContent}})()`,
    returnByValue: true,
  });
  const interactionResult = interaction.result?.value;
  if (!interactionResult?.fleetVisible || !interactionResult?.timelineVisible || interactionResult.worldSelected !== 'true' || !interactionResult.selected.startsWith('CODEX')) {
    throw new Error(`Interactive view/selection controls failed: ${JSON.stringify(interactionResult)}`);
  }
  let gpuMeasurement = null;
  let contextRecovery = null;
  if (physicalGpu && !expectFallback && result.webgl2 && soakMs >= 10000) {
    const measurement = await send('Runtime.evaluate', {
      expression: `(()=>new Promise(resolve=>{const canvas=document.querySelector('#aw-canvas');const gl=canvas?.getContext('webgl2');if(!gl){resolve({error:'WEBGL2_UNAVAILABLE'});return}const info=gl.getExtension('WEBGL_debug_renderer_info');const renderer=info?gl.getParameter(info.UNMASKED_RENDERER_WEBGL):'RENDERER_HIDDEN';const frames=[];let lastDraw=0;for(const name of ['drawElements','drawArrays','drawElementsInstanced','drawArraysInstanced']){const original=gl[name]?.bind(gl);if(!original)continue;gl[name]=(...args)=>{const now=performance.now();if(now-lastDraw>20)frames.push(now);lastDraw=now;return original(...args)}}const heap=[];const memory=()=>performance.memory?.usedJSHeapSize??null;const initialHeap=memory();let peakHeap=initialHeap;const sampler=setInterval(()=>{const value=memory();if(value!==null){heap.push(value);peakHeap=Math.max(peakHeap||0,value)}},1000);const start=performance.now();setTimeout(()=>{clearInterval(sampler);const elapsed=performance.now()-start;const finalHeap=memory();resolve({renderer,elapsedMs:Math.round(elapsed),renderBatches:frames.length,fps:Math.round(frames.length*1000/elapsed*10)/10,heapStartBytes:initialHeap,heapEndBytes:finalHeap,heapPeakSampledBytes:peakHeap,heapSamples:heap.length,webglVersion:gl.getParameter(gl.VERSION)})},${soakMs})}))()`,
      awaitPromise: true, returnByValue: true,
    }, soakMs + 10000);
    gpuMeasurement = measurement.result?.value || null;
    if (!gpuMeasurement?.renderer || gpuMeasurement.error) throw new Error(`Physical GPU measurement failed: ${JSON.stringify(gpuMeasurement)}`);
    if (/swiftshader|software|llvmpipe/i.test(gpuMeasurement.renderer)) throw new Error(`Software renderer detected; physical GPU evidence rejected: ${gpuMeasurement.renderer}`);
    const recovery = await send('Runtime.evaluate', {
      expression: `(()=>new Promise(resolve=>{const canvas=document.querySelector('#aw-canvas');const fallback=document.querySelector('#aw-fallback');const gl=canvas?.getContext('webgl2');const ext=gl?.getExtension('WEBGL_lose_context');if(!ext){resolve({status:'NOT_SUPPORTED'});return}let lost=false,restored=false;const onLost=e=>{e.preventDefault();lost=true};const onRestored=()=>{restored=true};canvas.addEventListener('webglcontextlost',onLost,{once:true});canvas.addEventListener('webglcontextrestored',onRestored,{once:true});ext.loseContext();setTimeout(()=>{const fallbackShown=Boolean(fallback&&!fallback.hidden&&fallback.getBoundingClientRect().height>0);ext.restoreContext();setTimeout(()=>resolve({status:lost&&restored?'PASS':'FAIL',lost,restored,fallbackShown,canvasVisible:!canvas.hidden}),1200)},500)}))()`,
      awaitPromise: true, returnByValue: true,
    }, 5000);
    contextRecovery = recovery.result?.value || null;
    if (contextRecovery?.status !== 'PASS' || !contextRecovery.fallbackShown) throw new Error(`WebGL context recovery failed: ${JSON.stringify(contextRecovery)}`);
  }
  await delay(300);
  await mkdir(dirname(resolve(args.screenshot)), { recursive: true });
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, fromSurface: true });
  await writeFile(resolve(args.screenshot), Buffer.from(shot.data, 'base64'));
  const functionalPass = expectFallback ? (!result.webgl2 && Boolean(result.fallback) && result.fallbackVisible) : (result.canvas && result.webgl2);
  const report = {
    browserPath: browser, browserVersion: version.Browser, chromiumProtocol: version['Protocol-Version'],
    navigation: args.url, viewport: { width: 1600, height: 1100 }, result, interactions: interactionResult,
    consoleErrors, runtimeErrors: errors, externalRequests,
    gpuMeasurement,
    contextRecovery,
    screenshot: args.screenshot,
    expectedMode: expectFallback ? 'WEBGL2_DISABLED_2D_FALLBACK' : 'WEBGL2_SCENE',
    status: functionalPass && errors.length === 0 && externalRequests.length === 0 ? 'PASS' : 'FAIL',
    note: physicalGpu ? 'Disposable staging Registry and credential. Interactive GPU result applies only to the detected local adapter; browser GPU memory is not exposed by this harness.' : 'Disposable staging Registry and credential. Headless Chromium renderer is software rendering and is not physical GPU performance evidence.'
  };
  await writeFile(resolve(args.report), JSON.stringify(report, null, 2) + '\n', 'utf8');
  if (report.status !== 'PASS') throw new Error(`Browser E2E did not pass: ${JSON.stringify({ ...report, result: { ...result, worldLabel: undefined } })}`);
  console.log(JSON.stringify({ status: report.status, browserVersion: report.browserVersion, webgl2: result.webgl2, renderer: result.renderer, errors: errors.length + consoleErrors.length, externalRequests: externalRequests.length, screenshot: report.screenshot }));
} finally {
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
  if (process.platform === 'win32' && chrome.pid) {
    await new Promise((done) => {
      const killer = spawn('taskkill.exe', ['/PID', String(chrome.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
      killer.once('exit', done);
    });
  } else if (!chrome.killed) chrome.kill();
  if (chrome.exitCode === null) await new Promise((done) => chrome.once('exit', done));
  await rm(profile, { recursive: true, force: true });
}
