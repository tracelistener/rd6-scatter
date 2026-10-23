// Offline checks for rd6_webmidi_uploader.html: the transfer engine and its safety
// rules, driven through the page's own buttons against its built-in simulated RD-6.
// No MIDI ports are opened.
// Usage (from the repository root):  node outputs/check_rd6_webmidi_uploader.cjs
// Needs the `playwright` npm package and a Chromium it can launch
// (or set RD6_CHROME_PATH to a Chrome executable).
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const STOCK105 = path.join(ROOT, 'firmware/RD-6_V1.0.5.syx');
const STOCK106 = path.join(ROOT, 'firmware/RD-6_V1.0.6.syx');
for (const f of [STOCK105, STOCK106]) if (!fs.existsSync(f)) throw new Error('Missing mirrored official firmware file ' + f);
const SHA105 = '29fc1fb89a951a864e294764d2fe8bba4ad1ce890f9c308f09944749321571eb';
const SHA106 = '4446914dffce8152dc7f7c0065de52d266f062a6499a22a8fef36b221982cfc3';
const SCATTER_V1_4_1 = '85a82682af14807ef7c6754ec9a828b0588d5483cdae6b377e087e79a4b9fdf2';
const BLOCK120 = 'f0 00 20 32 00 01 0d 00 0b 00 78 00 00 00';

function serve() {
  const server = http.createServer((req, res) => {
    const p = path.resolve(ROOT, '.' + decodeURIComponent(req.url.split('?')[0]));
    if (!p.startsWith(ROOT + path.sep) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': p.endsWith('.html') ? 'text/html' : 'application/octet-stream' });
    fs.createReadStream(p).pipe(res);
  });
  return new Promise(r => server.listen(0, '127.0.0.1', () => r(server)));
}

// A page using the simulated RD-6, which starts in application mode reporting `version`.
async function fresh(browser, base, version = '1.0.5') {
  const page = await browser.newPage();
  page.on('dialog', d => d.accept());
  page.on('pageerror', e => { throw e; });
  await page.goto(base + '/rd6_webmidi_uploader.html');
  await page.click('#advanced > summary');
  await page.check('#useSim');
  await page.check('#simFast');
  await page.evaluate(v => { Sim.version = v; }, version);
  return page;
}
const text = (page, sel) => page.textContent(sel);
const events = page => page.evaluate(() => S.events);
const idle = (page, timeout = 30000) => page.waitForFunction(() => !S.busy, null, { timeout });
async function connect(page) { await page.click('#connect'); await idle(page); }
async function saveBackup(page) {
  const [download] = await Promise.all([page.waitForEvent('download'), page.click('#saveBackup')]);
  await idle(page);
  return { name: download.suggestedFilename(), doc: JSON.parse(fs.readFileSync(await download.path(), 'utf8')) };
}
// Clicks the main Install/Restore button and waits for that run to finish.
async function start(page, timeout = 90000) {
  const before = await page.evaluate(() => S.started);
  await page.click('#start');
  await page.waitForFunction(b => S.started !== b && !S.busy, before, { timeout });
}
async function chooseRestoreFile(page, file, ready = /Ready to restore/) {
  await page.setInputFiles('#restoreFile', file);
  await page.waitForFunction(re => new RegExp(re).test(document.querySelector('#restoreFileStatus').textContent), ready.source);
}
const jsonFile = (name, doc) => ({ name, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(doc)) });

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/outputs`;
  const browser = await chromium.launch(process.env.RD6_CHROME_PATH ? { executablePath: process.env.RD6_CHROME_PATH } : {});
  const results = [];
  const check = (name, pass, detail = '') => { results.push({ name, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`); };

  try {
    // 1. RD-6 on official 1.0.5: backup, every gate, then a full Scatter v1.4.1 install.
    let page = await fresh(browser, base);
    check('install blocked before connecting', await page.isDisabled('#start') && /Connect your RD-6 first/.test(await text(page, '#startHint')));
    await connect(page);
    check('identity reports 1.0.5 and asks whether it is official or Scatter', /reports firmware version 1\.0\.5/.test(await text(page, '#devStatus')) && await page.isVisible('#ask105'));
    check('install blocked until the 1.0.5 question is answered', await page.isDisabled('#start') && /Answer the question/.test(await text(page, '#startHint')));
    await page.check('input[name=fw105][value=official]');
    check('install blocked until a backup is saved', await page.isDisabled('#start') && /Save your backup first/.test(await text(page, '#startHint')));
    const backup105 = await saveBackup(page);
    const d = backup105.doc;
    check('backup is the exact official 1.0.5 file, labelled as not a device dump',
      d.format === 'rd6-firmware-file-backup-v1' && d.kind === 'official-download-not-device-dump' && d.firmware === 'official-1.0.5' &&
      d.device_reported_version === '1.0.5' && d.sha256 === SHA105 && Buffer.compare(Buffer.from(d.syx_base64, 'base64'), fs.readFileSync(STOCK105)) === 0 &&
      /^RD6_BACKUP_official-1\.0\.5_\d{4}-\d\d-\d\d\.json$/.test(backup105.name), backup105.name);
    check('install blocked until the saved backup is confirmed', await page.isDisabled('#start') && /confirm you saved/.test(await text(page, '#startHint')));
    await page.check('#backupSaved');
    check('install blocked until experimental firmware is acknowledged', await page.isDisabled('#start') && /experimental/.test(await text(page, '#startHint')));
    await page.check('#understand');
    check('install enabled once everything is confirmed', await page.isEnabled('#start'));
    await start(page);
    let ev = await events(page);
    check('one click enters update mode: port absent then present, two ACKs',
      ev.some(e => e.event === 'port_absent') && ev.some(e => e.event === 'port_present_again') && ev.some(e => e.event === 'entry_acks' && e.count === 2));
    check('378 firmware ACKs then version reply 1.0.5', ev.filter(e => e.event === 'firmware_ack').length === 378 &&
      ev.some(e => e.event === 'application_version_reply_after_transfer' && e.version === '1.0.5'));
    check('simulated device saw the exact Scatter v1.4.1 stream', await page.evaluate(() => S.image.hash) === SCATTER_V1_4_1 && ev.some(e => e.event === 'sim_stream_check' && e.byte_exact === true));
    check('status reports done', /^Done! Scatter v1\.4\.1 is installed/.test(await text(page, '#xferStatus')));
    check('afterwards the RD-6 is known to run Scatter, with nothing to back up',
      /running Scatter/.test(await text(page, '#devStatus')) && /nothing to back up/.test(await text(page, '#backupStatus')) && await page.isHidden('#ask105'));

    // 2. Restore the saved backup, then official 1.0.6, then reinstall Scatter.
    await page.check('input[name=action][value=restore]');
    check('restore offers official 1.0.6 without a file or a backup', await text(page, '#start') === 'Restore official firmware 1.0.6' && await page.isEnabled('#start'));
    await page.check('input[name=restoreFrom][value=file]');
    check('restore from file waits for a file', await page.isDisabled('#start'));
    await chooseRestoreFile(page, jsonFile(backup105.name, backup105.doc));
    check('saved backup is recognised', /Backup of official firmware 1\.0\.5/.test(await text(page, '#restoreFileStatus')));
    await start(page);
    ev = await events(page);
    check('backup restore writes exact stock 1.0.5 and verifies 1.0.5',
      await page.evaluate(() => S.image.hash) === SHA105 && ev.some(e => e.event === 'sim_stream_check' && e.byte_exact) &&
      await page.evaluate(() => Sim.version === '1.0.5' && S.mode === 'restore') && /^Done! Official firmware 1\.0\.5 is installed/.test(await text(page, '#xferStatus')));
    check('after restoring, the RD-6 is known to run official 1.0.5 and a backup is offered',
      /official firmware 1\.0\.5/.test(await text(page, '#devStatus')) && await page.isVisible('#saveBackup'));
    await page.check('input[name=restoreFrom][value=official]');
    await start(page);
    ev = await events(page);
    check('official 1.0.6 restore verifies version 1.0.6', await page.evaluate(() => S.image.hash) === SHA106 && await page.evaluate(() => Sim.version === '1.0.6') &&
      ev.some(e => e.event === 'application_version_reply_after_transfer' && e.version === '1.0.6') && /^Done! Official firmware 1\.0\.6/.test(await text(page, '#xferStatus')));
    await connect(page);
    check('identity accepts official 1.0.6', /1\.0\.6, Behringer's latest/.test(await text(page, '#devStatus')));
    await page.check('input[name=action][value=install]');
    check('reinstalling Scatter asks for a new backup of 1.0.6', await page.isDisabled('#start') && /Save your backup first/.test(await text(page, '#startHint')));
    await saveBackup(page);
    await page.check('#backupSaved');
    await start(page);
    check('Scatter v1.4.1 reinstalls from 1.0.6 and verifies 1.0.5', await page.evaluate(() => Sim.version === '1.0.5') &&
      await page.evaluate(() => S.image.hash) === SCATTER_V1_4_1 && /^Done!/.test(await text(page, '#xferStatus')));

    // 3. Older restore files and raw .syx files are accepted; damaged files are refused.
    await page.check('input[name=action][value=restore]');
    await page.check('input[name=restoreFrom][value=file]');
    const legacy = { format: 'rd6-firmware-file-backup-v1', kind: 'official-download-not-device-dump', name: 'RD-6_V1.0.6.syx', sha256: SHA106,
      created: '2026-10-16T00:00:00.000Z', syx_base64: fs.readFileSync(STOCK106).toString('base64') };
    await chooseRestoreFile(page, jsonFile('RD6_RESTORE_4446914dffce.json', legacy));
    check('restore file from the previous updater version is accepted', /Official firmware 1\.0\.6/.test(await text(page, '#restoreFileStatus')) && await page.isEnabled('#start'));
    await chooseRestoreFile(page, STOCK106);
    check('official .syx file is recognised for restore', /Official firmware 1\.0\.6 \(RD-6_V1\.0\.6\.syx\)/.test(await text(page, '#restoreFileStatus')));
    await chooseRestoreFile(page, jsonFile('damaged.json', { ...backup105.doc, sha256: '0'.repeat(64) }), /damaged/);
    check('damaged backup clears the previous file and blocks restore', await page.evaluate(() => S.restoreFile === null) && await page.isDisabled('#start'));
    await chooseRestoreFile(page, jsonFile('notes.json', { hello: 'world' }), /isn't an RD-6 backup/);
    check('unrelated JSON is refused', await page.isDisabled('#start'));
    await page.close();

    // 4. A device that stays in application mode never receives setup or firmware frames.
    page = await fresh(browser, base);
    await connect(page);
    await page.selectOption('#simFault', 'appmode');
    await page.click('#preamble');
    await idle(page);
    const tx1 = await page.evaluate(() => S.events.filter(e => e.event === 'tx').length);
    check('handshake refused after one read-only query in application mode', /Handshake stopped/.test(await text(page, '#xferStatus')) && tx1 === 1, `tx=${tx1}`);
    await page.check('input[name=fw105][value=scatter]');
    await page.check('#understand');
    await start(page);
    const tx2 = (await events(page)).filter(e => e.event === 'tx').map(e => e.hex);
    const st2 = await text(page, '#xferStatus');
    check('install stops when the RD-6 ignores update-mode entry; no setup or firmware frames sent',
      /didn't switch to update mode/.test(st2) && /No firmware was written/.test(st2) && !tx2.some(h => /^f0 00 20 32 00 01 0d 00 (04|06|0a|0b)/.test(h)), `tx=${tx2.length}`);
    await page.close();

    // 5. Faults mid-image: NACK, silence (timeout) and a duplicate ACK abort without retry.
    for (const [fault, re] of [['nack', /unexpected answer/], ['silent', /stopped answering/], ['dup', /unexpected answer/]]) {
      page = await fresh(browser, base);
      await connect(page);
      await page.check('input[name=fw105][value=scatter]');
      await page.check('#understand');
      await page.selectOption('#simFault', fault);
      await page.fill('#simBlock', '120');
      await start(page);
      const ev3 = await events(page);
      const sentAt120 = ev3.filter(e => e.event === 'tx' && e.hex.startsWith(BLOCK120)).length;
      const st = await text(page, '#xferStatus');
      check(`fault "${fault}" aborts, block 120 sent once, partial-write advice shown`,
        /^Install stopped/.test(st) && re.test(st) && /only partly written/.test(st) && sentAt120 === 1 &&
        !ev3.some(e => e.event === 'all_firmware_frames_acknowledged') && await page.isVisible('#saveLog'), st.split('\n')[0]);
      check(`fault "${fault}" leaves the RD-6 marked for a fresh check`, await page.isDisabled('#start') && /Click Connect/.test(await text(page, '#devStatus')));
      await page.close();
    }

    // 6. Chrome can miss the short re-enumeration: update mode is confirmed read-only first.
    page = await fresh(browser, base);
    await connect(page);
    await page.check('input[name=fw105][value=scatter]');
    await page.check('#understand');
    await page.evaluate(() => { Sim.disconnect = function (ms, then) { setTimeout(() => { then(); this.update(); }, ms); }; });
    await start(page);
    ev = await events(page);
    check('missed re-enumeration: 08 40 confirms update mode, then the transfer completes',
      !ev.some(e => e.event === 'port_absent') && ev.some(e => e.event === 'already_in_update_mode_confirmed') &&
      ev.filter(e => e.event === 'firmware_ack').length === 378 && /^Done!/.test(await text(page, '#xferStatus')));
    await page.close();

    // 7. Stop during the transfer.
    page = await fresh(browser, base);
    await connect(page);
    await page.check('input[name=fw105][value=scatter]');
    await page.check('#understand');
    await page.click('#start');
    await page.waitForFunction(() => S.events.filter(e => e.event === 'firmware_ack').length >= 40, null, { timeout: 60000 });
    await page.click('#abort');
    const armed = await text(page, '#abort');
    const ackedWhileArmed = (await events(page)).filter(e => e.event === 'firmware_ack').length;
    await page.waitForFunction(n => S.events.filter(e => e.event === 'firmware_ack').length > n + 5, ackedWhileArmed, { timeout: 30000 });
    check('first Stop click only asks for a second click; the transfer keeps going', armed === 'Click again to stop' && await page.evaluate(() => !S.abort && S.transferring));
    await page.click('#abort');
    await idle(page, 60000);
    const acks = (await events(page)).filter(e => e.event === 'firmware_ack').length;
    const st7 = await text(page, '#xferStatus');
    check('second Stop click ends the transfer after the current block with clear advice', /You pressed Stop/.test(st7) && /only partly written/.test(st7) && acks < 378, `acks=${acks}`);
    await page.close();

    // 8. A modified patch is rejected; a modified firmware file needs the explicit override.
    page = await fresh(browser, base);
    const refusal = await page.evaluate(async () => {
      const patch = await (await fetch(SCATTER.patch)).json(); patch.runs[0][1] = 'AA==';
      const stock = new Uint8Array(await (await fetch('../firmware/RD-6_V1.0.5.syx')).arrayBuffer());
      try { await applyPatch(stock, patch, SCATTER.sha); return false; } catch (e) { return /hash mismatch/.test(e.message); }
    });
    check('tampered patch rejected by pinned target hash', refusal);
    await connect(page);
    await page.check('input[name=action][value=restore]');
    await page.check('input[name=restoreFrom][value=file]');
    const bad = Buffer.from(fs.readFileSync(STOCK105)); bad[5000] ^= 1;
    await chooseRestoreFile(page, { name: 'modified.syx', mimeType: 'application/octet-stream', buffer: bad }, /doesn't recognise/);
    const hash = await page.evaluate(() => S.restoreFile.analysis.hash);
    check('modified firmware is not silently accepted', await page.isDisabled('#start') && await page.isVisible('#unpinnedBox'));
    await page.check('#allowUnpinned');
    await page.fill('#unpinnedConfirm', 'deadbeef');
    check('wrong checksum confirmation keeps it blocked', await page.isDisabled('#start'));
    await page.fill('#unpinnedConfirm', hash.slice(0, 8));
    check('typed checksum confirmation unlocks it', await page.isEnabled('#start'));
    await start(page);
    check('confirmed unrecognised file is written and then treated as unrecognised firmware',
      /^Done!/.test(await text(page, '#xferStatus')) && /doesn't recognise/.test(await text(page, '#backupStatus')) && await page.isVisible('#noBackupRow'));
    await page.close();

    // 9. Chrome loses its connection when the RD-6 switches to update mode (seen on hardware):
    //    nothing is written, and Reconnect reloads the page, keeps the choices and the log, and connects again.
    page = await fresh(browser, base);
    await connect(page);
    await page.check('input[name=action][value=restore]');
    await page.evaluate(() => { Sim.disconnect = function () { this.mode = 'lost'; this.update(); }; });
    await start(page);
    const st9 = await text(page, '#xferStatus');
    const tx9 = (await events(page)).filter(e => e.event === 'tx').map(e => e.hex);
    check('connection lost after the mode switch: explained, nothing written, Reconnect offered',
      /Chrome lost its connection to your RD-6 when the RD-6 switched to update mode/.test(st9) && /No firmware was written/.test(st9) &&
      await page.isVisible('#reconnect3') && await page.isHidden('#reconnect1') && !tx9.some(h => /^f0 00 20 32 00 01 0d 00 (04|06|0a|0b)/.test(h)));
    const before9 = await page.evaluate(() => S.events.length);
    await Promise.all([page.waitForEvent('load'), page.click('#reconnect3')]);
    await page.waitForFunction(() => typeof S !== 'undefined' && S.events.some(e => e.event === 'reconnect_reload') && !S.busy &&
      /Reconnected/.test(document.querySelector('#xferStatus').textContent), null, { timeout: 30000 });
    check('Reconnect reloads, keeps the choices and the failed run log, and connects again',
      await page.evaluate(n => $('useSim').checked && radio('action') === 'restore' && radio('restoreFrom') === 'official' &&
        S.events.length > n && S.events.some(e => e.event === 'aborted') && S.device.mode === 'application', before9) && await page.isVisible('#saveLog'));
    await page.close();

    // 10. Chrome loses the connection when the RD-6 restarts after a complete write.
    page = await fresh(browser, base);
    await connect(page);
    await page.check('input[name=fw105][value=official]');
    await page.check('input[name=action][value=restore]');
    await page.check('input[name=restoreFrom][value=file]');
    await chooseRestoreFile(page, STOCK105);
    await page.evaluate(() => {
      const original = Sim.disconnect; let calls = 0;
      Sim.disconnect = function (ms, then) { if (++calls === 1) return original.call(this, ms, then); this.mode = 'lost'; this.update(); };
    });
    await start(page);
    const st10 = await text(page, '#xferStatus');
    check('connection lost after a complete write: says all firmware was written and offers Reconnect',
      /All of the firmware was written/.test(st10) && /Click Reconnect/.test(st10) && await page.isVisible('#reconnect3') &&
      (await events(page)).filter(e => e.event === 'firmware_ack').length === 378);
    await chooseRestoreFile(page, STOCK106);   // a later file choice must not change what is being checked
    await Promise.all([page.waitForEvent('load'), page.click('#reconnect3')]);
    await page.waitForFunction(() => typeof S !== 'undefined' && S.events.some(e => e.event === 'reconnect_reload') && !S.busy &&
      /Reconnected/.test(document.querySelector('#xferStatus').textContent), null, { timeout: 30000 });
    check('after Reconnect the expected version confirms the new firmware is running',
      /so the new firmware is running/.test(await text(page, '#xferStatus')) && /official firmware 1\.0\.5/.test(await text(page, '#devStatus')));
    await page.close();

    // 11. Patterns and settings: read-only backup, exact restore, damaged files and faults.
    page = await fresh(browser, base);
    await page.evaluate(() => { Sim.settings = [3, 16, 1, 2, 3, 77]; Sim.patterns[16][0] = 1; });
    check('patterns backup waits for a connected RD-6', await page.isDisabled('#savePatterns'));
    await connect(page);
    const original = await page.evaluate(() => ({ patterns: Sim.patterns.map(p => Array.from(p)), settings: [...Sim.settings] }));
    const [pdl] = await Promise.all([page.waitForEvent('download'), page.click('#savePatterns')]);
    await idle(page);
    const pname = pdl.suggestedFilename(), pdoc = JSON.parse(fs.readFileSync(await pdl.path(), 'utf8'));
    const reads = (await events(page)).filter(e => e.event === 'tx').map(e => e.hex.split(' ')[8]);
    check('patterns backup reads all 32 patterns and the settings using read-only requests',
      pdoc.format === 'rd6-patterns-settings-backup-v1' && pdoc.kind === 'read-from-device' && pdoc.patterns.length === 32 &&
      pdoc.patterns.every((p, i) => p.group === (i >> 4) + 1 && p.pattern === (i & 15) + 1 && p.data === Buffer.from(original.patterns[i]).toString('hex')) &&
      JSON.stringify(pdoc.settings) === JSON.stringify(original.settings) && /^RD6_PATTERNS_\d{4}-\d\d-\d\d\.json$/.test(pname) &&
      reads.length === 33 && reads.every(c => c === '77' || c === '75'), `${reads.length} requests`);
    check('patterns backup checksum matches its contents', crypto.createHash('sha256')
      .update(Buffer.concat([...pdoc.patterns.map(p => Buffer.from(p.data, 'hex')), Buffer.from(pdoc.settings)])).digest('hex') === pdoc.sha256);
    await page.evaluate(() => { Sim.patterns = Sim.patterns.map(() => new Uint8Array(22)); Sim.settings = [0, 0, 0, 0, 0, 0]; });
    await page.check('input[name=action][value=restore]');
    await page.check('input[name=restoreFrom][value=patterns]');
    check('patterns restore waits for a file', await page.isDisabled('#start') && await text(page, '#start') === 'Restore patterns and settings');
    const choosePatterns = async (doc, ready = /Ready to restore/) => {
      await page.setInputFiles('#patternsFile', jsonFile(pname, doc));
      await page.waitForFunction(re => new RegExp(re).test(document.querySelector('#patternsFileStatus').textContent), ready.source);
    };
    await choosePatterns(pdoc);
    await start(page);
    const writes = (await events(page)).filter(e => e.event === 'tx').map(e => e.hex.split(' ')[8]);
    check('patterns restore puts every pattern and setting back exactly and never touches firmware',
      await page.evaluate(o => JSON.stringify({ patterns: Sim.patterns.map(p => Array.from(p)), settings: Sim.settings }) === JSON.stringify(o), original) &&
      /^Done! All 32 patterns and the settings are restored/.test(await text(page, '#xferStatus')) &&
      writes.filter(c => c === '78').length === 32 && !writes.some(c => ['03', '04', '06', '0a', '0b'].includes(c)));
    await choosePatterns({ ...pdoc, patterns: pdoc.patterns.map((p, i) => i === 7 ? { ...p, data: 'ff' + p.data.slice(2) } : p) }, /damaged/);
    check('an edited or damaged patterns file is refused', await page.isDisabled('#start') && await page.evaluate(() => S.patternFile === null));
    await choosePatterns(backup105.doc, /isn't an RD-6 patterns/);
    check('a firmware backup is not accepted as a patterns backup', await page.isDisabled('#start'));
    await choosePatterns(pdoc);
    await page.evaluate(() => { Sim.patterns = Sim.patterns.map(() => new Uint8Array(22)); });
    await page.selectOption('#simFault', 'nack');
    await page.fill('#simBlock', '5');
    await start(page);
    const st11 = await text(page, '#xferStatus');
    check('a NACK part-way stops the restore at once and says how far it got',
      /Restore stopped/.test(st11) && /5 of 32 patterns were restored/.test(st11) &&
      await page.evaluate(o => Sim.patterns.every((p, i) => i < 5 ? JSON.stringify(Array.from(p)) === JSON.stringify(o.patterns[i]) : p.every(b => b === 0)), original), st11.split('\n')[1]);
    await connect(page);
    await page.selectOption('#simFault', 'silent');
    await page.fill('#simBlock', '3');
    let downloads = 0; page.on('download', () => downloads++);
    await page.click('#savePatterns'); await idle(page);
    check('no answer while reading: nothing is saved and Reconnect is offered',
      downloads === 0 && /nothing was saved/.test(await text(page, '#patternsStatus')) && await page.isVisible('#reconnect1'));
    await page.close();

    // 12. In update mode there is no firmware running to read or write patterns.
    page = await fresh(browser, base);
    await page.evaluate(() => { Sim.mode = 'update'; });
    await connect(page);
    await page.check('input[name=action][value=restore]');
    await page.check('input[name=restoreFrom][value=patterns]');
    check('update mode blocks patterns backup and restore with a clear reason',
      await page.isDisabled('#savePatterns') && /update mode/.test(await text(page, '#patternsStatus')) && /update mode/.test(await text(page, '#startHint')));
    await page.close();
  } finally {
    await browser.close();
    server.close();
  }
  const failed = results.filter(r => !r.pass).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
