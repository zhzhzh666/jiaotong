"""Method B research prototype: topographic D8 stores, not sewer/2D hydraulics.

Priority-flood supplies a draining DAG and a per-cell depression storage proxy.
The original elevations are retained. Positive mobile storage is transferred
to one downstream cell with an assumed linear-reservoir travel time. There is
no momentum, pressure head reversal, river boundary or coupled sewer model.
"""
import heapq
import numpy as np


def priority_drainage(elevation, cell_size_m):
    """Return receiver, spill depth and pop rank; all exterior cells can drain.

    The priority-flood parent was popped before its child, so its rank is lower.
    This also defines deterministic drainage on flats without routing cycles.
    Filled elevation is used only to estimate spill storage and connectivity.
    Per-cell storage is an approximation to a connected depression, not a
    depression-wide level/volume curve or a hydraulic flood level prediction.
    """
    z=np.asarray(elevation,float)
    if z.ndim!=2 or min(z.shape)<2 or not np.isfinite(z).all() or cell_size_m<=0:
        raise ValueError('invalid terrain')
    nr,nc=z.shape
    edge=np.zeros(z.shape,bool);edge[[0,-1],:]=True;edge[:,[0,-1]]=True
    seen=edge.ravel().copy();filled=z.ravel().copy()
    receiver=np.full(z.size,-1,dtype=np.int64)
    rank=np.full(z.size,-1,dtype=np.int64)
    distance=np.full(z.size,cell_size_m,float)
    queue=[(float(z.ravel()[j]),int(j)) for j in np.flatnonzero(seen)]
    heapq.heapify(queue);order=0
    while queue:
        level,j=heapq.heappop(queue)
        rank[j]=order;order+=1
        r,c=divmod(j,nc)
        for dr,dc in ((-1,0),(0,-1),(0,1),(1,0),(-1,-1),(-1,1),(1,-1),(1,1)):
            rr,cc=r+dr,c+dc
            if not (0<=rr<nr and 0<=cc<nc):continue
            k=rr*nc+cc
            if seen[k]:continue
            seen[k]=True;receiver[k]=j
            distance[k]=cell_size_m*np.hypot(dr,dc)
            filled[k]=max(z.ravel()[k],level)
            heapq.heappush(queue,(float(filled[k]),k))
    if order!=z.size:raise ValueError('incomplete drainage tree')
    internal=receiver>=0
    if not np.all(rank[receiver[internal]]<rank[internal]):raise ValueError('cyclic drainage')
    spill=np.maximum(0,filled-z.ravel())
    slope=np.zeros(z.size,float)
    slope[internal]=(filled[internal]-filled[receiver[internal]])/distance[internal]
    return {'receiver':receiver,'spill_depth_m':spill,'filled_elevation_m':filled,
            'rank':rank,'distance_m':distance,'slope':slope}


def travel_time(drainage,settings):
    slope=np.maximum(drainage['slope'],settings['slope_floor'])
    velocity=settings['reference_velocity_m_s']*np.sqrt(slope/settings['reference_slope'])
    if not np.isfinite(velocity).all() or (velocity<=0).any():raise ValueError('invalid velocity assumption')
    return np.clip(drainage['distance_m']/velocity,settings['tau_min_seconds'],settings['tau_max_seconds'])


def route_step(storage_m, rain_m, loss_capacity_m, receiver, spill_m, tau_s, dt_s):
    """One positive operator-split step: rain, capacity-limited loss, transfer.

    All faces transfer simultaneously. A recipient can send that newly received
    water onward on the following step. Temporal splitting error is measured by
    a smaller-step replay. Returned volumes are depths summed over equal cells.
    """
    h=np.asarray(storage_m,float)+rain_m
    removed=np.minimum(h,loss_capacity_m)
    h=h-removed
    transfer=np.maximum(h-spill_m,0)*(-np.expm1(-dt_s/tau_s))
    h=h-transfer
    inside=receiver>=0
    h+=np.bincount(receiver[inside],weights=transfer[inside],minlength=len(h))
    return h,float(removed.sum()),float(transfer[~inside].sum())


def simulate(elevation, drainage, tau_s, hourly_mm, rain_grid, cell_size_m,
             district_weights, road_cells, settings, case, *, dt_s=None, save_fields=False):
    """Conservative equal-area raster simulation; hourly rain is uniform within hour."""
    dt=int(dt_s or settings['time']['internal_seconds'])
    output_s=int(settings['time']['output_minutes']*60)
    if dt<=0 or 3600%dt or output_s%dt:raise ValueError('time steps must divide hour and output interval')
    rain=np.asarray(hourly_mm,float)
    if rain.ndim!=2 or not np.isfinite(rain).all() or (rain<0).any():raise ValueError('invalid rain')
    n=np.asarray(elevation).size
    grid=np.asarray(rain_grid,int)
    receiver=np.asarray(drainage['receiver'],int)
    spill=np.asarray(drainage['spill_depth_m'],float)
    tau=np.asarray(tau_s,float)*case['tau_multiplier']
    for a in (grid,receiver,spill,tau,district_weights):
        if a.shape!=(n,):raise ValueError('invalid cell array')
    if (grid<0).any() or (grid>=rain.shape[1]).any():raise ValueError('missing rain grid')
    if not np.isfinite(tau).all() or (tau<=0).any() or (spill<0).any():raise ValueError('invalid routing')
    if min(case.values())<0 or case['tau_multiplier']==0:raise ValueError('invalid case')
    if np.sum(district_weights)<=0:raise ValueError('empty reporting district')
    h=np.full(n,settings['initial_depth_m'],float)
    if not np.isfinite(h).all() or (h<0).any():raise ValueError('invalid initial storage')
    loss_capacity=settings['loss']['capacity_mm_h']*case['loss_multiplier']*dt/3600/1000
    if loss_capacity<0:raise ValueError('negative loss')
    cell_area=cell_size_m**2;initial=float(h.sum()*cell_area)
    inside=receiver>=0
    if (receiver[inside]>=n).any():raise ValueError('invalid receiver')
    if 'rank' in drainage and not np.all(drainage['rank'][receiver[inside]]<drainage['rank'][inside]):
        raise ValueError('cyclic drainage')
    # Precompute exact linear-reservoir release fractions for the fixed step.
    fraction=-np.expm1(-dt/tau)
    wet_weights=np.asarray(district_weights,float)
    road_cells=np.asarray(road_cells,int)
    if (road_cells<0).any() or (road_cells>=n).any():raise ValueError('invalid road sampling cell')
    rows=[];road=[h[road_cells].astype(np.float32)];fields=[h.astype(np.float32)] if save_fields else []
    peak=h.copy();cumrain=cumloss=cumout=0.;periodrain=periodloss=periodout=0.
    maxresidual=0.;duration_s=rain.shape[0]*3600
    def record(t):
        storage=float(h.sum()*cell_area)
        residual=storage-initial-cumrain+cumloss+cumout
        row={'time_h':t/3600,'rain_m3_interval':periodrain,'loss_m3_interval':periodloss,
             'boundary_outflow_m3_interval':periodout,'storage_m3':storage,
             'cumulative_rain_m3':cumrain,'cumulative_loss_m3':cumloss,
             'cumulative_boundary_outflow_m3':cumout,'balance_residual_m3':residual,
             'district_max_cell_depth_m':float(h[wet_weights>0].max())}
        for threshold in settings['thresholds_m']:
            row[f'district_area_above_{threshold:g}_km2']=float(wet_weights[h>threshold].sum()*cell_area/1e6)
        return row
    rows.append(record(0))
    for step in range(duration_s//dt):
        rain_depth=rain[(step*dt)//3600,grid]*case['rain_multiplier']*(dt/3600)/1000
        before=float(h.sum())
        h+=rain_depth
        removed=np.minimum(h,loss_capacity);h-=removed
        transfer=np.maximum(h-spill,0)*fraction;h-=transfer
        h+=np.bincount(receiver[inside],weights=transfer[inside],minlength=n)
        r=float(rain_depth.sum())*cell_area;l=float(removed.sum())*cell_area
        o=float(transfer[~inside].sum())*cell_area
        residual=(float(h.sum())-before)*cell_area-r+l+o
        maxresidual=max(maxresidual,abs(residual))
        cumrain+=r;cumloss+=l;cumout+=o
        periodrain+=r;periodloss+=l;periodout+=o
        peak=np.maximum(peak,h)
        if (step+1)*dt%output_s==0:
            rows.append(record((step+1)*dt))
            road.append(h[road_cells].astype(np.float32))
            if save_fields:fields.append(h.astype(np.float32))
            periodrain=periodloss=periodout=0.
    if not np.isfinite(h).all() or (h<0).any():raise ValueError('invalid resulting depths')
    return {'ledger':rows,'road_sample_depth_m':np.asarray(road),
            'depth_fields_m':np.asarray(fields) if save_fields else None,
            'peak_depth_m':peak,'final_depth_m':h,'maximum_step_residual_m3':maxresidual,
            'internal_seconds':dt}
