import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {arrayDemoProps, arrayDemoFixture} from '../src/fixtures/arrayFixtureData';
import {parseRenderProps} from '../src/lesson/validate';
import {prepareArrayScene} from '../src/lesson/visual/backendArray';

test('normal RenderProps preserve an optional raw visual-v1 sidecar for scene validation', () => {
  const value={...arrayDemoProps, visualSpec: arrayDemoFixture.spec};
  const props=parseRenderProps(value);
  assert.equal(props.visualSpec, arrayDemoFixture.spec);
  assert.equal(prepareArrayScene(props.visualSpec, props, 's2').objects.length, 6);
  assert.ok(!('visualSpec' in parseRenderProps(arrayDemoProps)));
});

test('invalid optional visual data does not invalidate the trusted lesson/timeline', () => {
  for (const visualSpec of [null, 1, {}, {...arrayDemoFixture.spec, visual_schema_version: 'unknown'}]) {
    const props=parseRenderProps({...arrayDemoProps, visualSpec});
    assert.equal(props.lesson.lesson_id, arrayDemoProps.lesson.lesson_id);
    assert.throws(() => prepareArrayScene(props.visualSpec,props,'s2'));
  }
});

test('production entry uses normal Lesson; no fixture or topic is substituted by default', () => {
  for (const file of ['../src/lesson/Lesson.tsx','../src/remotion/Root.tsx','../src/lesson/visual/VisualSpecRenderer.tsx']) {
    const source=readFileSync(new URL(file,import.meta.url),'utf8');
    assert.ok(!source.includes('array-grid-demo') && !source.includes('arrayDemoFixture'));
  }
});
