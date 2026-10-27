"""Small topic-independent composers targeting the unchanged VisualSpec v1."""
from __future__ import annotations

from collections import Counter
import math
from ..planner.schema import Scene
from .schema import SceneVisual
from .validate import check_scene
from .semantic import (SemanticIntent,ArrayIntent,SpatialIntent,GraphIntent,UnsupportedIntent,
                       Select,Range,Compare,Swap,Transfer,validate_semantic)


def point(x:float,y:float)->dict:
    return dict(x=round(x,8),y=round(y,8))


class Builder:
    def __init__(self,scene:Scene,family:str,changes:list):
        self.scene=scene;self.family=family;self.objects=[];self.actions=[];self.relationships=[]
        self.counts=Counter(c.beat_id for c in changes);self.used=Counter();self.states={}

    def object(self,kind:str,id:str,role:str,**kw):
        obj=dict(kind=kind,id=id,role=role,**kw);self.objects.append(obj)
        self.states[id,'style']=obj.get('style','primary')
        return obj

    def event(self,change):
        beat=change.beat_id;n=self.counts[beat];i=self.used[beat];self.used[beat]+=1
        return beat,.8*i/n,.8*(i+1)/n

    def action(self,kind,target,event,**kw):
        beat,start,end=event
        self.actions.append(dict(id=f'a{len(self.actions)}',kind=kind,target=target,
                                 beat_id=beat,start=start,end=end,**kw))

    def highlight(self,target,event,style='highlight'):
        previous=self.states.get((target,'style'),'primary')
        if previous!=style:self.action('highlight',target,event,from_style=previous,to_style=style)
        self.states[target,'style']=style

    def move(self,target,position,event,initial):
        previous=self.states.get((target,'position'),initial)
        if previous!=position:self.action('move',target,event,from_position=previous,to_position=position)
        self.states[target,'position']=position

    def finish(self,mechanism):
        visual=SceneVisual.model_validate(dict(scene_id=self.scene.id,layout=self.family,mechanism=mechanism,
            limitations=['Source-grounded qualitative illustration; scientific review still required',
                         'Supplemental evidence labels remain English; no new localization is performed'],
            objects=self.objects,actions=self.actions,relationships=self.relationships))
        check_scene(visual,self.scene);return visual


def array(data:ArrayIntent,scene:Scene)->SceneVisual:
    b=Builder(scene,'array_grid',data.changes);n=len(data.values)
    xs=[.1+.8*i/(n-1) for i in range(n)];width=min(.14,.65/n)
    positions={v:i for i,v in enumerate(data.values)}
    ids={v:f'cell{i}' for i,v in enumerate(data.values)}
    for i,v in enumerate(data.values):
        b.object('rectangle',ids[v],'Ordered value',position=point(xs[i],.5),width=width,height=.2,
                 label=dict(kind='literal',text=str(v)))
        b.object('text',f'index{i}','Fixed array index',position=point(xs[i],.68),width=.08,height=.08,
                 label=dict(kind='literal',text=str(i)))
        if i:b.relationships.append(dict(kind='ordered_with',source=ids[data.values[i-1]],target=ids[v]))
    pointers=[('lo',xs[0],.31,'low'),('hi',xs[-1],.31,'high')]
    if any(isinstance(c,Select) for c in data.changes):pointers.append(('current',xs[0],.8,'current'))
    for id,x,y,label in pointers:
        b.object('marker',id,'Array pointer '+label,position=point(x,y),radius=.01)
        if id!='current':b.object('text',id+'_label','Array bound',position=point(x,y-.1),width=.1,height=.08,label=dict(kind='literal',text=label))
    active=list(data.values);current_order=list(data.values);revealed=False;selected=None;comparison=None
    for c in data.changes:
        event=b.event(c)
        if isinstance(c,Range):
            if revealed and selected not in c.values:
                b.action('reveal','current',event,from_opacity=1.0,to_opacity=0.0);revealed=False
            for v in active:
                if v not in c.values:b.highlight(ids[v],event,'muted')
            for id,index in [('lo',positions[c.values[0]]),('hi',positions[c.values[-1]])]:
                initial=point(xs[0 if id=='lo' else -1],.31)
                b.move(id,point(xs[index],.31),event,initial)
                b.move(id+'_label',point(xs[index],.21),event,point(initial['x'],.21))
            active=c.values
            # A full initial range still has an explanatory beat action.
            if not any(a['beat_id']==c.beat_id for a in b.actions):b.highlight('lo',event)
        elif isinstance(c,Select):
            if not revealed:b.action('reveal','current',event);revealed=True
            selected=c.value
            b.move('current',point(xs[positions[c.value]],.8),event,point(xs[0],.8))
            b.highlight(ids[c.value],event)
        elif isinstance(c,Compare):
            if comparison:b.action('reveal',comparison,event,from_opacity=1.0,to_opacity=0.0)
            symbol={'lt':'<','gt':'>','eq':'='}[c.relation];id=f'comparison{len(b.actions)}'
            b.object('text',id,'Source-stated comparison',position=point(.5,.08),width=.35,height=.1,
                     label=dict(kind='literal',text=f'{c.left} {symbol} {c.right}'))
            b.action('reveal',id,event)
            comparison=id
        else:
            a,z=positions[c.first],positions[c.second]
            for value,index in [(c.first,z),(c.second,a)]:
                b.move(ids[value],point(xs[index],.5),event,point(xs[positions[value]],.5))
            positions[c.first],positions[c.second]=z,a
            current_order[a],current_order[z]=current_order[z],current_order[a]
    return b.finish('Source array values, bounds and narrated state changes')


PREFERRED={'energy_source':0,'reservoir':6,'cloud':2,'material':4,'plant':8,
           'body':7,'container':7,'barrier':5,'electrical_source':3,'resistor':5,'force_source':0}


def entity_geometry(b:Builder,entity,position:dict,index:int)->str:
    """Reusable entity motifs, not complete topic animations or licensed assets."""
    x,y=position['x'],position['y'];id=f'entity{index}';k=entity.kind
    main=id+'_main'
    if k=='energy_source':
        b.object('circle',main,k,position=position,radius=.065,style='accent')
        for i in range(6):
            a=i*math.tau/6
            b.object('line',id+f'_ray{i}','Energy rays',start=point(x+.038*math.cos(a),y+.095*math.sin(a)),
                     end=point(x+.052*math.cos(a),y+.13*math.sin(a)),style='accent')
    elif k=='force_source':
        b.object('marker',main,'Point of applied force',position=position,radius=.012)
    elif k=='cloud':
        for i,(dx,dy,rx,ry) in enumerate([(-.045,.015,.05,.05),(0,-.02,.06,.085),(.05,.015,.05,.05)]):
            b.object('ellipse',main if i==0 else id+f'_lobe{i}',k,position=point(x+dx,y+dy),rx=rx,ry=ry)
    elif k in {'reservoir','container'}:
        b.object('path',main,'Open vessel or surface reservoir',start=point(x-.11,y-.06),segments=[
            dict(kind='line',end=point(x-.09,y+.065)),dict(kind='line',end=point(x+.09,y+.065)),
            dict(kind='line',end=point(x+.11,y-.06))])
        if k=='reservoir':
            for i in range(2):b.object('line',id+f'_water{i}','Water surface',start=point(x-.075,y+i*.035),end=point(x+.075,y+i*.035),style='accent')
    elif k=='material':
        b.object('particles',main,'Material parcels',positions=[point(x+(i%3-1)*.018,y+(i//3-1)*.04) for i in range(9)],radius=.007)
    elif k=='plant':
        b.object('line',main,'Plant stem',start=point(x,y+.1),end=point(x,y-.1))
        for i,sign in enumerate([-1,1]):b.object('ellipse',id+f'_leaf{i}','Leaf',position=point(x+sign*.04,y-.03),rx=.045,ry=.08)
    elif k=='electrical_source':
        b.object('line',main,'Electrical source long terminal',start=point(x-.025,y-.1),end=point(x-.025,y+.1))
        b.object('line',id+'_short','Electrical source short terminal',start=point(x+.025,y-.055),end=point(x+.025,y+.055))
    elif k=='resistor':
        b.object('path',main,'Schematic resistor',start=point(x-.11,y),segments=[
            dict(kind='line',end=point(x-.075+i*.025,y+(.055 if i%2==0 else -.055))) for i in range(7)]+[
            dict(kind='line',end=point(x+.11,y))])
    elif k=='barrier':
        b.object('line',main,'Barrier',start=point(x,y-.12),end=point(x,y+.12))
    else:b.object('rectangle',main,'Physical body',position=position,width=.16,height=.18)
    label_y=y+.17
    b.object('text',id+'_label','Source entity label',position=point(x,label_y),width=.26,height=.09,
             label=dict(kind='literal',text=entity.evidence[:100]))
    return main


def spatial(data:SpatialIntent,scene:Scene)->SceneVisual:
    b=Builder(scene,'spatial',data.changes)
    slots=[point(x,y) for y in (.17,.46,.75) for x in (.18,.5,.82)]
    occupied=set();positions={}
    for e in data.entities:
        desired=PREFERRED[e.kind]
        available=[i for i in range(9) if i not in occupied]
        pick=min(available,key=lambda i:(abs(i//3-desired//3),abs(i%3-desired%3),i))
        occupied.add(pick);positions[e.id]=slots[pick]
    # General relative constraints, independent of topic/name. Reject ambiguous cycles.
    for axis,positive,negative in [('y','below','above'),('x','right_of','left_of')]:
        edges=[]
        for r in data.relationships:
            if r.kind==negative:edges.append((r.source,r.target))
            elif r.kind==positive:edges.append((r.target,r.source))
        ranks={e.id:0 for e in data.entities}
        for _ in range(len(ranks)):
            changed=False
            for a,z in edges:
                if ranks[z]<=ranks[a]:ranks[z]=ranks[a]+1;changed=True
            if not changed:break
        else:
            if changed:raise ValueError('placement_cycle: contradictory relative positions')
        maximum=max(ranks.values())
        if maximum:
            for id,rank in ranks.items():positions[id][axis]=.18+.55*rank/maximum
    targets={e.id:entity_geometry(b,e,positions[e.id],i) for i,e in enumerate(data.entities)}
    paths={}
    for i,r in enumerate(data.relationships):
        if r.kind in {'above','below','left_of','right_of'}:continue
        a,z=positions[r.source],positions[r.target];id=f'rel{i}'
        if a==z:raise ValueError('placement_conflict: semantic relation endpoints coincide')
        if r.kind=='flows_to':
            b.object('path',id,'Qualitative material transfer route',start=a,
                     segments=[dict(kind='line',end=z)],style='secondary')
            paths[r.source,r.target]=id
        else:
            b.object('line' if r.kind=='connected_to' else 'arrow',id,'Schematic '+r.kind,
                     start=point(a['x']*.75+z['x']*.25,a['y']*.75+z['y']*.25),
                     end=point(a['x']*.25+z['x']*.75,a['y']*.25+z['y']*.75),style='secondary')
        b.relationships.append(dict(kind='connected_to' if r.kind=='connected_to' else 'points_toward',
                                    source=targets[r.source],target=targets[r.target]))
    for i,c in enumerate(data.changes):
        event=b.event(c)
        if isinstance(c,Transfer):
            id=f'parcel{i}'
            b.object('marker',id,'Material parcel along stated transfer',position=positions[c.source],radius=.009)
            b.action('reveal',id,event)
            b.action('trace',id,event,path_id=paths[c.source,c.target])
        else:b.highlight(targets[c.entity],event)
    return b.finish('Recognizable physical entities with source-grounded interactions')


def graph(data:GraphIntent,scene:Scene)->SceneVisual:
    b=Builder(scene,'graph_network',data.visits);n=len(data.nodes)
    positions={node.id:point(.5+.32*math.cos(math.tau*i/n),.47+.28*math.sin(math.tau*i/n)) for i,node in enumerate(data.nodes)}
    ids={node.id:f'vertex{i}' for i,node in enumerate(data.nodes)}
    for node in data.nodes:b.object('circle',ids[node.id],'Graph vertex',position=positions[node.id],radius=.07,label=dict(kind='literal',text=node.label))
    for i,e in enumerate(data.edges):
        a,z=positions[e.source],positions[e.target]
        b.object('arrow' if e.directed else 'line',f'edge{i}','Graph edge',
                 start=point(.9*a['x']+.1*z['x'],.9*a['y']+.1*z['y']),
                 end=point(.1*a['x']+.9*z['x'],.1*a['y']+.9*z['y']))
        b.relationships.append(dict(kind='points_toward' if e.directed else 'connected_to',source=ids[e.source],target=ids[e.target]))
    route=[positions[v.node] for v in data.visits]
    b.object('path','walk','Narrated graph walk',start=route[0],segments=[dict(kind='line',end=p) for p in route[1:]],style='muted')
    b.object('marker','current','Current graph vertex',position=route[0],radius=.012)
    lengths=[math.hypot((z['x']-a['x'])*1152,(z['y']-a['y'])*460) for a,z in zip(route,route[1:])]
    total=sum(lengths);progress=0.0
    if not total:raise ValueError('traversal_state: no movement along graph edges')
    for i,v in enumerate(data.visits):
        event=b.event(v);b.highlight(ids[v.node],event)
        if not i:b.action('reveal','current',event)
        else:
            end=1.0 if i==len(data.visits)-1 else progress+lengths[i-1]/total
            b.action('trace','current',event,path_id='walk',from_progress=progress,to_progress=end);progress=end
    return b.finish('Explicit graph topology and narrated traversal')


def compose_semantic(intent:SemanticIntent,scene:Scene)->SceneVisual:
    # Revalidation prevents bypass with model_construct/model_copy.
    intent=SemanticIntent.model_validate(intent.model_dump(mode='json'))
    validate_semantic(intent,scene)
    data=intent.root
    if isinstance(data,UnsupportedIntent):
        from .planner import legacy
        return legacy(scene,'source_inaccurate' if data.reason=='inconsistent_source' else 'unsupported_mechanism',data.reason)
    if isinstance(data,ArrayIntent):return array(data,scene)
    if isinstance(data,SpatialIntent):return spatial(data,scene)
    return graph(data,scene)
