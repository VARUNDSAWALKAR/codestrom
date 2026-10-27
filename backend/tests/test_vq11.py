"""Semantic recovery checks; fake inference only, no heavy model dependencies."""
import copy
import json
from pathlib import Path
import httpx
import pytest

from backend.app.config import Settings
from backend.app.planner.schema import Lesson
from backend.app.visuals.semantic import SemanticIntent,validate_semantic
from backend.app.visuals.compose import compose_semantic
from backend.app.visuals.planner import plan_semantic_visuals,plan_visuals,Ollama,Options
from backend.app.visuals.validate import validate_visuals,source_fingerprint

FIXTURES=Path(__file__).parent/'fixtures/visuals_v11'


def case(name='water_cycle'):
    value=json.loads((FIXTURES/f'{name}.json').read_text(encoding='utf-8'))
    source=Lesson.model_validate(value['source'])
    scene=next(s for s in source.scenes if s.id==value['scene_id'])
    return value,source,scene


def envelope(value):return dict(done=True,message=dict(content=json.dumps(value)))


@pytest.mark.parametrize('name',['water_cycle','array_bounds','binary_search_cached','concave_lens','graph_traversal','ohms_law','heldout_settling','heldout_swap'])
def test_authored_fixtures(name):
    value,source,scene=case(name)
    intent=SemanticIntent.model_validate(value['intent'])
    result=compose_semantic(intent,scene)
    assert result==next(s for s in validate_visuals(value['spec'],source).spec.scenes if s.scene_id==scene.id)
    assert result==compose_semantic(intent,scene)


def test_schema_export():
    path=Path(__file__).parents[1]/'app/visuals/semantic.schema.json'
    assert json.loads(path.read_text())==SemanticIntent.model_json_schema()


@pytest.mark.parametrize('bad',['shape','position','svg','slot','style','duration','python','keyframes'])
def test_presentation_not_allowed(bad):
    value,_,_=case();value['intent']['entities'][0][bad]='untrusted'
    with pytest.raises(ValueError):SemanticIntent.model_validate(value['intent'])


@pytest.mark.parametrize('mutation',['entity','relation','family','beat','quote','target','order','transfer','duplicate','cycle'])
def test_bad_spatial_intent(mutation):
    value,_,scene=case();d=value['intent']
    if mutation=='entity':d['entities'][0]['kind']='custom_svg'
    elif mutation=='relation':d['relationships'][0]['kind']='simulate'
    elif mutation=='family':d['family']='flow_cycle'
    elif mutation=='beat':d['changes'][0]['beat_id']='s99.step0'
    elif mutation=='quote':d['changes'][0]['evidence']='Invented physical claim'
    elif mutation=='target':d['changes'][0]['target']='missing'
    elif mutation=='order':d['changes'].reverse()
    elif mutation=='transfer':d['changes'][0]['evidence']='Evaporation'
    elif mutation=='duplicate':d['entities'][1]['id']=d['entities'][0]['id']
    else:d['relationships'] += [dict(kind='above',source='sun',target='water',evidence='Sun'),dict(kind='above',source='water',target='sun',evidence='water')]
    with pytest.raises(ValueError):compose_semantic(SemanticIntent.model_validate(d),scene)


def test_no_renamed_process_boxes():
    value,_,scene=case();d=value['intent'];d['entities'][0].update(kind='body',evidence='Evaporation')
    with pytest.raises(ValueError,match='entity_evidence'):compose_semantic(SemanticIntent.model_validate(d),scene)


def test_spatial_transfer_directions_and_beats():
    value,_,scene=case();result=compose_semantic(SemanticIntent.model_validate(value['intent']),scene)
    assert result.layout=='spatial' and not any(o.kind=='rectangle' for o in result.objects)
    paths={o.id:o for o in result.objects if o.kind=='path'}
    traces=[a for a in result.actions if a.kind=='trace']
    assert [a.beat_id for a in traces]==['s2.step0','s2.step2']
    first,second=[paths[a.path_id] for a in traces]
    assert first.start.y>first.segments[-1].end.y
    assert second.start.y<second.segments[-1].end.y
    assert sum(o.kind=='ellipse' for o in result.objects)>=3


@pytest.mark.parametrize('mutation',['invent_values','selection','range','comparison','swap','backwards'])
def test_array_source_fidelity(mutation):
    value,_,scene=case('array_bounds');d=value['intent']
    if mutation=='invent_values':d['values']=[2,4,6]
    elif mutation=='selection':d['changes'][1]['value']=8
    elif mutation=='range':d['changes'][2]['values']=[1,7]
    elif mutation=='comparison':d['changes'][1]=dict(kind='compare',left=5,right=3,relation='lt',beat_id='s2.step1',evidence='Midpoint 5')
    elif mutation=='swap':d['changes'][1]=dict(kind='swap',first=1,second=9,beat_id='s2.step1',evidence='Midpoint 5')
    else:d['changes'][3]['beat_id']='s2.step0'
    with pytest.raises(ValueError):compose_semantic(SemanticIntent.model_validate(d),scene)


def test_actual_bad_binary_source_cannot_be_silently_corrected():
    _,_,scene=case('binary_search_cached')
    intent=dict(family='array_grid',values=[1,3,5,7,9],changes=[dict(kind='select',value=5,beat_id='s3.step1',evidence='Check 5')])
    with pytest.raises(ValueError,match='source_inaccurate'):compose_semantic(SemanticIntent.model_validate(intent),scene)


def test_array_pointer_and_range_consistency():
    value,_,scene=case('array_bounds');r=compose_semantic(SemanticIntent.model_validate(value['intent']),scene)
    assert r.layout=='array_grid'
    assert [o.label.text for o in r.objects if o.kind=='rectangle']==['1','3','5','7','9']
    assert any(a.target=='lo' and a.kind=='move' and a.beat_id=='s2.step2' for a in r.actions)
    assert any(a.target=='current' and a.kind=='reveal' and a.to_opacity==0 and a.beat_id=='s2.step2' for a in r.actions)


def test_swaps_move_values_but_not_indexes():
    v,_,s=case('heldout_swap');r=compose_semantic(SemanticIntent.model_validate(v['intent']),s)
    moves=[a for a in r.actions if a.kind=='move']
    assert len(moves)==2 and all(a.target.startswith('cell') for a in moves)
    assert moves[0].from_position==moves[1].to_position


def test_valid_numeric_comparison():
    value,_,scene=case('array_bounds')
    scene=scene.model_copy(deep=True);scene.steps[1].note='5 < 7'
    value['intent']['changes'][1]=dict(kind='compare',left=5,right=7,relation='lt',beat_id='s2.step1',evidence='5 < 7')
    r=compose_semantic(SemanticIntent.model_validate(value['intent']),scene)
    assert any(o.kind=='text' and o.label.text=='5 < 7' for o in r.objects)


@pytest.mark.parametrize('mutation',['edge','visit','jump','wrong_quote'])
def test_graph_consistency(mutation):
    v,_,s=case('graph_traversal');d=v['intent']
    if mutation=='edge':d['edges'][0]['target']='missing'
    elif mutation=='visit':d['visits'][0]['node']='missing'
    elif mutation=='jump':d['edges'].pop()
    else:d['edges'][0]['evidence']='No such source edge'
    with pytest.raises(ValueError):compose_semantic(SemanticIntent.model_validate(d),s)


def test_graph_current_visited_and_no_extra_edges():
    v,_,s=case('graph_traversal');r=compose_semantic(SemanticIntent.model_validate(v['intent']),s)
    assert r.layout=='graph_network'
    assert sum(o.kind=='arrow' for o in r.objects)==2
    assert len([a for a in r.actions if a.kind=='trace'])==2
    assert {a.target for a in r.actions if a.kind=='highlight'}=={'vertex0','vertex1','vertex2'}


@pytest.mark.parametrize('name',['concave_lens','binary_search_cached'])
def test_supported_vs_unsupported(name):
    v,_,s=case(name);r=compose_semantic(SemanticIntent.model_validate(v['intent']),s)
    assert r.fallback and not r.objects and not r.actions


def test_coordinate_is_explicitly_deferred():
    v,_,s=case('concave_lens');d=dict(family='unsupported',reason='coordinate_geometry',evidence=s.heading)
    assert compose_semantic(SemanticIntent.model_validate(d),s).fallback
    with pytest.raises(ValueError):SemanticIntent.model_validate(dict(family='coordinate_plane',expression='x**2'))


def test_mock_generation_cache_and_language_reuse(tmp_path):
    v,source,_=case();calls=[];settings=Settings(cache_dir=tmp_path,device='cpu')
    def fake(*args):calls.append(args);return envelope(v['intent'])
    a=plan_semantic_visuals(source,settings,inference=fake,model_identity='local-digest',scene_ids=['s2'])
    for language in ['en','hi','kn']:
        b=plan_semantic_visuals(source,settings.model_copy(update={'default_language':language}),
                               inference=lambda *_:pytest.fail('Warm semantic cache inferred'),model_identity='local-digest',scene_ids=['s2'])
        assert b.stats.cache_hit and b.cache_key==a.cache_key
    assert len(calls)==1 and a.spec.provenance.prompt_version=='visual-semantic-p1'
    assert a.spec.provenance.semantics_version=='semantic-composer-v1'


def test_legacy_cache_is_separate_and_compatible(tmp_path):
    v,source,_=case();settings=Settings(cache_dir=tmp_path,device='cpu')
    legacy_value=dict(layout='spatial',mechanism='Old schematic',representation='unsupported',limitation='Unsupported',entities=[
        dict(id='sun',shape='circle',role='Sun',slot='top',label_ref=None)],links=[],actions=[dict(kind='reveal',target='sun',beat_id='s2.step0')])
    a=plan_visuals(source,settings,inference=lambda *_:envelope(legacy_value),model_identity='digest',scene_ids=['s2'])
    b=plan_semantic_visuals(source,settings,inference=lambda *_:envelope(v['intent']),model_identity='digest',scene_ids=['s2'])
    assert a.cache_key!=b.cache_key
    assert validate_visuals(a.spec,source).spec and validate_visuals(b.spec,source).spec


def test_one_repair_and_invalid_fallback(tmp_path):
    v,source,_=case();calls=[]
    def fake(*args):calls.append(args);return envelope(dict(family='spatial',shapes=['invented']))
    r=plan_semantic_visuals(source,Settings(cache_dir=tmp_path,device='cpu'),inference=fake,model_identity='digest',scene_ids=['s2'])
    assert len(calls)==2 and r.stats.repairs==1 and all(s.fallback for s in r.spec.scenes)


def test_http_receives_semantic_schema_only():
    v,source,_=case();bodies=[]
    def handler(request):
        body=json.loads(request.content);bodies.append(body);return httpx.Response(200,json=envelope(v['intent']))
    client=Ollama(Settings(device='cpu'),httpx.MockTransport(handler))
    client.generate([dict(role='user',content='data')],Options(),output_schema=SemanticIntent.model_json_schema())
    assert 'SpatialIntent' in bodies[0]['format']['$defs'] and bodies[0]['options']['num_gpu']==0


def test_unsafe_payloads_and_unknown_quantities():
    v,_,s=case();d=v['intent'];d['entities'][0]['evidence']='<script/>'
    with pytest.raises(ValueError):compose_semantic(SemanticIntent.model_validate(d),s)
    with pytest.raises(ValueError):SemanticIntent.model_validate(dict(family='array_grid',values=[1,float('inf')],changes=[]))


def test_signed_values_cannot_be_confused():
    from backend.app.visuals.semantic import numbers_in
    assert numbers_in('select -1, compare 12 and 2')=={-1,12,2}
    assert 1 not in numbers_in('select -1')


def test_namespace_handles_reserved_and_long_semantic_ids():
    v,_,s=case('graph_traversal');d=v['intent'];replacement='current_'+'a'*24
    old=d['nodes'][0]['id'];d['nodes'][0]['id']=replacement
    for e in d['edges']:
        if e['source']==old:e['source']=replacement
        if e['target']==old:e['target']=replacement
    for e in d['visits']:
        if e['node']==old:e['node']=replacement
    r=compose_semantic(SemanticIntent.model_validate(d),s)
    assert len({o.id for o in r.objects})==len(r.objects)


def test_force_application_does_not_emit_radiation():
    from backend.app.visuals.compose import Builder,entity_geometry
    from backend.app.visuals.semantic import SemanticEntity
    _,_,s=case();builder=Builder(s,'spatial',[])
    entity_geometry(builder,SemanticEntity(id='force',kind='force_source',evidence='force'),dict(x=.5,y=.5),0)
    assert not any('ray' in o['id'] for o in builder.objects)
