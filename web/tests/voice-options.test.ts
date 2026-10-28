import assert from 'node:assert/strict';
import {test} from 'node:test';
import {getConfig, voicesFor, type AppConfig} from '../src/app/api';
import {config} from './api-fixtures';

const approved: AppConfig = {...config, voice_options: {
  en: [{voice:'female',speaker:'hf_alpha',engine:'kokoro'},{voice:'male',speaker:'hm_omega',engine:'kokoro'}],
  hi: [{voice:'female',speaker:'hf_alpha',engine:'kokoro'},{voice:'male',speaker:'hm_omega',engine:'kokoro'}],
  kn: [{voice:'male',speaker:'Suresh',engine:'parler',seed:21,seed_policy:'seed-once-ordered-utterances-v1'}],
}};
test('Kannada exposes approved Suresh only; English/Hindi retain both voices',()=>{
  for (const language of ['en','hi'] as const) assert.deepEqual(voicesFor(approved,language).map(v=>v.voice),['female','male']);
  assert.deepEqual(voicesFor(approved,'kn').map(v=>[v.voice,v.speaker,v.seed]),[['male','Suresh',21]]);
  assert.deepEqual(voicesFor(config,'kn'),[]); // no silent Anu/Suresh approval for older config
});
test('API validates per-language voice options without discarding preset metadata',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>Response.json(approved);
    assert.deepEqual(await getConfig(),approved);
    for(const options of [[{voice:'female',speaker:'Anu',engine:'cloud'}],[{voice:'male',speaker:'Suresh',engine:'parler',seed:-1}]]) {
      globalThis.fetch=async()=>Response.json({...approved,voice_options:{kn:options}});
      await assert.rejects(getConfig());
    }
  }finally{globalThis.fetch=original;}
});
