// Workflow checks for rd6_webmidi_uploader.html in a real browser: Connect through
// the Web MIDI code path (with a stand-in MIDI device), automatic port detection,
// file-free backups and installs, update-mode devices, network failures and layout.
// No real MIDI ports are opened and nothing is sent to hardware.
// Usage (from the repository root):  node outputs/check_rd6_automatic_workflow.cjs
// Needs the `playwright` npm package and a Chromium it can launch (or set
// RD6_CHROME_PATH). Set RD6_SCREENSHOT_DIR to also save desktop/mobile screenshots.
const fs = require('fs'), path = require('path'), http = require('http'), crypto = require('crypto');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const SHA106 = '4446914dffce8152dc7f7c0065de52d266f062a6499a22a8fef36b221982cfc3';
const SCATTER_V1_2 = '8bbc359ebdf78357f7233556bf2843d53b34e8a1a52a4f1c0b8b83a9db9d41dc';
let checks = 0;
function check(name, pass) { if (!pass) throw new Error('FAIL ' + name); console.log('PASS ' + name); checks++; }

// Stand-in for navigator.requestMIDIAccess. Each port pair is an RD-6 in application
// mode that answers the version query (08) with `version`; other ports stay silent.
function fakeMidi(ports) {
  window.__midiRequests = 0;
  window.__midiSent = [];
  const PRE = [0xf0, 0x00, 0x20, 0x32, 0x00, 0x01, 0x0d, 0x00];
  const inputs = new Map(), outputs = new Map();
  ports.forEach(({ name, version }, i) => {
    const input = { id: 'in' + i, name, state: 'connected', onmidimessage: null, open: async () => {} };
    const output = { id: 'out' + i, name, state: 'connected', open: async () => {}, send(bytes) {
      const b = Array.from(bytes); window.__midiSent.push(b);
      if (version && b.length === 10 && b[8] === 0x08) {
        const v = version.split('.').map(Number);
        setTimeout(() => input.onmidimessage?.({ data: Uint8Array.from([...PRE, 0x09, 0x00, ...v, 0xf7]) }), 5);
      }
    } };
    inputs.set(input.id, input); outputs.set(output.id, output);
  });
  const access = { inputs, outputs, onstatechange: null };
  navigator.requestMIDIAccess = async opts => {
    window.__midiRequests++;
    if (!opts || !opts.sysex) throw new Error('SysEx access must be requested');
    return access;
  };
}

(async () => {
  const server = http.createServer((req, res) => { const p = path.resolve(ROOT, '.' + decodeURIComponent(req.url.split('?')[0])); if (!p.startsWith(ROOT + path.sep) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); } res.writeHead(200, { 'content-type': p.endsWith('.html') ? 'text/html' : 'application/octet-stream' }); res.end(fs.readFileSync(p)); });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const url = 'http://127.0.0.1:' + server.address().port + '/outputs/rd6_webmidi_uploader.html';
  const browser = await chromium.launch(process.env.RD6_CHROME_PATH ? { executablePath: process.env.RD6_CHROME_PATH } : {});
  const errors = [];
  const open = async (ports) => {
    const page = await browser.newPage();
    if (ports) await page.addInitScript(fakeMidi, ports);
    page.on('dialog', d => d.accept()); page.on('pageerror', e => errors.push(e.message));
    await page.goto(url);
    return page;
  };
  const simPage = async (setup) => {
    const page = await open(null);
    await page.click('#advanced > summary'); await page.check('#useSim'); await page.check('#simFast');
    await page.evaluate(setup);
    await page.click('#connect'); await idle(page);
    return page;
  };
  const idle = (page, timeout = 30000) => page.waitForFunction(() => !S.busy, null, { timeout });
  const start = async (page, timeout = 90000) => { const b = await page.evaluate(() => S.started); await page.click('#start'); await page.waitForFunction(x => S.started !== x && !S.busy, b, { timeout }); };
  const download = async (page, selector) => { const [d] = await Promise.all([page.waitForEvent('download'), page.click(selector)]); await idle(page); return { name: d.suggestedFilename(), bytes: fs.readFileSync(await d.path()) }; };
  const txt = (page, sel) => page.textContent(sel);
  try {
    // A. Web MIDI path: port found by name, official 1.0.6 identified, file-free backup.
    let page = await open([{ name: 'Other Synth' }, { name: 'RHYTHM DESIGNER RD-6 MIDI 1', version: '1.0.6' }]);
    check('no MIDI access requested before Connect', await page.evaluate(() => window.__midiRequests === 0));
    check('install blocked before connecting', await page.isDisabled('#start') && /Connect your RD-6 first/.test(await txt(page, '#startHint')));
    check('one Scatter build is offered, with no build to choose', await page.$('input[name=build]') === null && await page.$('#useTestBuild') === null);
    await page.click('#connect'); await idle(page);
    check('port found automatically and official 1.0.6 identified', await page.inputValue('#portName') === 'RHYTHM DESIGNER RD-6 MIDI 1' &&
      /1\.0\.6, Behringer's latest/.test(await txt(page, '#devStatus')) && await page.evaluate(() => window.__midiRequests === 1));
    check('only the read-only version query was sent while connecting', await page.evaluate(() => window.__midiSent.length === 1 && window.__midiSent[0].join(',') === '240,0,32,50,0,1,13,0,8,247'));
    check('update mode blocked until a backup is saved', await page.isDisabled('#enterUpdate'));
    const backup = await download(page, '#saveBackup');
    const doc = JSON.parse(backup.bytes);
    check('backup of a 1.0.6 RD-6 is the exact official 1.0.6 file', doc.kind === 'official-download-not-device-dump' && doc.firmware === 'official-1.0.6' &&
      doc.device_reported_version === '1.0.6' && doc.sha256 === SHA106 && sha(Buffer.from(doc.syx_base64, 'base64')) === SHA106 && /^RD6_BACKUP_official-1\.0\.6_/.test(backup.name));
    check('backup needed no file chooser and sent nothing more to the RD-6', await page.evaluate(() => [...document.querySelectorAll('input[type=file]')].every(f => f.files.length === 0) && window.__midiSent.length === 1));
    await page.check('#backupSaved');
    check('update mode allowed once the backup is confirmed', await page.isEnabled('#enterUpdate'));
    await page.check('input[name=action][value=restore]');
    check('restoring 1.0.6 onto 1.0.6 is allowed but flagged as not needed', await page.isEnabled('#start') && /already reports official firmware 1\.0\.6/.test(await txt(page, '#startHint')));
    await page.evaluate(() => { const p = [...S.midi.inputs.values()].find(p => /RD-6/.test(p.name)); p.state = 'disconnected'; S.midi.onstatechange(); });
    check('unplugging the RD-6 is noticed and asks to reconnect', /was disconnected/.test(await txt(page, '#devStatus')) && await page.isDisabled('#start'));
    await page.close();

    // B. No RD-6, or two of them.
    page = await open([{ name: 'Other Synth' }]);
    await page.click('#connect'); await idle(page);
    check('missing RD-6 gives plain advice', /No RD-6 found/.test(await txt(page, '#devStatus')) && /SynthTribe/.test(await txt(page, '#devStatus')));
    await page.close();
    page = await open([{ name: 'RHYTHM DESIGNER RD-6', version: '1.0.6' }, { name: 'RHYTHM DESIGNER RD-6', version: '1.0.6' }]);
    await page.click('#connect'); await idle(page);
    check('two RD-6s connected is refused before anything is sent', /More than one RD-6/.test(await txt(page, '#devStatus')) && await page.evaluate(() => window.__midiSent.length === 0));
    await page.close();

    // B2. A listed RD-6 port that never answers (Chrome lost the connection): Connect offers
    //     Reconnect, which reloads, keeps the user's choice and tries again on its own.
    page = await open([{ name: 'RHYTHM DESIGNER RD-6' }]);
    await page.click('#connect'); await idle(page);
    check('silent RD-6 on Connect: lost Chrome connection explained and Reconnect offered',
      /Chrome may have lost its connection/.test(await txt(page, '#devStatus')) && await page.isVisible('#reconnect1') && await page.isHidden('#reconnect3'));
    await page.check('input[name=action][value=restore]');
    await Promise.all([page.waitForEvent('load'), page.click('#reconnect1')]);
    await page.waitForFunction(() => typeof S !== 'undefined' && S.events.some(e => e.event === 'reconnect_reload') && !S.busy &&
      /Still no answer/.test(document.querySelector('#xferStatus').textContent), null, { timeout: 30000 });
    check('after Reconnect a still-silent RD-6 gets next steps, with the choice kept and no unplug advice',
      await page.evaluate(() => radio('action') === 'restore' && window.__midiRequests === 1) && await page.isVisible('#reconnect1') &&
      !/unplug/.test(await txt(page, '#xferStatus')));
    await page.close();

    // C. Simulated RD-6 on 1.0.6: Scatter v1.2 install end to end, plus the .syx file from Advanced.
    page = await simPage(() => { Sim.version = '1.0.6'; });
    await download(page, '#saveBackup'); await page.check('#backupSaved'); await page.check('#understand');
    await start(page);
    check('Scatter v1.2 installs with 378 ACKs and the exact pinned image stream', await page.evaluate(() => S.image.hash) === SCATTER_V1_2 &&
      await page.evaluate(() => S.events.filter(e => e.event === 'firmware_ack').length === 378 && S.events.some(e => e.event === 'sim_stream_check' && e.byte_exact)) &&
      /^Done! Scatter v1\.2 is installed/.test(await txt(page, '#xferStatus')));
    const t14 = await download(page, '#saveScatter');
    check('Scatter v1.2 .syx saved from Advanced has the pinned checksum', sha(t14.bytes) === SCATTER_V1_2 && t14.name === 'RD6_Scatter_v1.2.syx');
    await page.close();

    // D. A version this page has no copy of.
    page = await simPage(() => { Sim.version = '1.0.7'; });
    check('unknown version explains the backup limit and points to SynthTribe', /doesn't have a copy of that version/.test(await txt(page, '#backupStatus')) && /SynthTribe/.test(await txt(page, '#backupStatus')) &&
      await page.isHidden('#saveBackup') && await page.isVisible('#noBackupRow'));
    await page.check('#understand');
    check('install waits for the no-backup acknowledgement', await page.isDisabled('#start'));
    await page.check('#noBackupOk');
    check('install allowed after the acknowledgement', await page.isEnabled('#start'));
    await page.close();

    // E. Already in update mode, with a bootloader that ignores 08: restore 1.0.6 without re-entering.
    page = await simPage(() => { Sim.mode = 'update'; });
    check('silent-08 bootloader recognised as update mode with read-only 08 40', /in update mode/.test(await txt(page, '#devStatus')) &&
      await page.evaluate(() => S.events.some(e => e.event === 'already_in_update_mode_confirmed') && !S.events.some(e => e.event === 'tx' && / 0[ab] /.test(e.hex))));
    check('nothing to back up in update mode', /nothing to back up/.test(await txt(page, '#backupStatus')));
    await page.check('input[name=action][value=restore]');
    await start(page);
    // 03 30 appears once, as the fifth handshake frame; a repeated mode entry would add a second one.
    check('restore from update mode writes 1.0.6 without repeating mode entry', await page.evaluate(() => Sim.version === '1.0.6' && S.mode === 'restore' &&
      !S.events.some(e => e.event === 'entry_acks') && S.events.filter(e => e.event === 'tx' && e.hex === 'f0 00 20 32 00 01 0d 00 03 30 f7').length === 1) &&
      /^Done!/.test(await txt(page, '#xferStatus')));
    await page.close();

    // F. Network failures stop before anything reaches the RD-6.
    page = await simPage(() => {});
    await page.check('input[name=fw105][value=scatter]'); await page.check('#understand');
    await page.route('**/firmware/RD-6_V1.0.5.syx', route => route.fulfill({ status: 200, body: Buffer.alloc(116186) }));
    await start(page);
    check('corrupted download is refused and nothing is sent', /failed its checksum/.test(await txt(page, '#xferStatus')) && /Nothing was sent to your RD-6/.test(await txt(page, '#xferStatus')) &&
      await page.evaluate(() => !S.events.some(e => e.event === 'tx')) && /Connected/.test(await txt(page, '#devStatus')));
    await page.unroute('**/firmware/RD-6_V1.0.5.syx');
    await page.close();
    page = await simPage(() => { Sim.version = '1.0.6'; });
    await page.route('**/firmware/RD-6_V1.0.6.syx', route => route.fulfill({ status: 503, body: 'Unavailable' }));
    await page.click('#saveBackup'); await idle(page);
    check('HTTP failure during backup is explained and nothing counts as saved', /HTTP 503/.test(await txt(page, '#backupStatus')) && await page.evaluate(() => !S.backup.downloaded) && await page.isDisabled('#backupSaved'));
    await page.unroute('**/firmware/RD-6_V1.0.6.syx');

    // G. Layout.
    await page.click('#advanced > summary');
    await page.setViewportSize({ width: 390, height: 844 });
    check('mobile page fits without horizontal scrolling', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    if (process.env.RD6_SCREENSHOT_DIR) {
      await page.screenshot({ path: path.join(process.env.RD6_SCREENSHOT_DIR, 'rd6-updater-mobile.png'), fullPage: true });
      await page.setViewportSize({ width: 1100, height: 1000 });
      await page.screenshot({ path: path.join(process.env.RD6_SCREENSHOT_DIR, 'rd6-updater-desktop.png'), fullPage: true });
    }
    await page.close();
    check('no browser exceptions', errors.length === 0);
    console.log(checks + '/' + checks + ' checks passed');
  } finally { await browser.close(); await new Promise(r => server.close(r)); }
})().catch(e => { console.error(e); process.exitCode = 1; });
