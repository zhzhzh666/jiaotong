"""Interval demand and frozen road-state adapters for time-slice assignment."""
import numpy as np


def validate_profile(profile):
    required=['interval_index','start_hour','end_hour','duration_hours','base_period','rate_multiplier']
    if any(k not in profile for k in required):raise ValueError('incomplete departure profile')
    start=profile.start_hour.to_numpy(float);end=profile.end_hour.to_numpy(float)
    duration=profile.duration_hours.to_numpy(float);mult=profile.rate_multiplier.to_numpy(float)
    if len(start)!=96 or not np.array_equal(profile.interval_index,np.arange(96)):
        raise ValueError('ordered 96 intervals required')
    if not all(np.isfinite(x).all() for x in [start,end,duration,mult]) or (mult<0).any():
        raise ValueError('finite nonnegative demand required')
    if not np.allclose(start,np.arange(96)/4,rtol=0,atol=1e-12) or not np.allclose(end,start+.25,rtol=0,atol=1e-12) or not np.allclose(duration,.25,rtol=0,atol=1e-12):
        raise ValueError('continuous quarter-hour intervals covering [0,24) required')


def interval_od(base, multiplier):
    """Keep every OD row and route status; output is veh/h, never interval trips."""
    if not np.isfinite(multiplier) or multiplier<0:raise ValueError('invalid demand multiplier')
    result=base.copy()
    result['flow_veh_h']=base.flow_veh_h*multiplier
    return result


def state_arrays(network, sparse):
    """Join by authoritative directed IDs, with explicit dry-road defaults."""
    if not sparse.edge_id.is_unique:raise ValueError('one snapshot required')
    index=network.edges.set_index('edge_id')
    if not set(sparse.edge_id)<=set(index.index):raise ValueError('unknown directed edge')
    original=index.loc[sparse.edge_id]
    for k in ['u','v','key']:
        if not np.array_equal(original[k].to_numpy(),sparse[k].to_numpy()):raise ValueError('directed identity mismatch')
    t0=network.edges.length_m.to_numpy()*3.6/network.edges.free_flow_speed_kph.to_numpy()
    cap=network.capacity.copy();closed=np.zeros(len(cap),bool)
    positions=index.index.get_indexer(sparse.edge_id)
    t0[positions]=sparse.travel_time_s;cap[positions]=sparse.capacity_veh_h;closed[positions]=sparse.closed
    if not np.isfinite(t0[~closed]).all() or (t0[~closed]<=0).any() or not np.isfinite(cap).all() or (cap[~closed]<=0).any():
        raise ValueError('invalid open road state')
    if not np.isinf(t0[closed]).all() or (cap[closed]!=0).any():raise ValueError('invalid closed road state')
    return t0,cap,closed


def integrate_intervals(profile, values):
    """Left-endpoint hold over the 96 departure intervals; no 97th departure."""
    validate_profile(profile)
    q=np.asarray(values,float)
    if q.shape!=(len(profile),) or not np.isfinite(q).all():raise ValueError('one finite value per interval required')
    return float(np.dot(q,profile.duration_hours)/profile.duration_hours.sum())


def congestion_fraction(flow, capacity, closed):
    active=~np.asarray(closed,bool)
    if (np.asarray(capacity)[active]<=0).any():raise ValueError('positive active capacity required')
    return float(np.mean(np.asarray(flow)[active]/np.asarray(capacity)[active]>.9)) if active.any() else 0.
