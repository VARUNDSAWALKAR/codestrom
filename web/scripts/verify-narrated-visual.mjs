/** Inspect an already exported, genuinely narrated normal Lesson composition. */
import assert from 'node:assert/strict';
import {readFile, writeFile, mkdir, access} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {chromium} from 'playwright-core';
import {bundle} from '@remotion/bundler';
import {openBrowser, selectComposition, renderStill} from '@remotion/renderer';
import {parseRenderProps} from '../src/lesson/validate.ts';
import {prepareArrayScene, arrayObjectState} from '../src/lesson/visual/backendArray.ts';

const [propsPath, output] = process.argv.slice(2);
assert.ok(propsPath && output, 'Pass visual.props.json and a new verification folder');
const out=path.resolve(output), folder=path.dirname(path.resolve(propsPath));
await mkdir(out, {recursive:true});
const props=parseRenderProps(JSON.parse(await readFile(propsPath,'utf8')));
assert.ok(props.timeline.audio && props.timeline.voice.engine==='kokoro');
const prepared=prepareArrayScene(props.visualSpec,props,'s2');
const actionFrames=[...new Set(prepared.events.flatMap((e)=>[Math.floor(e.start)-1,Math.floor((e.start+e.end)/2),Math.ceil(e.end)+1]))];
const first=props.timeline.scenes[0], last=props.timeline.scenes.at(-1);
const frames=[...new Set([...actionFrames,Math.floor(first.start_frame+first.duration_frames/2),last.beats[0].start_frame+3])].sort((a,b)=>a-b);
const report={frames,actionFrames,events:prepared.events,clock:'measured Kokoro PCM sample lengths via existing run_timeline',browser:[],fallback:[],errors:[]};
const tool=(name,args)=>{
  const r=spawnSync(name,args,{encoding:'utf8',maxBuffer:8*1024*1024});
  if(r.error||r.status!==0)throw new Error(`${name}: ${r.error?.message??r.stderr}`);
  return r.stdout;
};
let server,browser,renderer;
try{
  const probe=JSON.parse(tool('ffprobe',['-v','error','-show_streams','-show_format','-of','json',path.join(folder,'lesson.mp4')]));
  const video=probe.streams.find(s=>s.codec_type==='video'),audio=probe.streams.find(s=>s.codec_type==='audio');
  assert.equal(video.codec_name,'h264');assert.equal(audio.codec_name,'aac');
  assert.equal(video.width,1280);assert.equal(video.height,720);assert.equal(video.r_frame_rate,'30/1');
  assert.ok(Math.abs(Number(probe.format.duration)-props.timeline.duration_frames/30)<.1);
  tool('ffmpeg',['-v','error','-i',path.join(folder,'lesson.mp4'),'-f','null','-']);
  const expr=frames.map(n=>`eq(n,${n})`).join('+');
  tool('ffmpeg',['-n','-v','error','-i',path.join(folder,'lesson.mp4'),'-vf',`select='${expr}'`,'-fps_mode','passthrough',path.join(out,'export-%02d.png')]);
  tool('ffmpeg',['-n','-v','error','-i',path.join(folder,'lesson.mp4'),'-vn','-ac','1','-ar','24000',path.join(out,'decoded-audio.wav')]);
  report.probe=probe;report.full_decode='pass';
  const srt=await readFile(path.join(folder,'lesson.srt'),'utf8');
  for(const scene of props.timeline.scenes)for(const beat of scene.beats)for(const cap of beat.captions)assert.ok(srt.includes(cap.text));
  const head=await fetch(props.mediaBase+props.timeline.audio.wav,{method:'HEAD'});
  assert.equal(head.status,200);assert.ok(Number(head.headers.get('content-length'))>1000);
  report.media_http={status:head.status,wav_bytes:Number(head.headers.get('content-length'))};
  const web=fileURLToPath(new URL('../',import.meta.url));
  const executable='C:/Program Files/Google/Chrome/Application/chrome.exe';await access(executable);
  server=await createServer({root:web,server:{host:'127.0.0.1',port:5173,strictPort:true}});await server.listen();
  browser=await chromium.launch({executablePath:executable,headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});
  page.on('pageerror',e=>report.errors.push(e.message));
  await page.route('**/*',route=>{
    const url=new URL(route.request().url());
    if(['http:','https:'].includes(url.protocol)&&!['127.0.0.1','localhost'].includes(url.hostname)){
      report.errors.push(`Blocked external request: ${url.href}`);return route.abort();
    }
    return route.continue();
  });
  await page.goto('http://127.0.0.1:5173/tests/browser.html');
  await page.waitForFunction(()=>Boolean(window.lessonTest));
  await page.evaluate(p=>window.lessonTest.mount(p),props);
  await page.locator('[data-scene-id]').waitFor();
  for(const frame of frames){
    await page.evaluate(f=>window.lessonTest.seek(f),frame);
    const timed=props.timeline.scenes.find(s=>frame>=s.start_frame&&frame<s.start_frame+s.duration_frames);
    await page.waitForFunction(id=>document.querySelector('[data-scene-id]')?.getAttribute('data-scene-id')===id,timed.scene_id);
    await page.evaluate(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));});
    const beat=timed.beats.find(b=>frame>=b.start_frame&&frame<b.end_frame);
    const cue=beat?.captions.find(c=>frame>=c.start_frame&&frame<c.end_frame);
    const captions=page.locator('[data-chrome="caption"]');
    const actualCaption=await captions.count()?await captions.textContent():null;
    assert.equal(actualCaption,cue?.text??null);
    let objects=[];
    if(timed.scene_id==='s2'){
      objects=await page.locator('[data-backend-object]').evaluateAll(es=>es.map(e=>({id:e.getAttribute('data-backend-object'),opacity:Number(e.getAttribute('opacity')),fill:e.querySelector('rect')?.getAttribute('fill'),stroke:e.querySelector('rect')?.getAttribute('stroke'),label:e.querySelector('text')?.textContent})));
      assert.deepEqual(objects.map(o=>o.id),prepared.objects.map(o=>o.id));
      for(const object of prepared.objects){
        const state=arrayObjectState(prepared,object,frame),actual=objects.find(o=>o.id===object.id);
        assert.ok(Math.abs(state.opacity-actual.opacity)<1e-8);assert.equal(actual.stroke,state.stroke);
        assert.equal(actual.fill,object.kind==='highlight_region'?'none':state.fill);
      }
      assert.deepEqual(objects.slice(0,5).map(o=>o.label),['1','3','5','7','9']);
    }else assert.equal(await page.locator('[data-backend-visual]').count(),0);
    const file=`browser-${frame}.png`;await page.screenshot({path:path.join(out,file)});
    report.browser.push({frame,file,scene:timed.scene_id,caption:actualCaption,objects});
  }
  const seek=actionFrames[4];await page.evaluate(f=>window.lessonTest.seek(f),seek);
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  await page.screenshot({path:path.join(out,'browser-repeat.png')});
  assert.deepEqual(await readFile(path.join(out,'browser-repeat.png')),await readFile(path.join(out,`browser-${seek}.png`)));
  report.backward_seek='identical screenshot';
  for(const mode of ['missing','invalid','unsupported']){
    const candidate=structuredClone(props);
    if(mode==='missing')delete candidate.visualSpec;
    else if(mode==='invalid')candidate.visualSpec.visual_schema_version='invalid';
    else candidate.visualSpec.scenes.find(s=>s.scene_id==='s2').layout='spatial';
    await page.evaluate(p=>window.lessonTest.mount(p),candidate);
    await page.evaluate(f=>window.lessonTest.seek(f),actionFrames[5]);
    await page.locator('[data-visual-spec]').waitFor();
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
    assert.equal(await page.locator('[data-backend-visual]').count(),0);
    assert.ok((await page.locator('svg text').allTextContents()).some(t=>t.includes('Midpoint 5')));
    await page.screenshot({path:path.join(out,`fallback-${mode}.png`)});
    report.fallback.push({mode,legacy_visible:true});
  }
  // Normal Remotion entry, no demo-specific composition. Verify absent sidecar and
  // an existing legacy Water Cycle sample without exporting a second full video.
  const serveUrl=await bundle({entryPoint:path.join(web,'src/remotion/index.ts'),rootDir:web,publicDir:path.join(web,'public'),outDir:path.join(out,'bundle'),enableCaching:false});
  renderer=await openBrowser('chrome',{browserExecutable:executable});
  const plain={...props};delete plain.visualSpec;
  const composition=await selectComposition({serveUrl,id:'Lesson',inputProps:plain,puppeteerInstance:renderer});
  await renderStill({serveUrl,composition,inputProps:plain,frame:actionFrames[5],output:path.join(out,'legacy-normal-root.png'),puppeteerInstance:renderer});
  const old=parseRenderProps(JSON.parse(await readFile(path.resolve(web,'../data/samples/water_cycle.props.json'),'utf8')));
  const oldTime=old.timeline.scenes.find(s=>s.type==='diagram');
  const oldFrame=oldTime.beats.find(b=>b.step_index!==null).start_frame+12;
  const oldComp=await selectComposition({serveUrl,id:'Lesson',inputProps:old,puppeteerInstance:renderer});
  await renderStill({serveUrl,composition:oldComp,inputProps:old,frame:oldFrame,output:path.join(out,'legacy-water-cycle.png'),puppeteerInstance:renderer});
  report.legacy_export_path='normal Lesson composition rendered without sidecar and existing Water Cycle sample';
  assert.deepEqual(report.errors,[]);report.ok=true;
}catch(error){report.ok=false;report.errors.push(error.stack??String(error));process.exitCode=1;}
finally{
  if(renderer)await renderer.close({silent:true});if(browser)await browser.close();if(server)await server.close();
  await writeFile(path.join(out,'verification.json'),JSON.stringify(report,null,2));
}
console.log(JSON.stringify({out,ok:report.ok,samples:report.browser.length,errors:report.errors},null,2));
