// Real browser UI, mirrored official files, simulated MIDI only. No own files.
const fs=require('fs'),path=require('path'),http=require('http'),crypto=require('crypto');
const {chromium}=require('playwright');
const ROOT=path.resolve(__dirname,'..');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const STOCK106='4446914dffce8152dc7f7c0065de52d266f062a6499a22a8fef36b221982cfc3';
const TEST14='2cdce8d2ae225feb21a153d69669c3406410893e9d1882ac0c8fb5391468b97b';
let checks=0;
function check(name,pass){if(!pass)throw new Error(name);console.log('PASS '+name);checks++;}
(async()=>{
 const server=http.createServer((req,res)=>{const p=path.resolve(ROOT,'.'+decodeURIComponent(req.url.split('?')[0]));if(!p.startsWith(ROOT+path.sep)||!fs.existsSync(p)||fs.statSync(p).isDirectory()){res.writeHead(404);return res.end();}res.writeHead(200,{'content-type':p.endsWith('.html')?'text/html':'application/octet-stream'});res.end(fs.readFileSync(p));});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch(process.env.RD6_CHROME_PATH?{executablePath:process.env.RD6_CHROME_PATH}:{});
 try{
  const page=await browser.newPage();
  await page.addInitScript(()=>{navigator.requestMIDIAccess=()=>{throw new Error('Preparation must not request MIDI');};});
  page.on('dialog',d=>d.accept());const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/outputs/rd6_webmidi_uploader.html');
  check('TEST14 fix build is clearly marked hardware test pending',await page.inputValue('#buildChoice')==='test14' && /pending/.test(await page.textContent('#buildNote')));
  const [download]=await Promise.all([page.waitForEvent('download'),page.click('#downloadStock')]);
  const backupBytes=fs.readFileSync(await download.path()),backup=JSON.parse(backupBytes);
  check('automatic restore copy is exact official stock1.0.6',backup.kind==='official-download-not-device-dump' && backup.sha256===STOCK106 && sha(Buffer.from(backup.syx_base64,'base64'))===STOCK106);
  check('both stock packages verified without file inputs or MIDI',await page.evaluate(()=>S.patchSource.hash===STOCK_SHA && S.backup.hash===STOCK106_SHA && !S.midi && [...document.querySelectorAll('input[type=file]')].every(f=>f.files.length===0)));
  check('saved-file confirmation gates preparation',await page.isDisabled('#loadPinned'));
  await page.check('#backupSaved');
  const [scatter]=await Promise.all([page.waitForEvent('download'),page.click('#loadPinned')]);
  check('TEST14 prepares to exact pinned checksum',sha(fs.readFileSync(await scatter.path()))===TEST14);
  check('preparation keeps stock1.0.6 restore copy',await page.evaluate(()=>S.backup.hash===STOCK106_SHA && S.image.hash===TARGET_SHA));
  await page.check('#useSim');await page.check('#understand');await page.click('#enterUpdate');await page.waitForFunction(()=>!S.busy);
  await page.click('#send');await page.waitForFunction(()=>S.busy);await page.waitForFunction(()=>!S.busy,null,{timeout:60000});
  check('TEST14 simulated full transfer uses378 ACKs and exact image stream',await page.evaluate(()=>S.events.filter(e=>e.event==='firmware_ack').length===378 && S.events.some(e=>e.event==='sim_stream_check' && e.byte_exact)) && /^Done/.test(await page.textContent('#xferStatus')));
  await page.selectOption('#buildChoice','test12');
  const [legacy]=await Promise.all([page.waitForEvent('download'),page.click('#loadPinned')]);
  check('original TEST12 also prepares without user file',sha(fs.readFileSync(await legacy.path()))==='9bc1c3a74da476c6694724314d275030a7debb4299c561d06cf56f4e55b540ef');
  await page.locator('details').evaluate(e=>e.open=true);
  await page.setInputFiles('#restoreFile',{name:'RD6_RESTORE.json',mimeType:'application/json',buffer:backupBytes});
  await page.waitForFunction(()=>S.restoreMode && S.image?.hash===STOCK106_SHA);
  await page.check('#backupSaved');await page.click('#enterUpdate');await page.waitForFunction(()=>!S.busy);
  await page.click('#send');await page.waitForFunction(()=>S.busy);await page.waitForFunction(()=>!S.busy,null,{timeout:60000});
  check('downloaded restore JSON reinstalls stock1.0.6 in simulator',await page.evaluate(()=>Sim.version==='1.0.6' && S.mode==='restore') && /^Done/.test(await page.textContent('#xferStatus')));
  await page.route('**/firmware/RD-6_V1.0.5.syx',route=>route.fulfill({status:200,body:Buffer.alloc(116186)}));
  await page.click('#downloadStock');await page.waitForFunction(()=>!S.busy);
  check('corrupted network download clears authority and refuses preparation',await page.evaluate(()=>!S.image && !S.backup && !S.patchSource && !S.backupDownloaded) && await page.isDisabled('#loadPinned') && /mismatch/.test(await page.textContent('#backupStatus')));
  await page.unroute('**/firmware/RD-6_V1.0.5.syx');
  await page.route('**/firmware/RD-6_V1.0.6.syx',route=>route.fulfill({status:503,body:'Unavailable'}));
  await page.click('#downloadStock');await page.waitForFunction(()=>!S.busy);
  check('HTTP failure is actionable and leaves no image',/HTTP 503/.test(await page.textContent('#backupStatus')) && await page.evaluate(()=>!S.image && !S.backup));
  check('no browser exceptions',errors.length===0);
  await page.unroute('**/firmware/RD-6_V1.0.6.syx');
  await page.setViewportSize({width:390,height:844});
  check('mobile page fits without horizontal scrolling',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(ROOT,'../rd6-automatic-workflow-mobile.png'),fullPage:true});
  await page.setViewportSize({width:1100,height:1000});
  await page.screenshot({path:path.join(ROOT,'../rd6-automatic-workflow-desktop.png'),fullPage:true});
  console.log(checks+'/'+checks+' checks passed');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
