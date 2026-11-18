"""Generate independent, versioned Longgang synthetic demand, offline only."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import yaml

from uftr.demand import make_zones, connect_zones, boundary_gateways, build_od
from uftr.longgang_od import inferred_graph, population_allocation, fast_network_skims, schedule

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(config):
    started = time.time()
    cfg = yaml.safe_load(config.read_text(encoding='utf-8'))
    if cfg['include_dapeng'] is not False:
        raise ValueError('This authorized run excludes Dapeng')
    out = ROOT/cfg['output_root']/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_longgang_od_'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    print('OUTPUT '+str(out), flush=True)
    write(out/'status.json', {'status':'running','observed_od':False})
    inputs = [config,Path(__file__).resolve(),ROOT/'src/uftr/longgang_od.py',ROOT/'src/uftr/demand.py',
        ROOT/cfg['roads'],ROOT/cfg['population'],ROOT/cfg['intake_directory']/'study_boundary_supplied.geojson']
    try:
        print('Reading boundary and full Shenzhen source road layer',flush=True)
        boundary_frame = gpd.read_file(inputs[-1])
        if boundary_frame.include_dapeng.any():
            raise ValueError('Boundary still includes Dapeng')
        boundary = boundary_frame.geometry.union_all()
        boundary_frame.to_file(out/'study_boundary.geojson', driver='GeoJSON')
        roads = gpd.read_file(ROOT/cfg['roads'],layer=cfg['road_layer'])
        graph,nodes,rejected,network_report = inferred_graph(roads,cfg['network'])
        write(out/'network_report.json',network_report)
        rejected.to_csv(out/'excluded_source_features.csv',index=False,encoding='utf-8-sig')
        print('Inferred graph '+json.dumps(network_report),flush=True)
        nx.write_graphml(graph,out/'inferred_source_network.graphml')
        print('Clipping native WorldPop cells and creating 1km zones',flush=True)
        zones = make_zones(boundary,cfg['zone_size_m'])
        values,allocation,pop_report = population_allocation(zones,ROOT/cfg['population'])
        internal = connect_zones(zones,nodes,graph,cfg['max_connector_distance_m'])
        gates = boundary_gateways(graph,nodes,boundary,cfg['boundary_gateways'])
        # The generic helper labels authoritative OSM nodes. This source has
        # geometry-derived node IDs, so expose that distinction in the GIS file.
        gates['source_kind'] = 'inferred_source_vertex_synthetic_boundary_demand'
        # External candidates all have a real source arc crossing this boundary;
        # equal shares are assumptions, never observed boundary traffic counts.
        external = pd.DataFrame([{'zone_id':r.zone_id,'zone_kind':'external_gateway','node_id':r.node_id,
            'connector_distance_m':0.,'connected':True,'candidate_nodes_in_zone':1,
            'can_depart':graph.out_degree(r.node_id)>0,'can_arrive':graph.in_degree(r.node_id)>0,
            'status':'existing_outside_vertex_with_boundary_crossing_arc','source_kind':'inferred_node_synthetic_demand'} for r in gates.itertuples()])
        connectors = pd.concat([internal,external],ignore_index=True)
        connectors.node_id = connectors.node_id.astype('Int64')
        print(f'Zones {len(zones)}, population {pop_report["allocated_people"]:.4f}; computing directed skims',flush=True)
        times = fast_network_skims(connectors,graph,cfg['access_speed_kph'],cfg['intrazonal_time_s'])
        # Independent reference Dijkstra on selected origins and all zone targets.
        skim_error = 0.
        for i in np.flatnonzero(connectors.connected.to_numpy(bool))[::max(1,len(connectors)//8)]:
            ref = nx.single_source_dijkstra_path_length(graph,int(connectors.node_id.iloc[i]),weight='free_flow_time_s')
            for j in np.flatnonzero(connectors.connected.to_numpy(bool)):
                if i==j and connectors.zone_kind.iloc[i]=='internal':continue
                node = int(connectors.node_id.iloc[j])
                if node in ref:
                    expected = ref[node]+(connectors.connector_distance_m.iloc[i]+connectors.connector_distance_m.iloc[j])/(cfg['access_speed_kph']/3.6)
                    skim_error = max(skim_error,abs(expected-times[i,j]))
                elif np.isfinite(times[i,j]):raise AssertionError('Invented reachable pair')
        print('Balancing gravity OD with IPF; retaining all zero-population zones',flush=True)
        od,targets,trace,period_report = build_od(connectors,values,times,cfg)
        ids = connectors.zone_id.tolist()
        matrices = {}
        for period in cfg['periods']:
            matrix = od.loc[od.period.eq(period)].pivot(index='origin_zone',columns='destination_zone',values='flow_veh_h').reindex(index=ids,columns=ids).fillna(0.)
            matrices[period] = matrix.to_numpy()
            matrix.rename_axis('origin_zone').to_csv(out/f'od_{period}_veh_h.csv',encoding='utf-8-sig',float_format='%.12g')
        od.to_parquet(out/'od_all_periods.parquet',index=False)
        targets.to_csv(out/'zone_marginal_targets.csv',index=False,encoding='utf-8-sig')
        trace.to_csv(out/'ipf_trace.csv',index=False)
        values.to_csv(out/'zone_population.csv',index=False,encoding='utf-8-sig')
        allocation.to_csv(out/'population_cell_allocation.csv',index=False,encoding='utf-8-sig')
        connectors.to_csv(out/'zone_connectors.csv',index=False,encoding='utf-8-sig')
        zones.to_crs(4326).to_file(out/'traffic_zones.geojson',driver='GeoJSON')
        gates.to_crs(4326).to_file(out/'boundary_gateways.geojson',driver='GeoJSON')
        np.savez_compressed(out/'network_skims.npz',zone_ids=np.array(ids),travel_time_with_access_s=times)
        np.savez_compressed(out/'od_sensitivity_veh_h.npz',zone_ids=np.array(ids),**{case+'__'+p:m*f for case,f in cfg['sensitivity'].items() for p,m in matrices.items()})
        intervals = schedule(matrices,cfg['time'])
        for case,factor in cfg['sensitivity'].items():
            intervals[case+'_expected_vehicle_trips'] = intervals.expected_vehicle_trips*factor
        intervals.to_csv(out/'interval_totals.csv',index=False,encoding='utf-8-sig')
        # Materialize each baseline 15min complete square matrix for direct reuse.
        folder = out/'od_15min_base';folder.mkdir()
        for r in intervals.itertuples():
            pd.DataFrame(matrices[r.period]*r.duration_hours,index=ids,columns=ids).rename_axis('origin_zone').to_csv(folder/f'od_{r.start_time.replace(":","")}_expected_trips.csv.gz',compression='gzip',float_format='%.12g')
        daily = sum(matrices[r.period]*r.duration_hours for r in intervals.itertuples())
        pd.DataFrame(daily,index=ids,columns=ids).rename_axis('origin_zone').to_csv(out/'od_daily_expected_trips.csv',encoding='utf-8-sig',float_format='%.12g')
        case_daily = {case:float(daily.sum()*factor) for case,factor in cfg['sensitivity'].items()}
        final = trace.groupby(['period','block']).tail(1)
        checks = {
            'scope_excludes_dapeng':bool(not boundary_frame.include_dapeng.any()),
            'population_fraction_weights_not_above_one':bool((allocation.groupby('cell_id').overlap_area_m2.sum()/allocation.groupby('cell_id').native_cell_area_m2.first() <= 1+1e-10).all()),
            'allocated_population_conserved':bool(np.isclose(values.population_estimate.sum(),allocation.allocated_people.sum(),rtol=1e-12)),
            'all_zones_including_zero_population_retained':len(connectors)==len(zones)+len(gates),
            'all_matrices_finite_nonnegative':all(np.isfinite(m).all() and (m>=0).all() for m in matrices.values()),
            'ipf_margins_converged':bool(final.relative_margin_error.max()<=cfg['ipf_tolerance']),
            'external_external_zero':all((m[-len(gates):,-len(gates):]==0).all() for m in matrices.values()),
            'route_status_accounting':all(np.isclose(sum(v['by_route_status_veh_h'].values()),v['total_veh_h']) for v in period_report.values()),
            'independent_skim_error_below_1e_7_s':bool(skim_error<1e-7),
            'exactly_96_intervals':len(intervals)==96,
            'daily_integral_matches_intervals':bool(np.isclose(daily.sum(),intervals.expected_vehicle_trips.sum(),rtol=1e-12)),
            'all_interval_csvs_written':len(list(folder.glob('*.csv.gz')))==96,
            'sampled_interval_roundtrip':True,
        }
        for k in [0,28,40,68,80,95]:
            row=intervals.iloc[k]
            disk=pd.read_csv(folder/f'od_{row.start_time.replace(":","")}_expected_trips.csv.gz',index_col=0)
            checks['sampled_interval_roundtrip'] &= bool(np.allclose(disk.to_numpy(),matrices[row.period]*row.duration_hours,rtol=1e-10,atol=1e-10))
        assert all(checks.values()),checks
        report = {'run_id':out.name,'region':'longgang','include_dapeng':False,'observed_od':False,
            'source_kind':'synthetic_population_gravity_IPF_inferred_network',
            'zones':len(zones),'external_gateways':len(gates),'matrix_shape':[len(ids),len(ids)],
            'positive_population_zones':int((values.population_estimate>0).sum()),
            'connected_internal_zones':int(internal.connected.sum()),
            'unconnected_positive_population_zones':int(((values.population_estimate>0)&(~internal.connected)).sum()),
            'population':pop_report,'network':network_report,'periods':period_report,
            'daily_expected_vehicle_trips':case_daily,'intervals':len(intervals),
            'max_ipf_relative_error':float(final.relative_margin_error.max()),
            'independent_skim_max_error_s':skim_error,'checks':checks,'elapsed_seconds':time.time()-started,
            'limitations':['All quantities are uncalibrated synthetic expected vehicle trips, not official or observed traffic',
                'Boundary coordinates assumed WGS84 per supplier; datum independently unverified',
                'Population 2020 differs from 2026 source roads; no event-specific historical reconstruction',
                'Attraction is population-only; peak periods have no independently estimated commuting direction',
                'Exact-vertex topology is inferred; unresolved grade transitions and missing source junctions remain',
                'Uniform intrazonal demand is retained but not loaded to graph; unreachable demand retained',
                'Inbound and outbound each 10% of internal demand; equal weights across 12 gateways are assumptions',
                'External-external through traffic excluded, not measured zero',
                '15min profiles and low/high scales are assumptions, not observations or confidence bounds',
                'No congestion, water depth, traffic assignment, resilience or SUMO recalculated']}
        write(out/'demand_report.json',report)
        shutil.copy2(config,out/'config.yaml')
        for p in [Path(__file__).resolve(),ROOT/'src/uftr/longgang_od.py',ROOT/'src/uftr/demand.py']:
            shutil.copy2(p,out/p.name)
        plot(out,zones,values,roads,matrices,intervals,cfg)
        write(out/'status.json',{'status':'complete_synthetic_OD_topology_uncertified','observed_od':False})
        manifest={'run_id':out.name,'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in inputs],
            'outputs':[{'path':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()]}
        write(out/'manifest.json',manifest)
        with zipfile.ZipFile(str(out)+'.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for p in out.rglob('*'):
                if p.is_file():archive.write(p,arcname=p.relative_to(out))
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        return out
    except Exception as exc:
        write(out/'status.json',{'status':'failed','error':repr(exc)})
        raise


def plot(out,zones,values,roads,matrices,intervals,cfg):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    fig,axs=plt.subplots(1,2,figsize=(13,6),layout='constrained')
    joined=zones.merge(values[['zone_id','population_estimate']],on='zone_id')
    joined.plot(ax=axs[0],column='population_estimate',cmap='YlOrRd',legend=True,legend_kwds={'label':'WorldPop people allocated by cell overlap','shrink':.65})
    roads=roads.to_crs(32650)
    bounds=zones.total_bounds
    subset=roads.cx[bounds[0]:bounds[2],bounds[1]:bounds[3]]
    subset.plot(ax=axs[0],color='#4c6170',linewidth=.15,alpha=.5)
    axs[0].set_xlim(bounds[0],bounds[2]);axs[0].set_ylim(bounds[1],bounds[3]);axs[0].set_title('Longgang 1 km zones; Dapeng excluded')
    axs[0].set_axis_off()
    m=matrices['morning_peak'];pos=m[m>0]
    im=axs[1].imshow(np.ma.masked_less_equal(m,0),cmap='magma',norm=LogNorm(vmin=pos.min(),vmax=pos.max()),interpolation='nearest')
    axs[1].set_title('Synthetic morning-peak OD (veh/h)');axs[1].set_xlabel('Destination zone index');axs[1].set_ylabel('Origin zone index')
    fig.colorbar(im,ax=axs[1],shrink=.65,label='veh/h, logarithmic')
    for ext in ['png','svg']:fig.savefig(out/('longgang_zones_od.'+ext),dpi=170)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,4),layout='constrained')
    for case in ['low','base','high']:
        ax.step(intervals.start_minute/60,intervals[case+'_expected_vehicle_trips'],where='post',label=case)
    ax.set(xlim=(0,24),xlabel='Hour, assumed local simulation day',ylabel='Expected vehicle trips per 15 min',title='Synthetic daily demand; low/base/high = 0.7 / 1.0 / 1.3')
    ax.grid(alpha=.2);ax.legend()
    for ext in ['png','svg']:fig.savefig(out/('longgang_daily_demand.'+ext),dpi=170)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'configs/longgang_od.yaml')
    run(p.parse_args().config.resolve())
