// Offline check for rd6_webmidi_uploader.html. Drives the page in headless
// Chromium against its built-in simulated RD-6 only; no MIDI ports are opened.
// Usage (from the repository root):  node outputs/check_rd6_webmidi_uploader.cjs
// Needs the `playwright` npm package and a Chromium it can launch.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname,'..');
const STOCK = process.env.RD6_STOCK_SYX || path.join(ROOT,'firmware/RD-6_V1.0.5.syx');
if(!fs.existsSync(STOCK)) throw new Error('Missing mirrored official stock1.0.5 SysEx file.');

function serve() {
  const server = http.createServer((req, res) => {
    const p = path.resolve(ROOT, '.'+decodeURIComponent(req.url.split('?')[0]));
    if (!p.startsWith(ROOT+path.sep) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': p.endsWith('.html') ? 'text/html' : 'application/octet-stream' });
    fs.createReadStream(p).pipe(res);
  });
  return new Promise(r => server.listen(0, '127.0.0.1', () => r(server)));
}

async function fresh(browser, base) {
  const page = await browser.newPage();
  page.on('dialog', d => d.accept());
  page.on('pageerror', e => { throw e; });
  await page.goto(base + '/rd6_webmidi_uploader.html');
  await page.selectOption('#buildChoice','test12');
  await page.check('#useSim');
  await page.check('#simFast');
  return page;
}
const text = (page, id) => page.textContent(id);
async function loadPinned(page) {
  await page.setInputFiles('#stockFile',[]);
  await page.setInputFiles('#stockFile',STOCK);
  await page.waitForFunction(()=>S.backup?.hash===STOCK_SHA && !S.backupDownloaded && !document.querySelector('#backupSaved').checked);
  if(!await page.isDisabled('#loadPinned'))throw new Error('Preparation must wait for backup');
  const [download]=await Promise.all([page.waitForEvent('download'),page.click('#saveBackup')]);
  const backup=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
  if(Buffer.compare(Buffer.from(backup.syx_base64,'base64'),fs.readFileSync(STOCK))!==0)throw new Error('Backup not byte-exact');
  page.__backup=backup;
  await page.check('#backupSaved');
  await page.click('#loadPinned');
  await page.waitForFunction(() => /Pinned: TEST12/.test(document.querySelector('#fileStatus').textContent));
}
async function waitIdle(page, timeout = 60000) {
  await page.waitForFunction(() => document.querySelector('#abort').disabled, null, { timeout });
}
async function enterUpdate(page) {
  await page.click('#enterUpdate');
  await page.waitForFunction(() => /Re-enumerated|did not|No disconnect|stopping/.test(document.querySelector('#devStatus').textContent), null, { timeout: 20000 });
}
async function send(page) {
  await page.check('#understand');
  await page.click('#send');
  await page.waitForFunction(() => !document.querySelector('#abort').disabled);
  await waitIdle(page);
}
const events = page => page.evaluate(() => S.events.map(e => e.event));

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/outputs`;
  const browser = await chromium.launch(process.env.RD6_CHROME_PATH ? {executablePath:process.env.RD6_CHROME_PATH} : {});
  const results = [];
  const check = (name, pass, detail = '') => { results.push({ name, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`); };

  try {
    // 1. Happy path: identity, entry, full transfer, reboot reply, byte-exact stream.
    let page = await fresh(browser, base);
    await loadPinned(page);
    check('pinned TEST12 accepted', /Pinned: TEST12_GLITCH/.test(await text(page, '#fileStatus')));
    check('all file checks pass', await page.$$eval('#fileChecks li.fail', l => l.length) === 0);
    await page.click('#identity');
    await page.waitForFunction(() => /Application mode|No 1.0.5/.test(document.querySelector('#devStatus').textContent));
    check('identity reports application 1.0.5', /Application mode, version 1.0.5/.test(await text(page, '#devStatus')));
    await enterUpdate(page);
    const ev0 = await page.evaluate(() => S.events);
    check('entry: port absent then present, two ACKs', /Re-enumerated/.test(await text(page, '#devStatus')) &&
      ev0.some(e => e.event === 'entry_acks' && e.count === 2), JSON.stringify(ev0.find(e => e.event === 'entry_acks')));
    check('send disabled until acknowledgement ticked', await page.isDisabled('#send'));
    await send(page);
    const ev = await page.evaluate(() => S.events);
    const acks = ev.filter(e => e.event === 'firmware_ack').length;
    check('378 firmware ACKs then version reply', acks === 378 && ev.some(e => e.event === 'application_version_reply_after_transfer'), `acks=${acks}`);
    check('simulated device saw byte-exact stream', ev.some(e => e.event === 'sim_stream_check' && e.byte_exact === true));
    check('status reports done', /^Done\./.test(await text(page, '#xferStatus')));
    await page.close();

    // Backup round trip and corrupted backup refusal (no device access).
    page = await fresh(browser,base);await loadPinned(page);
    const backup=page.__backup;
    await page.setInputFiles('#restoreFile',{name:'restore.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(backup))});
    await page.waitForFunction(()=>/Restore:/.test(document.querySelector('#fileStatus').textContent));
    check('saved restore file round-trips to exact stock firmware',await page.evaluate(()=>S.image.hash===STOCK_SHA));
    check('restore button is clearly labeled',await text(page,'#send')==='Restore selected firmware');
    await page.check('#backupSaved');await enterUpdate(page);await send(page);
    check('complete simulated stock restore returns to application',/^Done/.test(await text(page,'#xferStatus')) && await page.evaluate(()=>S.mode==='restore' && S.image.hash===STOCK_SHA && S.events.some(e=>e.event==='sim_stream_check' && e.byte_exact)));
    const stock106=process.env.RD6_STOCK_106_SYX || path.join(ROOT,'firmware/RD-6_V1.0.6.syx');
    if(stock106){
      await page.setInputFiles('#restoreFile',stock106);
      await page.waitForFunction(()=>/Pinned: Stock RD-6 1.0.6/.test(document.querySelector('#fileStatus').textContent));
      check('stock1.0.6 hash recognized',await page.evaluate(()=>S.image.version==='1.0.6'));
      await page.check('#backupSaved');await enterUpdate(page);await send(page);
      check('stock1.0.6 restore verifies version1.0.6',await page.evaluate(()=>Sim.version==='1.0.6' && S.events.some(e=>e.event==='application_version_reply_after_transfer' && e.version==='1.0.6')) && /^Done/.test(await text(page,'#xferStatus')));
      await page.click('#identity');await page.waitForFunction(()=>document.querySelector('#abort').disabled);
      check('identity accepts stock1.0.6',/Application mode, version 1.0.6/.test(await text(page,'#devStatus')));
      await loadPinned(page);await enterUpdate(page);await send(page);
      check('TEST12 reinstalls from stock1.0.6 and verifies1.0.5',await page.evaluate(()=>Sim.version==='1.0.5' && S.image.hash===TARGET_SHA && S.events.some(e=>e.event==='application_version_reply_after_transfer' && e.version==='1.0.5')) && /^Done/.test(await text(page,'#xferStatus')));
    }
    const damaged={...backup,sha256:'0'.repeat(64)};
    await page.setInputFiles('#restoreFile',{name:'damaged.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(damaged))});
    await page.waitForFunction(()=>/checksum mismatch/.test(document.querySelector('#backupStatus').textContent));
    check('corrupt backup clears previous authority and blocks send',await page.evaluate(()=>S.image===null && S.backup===null) && await page.isDisabled('#send'));
    await page.close();

    // 2. Device still in application mode: the 08 40 guard refuses before any setup frame.
    page = await fresh(browser, base);
    await loadPinned(page);
    await page.selectOption('#simFault', 'appmode');
    await send(page);
    let ev2 = await events(page);
    let txs = await page.evaluate(() => S.events.filter(e => e.event === 'tx').length);
    check('application-mode reply refused after one query', /ABORTED: unexpected/.test(await text(page, '#xferStatus')) && txs === 1, `tx=${txs}`);
    await page.close();

    // 3â€“5. Faults mid-image: NACK, silence (timeout) and duplicate ACK must abort without retry.
    for (const [fault, re] of [['nack', /unexpected, failed or duplicate/], ['silent', /timeout/], ['dup', /unsolicited|duplicate|unexpected/]]) {
      page = await fresh(browser, base);
      await loadPinned(page);
      await enterUpdate(page);
      await page.selectOption('#simFault', fault);
      await page.fill('#simBlock', '120');
      await send(page);
      const ev3 = await page.evaluate(() => S.events);
      const blocks = ev3.filter(e => e.event === 'tx').map(e => e.hex);
      const sentAt120 = blocks.filter(h => h.startsWith('f0 00 20 32 00 01 0d 00 0b 00 78 00 00 00')).length;
      const st = await text(page, '#xferStatus');
      check(`fault "${fault}" aborts, block 120 sent once`, /ABORTED/.test(st) && re.test(st) && sentAt120 === 1 && !ev3.some(e => e.event === 'all_firmware_frames_acknowledged'), st.split('\n')[0]);
      await page.close();
    }

    // A modified patch is rejected before selecting an image.
    page=await fresh(browser,base);await loadPinned(page);
    const refusal=await page.evaluate(async()=>{
      const patch=await (await fetch(PATCH_RELATIVE)).json();patch.runs[0][1]='AA==';
      try{await applyPatch(S.backup.bytes,patch);return false;}catch(e){return /hash mismatch/.test(e.message);}
    });
    check('tampered patch rejected by pinned target hash',refusal);
    const bad=Buffer.from(fs.readFileSync(STOCK));bad[5000]^=1;
    await page.setInputFiles('#file',{name:'corrupt.syx',mimeType:'application/octet-stream',buffer:bad});
    await page.waitForFunction(()=>/corrupt/.test(document.querySelector('#fileStatus').textContent));
    check('modified firmware not silently pinned',/Not a pinned image|REFUSED/.test(await text(page,'#fileStatus')) && await page.isDisabled('#send'));
    await page.close();
  } finally {
    await browser.close();
    server.close();
  }
  const failed = results.filter(r => !r.pass).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
