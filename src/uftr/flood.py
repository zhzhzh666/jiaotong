"""Parameterized, spatially correlated flood scenarios; not hydrodynamics."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist


def hydrograph(times_s, peak_s, rise_s, recession_s):
    t=np.asarray(times_s,float)[:,None]
    peak=np.atleast_1d(peak_s); rise=np.atleast_1d(rise_s); fall=np.atleast_1d(recession_s)
    if np.any(rise<=0) or np.any(fall<=0): raise ValueError('positive durations required')
    before=np.clip((t-(peak-rise))/rise,0,1)
    after=np.clip(1-(t-peak)/fall,0,1)
    # Smoothstep has a finite dry start/end, unlike an infinite exponential tail.
    z=np.where(t<=peak,before,after)
    return z*z*(3-2*z)


def spatial_parameters(points_xy, seed, settings):
    xy=np.asarray(points_xy,float); n=len(xy)
    if n==0: raise ValueError('no risk points')
    correlation=np.exp(-cdist(xy,xy)/settings['correlation_length_m'])
    rng=np.random.default_rng(seed)
    correlated=np.linalg.cholesky(correlation+np.eye(n)*1e-9)@rng.normal(size=n)
    peak=settings['base_peak_m']*np.exp(settings['log_depth_sd']*correlated)
    delay=np.clip(correlated*settings['delay_sd_hours'],-2,2)*3600
    return pd.DataFrame({'peak_m':peak,'peak_s':settings['peak_hour']*3600+delay,
        'rise_s':np.full(n,settings['rise_hours']*3600),
        'recession_s':np.full(n,settings['recession_hours']*3600)})


def generate_depths(points, mapping, times, seed, settings):
    params=spatial_parameters(np.array([(g.x,g.y) for g in points.to_crs(32650).geometry]),seed,settings)
    params['point_id']=points.point_id.to_numpy()
    pulse=hydrograph(times,params.peak_s,params.rise_s,params.recession_s)*params.peak_m.to_numpy()
    selected=mapping[mapping.selected_geometry.eq(True) & mapping.edge_id.notna()]
    point_index={v:i for i,v in enumerate(points.point_id)}
    edges=sorted(selected.edge_id.unique()); depths=np.zeros((len(times),len(edges)))
    edge_index={v:i for i,v in enumerate(edges)}
    for r in selected.itertuples():
        k=edge_index[r.edge_id]; depths[:,k]=np.maximum(depths[:,k],pulse[:,point_index[r.point_id]])
    frames=[]
    for scenario,mult in settings['scenario_multipliers'].items():
        frames.append(pd.DataFrame({'scenario':scenario,'time_s':np.repeat(times,len(edges)),
            'edge_id':np.tile(edges,len(times)),'depth_m':(depths*mult).ravel(),
            'source_kind':'synthetic_parameterized','zero_datum_observed':False}))
    return pd.concat(frames,ignore_index=True),params


def road_response(depth_m, speed_kph, capacity_veh_h, settings, model='pregnolato'):
    h,v,c=np.broadcast_arrays(np.asarray(depth_m,float),np.asarray(speed_kph,float),np.asarray(capacity_veh_h,float))
    if not np.isfinite(h).all() or (h<0).any() or not np.isfinite(v).all() or (v<=0).any() or not np.isfinite(c).all() or (c<=0).any():
        raise ValueError('finite nonnegative depth and positive normal attributes required')
    threshold=settings['closure_depth_m']
    if threshold<=0 or threshold>.3: raise ValueError('validated polynomial domain is 0 to 300 mm')
    closed=h>=threshold
    if model=='pregnolato':
        # Pregnolato et al. 2017, PDF p7 Eq4; mm -> km/h. Capacity is separate.
        w=h*1000; limit=np.maximum(0,.0009*w*w-.5529*w+86.9448)
        speed=np.where(h==0,v,np.minimum(v,limit))
    elif model=='linear': speed=v*np.maximum(0,1-h/threshold)
    else: raise ValueError('unknown speed model')
    speed=np.where(closed,0,speed)
    cap=np.where(closed,0,c*np.maximum(settings['minimum_capacity_fraction'],1-settings['capacity_loss_at_closure']*h/threshold))
    state=np.select([closed,h>=.15,h>0],['closed','heavy','light'],default='normal')
    return pd.DataFrame({'speed_kph':speed.ravel(),'capacity_veh_h':cap.ravel(),'closed':closed.ravel(),'state':state.ravel()})
