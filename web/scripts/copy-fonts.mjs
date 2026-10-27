import {copyFile, mkdir, readdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const destination = path.join(root, 'public/fonts');
await mkdir(destination, {recursive: true});
const families = [
  ['noto-sans', 'latin'], ['noto-sans-mono', 'latin'],
  ['noto-sans-devanagari', 'devanagari'], ['noto-sans-kannada', 'kannada'],
  ['noto-sans-tamil', 'tamil'], ['noto-sans-telugu', 'telugu'], ['noto-sans-bengali', 'bengali'],
];
for (const [family, subset] of families) {
  const source = path.join(root, 'node_modules/@fontsource', family);
  const weights = family.endsWith('-mono') ? [400] : [400, 500, 600];
  for (const weight of weights) {
    const file = `${family}-${subset}-${weight}-normal.woff2`;
    await copyFile(path.join(source, 'files', file), path.join(destination, file));
  }
  const license = (await readdir(source)).find((name) => /^(OFL|LICENSE)(\.|$)/i.test(name));
  if (!license) throw new Error(`Missing font license: ${family}`);
  await copyFile(path.join(source, license), path.join(destination, `${family}-LICENSE.txt`));
}
console.log('Copied local Noto fonts and their licenses.');
