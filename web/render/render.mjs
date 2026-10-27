import {readFile, mkdir, access, rm} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {availableParallelism, totalmem, tmpdir} from 'node:os';
import {mkdtemp} from 'node:fs/promises';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import {parseRenderProps} from '../src/lesson/validate.ts';

const emit = (value) => process.stdout.write(`${JSON.stringify(value)}\n`);
const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const started = performance.now();
let temporary;
try {
  const options = {};
  for (let i = 2; i < process.argv.length; i += 2) {
    const key = process.argv[i];
    const value = process.argv[i + 1];
    if (!['--props', '--out', '--concurrency'].includes(key) || !value || options[key]) throw new Error('Usage: node web/render/render.mjs --props <json> --out <mp4> [--concurrency N]');
    options[key] = value;
  }
  if (!options['--props'] || !options['--out']) throw new Error('--props and --out are required');
  const inputProps = parseRenderProps(JSON.parse(await readFile(path.resolve(options['--props']), 'utf8')));
  if (inputProps.timeline.fps !== 30) throw new Error('MP4 export requires the documented 30 fps timeline');
  const requested = options['--concurrency'] ?? process.env.RENDER_CONCURRENCY;
  const concurrency = requested === undefined ? Math.max(1, Math.min(totalmem() <= 9 * 1024 ** 3 ? 2 : 4, Math.floor(availableParallelism() / 2))) : Number(requested);
  if (!Number.isSafeInteger(concurrency) || concurrency < 1) throw new Error('concurrency must be a positive integer');
  const out = path.resolve(options['--out']);
  if (path.extname(out).toLowerCase() !== '.mp4') throw new Error('--out must end in .mp4');
  if (out === path.resolve(options['--props'])) throw new Error('Output cannot overwrite input props');
  await mkdir(path.dirname(out), {recursive: true});
  let serveUrl = path.join(web, 'build');
  try { await access(path.join(serveUrl, 'index.html')); }
  catch {
    temporary = await mkdtemp(path.join(tmpdir(), 'blu-render-'));
    serveUrl = await bundle({entryPoint: path.join(web, 'src/remotion/index.ts'),
      publicDir: path.join(web, 'public'), outDir: temporary, onProgress: () => {}});
  }
  // On prepared machines Chromium is local. Never download a browser at runtime.
  const candidates = [process.env.REMOTION_BROWSER_EXECUTABLE, process.env.CHROMIUM_PATH,
    path.join(web, 'node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell'),
    path.join(web, 'node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell.exe'),
    path.join(web, 'node_modules/.remotion/chrome-headless-shell/mac-arm64/chrome-headless-shell'),
    '/usr/bin/chromium', '/usr/bin/google-chrome',
    process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Google/Chrome/Application/chrome.exe'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].filter(Boolean);
  let browserExecutable;
  for (const candidate of candidates) { try { await access(candidate); browserExecutable = candidate; break; } catch {} }
  if (!browserExecutable) throw new Error('No local Chromium found. Set REMOTION_BROWSER_EXECUTABLE to your preinstalled browser.');
  const composition = await selectComposition({serveUrl, id: 'Lesson', inputProps, browserExecutable});
  let lastProgress = 0;
  emit({progress: 0});
  await renderMedia({serveUrl, composition, inputProps, outputLocation: out, browserExecutable,
    codec: 'h264', pixelFormat: 'yuv420p', colorSpace: 'bt709', crf: 23, concurrency, timeoutInMilliseconds: 60000,
    ...(inputProps.timeline.audio ? {audioCodec: 'aac', audioBitrate: '128k'} : {muted: true}),
    onProgress: ({progress}) => {
      const rounded = Math.floor(progress * 100) / 100;
      if (rounded - lastProgress >= 0.02 || rounded === 1 && lastProgress !== 1) {
        lastProgress = rounded; emit({progress: rounded});
      }
    }});
  emit({done: true, out, ms: Math.round(performance.now() - started)});
} catch (error) {
  emit({error: error instanceof Error ? error.message : String(error)});
  process.exitCode = 1;
} finally {
  if (temporary) await rm(temporary, {recursive: true, force: true});
}
