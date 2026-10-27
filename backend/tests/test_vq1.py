"""Isolated VQ1 contract tests; no real models, TTS, translation or renderer."""
import copy
import json
from pathlib import Path

import httpx
import pytest
from backend.app.config import Settings
from backend.app.planner.schema import Lesson
from backend.app.planner.ollama_client import PlanRequest, lesson_key
from backend.app.visuals.schema import VisualSpec, SceneVisual, Provenance
from backend.app.visuals.validate import validate_visuals, check_scene, fingerprint, source_fingerprint, safe_text
from backend.app.visuals.planner import plan_visuals, Intent, compile_intent, Ollama, Options
from backend.app.visuals.cache import VisualCache
from backend.app.visuals.bind import bind_timeline, resolve_labels
from backend.app.visuals.geometry import linear_points
from backend.app.timeline.schema import Timeline

FIXTURES = Path(__file__).parent/'fixtures/visuals'


def fixture(name='water_cycle'):
    value=json.loads((FIXTURES/f'{name}.json').read_text(encoding='utf-8'))
    return Lesson.model_validate(value['source']), value['spec']


def intent():
    return dict(layout='spatial', mechanism='Energy heats surface water', representation='schematic',
        limitation='Qualitative only, no physical simulation', entities=[
            dict(id='sun',shape='circle',role='Solar heat',slot='top_left',label_ref=None),
            dict(id='water',shape='ellipse',role='Reservoir',slot='bottom',label_ref='step0.text')],
        links=[dict(source='sun',target='water',kind='points_toward')], actions=[
            dict(kind='reveal',target='sun',beat_id='s2.step0'),
            dict(kind='draw',target='link0',beat_id='s2.step1')])


def envelope(value):
    return dict(message=dict(content=json.dumps(value)),done=True,done_reason='stop',eval_count=12)


def run(tmp_path, fake, **kw):
    source,_=fixture()
    return plan_visuals(source,Settings(cache_dir=tmp_path,device='cpu'),inference=fake,
                        model_identity='local-model-digest',scene_ids=['s2'],**kw)


@pytest.mark.parametrize('path',sorted(FIXTURES.glob('*.json')))
def test_saved_fixtures(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or 'spec' not in data:return
    source=Lesson.model_validate(data['source'])
    assert validate_visuals(data['spec'],source).spec is not None


def test_schema_export_matches():
    path=Path(__file__).parents[1]/'app/visuals/visual.schema.json'
    assert json.loads(path.read_text()) == VisualSpec.model_json_schema()


@pytest.mark.parametrize('field,value',[
    ('layout','unknown'),('extra','unsupported'),('scene_id','s99'),
    ('actions',[dict(id='bad',kind='explode',target='sun',beat_id='s2.step0')]),
])
def test_unknown_contract(field,value):
    source,spec=fixture();spec['scenes'][1][field]=value
    assert validate_visuals(spec,source).spec is None


@pytest.mark.parametrize('text',[
    '<svg/>','<script>alert(1)</script>','https://bad.test/a','file:///secret',
    r'C:\secret\x','../secret','/etc/passwd','data:image/png;base64,AAA',
    'javascript:alert(1)','eval("bad")','a\x00b',r'\\host\share',
])
def test_unsafe_text(text):
    with pytest.raises(ValueError):safe_text(text)
    source,spec=fixture();spec['scenes'][1]['objects'][0]['role']=text
    assert validate_visuals(spec,source).spec is None


@pytest.mark.parametrize('number',[float('nan'),float('inf'),float('-inf'),-1,2])
def test_finite_geometry(number):
    source,spec=fixture();spec['scenes'][1]['objects'][0]['position']['x']=number
    assert validate_visuals(spec,source).spec is None


@pytest.mark.parametrize('mutation,code',[
    ('duplicate','duplicate_id'),('beat','beat_reference'),('target','action_target'),
    ('relation','relationship_reference'),('bounds','geometry_bounds'),('style','schema_invalid'),
    ('asset','asset_unapproved'),('source','source_mismatch'),('scene_order','scene_reference'),
    ('path','schema_invalid'),('interval','schema_invalid'),('conflict','action_conflict'),
    ('discontinuity','state_discontinuity'),('group_cycle','containment_cycle'),
    ('nesting','nesting_limit'),('group_target','action_group'),('label_ref','text_reference'),
    ('draw_wrong','action_compatibility'),('move_bounds','geometry_bounds'),
    ('too_many','schema_invalid'),('unknown_object','schema_invalid'),
])
def test_invalid_visuals(mutation,code):
    source,spec=fixture();s=spec['scenes'][1];obj=s['objects'][0]
    if mutation=='duplicate':s['objects'].append(copy.deepcopy(obj))
    elif mutation=='beat':s['actions'][0]['beat_id']='s3.step0'
    elif mutation=='target':s['actions'][0]['target']='missing'
    elif mutation=='relation':s['relationships'][0]['target']='missing'
    elif mutation=='bounds':obj['position']['y']=0.0
    elif mutation=='style':obj['style']='red'
    elif mutation=='asset':s['objects'].append(dict(id='asset',role='Icon',kind='asset',asset_id='sun_icon',position=dict(x=.5,y=.5),width=.2,height=.2))
    elif mutation=='source':spec['source_fingerprint']='0'*64
    elif mutation=='scene_order':spec['scenes'].reverse()
    elif mutation=='path':next(o for o in s['objects'] if o['kind']=='path')['segments'][0]['svg']='M 0 0'
    elif mutation=='interval':s['actions'][0].update(start=.8,end=.1)
    elif mutation in {'conflict','discontinuity'}:
        s['actions']=[dict(id='a',kind='reveal',target='sun',beat_id='s2.step0'),
            dict(id='b',kind='reveal',target='sun',beat_id='s2.step0' if mutation=='conflict' else 's2.step1')]
    elif mutation=='group_cycle':s['objects'] += [dict(id='g1',role='Group',kind='group',children=['g2']),dict(id='g2',role='Group',kind='group',children=['g1'])]
    elif mutation=='nesting':
        s['objects'] += [dict(id='g'+str(i),role='Group',kind='group',children=['g'+str(i+1)]) for i in range(5)]
        s['objects'].append(dict(id='g5',role='Group',kind='group',children=['sun']))
    elif mutation=='group_target':
        s['objects'].append(dict(id='g',role='Group',kind='group',children=['sun']))
        s['actions'][0]['target']='g'
    elif mutation=='label_ref':s['objects'][-1]['label']['step_index']=5
    elif mutation=='draw_wrong':s['actions'][0]=dict(id='a',kind='draw',target='sun',beat_id='s2.step0')
    elif mutation=='move_bounds':s['actions'][0]=dict(id='a',kind='move',target='sun',beat_id='s2.step0',from_position=obj['position'],to_position=dict(x=1.0,y=1.0))
    elif mutation=='too_many':s['objects']*=7
    else:obj['kind']='svg'
    checked=validate_visuals(spec,source)
    assert checked.spec is None
    assert code in [d.code for d in checked.diagnostics]


@pytest.mark.parametrize('layout',['flow_cycle','spatial','array_grid','graph_network','coordinate_plane','comparison','code_walkthrough'])
def test_layouts(layout):
    source,spec=fixture();spec['scenes'][1]['layout']=layout
    assert validate_visuals(spec,source).spec is not None


def test_remaining_primitives_and_actions():
    source,spec=fixture();s=spec['scenes'][1]
    s['objects'] += [dict(id='poly',role='Simple triangle',kind='polygon',points=[dict(x=.1,y=.1),dict(x=.2,y=.1),dict(x=.15,y=.2)]),
        dict(id='box',role='Comparison quantity',kind='rectangle',position=dict(x=.5,y=.5),width=.1,height=.1),
        dict(id='group',role='Grouping',kind='group',children=['poly','box']),
        dict(id='hl',role='Selection',kind='highlight_region',position=dict(x=.5,y=.5),width=.2,height=.2),
        dict(id='axis',role='Axis',kind='line',start=dict(x=.1,y=.5),end=dict(x=.9,y=.5))]
    s['actions'] += [dict(id='move',kind='move',target='box',beat_id='s2.step0',from_position=dict(x=.5,y=.5),to_position=dict(x=.6,y=.5)),
        dict(id='transform',kind='transform',target='poly',beat_id='s2.step0')]
    assert validate_visuals(spec,source).spec is not None


def test_fallback_cannot_carry_visuals():
    source,spec=fixture();spec['scenes'][1]['fallback']=dict(code='legacy_scene',reason='Legacy')
    assert validate_visuals(spec,source).spec is None


def test_valid_mock_and_cache(tmp_path):
    calls=[]
    def fake(messages,options):calls.append(messages);return envelope(intent())
    first=run(tmp_path,fake);second=run(tmp_path,fake)
    assert first.stats.calls==1 and second.stats.calls==0 and second.stats.cache_hit
    assert len(calls)==1 and first.spec==second.spec
    assert first.spec.scenes[1].objects[0].role=='Solar heat'
    assert any(d.code=='accuracy_unverified' for d in first.diagnostics)


@pytest.mark.parametrize('failure',['json','schema','reference','timeout','model','length'])
def test_repair_and_failure(tmp_path,failure):
    count=0
    def fake(messages,options):
        nonlocal count
        count+=1
        if failure=='timeout':raise httpx.ReadTimeout('timeout')
        if failure=='model':raise RuntimeError('missing local model')
        if failure=='json':return dict(done=True,message=dict(content='not JSON'))
        value=intent()
        if failure=='schema':value['unknown']=1
        if failure=='reference':value['actions'][0]['beat_id']='s99.intro'
        result=envelope(value)
        if failure=='length':result['done_reason']='length'
        return result
    result=run(tmp_path,fake)
    assert all(s.fallback for s in result.spec.scenes)
    assert count==(1 if failure in {'timeout','model'} else 2)
    assert result.stats.repairs==(0 if count==1 else 1)


def test_single_targeted_repair(tmp_path):
    calls=[]
    def fake(messages,options):
        calls.append(copy.deepcopy(messages))
        return envelope(intent()) if len(calls)==2 else dict(done=True,message=dict(content='{}'))
    result=run(tmp_path,fake)
    assert result.spec.scenes[1].fallback is None
    assert len(calls)==2 and 'Repair only' in calls[-1][-1]['content']


@pytest.mark.parametrize('representation',['requires_solver','unsupported'])
def test_accuracy_fallback(tmp_path,representation):
    value=intent();value['representation']=representation
    result=run(tmp_path,lambda *_:envelope(value))
    assert result.spec.scenes[1].fallback.code=='unsupported_mechanism'
    assert result.spec.scenes[1].objects==[]


def test_source_model_config_versions_isolate(tmp_path):
    source,_=fixture();settings=Settings(cache_dir=tmp_path,device='cpu');calls=[]
    def fake(*_):calls.append(1);return envelope(intent())
    kw=dict(inference=fake,model_identity='digest-a',scene_ids=['s2'])
    a=plan_visuals(source,settings,**kw)
    changed=source.model_copy(deep=True);changed.scenes[1].narration+=' Changed meaning.'
    b=plan_visuals(changed,settings,**kw)
    c=plan_visuals(source,settings,**{**kw,'model_identity':'digest-b'})
    d=plan_visuals(source,settings,options=Options(seed=8),**kw)
    assert len({a.cache_key,b.cache_key,c.cache_key,d.cache_key})==4 and len(calls)==4
    stale=a.spec.model_copy(deep=True);stale.provenance.prompt_version='visual-p0'
    assert validate_visuals(stale,source).spec is None


def test_corruption_fails_closed(tmp_path):
    result=run(tmp_path,lambda *_:envelope(intent()))
    path=tmp_path/'visuals'/f'{result.cache_key}.json'
    path.write_text('{broken')
    again=run(tmp_path,lambda *_:pytest.fail('Corruption must not infer'))
    assert any(d.code=='cache_invalid' for d in again.diagnostics)
    assert path.read_text()=='{broken'


def test_cache_revalidates_even_rechecksummed_data(tmp_path):
    result=run(tmp_path,lambda *_:envelope(intent()))
    path=tmp_path/'visuals'/f'{result.cache_key}.json'
    envelope_=json.loads(path.read_text());envelope_['spec']['scenes'][1]['actions'][0]['target']='missing'
    envelope_['checksum']=fingerprint(envelope_['spec']);path.write_text(json.dumps(envelope_))
    again=run(tmp_path,lambda *_:pytest.fail('Invalid cache must not infer'))
    assert any(d.code=='cache_invalid' for d in again.diagnostics)


def test_atomic_publication(tmp_path,monkeypatch):
    source,_=fixture();result=run(tmp_path,lambda *_:envelope(intent()))
    cache=VisualCache(tmp_path);path=cache.path(result.cache_key);before=path.read_bytes()
    def fail(*_):raise OSError('interrupted publication')
    monkeypatch.setattr(Path,'replace',fail)
    with pytest.raises(OSError):cache.write(result.cache_key,result.spec,source)
    assert path.read_bytes()==before and not list(path.parent.glob('*.tmp'))


def test_ids_language_reuse_and_old_artifacts_unchanged(tmp_path):
    source,_=fixture();before=source.model_dump_json()
    folders=[]
    for lang in ['en','hi','kn']:
        folder=tmp_path/'lessons'/source.lesson_id/f'{lang}-female-1';folder.mkdir(parents=True)
        for name in ['lesson.json','narration.wav','timeline.json','lesson.mp4']:
            path=folder/name;path.write_bytes(b'old-media');folders.append(path)
    ids=[lesson_key(PlanRequest(topic='Water Cycle',subject='science',language=l),'qwen3:4b-instruct-2507-q4_K_M') for l in ['en','hi','kn']]
    assert ids==['c1f63f0ed69b']*3
    first=run(tmp_path,lambda *_:envelope(intent()))
    for language in ['hi','kn']:
        settings=Settings(cache_dir=tmp_path,device='cpu',default_language=language)
        result=plan_visuals(source,settings,inference=lambda *_:pytest.fail('No fresh inference'),model_identity='local-model-digest',scene_ids=['s2'])
        assert result.stats.cache_hit and result.cache_key==first.cache_key
    assert source.model_dump_json()==before
    assert all(p.read_bytes()==b'old-media' for p in folders)
    localized=source.model_copy(update={'language':'hi'})
    with pytest.raises(ValueError):plan_visuals(localized,Settings(cache_dir=tmp_path))


def test_localized_binding():
    source,spec=fixture();visual=VisualSpec.model_validate(spec)
    localized=source.model_copy(deep=True);localized.language='hi'
    localized.scenes[1].steps[0].text='वाष्पीकरण'
    labels,warnings=resolve_labels(visual,source,localized)
    assert labels['s2.label']=='वाष्पीकरण' and not warnings
    scenes=[];time=0
    for scene in localized.scenes:
        ids=([None] if scene.narration else [])+list(range(len(scene.steps)))
        entries=[]
        for i,index in enumerate(ids):
            start=time+i*30;end=start+30
            entries.append(dict(beat_id=f'{scene.id}.'+('intro' if index is None else f'step{index}'),step_index=index,
                start_frame=start,end_frame=end,captions=[dict(text='Hindi',start_frame=start,end_frame=end)]))
        scenes.append(dict(scene_id=scene.id,type=scene.type,start_frame=time,duration_frames=len(ids)*30,beats=entries))
        time+=len(ids)*30
    timeline=Timeline(lesson_id=source.lesson_id,language='hi',variant='hi-female-1',duration_frames=time,audio=None,
                      voice=dict(engine='kokoro',voice_id='hf_alpha',speed=1.0),scenes=scenes)
    bound=bind_timeline(visual,source,localized,timeline)
    assert len(bound)==4 and all(a.end_frame-a.start_frame==18 for a in bound)
    localized.scenes[1].steps.reverse()
    # Reordering translatable text alone is not observable as identity; narration
    # indexes are the contract. A protected structural edit MUST be rejected.
    localized.scenes[1].code='changed'
    with pytest.raises(ValueError):bind_timeline(visual,source,localized,timeline)


def test_literal_label_warns_for_kannada():
    source,spec=fixture('array_grid_demo');localized=source.model_copy(update={'language':'kn'})
    labels,warnings=resolve_labels(VisualSpec.model_validate(spec),source,localized)
    assert len(labels)==5 and len(warnings)==5


def test_localhost_only_and_ollama_payload(tmp_path):
    with pytest.raises(ValueError):Settings(ollama_url='https://cloud.example')
    requests=[]
    def handler(request):
        requests.append(request)
        if request.url.path=='/api/tags':return httpx.Response(200,json=dict(models=[dict(name=Options().model,digest='a'*64)]))
        return httpx.Response(200,json=envelope(intent()))
    client=Ollama(Settings(device='cpu'),transport=httpx.MockTransport(handler))
    assert client.identity(Options().model)=='a'*64
    client.generate([dict(role='user',content='data')],Options())
    body=json.loads(requests[-1].content)
    assert all(r.url.host=='127.0.0.1' and r.url.port==11434 for r in requests)
    assert body['options']['num_gpu']==0 and body['options']['temperature']==0
    assert body['stream'] is False and body['format']['additionalProperties'] is False
    assert 'think' not in body


def test_topic_dependent_intent_not_title_templates(tmp_path):
    source,_=fixture();calls=[]
    def fake(messages,options):
        data=json.loads(messages[1]['content']);calls.append(data['topic'])
        value=intent()
        if 'Graph' in data['topic']:
            value.update(layout='graph_network',mechanism='Visit connected vertices')
            value['entities'][0]['role']='Graph vertex'
        return envelope(value)
    settings=Settings(cache_dir=tmp_path,device='cpu')
    a=plan_visuals(source,settings,inference=fake,model_identity='digest',scene_ids=['s2'])
    source=source.model_copy(update={'topic':'Graph traversal'})
    b=plan_visuals(source,settings,inference=fake,model_identity='digest',scene_ids=['s2'])
    assert a.spec.scenes[1].layout != b.spec.scenes[1].layout and len(calls)==2


def test_never_executes_source_code(tmp_path):
    source,_=fixture('python_for_loop')
    count=len(source.scenes[1].code.splitlines())
    source.scenes[1].code='\n'.join(['raise RuntimeError("must never run")']+['pass']*(count-1))
    value=intent();value['entities'][0].update(shape='text',slot='left',label_ref='code')
    result=plan_visuals(source,Settings(cache_dir=tmp_path,device='cpu'),inference=lambda *_:envelope(value),
                        model_identity='digest',scene_ids=['s2'])
    assert result.spec.scenes[1].objects


def test_linear_construction():
    points=linear_points(1,1,0,4,0,6)
    for i,p in enumerate(points):
        x=i;y=(.9-p['y'])*6/.8
        assert y==pytest.approx(x+1)
    with pytest.raises(ValueError):linear_points(float('nan'),0,0,1,0,2)
    with pytest.raises(ValueError):linear_points(5,0,0,1,0,2)


def test_preferred_anchor_collision_is_deterministic():
    source,_=fixture();value=intent();value['entities'][1]['slot']='top_left'
    notes=[]
    a=compile_intent(Intent.model_validate(value),source.scenes[1],placement_notes=notes)
    b=compile_intent(Intent.model_validate(value),source.scenes[1])
    assert a==b and len(notes)==1
    assert a.objects[0].position != a.objects[1].position


@pytest.mark.parametrize('style',['primary','secondary','accent','muted','warning','highlight'])
def test_semantic_styles(style):
    source,spec=fixture();spec['scenes'][1]['objects'][0]['style']=style
    assert validate_visuals(spec,source).spec is not None


@pytest.mark.parametrize('bad',[None,[],dict(message=None,done=True),dict(message='bad',done=True)])
def test_malformed_envelopes_fallback(tmp_path,bad):
    result=run(tmp_path,lambda *_:bad)
    assert result.spec.scenes[1].fallback is not None and result.stats.calls==2


def test_static_label_diagram_warns():
    source,spec=fixture();spec['scenes'][1]['actions']=[dict(id='a',kind='reveal',target='sun',beat_id='s2.step0')]
    checked=validate_visuals(spec,source)
    assert checked.spec is not None and any(d.code=='limited_visual_mechanism' for d in checked.diagnostics)


@pytest.mark.parametrize('field',['prompt_version','capability_version','asset_version','semantics_version'])
def test_all_semantic_versions_validated(field):
    source,spec=fixture();spec['provenance'][field]='obsolete'
    assert validate_visuals(spec,source).spec is None


@pytest.mark.parametrize('mutation',['particles','instances','scale','trace','nan_action','path_points'])
def test_additional_complexity_and_action_limits(mutation):
    source,spec=fixture();s=spec['scenes'][1]
    if mutation=='particles':
        obj=next(o for o in s['objects'] if o['kind']=='particles');obj['positions']*=5
    elif mutation=='instances':
        s['objects'] += [dict(kind='particles',id='p'+str(i),role='Collection',positions=[dict(x=.5,y=.5)]*32,radius=.005) for i in range(5)]
    elif mutation=='scale':s['actions'][0]=dict(id='a',kind='transform',target='sun',beat_id='s2.step0',to_scale=2.0)
    elif mutation=='trace':s['actions'][0]['path_id']='sun'
    elif mutation=='nan_action':s['actions'][0]['end']=float('nan')
    else:next(o for o in s['objects'] if o['kind']=='path')['segments']*=9
    assert validate_visuals(spec,source).spec is None
