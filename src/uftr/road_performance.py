"""Depth-to-road state interface preserving directed edges and parallel arcs."""
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
from .flood import road_response


def graphml_edge_identities(path):
    """Read authoritative OSM directed identities absent from the GIS export."""
    names={};rows=[]
    for _,element in ET.iterparse(path,events=['end']):
        tag=element.tag.rsplit('}',1)[-1]
        if tag=='key':names[element.get('id')]=element.get('attr.name')
        elif tag=='edge':
            values={names.get(d.get('key')):d.text for d in element if d.tag.rsplit('}',1)[-1]=='data'}
            if 'edge_id' not in values:raise ValueError('GraphML edge_id required')
            rows.append({'edge_id':values['edge_id'],'u':int(element.get('source')),
                         'v':int(element.get('target')),'key':int(element.get('id'))})
            element.clear()
        elif tag=='node':element.clear()
    result=pd.DataFrame(rows)
    if result.empty or not result.edge_id.is_unique or result.duplicated(['u','v','key']).any():
        raise ValueError('unique GraphML edge identities required')
    return result


def validate_settings(settings):
    for key in ['closure_depth_m','minimum_capacity_fraction','capacity_loss_at_closure']:
        if not np.isfinite(settings[key]):raise ValueError('finite road-response parameters required')
    if not 0 < settings['closure_depth_m'] <= .3:raise ValueError('closure depth must be in (0,0.30] m')
    if not 0 < settings['minimum_capacity_fraction'] <= 1:raise ValueError('capacity floor must be in (0,1]')
    if not 0 <= settings['capacity_loss_at_closure'] <= 1:raise ValueError('capacity loss must be in [0,1]')


def evaluate_depth_rows(edges, depth_rows, settings, model='pregnolato'):
    """Sparse states: absent edges are not silently added to this table."""
    validate_settings(settings)
    if not edges.edge_id.is_unique:raise ValueError('unique directed edge_id required')
    keys=[k for k in ['case','scenario','time_s','edge_id'] if k in depth_rows]
    if depth_rows.duplicated(keys).any():raise ValueError('duplicate directed edge state')
    if not set(depth_rows.edge_id) <= set(edges.edge_id):raise ValueError('unknown directed edge')
    fields=['edge_id','u','v','key','length_m','free_flow_speed_kph','capacity_veh_h']
    attributes=edges[fields].rename(columns={'free_flow_speed_kph':'normal_speed_kph','capacity_veh_h':'normal_capacity_veh_h'})
    table=depth_rows.merge(attributes,on='edge_id',how='left',validate='many_to_one',sort=False).reset_index(drop=True)
    if not np.isfinite(table.length_m).all() or (table.length_m<=0).any():raise ValueError('positive finite road length required')
    response=road_response(table.depth_m,table.normal_speed_kph,table.normal_capacity_veh_h,settings,model)
    result=pd.concat([table,response],axis=1)
    result['travel_time_s']=np.divide(result.length_m.to_numpy()*3.6,result.speed_kph.to_numpy(),
        out=np.full(len(result),np.inf),where=result.speed_kph.to_numpy()>0)
    result['speed_ratio']=result.speed_kph/result.normal_speed_kph
    result['capacity_ratio']=result.capacity_veh_h/result.normal_capacity_veh_h
    result['traversable']=~result.closed
    return result


def network_snapshot(edges, sparse_depths, settings):
    """Materialize all edges, explicitly marking unlisted depth=0 assumptions."""
    if not sparse_depths.edge_id.is_unique:raise ValueError('select a single case/scenario/time first')
    if not set(sparse_depths.edge_id)<=set(edges.edge_id):raise ValueError('unknown edge')
    full=edges[['edge_id']].merge(sparse_depths[['edge_id','depth_m']],on='edge_id',how='left',sort=False,validate='one_to_one')
    full['unlisted_assumed_dry']=full.depth_m.isna()
    # Missing input for a listed edge is an error, not a dry-road observation.
    if sparse_depths.depth_m.isna().any():raise ValueError('listed depth cannot be missing')
    full['depth_m']=full.depth_m.fillna(0.)
    return evaluate_depth_rows(edges,full,settings)


def traversable_edges(snapshot):
    """Assignment-ready free-flow costs; closed arcs are physically excluded."""
    result=snapshot.loc[snapshot.traversable].copy()
    if not np.isfinite(result.travel_time_s).all() or (result.travel_time_s<=0).any() or (result.capacity_veh_h<=0).any():
        raise ValueError('open edges require positive finite costs and capacity')
    result['free_flow_time_s']=result.travel_time_s
    return result


def closure_episodes(time_h, depth_m, threshold_m):
    """h >= threshold is closed; crossings use piecewise linear endpoints.

    Handles equality/tangent contacts, repeated closures and window censoring.
    No hysteresis or post-flood road-inspection delay is assumed.
    """
    t,h=np.asarray(time_h,float),np.asarray(depth_m,float)
    if t.ndim!=1 or h.shape!=t.shape or len(t)<2 or not np.isfinite(t).all() or not np.isfinite(h).all():
        raise ValueError('equal finite endpoint vectors required')
    if (np.diff(t)<=0).any() or (h<0).any() or not np.isfinite(threshold_m) or threshold_m<=0:
        raise ValueError('increasing time, nonnegative depths and positive threshold required')
    intervals=[]
    for k in range(len(t)-1):
        a,b=h[k]>=threshold_m,h[k+1]>=threshold_m
        if not a and not b:continue
        start,end=float(t[k]),float(t[k+1])
        if a!=b:
            crossing=float(t[k]+(threshold_m-h[k])*(t[k+1]-t[k])/(h[k+1]-h[k]))
            if a:end=crossing
            else:start=crossing
        if intervals and start<=intervals[-1][1]+1e-12:intervals[-1][1]=end
        else:intervals.append([start,end])
    return [{'episode':i+1,'closed_from_hour':a,'closed_until_hour':b,'duration_h':b-a,
             'left_censored':bool(a==t[0] and h[0]>=threshold_m),
             'right_censored':bool(b==t[-1] and h[-1]>=threshold_m),
             'reopen_hour':None if b==t[-1] and h[-1]>=threshold_m else b} for i,(a,b) in enumerate(intervals)]
