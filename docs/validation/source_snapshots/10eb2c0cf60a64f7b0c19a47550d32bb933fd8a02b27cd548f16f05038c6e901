"""Transparent synthetic zoning and doubly constrained demand, not observed OD.

Unreachable pairs keep positive impedance and demand. Their missing network time
is never replaced by a fabricated route. No edges are added to the road graph.
"""
from pathlib import Path
import math
import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import box, Polygon, Point


def make_zones(boundary, size_m):
    if not math.isfinite(size_m) or size_m <= 0:
        raise ValueError('zone size must be positive metres')
    polygon = gpd.GeoSeries([boundary], crs=4326).to_crs(32650).iloc[0]
    x0, y0, x1, y1 = polygon.bounds
    rows = []
    for ix in range(math.floor(x0 / size_m), math.ceil(x1 / size_m)):
        for iy in range(math.floor(y0 / size_m), math.ceil(y1 / size_m)):
            geom = box(ix*size_m, iy*size_m, (ix+1)*size_m, (iy+1)*size_m).intersection(polygon)
            if not geom.is_empty and geom.area > 0:
                point = geom.representative_point()
                rows.append({'zone_id':f'TAZ_{ix}_{iy}', 'grid_x':ix, 'grid_y':iy,
                             'area_m2':geom.area, 'centre_x_m':point.x, 'centre_y_m':point.y,
                             'zone_kind':'internal', 'source_kind':'synthetic_zoning', 'geometry':geom})
    if not rows:
        raise ValueError('empty zoning boundary')
    return gpd.GeoDataFrame(rows, geometry='geometry', crs=32650)


def allocate_population(zones, raster_path):
    """Uniform within each retained native cell ∩ boundary, normalized to its count.

    This is an explicit synthetic allocation assumption, not finer observations.
    The Phase 02 centre-selected cell totals are preserved, including coast cells.
    """
    if zones.crs != 'EPSG:32650':
        raise ValueError('allocation requires projected metric zones')
    records = []
    with rasterio.open(raster_path) as source:
        values = source.read(1, masked=True)
        indices = np.argwhere(~np.ma.getmaskarray(values))
        cells = []
        for r, c in indices:
            value = float(values[r,c])
            if not np.isfinite(value) or value < 0:
                raise ValueError('population cells must be finite nonnegative counts')
            corners = [source.transform*(c,r), source.transform*(c+1,r),
                       source.transform*(c+1,r+1), source.transform*(c,r+1)]
            cells.append({'cell_id':f'r{r}_c{c}', 'people':value, 'geometry':Polygon(corners)})
        native = gpd.GeoDataFrame(cells, geometry='geometry', crs=source.crs).to_crs(32650)
    for cell in native.itertuples():
        ids = zones.sindex.query(cell.geometry, predicate='intersects')
        areas = [(int(i), cell.geometry.intersection(zones.geometry.iloc[i]).area) for i in sorted(ids)]
        areas = [(i,a) for i,a in areas if a > 0]
        denominator = sum(a for _,a in areas)
        if denominator <= 0:
            raise ValueError('retained native population cell has no zone overlap')
        for i, area in areas:
            records.append({'cell_id':cell.cell_id, 'zone_id':zones.zone_id.iloc[i],
                            'native_cell_people':cell.people, 'overlap_area_m2':area,
                            'weight':area/denominator, 'allocated_people':cell.people*area/denominator,
                            'source_kind':'modelled_population_synthetic_allocation'})
    allocation = pd.DataFrame(records)
    total = float(native.people.sum())
    if not np.isclose(allocation.allocated_people.sum(), total, rtol=1e-12, atol=1e-7):
        raise ValueError('native population conservation failed')
    summary = zones[['zone_id','area_m2']].copy()
    summary['population_estimate'] = summary.zone_id.map(allocation.groupby('zone_id').allocated_people.sum()).fillna(0.)
    summary['source_kind'] = 'WorldPop_2020_model_uniform_native_cell_allocation'
    return summary, allocation, {'native_cells':len(native), 'native_people':total,
        'allocated_people':float(allocation.allocated_people.sum()),
        'assumption':'Uniform distribution within retained native cell intersect study boundary, normalized to preserve Phase 02 cell count; not observed 1km TAZ population'}


def add_attraction(zones, population, facilities, population_share, facility_weights):
    if not 0 <= population_share <= 1:
        raise ValueError('population attraction share must be in [0,1]')
    result = population.copy()
    result['facility_score'] = 0.
    result['facility_count'] = 0
    for poi in facilities.to_crs(32650).itertuples():
        ids = sorted(zones.sindex.query(poi.geometry, predicate='intersects'))
        if len(ids):
            i = int(ids[0])  # A point exactly on a shared grid line counted once.
            result.loc[i,'facility_count'] += 1
            result.loc[i,'facility_score'] += facility_weights.get(poi.category,0.)
    pop = result.population_estimate.to_numpy(float)
    if pop.sum() <= 0:
        raise ValueError('positive population required for demand scaling')
    share = pop / pop.sum()
    score = result.facility_score.to_numpy(float)
    fallback = score.sum() == 0
    result['production_share'] = share
    result['attraction_share'] = share if fallback else population_share*share + (1-population_share)*score/score.sum()
    return result, {'facility_population_fallback':bool(fallback),
        'facility_count_assigned':int(result.facility_count.sum()),
        'assumption':'Population plus incomplete emergency POI score only; no measured employment, commercial trips or commuting validation'}


def connect_zones(zones, nodes, graph, max_distance_m):
    """Nearest existing graph node INSIDE each zone; no cross-water fallback."""
    projected = nodes.to_crs(32650).sort_values('node_id').reset_index(drop=True)
    rows = []
    for z in zones.itertuples():
        centre = Point(z.centre_x_m,z.centre_y_m)
        ids = projected.sindex.query(z.geometry, predicate='intersects')
        candidates = projected.iloc[ids].copy()
        if len(candidates):
            candidates['distance'] = candidates.geometry.distance(centre)
            chosen = candidates.sort_values(['distance','node_id']).iloc[0]
            linked = chosen.distance <= max_distance_m
        else:
            linked = False
        node = int(chosen.node_id) if linked else None
        rows.append({'zone_id':z.zone_id, 'zone_kind':'internal', 'node_id':node,
            'connector_distance_m':float(chosen.distance) if linked else None,
            'connected':linked, 'candidate_nodes_in_zone':len(candidates),
            'can_depart':bool(linked and graph.out_degree(node)>0),
            'can_arrive':bool(linked and graph.in_degree(node)>0),
            'status':'nearest_existing_node_in_zone' if linked else 'no_node_within_zone_and_distance_limit',
            'source_kind':'synthetic_access_connector_not_a_road'})
    result = pd.DataFrame(rows)
    result['node_id'] = result.node_id.astype('Int64')
    return result


def boundary_gateways(graph, nodes, boundary, count):
    """Existing outside nodes joined by real arcs to inside nodes, spatial spread.

    Counts/weights are synthetic. This identifies cut-network gateways, not full
    external routes or observed screenline flows. All graph components remain.
    """
    projected = nodes.to_crs(32650).set_index('node_id')
    polygon = gpd.GeoSeries([boundary],crs=4326).to_crs(32650).iloc[0]
    inside = {int(n) for n,g in projected.geometry.items() if polygon.covers(g)}
    candidates = []
    for node in sorted(set(graph)-inside):
        incoming = sum(1 for u,_,_ in graph.in_edges(node,keys=True) if u in inside)
        outgoing = sum(1 for _,v,_ in graph.out_edges(node,keys=True) if v in inside)
        if incoming or outgoing:
            candidates.append({'node_id':node,'incoming_crossing_arcs':incoming,
                               'outgoing_crossing_arcs':outgoing,'geometry':projected.loc[node,'geometry']})
    if not candidates:
        raise ValueError('no actual boundary-crossing node available; do not invent external gateways')
    # Deterministic farthest-point spread, initialized with lowest OSM node ID.
    chosen = [candidates[0]]
    remaining = candidates[1:]
    while remaining and len(chosen) < count:
        best = max(range(len(remaining)),key=lambda i:(min(remaining[i]['geometry'].distance(c['geometry']) for c in chosen),-remaining[i]['node_id']))
        chosen.append(remaining.pop(best))
    for i,c in enumerate(chosen):
        c.update(zone_id=f'EXT_{i:03d}', zone_kind='external_gateway',
                 source_kind='real_OSM_node_synthetic_boundary_demand', candidate_count=len(candidates))
    return gpd.GeoDataFrame(chosen,geometry='geometry',crs=32650)


def network_skims(connectors, graph, access_speed_kph, intrazonal_time_s):
    ids = connectors.zone_id.to_list()
    times = np.full((len(ids),len(ids)),np.nan)
    # One origin Dijkstra for each UNIQUE connector; parallel arc costs use min
    # for this shortest-path query only. The original MultiDiGraph is unchanged.
    positions = {}
    for i,c in connectors.iterrows():
        if c.connected:
            positions.setdefault(int(c.node_id),[]).append(i)
    for node,origins in positions.items():
        lengths = nx.single_source_dijkstra_path_length(graph,node,weight='free_flow_time_s')
        for dest,targets in positions.items():
            if dest in lengths:
                for i in origins:
                    for j in targets:
                        access = (connectors.iloc[i].connector_distance_m+connectors.iloc[j].connector_distance_m)/(access_speed_kph/3.6)
                        times[i,j] = lengths[dest]+access
    kinds = connectors.zone_kind.to_numpy()
    for i in range(len(ids)):
        if kinds[i] == 'internal':
            times[i,i] = intrazonal_time_s  # Retained local trips, not graph-loaded.
    return times


def ipf(seed, productions, attractions, tolerance=1e-9, max_iterations=2000):
    matrix = np.array(seed,dtype=float,copy=True)
    o = np.asarray(productions,float); d = np.asarray(attractions,float)
    if matrix.shape != (len(o),len(d)) or any(not np.isfinite(x).all() or (x<0).any() for x in [matrix,o,d]):
        raise ValueError('IPF inputs must be finite, nonnegative and aligned')
    if not math.isfinite(tolerance) or tolerance <= 0 or type(max_iterations) is not int or max_iterations < 1:
        raise ValueError('invalid IPF convergence settings')
    if not np.isclose(o.sum(),d.sum(),rtol=1e-12,atol=1e-9):
        raise ValueError('IPF marginal totals differ')
    matrix[o==0,:] = 0; matrix[:,d==0] = 0
    if o.sum() == 0:
        return matrix,[{'iteration':0,'relative_margin_error':0.,'max_abs_margin_error_veh_h':0.}]
    if ((matrix.sum(axis=1)==0)&(o>0)).any() or ((matrix.sum(axis=0)==0)&(d>0)).any():
        raise ValueError('positive marginal has no seed support')
    trace = []
    for iteration in range(1,max_iterations+1):
        matrix *= np.divide(o,matrix.sum(axis=1),out=np.zeros_like(o),where=matrix.sum(axis=1)>0)[:,None]
        matrix *= np.divide(d,matrix.sum(axis=0),out=np.zeros_like(d),where=matrix.sum(axis=0)>0)[None,:]
        ro = np.abs(matrix.sum(axis=1)-o); rd = np.abs(matrix.sum(axis=0)-d)
        error = max(np.max(ro/np.maximum(o,1e-12),initial=0),np.max(rd/np.maximum(d,1e-12),initial=0))
        absolute = max(float(np.max(ro,initial=0)),float(np.max(rd,initial=0)))
        trace.append({'iteration':iteration,'relative_margin_error':float(error),'max_abs_margin_error_veh_h':absolute})
        if error <= tolerance:
            return matrix,trace
    raise ValueError(f'IPF did not converge in {max_iterations} iterations; error={error}')


def build_od(connectors, zone_values, times, settings):
    """Balance II / incoming / outgoing blocks separately; no external bypass OD.

    Unreachable interzonal trips use a configurable impedance penalty to GENERATE
    demand, with missing network time and explicit unserved status in the output.
    """
    n = len(connectors)
    internal = np.flatnonzero(connectors.zone_kind.eq('internal'))
    external = np.flatnonzero(connectors.zone_kind.eq('external_gateway'))
    z = zone_values.set_index('zone_id').loc[connectors.iloc[internal].zone_id]
    pop = z.production_share.to_numpy(float); attr = z.attraction_share.to_numpy(float)
    pop = pop/pop.sum(); attr=attr/attr.sum()
    total = float(zone_values.population_estimate.sum())*settings['person_trip_rate_per_hour']*settings['motorized_person_trip_share']/settings['vehicle_occupancy']
    if len(external)==0:
        raise ValueError('boundary demand requires actual gateways')
    kernel = np.exp(-settings['gravity_beta_per_s']*np.maximum(
        np.where(np.isfinite(times),times,settings['unreachable_impedance_s']),settings['minimum_impedance_s']))
    if not (kernel>0).all():
        raise ValueError('gravity kernel underflow: revise explicit impedance parameters')
    tables=[]; targets=[]; traces=[]; summaries={}
    for period,spec in settings['periods'].items():
        if period=='morning_peak': o,d=pop,attr
        elif period=='evening_peak': o,d=attr,pop
        else: o=d=(pop+attr)/2
        scale=total*spec['factor']
        blocks=[('internal',internal,internal,o*scale,d*scale),
                ('inbound',external,internal,np.full(len(external),scale*settings['boundary_inbound_fraction']/len(external)),d*scale*settings['boundary_inbound_fraction']),
                ('outbound',internal,external,o*scale*settings['boundary_outbound_fraction'],np.full(len(external),scale*settings['boundary_outbound_fraction']/len(external)))]
        matrix=np.zeros((n,n)); target_o=np.zeros(n);target_d=np.zeros(n)
        for block,ii,jj,oo,dd in blocks:
            q,trace=ipf(kernel[np.ix_(ii,jj)],oo,dd,settings['ipf_tolerance'],settings['ipf_max_iterations'])
            matrix[np.ix_(ii,jj)]=q; target_o[ii]+=oo; target_d[jj]+=dd
            traces.extend({'period':period,'block':block,**t} for t in trace)
        for i in range(n):
            targets.append({'period':period,'zone_id':connectors.zone_id.iloc[i],
                            'production_veh_h':target_o[i],'attraction_veh_h':target_d[i],
                            'actual_production_veh_h':matrix[i].sum(),'actual_attraction_veh_h':matrix[:,i].sum()})
        records=[]
        for i,j in np.argwhere(matrix>0):
            intra=i==j and connectors.zone_kind.iloc[i]=='internal'
            reachable=bool(np.isfinite(times[i,j])) and not intra
            status='intrazonal_not_graph_loaded' if intra else ('routable' if reachable else 'unreachable_normal_network')
            records.append({'period':period,'origin_zone':connectors.zone_id.iloc[i], 'destination_zone':connectors.zone_id.iloc[j],
                'origin_node':connectors.node_id.iloc[i], 'destination_node':connectors.node_id.iloc[j],
                'flow_veh_h':float(matrix[i,j]),'network_reachable':reachable,
                'free_flow_with_access_s':float(times[i,j]) if reachable else None,
                'impedance_s':float(max(settings['minimum_impedance_s'],times[i,j] if np.isfinite(times[i,j]) else settings['unreachable_impedance_s'])),
                'route_status':status,'block':'inbound' if i in external else ('outbound' if j in external else 'internal'),
                'source_kind':'synthetic_gravity_ipf','observed_od':False})
        frame=pd.DataFrame(records)
        for col in ['origin_node','destination_node']:frame[col]=frame[col].astype('Int64')
        tables.append(frame)
        sums=frame.groupby('route_status').flow_veh_h.sum().to_dict()
        summaries[period]={'total_veh_h':float(matrix.sum()),'internal_veh_h':float(scale),
            'inbound_veh_h':float(scale*settings['boundary_inbound_fraction']),
            'outbound_veh_h':float(scale*settings['boundary_outbound_fraction']),
            'nonzero_od_pairs':len(frame),'by_route_status_veh_h':{k:float(v) for k,v in sums.items()},
            'max_absolute_margin_error_veh_h':float(max(np.abs(matrix.sum(1)-target_o).max(),np.abs(matrix.sum(0)-target_d).max())),
            'duration_note':'Hourly rate prototype only; not a 24h departure schedule'}
    return pd.concat(tables,ignore_index=True),pd.DataFrame(targets),pd.DataFrame(traces),summaries
