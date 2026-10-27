import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright-core';

// Requires port 3000 free. Never stops a pre-existing Studio process.
const web = fileURLToPath(new URL('../', import.meta.url));
const cli = fileURLToPath(new URL('../node_modules/@remotion/cli/remotion-cli.js', import.meta.url));
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH ?? '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
try {
  for (const name of ['python_loop', 'newtons_second_law', 'water_cycle']) {
    const child = spawn(process.execPath, [cli, 'studio', '--port', '3000', '--no-open', '--props', `../data/samples/${name}.props.json`], {cwd: web, stdio: ['ignore', 'pipe', 'pipe']});
    let output = '';
    child.stdout.on('data', (chunk) => {output += chunk;}); child.stderr.on('data', (chunk) => {output += chunk;});
    const page = await browser.newPage();
    try {
      const deadline = performance.now() + 20000;
      while (!output.includes('Server ready') && performance.now() < deadline) {
        if (child.exitCode !== null) throw new Error(output);
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      assert.ok(output.includes('Server ready'), output);
      assert.ok(!output.includes(':3001'), 'Port 3000 must be free');
      await page.route('**/*', (route) => {
        const host = new URL(route.request().url()).hostname;
        return host && !['127.0.0.1', 'localhost'].includes(host) ? route.abort() : route.continue();
      });
      const input = JSON.parse(await readFile(new URL(`../../data/samples/${name}.props.json`, import.meta.url), 'utf8'));
      await page.goto('http://127.0.0.1:3000/Lesson');
      await page.locator('[data-title="content"]').waitFor();
      assert.ok((await page.locator('[data-title="content"]').textContent()).includes(input.lesson.scenes[0].heading));
      console.log(`${name}: Studio opened Lesson with the actual sample props`);
    } finally {
      await page.close();
      if (child.exitCode === null) {child.kill('SIGTERM'); await once(child, 'exit');}
    }
  }
} finally {await browser.close();}
