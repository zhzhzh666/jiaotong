"""Phase 03: conservative population allocation, synthetic OD and water intake."""
from pathlib import Path
import json
import sys
import geopandas as gpd
import pandas as pd
import numpy as np
import osmnx as ox
from .archive import RunArchive, file_hash, write_json
from .config import load_config
from .demand import (make_zones, allocate_population, add_attraction, connect_zones,
                     boundary_gateways, network_skims, build_od)
from .user_water import seal_user_sources, inspect_user_water


def verify_inventory(root, path, relative_to):
    inventory=json.loads(path.read_text(encoding='utf-8'))
    paths=[path]
    for item in inventory['files']:
        source=(relative_to/item['path']).resolve();source.relative_to(root)
        if file_hash(source)!=item['sha256']:raise ValueError('earlier output changed: '+str(source))
        paths.append(source)
    return paths


def plot_demand(zones, values, connectors, gateways, edges, od, sites, levels, folder, run_id, dpi):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.collections import LineCollection
    roads=edges.to_crs(32650)
    paths=[]
    def save(fig,name,source):
        fig.text(.01,.015,f'{run_id} | {source}',fontsize=7)
        path=folder/(name+'.png');fig.savefig(path,dpi=dpi);plt.close(fig);paths.append(path)
    def base(title):
        fig,ax=plt.subplots(figsize=(10,8));fig.subplots_adjust(left=.12,right=.96,bottom=.13,top=.88)
        roads.plot(ax=ax,color='#96a7b0',linewidth=.2,alpha=.5)
        # Mainland display; all sea/island zones remain in datasets.
        x0,y0,x1,y1=roads.total_bounds
        ax.set_xlim(max(x0,x1-40000)-300,x1+300);ax.set_ylim(y0-300,y1+300)
        ax.set_aspect('equal');ax.set_title(title);ax.set_xlabel('Easting (m), EPSG:32650');ax.set_ylabel('Northing (m)')
        ax.ticklabel_format(style='plain',useOffset=False)
        return fig,ax
    fig,ax=base('Synthetic 1 km TAZ population and existing-node connectors\nUniform native-cell allocation; sea/island zones retained, mainland display')
    joined=zones.merge(values[['zone_id','population_estimate']],on='zone_id')
    joined[joined.population_estimate>0].plot(ax=ax,column='population_estimate',cmap='YlOrRd',alpha=.65,legend=True,legend_kwds={'label':'Estimated people allocated to TAZ','shrink':.6})
    for status,color in [(True,'#225e80'),(False,'#a43148')]:
        part=zones[zones.zone_id.isin(connectors.loc[connectors.connected.eq(status),'zone_id'])]
        ax.scatter(part.centre_x_m,part.centre_y_m,s=4,c=color,label=f'Connected={status}: {len(part)}')
    gateways.plot(ax=ax,color='black',marker='^',markersize=40,label='Existing boundary nodes')
    ax.legend(fontsize=8,loc='lower left');save(fig,'traffic_zones','WorldPop 2020 CC BY 4.0; OSM contributors ODbL 1.0')
    ids=connectors.zone_id.tolist();fig,axes=plt.subplots(1,3,figsize=(14,5.3))
    maximum=od.flow_veh_h.max()
    for ax,period in zip(axes,['offpeak','morning_peak','evening_peak']):
        table=od[od.period.eq(period)].pivot(index='origin_zone',columns='destination_zone',values='flow_veh_h').reindex(index=ids,columns=ids).fillna(0)
        img=ax.imshow(np.ma.masked_less_equal(table.to_numpy(),0),norm=LogNorm(vmin=max(1e-6,od.flow_veh_h.min()),vmax=maximum),cmap='magma',interpolation='nearest')
        ax.set_title(period);ax.set_xlabel('Destination TAZ index')
        if period=='offpeak':ax.set_ylabel('Origin TAZ index')
    fig.colorbar(img,ax=axes.ravel().tolist(),shrink=.6,label='Synthetic demand (veh/h), log scale')
    fig.suptitle('Gravity + IPF synthetic hourly OD; unreachable and intrazonal demand retained')
    save(fig,'od_heatmap','Synthetic assumptions; no measured OD; external-external block is zero')
    fig,ax=base('Morning-peak synthetic desire lines: 120 largest interzonal OD\nStraight lines show demand only, not road routes or observed trajectories')
    centres={z.zone_id:(z.centre_x_m,z.centre_y_m) for z in zones.itertuples()}
    centres.update({g.zone_id:(g.geometry.x,g.geometry.y) for g in gateways.itertuples()})
    part=od[od.period.eq('morning_peak') & od.route_status.ne('intrazonal_not_graph_loaded')].nlargest(120,'flow_veh_h')
    for reachable,color in [(True,'#247c9a'),(False,'#bb3e4c')]:
        q=part[part.network_reachable.eq(reachable)]
        if len(q):ax.add_collection(LineCollection([[centres[r.origin_zone],centres[r.destination_zone]] for r in q.itertuples()],colors=color,linewidths=.3+2*q.flow_veh_h.to_numpy()/part.flow_veh_h.max(),alpha=.5,label=f'Routable={reachable}'))
    ax.legend();save(fig,'od_desire_lines','Synthetic gravity/IPF; OSM contributors ODbL 1.0')
    fig,ax=plt.subplots(figsize=(10,7));fig.subplots_adjust(left=.12,right=.95,bottom=.14,top=.87)
    sites.plot(ax=ax,color='#5486a6',markersize=25,label='Address geocodes (unverified)')
    sites[sites.geocoding_warning].plot(ax=ax,color='#bd344c',marker='x',markersize=100,label='Suspicious Dongguan POI')
    zones.to_crs(4326).boundary.plot(ax=ax,color='#666666',linewidth=.2,label='Study zones')
    ax.set_title('45 user-supplied monitoring-station address geocodes\n6 within study boundary; geocodes are not surveyed sensor locations')
    ax.set_xlabel('Longitude (claimed WGS84)');ax.set_ylabel('Latitude (claimed WGS84)');ax.legend()
    save(fig,'user_station_map','User: Shenzhen open-data platform; Amap geocoding; exact dataset URL pending')
    fig,ax=plt.subplots(figsize=(12,5.5));fig.subplots_adjust(left=.08,right=.98,bottom=.23,top=.83)
    for code in sites.loc[sites.within_study,'CZBM']:
        group=levels[levels.CZBM.eq(code)].sort_values('timestamp_raw')
        stamps=pd.to_datetime(group.timestamp_raw);vals=group.water_level_raw.to_numpy(float)
        # Break line across >10min gaps; retain all original observation points.
        x=[];y=[]
        for k,(stamp,value) in enumerate(zip(stamps,vals)):
            if k and (stamp-stamps.iloc[k-1]).total_seconds()>600:x.append(stamp);y.append(np.nan)
            x.append(stamp);y.append(value)
        ax.plot(x,y,linewidth=.8,label=code);ax.scatter(stamps,vals,s=2)
    ax.set_title('Six in-study stations: original water-level samples, 7–8 Sep 2023\nSW unit/zero reference pending; not adopted as road depth')
    ax.set_ylabel('SW raw (summary claims m; unverified)');ax.set_xlabel('Source local timestamp; timezone not supplied')
    ax.legend(fontsize=7,ncol=3);fig.autofmt_xdate()
    save(fig,'user_water_series','User-selected high-water dates; lines broken at gaps >10 min; no interpolation')
    return paths


def run_phase03(root, config_path, user_source=None):
    root=root.resolve();config=load_config(config_path)
    if config['phase']!='03':raise ValueError('Phase 03 configuration required')
    s=config['demand'];network=(root/s['network_directory']).resolve();spatial=(root/s['spatial_directory']).resolve()
    network.relative_to(root);spatial.relative_to(root)
    inputs=[config_path,*sorted((root/'src/uftr').glob('*.py'))]
    inputs+=verify_inventory(root,network.parent/'output_inventory.json',network.parent)
    inputs+=verify_inventory(root,spatial/'output_inventory.json',root)
    with RunArchive(root,config,inputs) as run:
        run.manifest['command']=[sys.executable,*sys.argv]
        snapshot=(root/user_source).resolve() if user_source else root/'data/raw/user_sources'/run.run_id
        snapshot.relative_to(root)
        if not user_source:seal_user_sources(root,config['user_water']['files'],snapshot)
        run.manifest['inputs'].extend({'path':str(p.resolve()),'sha256':file_hash(p)} for p in sorted(snapshot.iterdir()) if p.is_file());run.flush()
        output=root/'data/processed/phase03'/run.run_id;output.mkdir(parents=True,exist_ok=False)
        synthetic=root/'data/synthetic/phase03'/run.run_id;synthetic.mkdir(parents=True,exist_ok=False)
        boundary=gpd.read_file(network/'study_boundary.geojson').to_crs(4326).geometry.iloc[0]
        nodes=gpd.read_file(network/'road_nodes.geojson');edges=gpd.read_file(network/'road_edges.geojson')
        graph=ox.load_graphml(network/'road_network.graphml',edge_dtypes={'free_flow_time_s':float,'length_m':float,'capacity_veh_h':float})
        run.log('build metric zones and conserve retained native population totals')
        zones=make_zones(boundary,s['zone_size_m'])
        population,allocation,pop_quality=allocate_population(zones,spatial/'population_2020_native_1km.tif')
        values,attraction_quality=add_attraction(zones,population,gpd.read_file(spatial/'facilities.geojson'),s['attraction_population_share'],s['facility_weights'])
        linked=connect_zones(zones,nodes,graph,s['max_connector_distance_m'])
        values['active_od']=values.production_share.gt(0)|values.attraction_share.gt(0)
        active=linked[linked.zone_id.isin(values.loc[values.active_od,'zone_id'])].copy()
        gates=boundary_gateways(graph,nodes,boundary,s['boundary_gateways'])
        ext=pd.DataFrame([{'zone_id':g.zone_id,'zone_kind':'external_gateway','node_id':int(g.node_id),'connected':True,'connector_distance_m':0.,'can_depart':graph.out_degree(int(g.node_id))>0,'can_arrive':graph.in_degree(int(g.node_id))>0,'status':'actual_boundary_node','source_kind':'real_node_synthetic_demand'} for g in gates.itertuples()])
        connectors=pd.concat([active,ext],ignore_index=True);connectors['node_id']=connectors.node_id.astype('Int64')
        run.log('compute directed free-flow skims; retain unconnected zone demand')
        times=network_skims(connectors,graph,s['access_speed_kph'],s['intrazonal_time_s'])
        od,targets,trace,periods=build_od(connectors,values,times,s)
        zones.to_crs(4326).to_file(output/'traffic_zones.geojson',driver='GeoJSON')
        gates.to_crs(4326).to_file(output/'boundary_gateways.geojson',driver='GeoJSON')
        for name,frame in [('zone_population',values),('population_allocation',allocation),('all_zone_connectors',linked),('zone_connectors',connectors),('zone_targets',targets),('ipf_trace',trace)]:
            frame.to_csv(output/(name+'.csv'),index=False,encoding='utf-8-sig')
        pd.DataFrame(times,index=connectors.zone_id,columns=connectors.zone_id).rename_axis('origin_zone').to_csv(output/'network_skims.csv',encoding='utf-8-sig')
        od.to_csv(synthetic/'od_all_periods.csv',index=False,encoding='utf-8-sig')
        for period in s['periods']:od[od.period.eq(period)].to_csv(synthetic/('od_'+period+'.csv'),index=False,encoding='utf-8-sig')
        od[od.period.eq('offpeak')].to_csv(synthetic/'od_matrix.csv',index=False,encoding='utf-8-sig')
        od[od.period.ne('offpeak')].to_csv(synthetic/'od_peak.csv',index=False,encoding='utf-8-sig')
        for status,name in [('unreachable_normal_network','unreachable_od'),('intrazonal_not_graph_loaded','intrazonal_od')]:
            od[od.route_status.eq(status)].to_csv(synthetic/(name+'.csv'),index=False,encoding='utf-8-sig')
        run.log('validate user water-level tables without adopting water levels as road depth')
        water,sites,levels=inspect_user_water(snapshot,output/'user_water',boundary,edges,config['user_water']['matching'])
        report={'run_id':run.run_id,'status':'passed_synthetic_demand_and_qualified_water_intake','processed_root':output.relative_to(root).as_posix(),'synthetic_root':synthetic.relative_to(root).as_posix(),'user_source_snapshot':snapshot.relative_to(root).as_posix(),
            'zones':len(zones),'active_internal_zones':len(active),'connected_active_zones':int(active.connected.sum()),'unconnected_active_zones':int((~active.connected).sum()),'boundary_gateways':len(gates),'graph_nodes':graph.number_of_nodes(),'graph_directed_edges':graph.number_of_edges(),
            'population':pop_quality,'attraction':attraction_quality,'periods':periods,'max_ipf_relative_error':float(trace.groupby(['period','block']).tail(1).relative_margin_error.max()),'water_intake':water,
            'limitations':['All OD is synthetic, uncalibrated hourly prototypes, no observed commuting or 24h schedule','Population and emergency POIs are incomplete attraction proxies; sensitivity required','Virtual within-zone access is an assumption, not a verified drivable access route','Intrazonal trips retained separately, not loaded onto graph edges','Disconnected demand remains positive; no graph edges invented','Boundary demand equal shares at actual outside crossing nodes, not measured screenline flows','Water-level SW unit/zero reference and address geocodes not sufficient for road-depth adoption']}
        write_json(output/'demand_report.json',report);write_json(run.path/'raw/demand_report.json',report)
        plots=plot_demand(zones,values,connectors,gates,edges,od,sites,levels,run.path/'figures',run.run_id,config['outputs']['dpi'])
        sources=[output/'demand_report.json',output/'traffic_zones.geojson',output/'zone_population.csv',output/'zone_connectors.csv',synthetic/'od_all_periods.csv',output/'user_water/user_water_levels_all.csv',output/'user_water/user_stations_all.geojson']
        for path in plots:run.add_artifact(path,title=path.stem,kind='figure',data_kind='mixed' if path.stem in ['traffic_zones','user_station_map'] else ('real' if path.stem=='user_water_series' else 'synthetic'),source_paths=sources,units={'flow':'veh/h','distance':'m','water_level':'raw SW; original unit pending'})
        write_json(output/'output_inventory.json',{'run_id':run.run_id,'files':[{'path':p.relative_to(root).as_posix(),'sha256':file_hash(p)} for folder in [output,synthetic] for p in sorted(folder.rglob('*')) if p.is_file()]})
        print(json.dumps(report,ensure_ascii=False),flush=True)
    return run.path
