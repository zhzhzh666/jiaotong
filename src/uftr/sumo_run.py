"""SUMO on actual OSM-derived directed geometry, no deletion of stranded vehicles."""
from pathlib import Path
from collections import Counter
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from .archive import write_json,file_hash
from .research import Experiment


def sumo_binary(name):
    import sumo
    p=Path(sumo.__file__).parent/'bin'/(name+'.exe' if sys.platform=='win32' else name)
    if not p.is_file():raise FileNotFoundError(str(p))
    return p


def build_network(exp,directory):
    """Plain XML preserves our OSM graph's directed edge IDs exactly."""
    nodes=ET.Element('nodes');edges=ET.Element('edges')
    from pyproj import Transformer
    transform=Transformer.from_crs(4326,32650,always_xy=True)
    for node,d in exp.graph.nodes(data=True):
        x,y=transform.transform(d['x'],d['y']);ET.SubElement(nodes,'node',id=str(node),x=str(x),y=str(y),type='priority')
    conversion={}
    from shapely.ops import substring
    for i,row in enumerate(exp.net.edges.itertuples()):
        geom=exp.edges.geometry.iloc[i]
        pieces=[(row.edge_id,str(row.u),str(row.v),geom,row.length_m)]
        if row.u==row.v:
            # SUMO removes a one-edge self-loop. Split the SAME existing curve at its midpoint.
            # This adds a geometry node, not a new road or connection to another component.
            mid=geom.interpolate(.5,normalized=True);node='shape_'+row.edge_id
            ET.SubElement(nodes,'node',id=node,x=str(mid.x),y=str(mid.y),type='priority')
            pieces=[(row.edge_id+'_a',str(row.u),node,substring(geom,0,.5,normalized=True),row.length_m/2),
                (row.edge_id+'_b',node,str(row.v),substring(geom,.5,1,normalized=True),row.length_m/2)]
        conversion[row.edge_id]=[x[0] for x in pieces]
        for edge_id,u,v,shape,length in pieces:
            element=ET.SubElement(edges,'edge',id=edge_id,**{'from':u,'to':v,'numLanes':str(int(row.lanes_per_direction)),
                'speed':str(row.free_flow_speed_kph/3.6),'length':str(length),'shape':' '.join(f'{x},{y}' for x,y,*_ in shape.coords),'allow':'passenger'})
            ET.SubElement(element,'param',key='source.osm_id',value=str(row.osm_id))
            ET.SubElement(element,'param',key='source.edge_id',value=row.edge_id)
    ET.ElementTree(nodes).write(directory/'network.nod.xml',encoding='utf-8',xml_declaration=True)
    ET.ElementTree(edges).write(directory/'network.edg.xml',encoding='utf-8',xml_declaration=True)
    args=[str(sumo_binary('netconvert')),'--node-files',str(directory/'network.nod.xml'),'--edge-files',str(directory/'network.edg.xml'),
        '--output-file',str(directory/'network.net.xml'),'--offset.disable-normalization','true','--no-turnarounds','false','--junctions.corner-detail','0']
    done=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    (directory/'netconvert.log').write_text(done.stdout+'\n'+done.stderr,encoding='utf-8')
    if done.returncode:raise RuntimeError('netconvert failed: '+done.stderr[-1200:])
    import sumolib
    net=sumolib.net.readNet(str(directory/'network.net.xml'))
    actual={e.getID() for e in net.getEdges()};expected={v for values in conversion.values() for v in values}
    mapping=exp.net.edges[['edge_id','u','v','osm_id']].copy();mapping['sumo_edge_id']=mapping.edge_id.map(lambda x:'|'.join(conversion[x]));mapping['present_in_sumo']=mapping.edge_id.map(lambda x:all(v in actual for v in conversion[x]))
    mapping.to_csv(directory/'osm_sumo_mapping.csv',index=False)
    if actual!=expected:raise ValueError(f'netconvert edge mismatch: missing {len(expected-actual)}, unexpected {len(actual-expected)}')
    return net


def generate_plan(exp,net,directory,limit,seed):
    from scipy.sparse.csgraph import dijkstra
    qrows=[]
    for t in range(0,86400,900):
        od=exp.od[exp.period(t)]
        for row in od.itertuples():qrows.append((t,row.origin_node,row.destination_node,row.flow_veh_h*.25,row.route_status))
    rates=np.array([r[3] for r in qrows]);expected=float(rates.sum());count=min(int(round(expected)),limit)
    rng=np.random.default_rng(seed);sample=rng.choice(len(qrows),count,p=rates/rates.sum())
    records=[];route_cache={};graph,lookup=exp.net.graph(exp.net.t0,np.ones(len(exp.net.edges),bool));pred_cache={}
    for i,k in enumerate(sample):
        start,o,d,weight,status=qrows[k];depart=float(start+rng.uniform(0,900));path=None;reason=''
        if status=='intrazonal_not_graph_loaded':reason='intrazonal_not_graph_loaded'
        elif o not in exp.net.node_index or d not in exp.net.node_index:reason='missing_connector'
        else:
            pair=(int(o),int(d))
            if pair not in route_cache:
                origin=exp.net.node_index[o];v=exp.net.node_index[d]
                if origin not in pred_cache:pred_cache[origin]=dijkstra(graph,indices=origin,return_predecessors=True)
                dist,pred=pred_cache[origin];ids=[]
                if np.isfinite(dist[v]):
                    while v!=origin:
                        u=int(pred[v]);ids.append(lookup[u*len(exp.net.nodes)+v]);v=u
                    original_edges=exp.net.edges.edge_id.iloc[ids[::-1]].tolist()
                    mapping=pd.read_csv(directory/'osm_sumo_mapping.csv').set_index('edge_id').sumo_edge_id.to_dict() if 'mapping' not in locals() else mapping
                    candidate=[e for source in original_edges for e in mapping[source].split('|')]
                    # SUMO lane-connection feasibility is stricter than our graph's junction adjacency.
                    valid=all(net.getEdge(a).getConnections(net.getEdge(b)) for a,b in zip(candidate,candidate[1:]))
                    route_cache[pair]=candidate if valid else None
                else:route_cache[pair]=None
            path=route_cache[pair]
            if not path:reason='no_lane_connected_normal_route'
        records.append({'vehicle_id':f'veh_{i:06d}','depart_s':depart,'origin_node':o,'destination_node':d,'normal_route':' '.join(path or []),'status':reason or 'routed'})
    plan=pd.DataFrame(records).sort_values('depart_s');plan.to_csv(directory/'departure_plan.csv',index=False)
    routes=ET.Element('routes');ET.SubElement(routes,'vType',id='car',vClass='passenger',length='5',minGap='2.5',accel='2.6',decel='4.5')
    # Vehicles are inserted by TraCI only after the current route is available.
    # Unavailable departures remain in an explicit external pending queue.
    ET.ElementTree(routes).write(directory/'demand.rou.xml',encoding='utf-8',xml_declaration=True)
    return plan,{'hourly_rate_integral_expected_vehicles':expected,'sampled_total_planned':count,'resource_limit':limit,'sampling_fraction':count/expected,
        'plan_status_counts':plan.status.value_counts().to_dict(),'outside_region_demand_excluded_veh_h':exp.excluded,'shared_departure_plan_sha256':file_hash(directory/'departure_plan.csv')}


def simulate(exp,directory,scenario,selection,effect):
    import traci
    folder=directory/scenario;folder.mkdir();summary=folder/'summary.xml';tripinfo=folder/'tripinfo.xml'
    args=[str(sumo_binary('sumo')),'--net-file',str(directory/'network.net.xml'),'--route-files',str(directory/'demand.rou.xml'),
        '--begin','0','--end','86400','--step-length','1','--seed',str(exp.seed),'--no-step-log','true','--duration-log.disable','true',
        '--time-to-teleport','-1','--max-depart-delay','-1','--tripinfo-output',str(tripinfo),'--tripinfo-output.write-unfinished','true',
        '--summary-output',str(summary),'--collision.action','warn','--error-log',str(folder/'sumo_errors.log'),'--log',str(folder/'sumo.log')]
    label='uftr_'+scenario+'_'+str(time.time_ns());traci.start(args,label=label,stdout=subprocess.DEVNULL);conn=traci.getConnection(label)
    snapshots=[];controls=[];reroute_errors=0;started=time.perf_counter();previous=np.zeros(len(exp.net.edges),bool)
    plan=pd.read_csv(directory/'departure_plan.csv');pending=plan[plan.status.eq('routed')].copy();injections=[]
    conversion=pd.read_csv(directory/'osm_sumo_mapping.csv').set_index('edge_id').sumo_edge_id.to_dict()
    try:
        for ti,t in enumerate(exp.times[:-1]):
            depth=np.zeros(len(exp.net.edges)) if scenario=='normal' else exp.depths['extreme'][ti]
            t0,cap,closed=exp.state(depth,effect if scenario=='optimized' else 0,selection if scenario=='optimized' else [])
            wet=np.flatnonzero((depth>0)|previous|closed)
            for i in wet:
                for edge in conversion[exp.net.edges.edge_id.iloc[i]].split('|'):
                    conn.edge.setAllowed(edge,[] if closed[i] else ['passenger'])
                    if closed[i]:conn.edge.setDisallowed(edge,['passenger'])
                    speed=.1 if closed[i] else exp.net.edges.length_m.iloc[i]/t0[i]
                    conn.edge.setMaxSpeed(edge,max(.1,float(speed)))
            if scenario!='normal':
                for vid in conn.vehicle.getIDList():
                    try:conn.vehicle.rerouteTraveltime(vid,currentTravelTimes=True)
                    except traci.TraCIException:reroute_errors+=1 # retain the vehicle and its current route
            injected=[]
            blocked_ids={e for i in np.flatnonzero(closed) for e in conversion[exp.net.edges.edge_id.iloc[i]].split('|')}
            for row in pending[pending.depart_s<float(t+900)].itertuples():
                original=row.normal_route.split();source=original[0];target=original[-1]
                if source in blocked_ids or target in blocked_ids:continue
                route=conn.simulation.findRoute(source,target,vType='car',depart=max(float(t+1),row.depart_s))
                if not route.edges:continue
                route_id='route_'+row.vehicle_id;conn.route.add(route_id,route.edges)
                conn.vehicle.add(row.vehicle_id,route_id,typeID='car',depart=str(max(float(t+1),row.depart_s)),departLane='best',departSpeed='max')
                injections.append({'vehicle_id':row.vehicle_id,'planned_depart_s':row.depart_s,'requested_actual_depart_s':max(float(t+1),row.depart_s),'external_queue_delay_s':max(0,float(t+1)-row.depart_s)})
                injected.append(row.Index)
            pending=pending.drop(index=injected)
            controls.append({'time_s':t,'closed_edges':int(closed.sum()),'running':conn.vehicle.getIDCount()})
            conn.simulationStep(float(t+900))
            if int(t)%21600==0:
                for vid in conn.vehicle.getIDList():
                    x,y=conn.vehicle.getPosition(vid);snapshots.append({'time_s':float(t+900),'vehicle_id':vid,'x_m':x,'y_m':y})
            previous=(depth>0).copy()
    finally:conn.close()
    steps=pd.DataFrame([x.attrib for x in ET.parse(summary).getroot().findall('step')]);last=steps.iloc[-1]
    trips=pd.DataFrame([x.attrib for x in ET.parse(tripinfo).getroot().findall('tripinfo')])
    departed=int(float(last.get('inserted',0)));arrived=int(float(last.get('ended',0)));running=int(float(last.get('running',0)));waiting=int(float(last.get('waiting',0)))
    # Summary teleports are per-step events, never silently dropped or counted as completions.
    teleport=sum(float(x) for x in steps.get('teleports',pd.Series([0.])))
    pd.DataFrame(controls).to_csv(folder/'controls.csv',index=False);pd.DataFrame(snapshots).to_csv(folder/'vehicle_snapshots.csv',index=False)
    pd.DataFrame(injections).to_csv(folder/'injection_log.csv',index=False)
    durations=pd.to_numeric(trips.get('duration',pd.Series(dtype=float)),errors='coerce');arrivals=pd.to_numeric(trips.get('arrival',pd.Series(dtype=float)),errors='coerce')
    complete=durations[arrivals>=0]
    return {'scenario':scenario,'departed':departed,'arrived':arrived,'running_at_end':running,'waiting_to_depart_at_end':waiting+len(pending),
        'external_pending_at_end':len(pending),'external_queue_delay_s':float(sum(i['external_queue_delay_s'] for i in injections)),
        'teleport_events':int(teleport),'reroute_errors_retained':reroute_errors,'completed_mean_travel_time_s':float(complete.mean()) if len(complete) else None,
        'total_waiting_time_s':float(pd.to_numeric(trips.get('waitingTime',pd.Series(dtype=float)),errors='coerce').sum()),
        'elapsed_s':time.perf_counter()-started,'vehicle_balance_departed_minus_arrived_running':departed-arrived-running}


def run_sumo(root,config,run):
    s=config['research'];settings=config['sumo'];selection_path=root/settings['selection']
    selection=json.loads(selection_path.read_text(encoding='utf-8'))['selected'];reports=[]
    for region in settings['regions']:
        exp=Experiment(root,s,config['seed'],region=region);directory=run.path/'raw'/region;directory.mkdir()
        net=build_network(exp,directory);plan,planning=generate_plan(exp,net,directory,settings['vehicle_limit'][region],config['seed'])
        local_selection=selection
        if region=='nanshan':
            # Small-network road choices do not apply to Nanshan. Use actual small selected OSM arc IDs
            # intersecting full risk mapping; no claim of full-city optimality.
            small=Experiment(root,s,config['seed']);selected_edges={small.net.edges.edge_id.iloc[i] for road in selection for i in small.candidate_groups[road]}
            local_selection=[road for road,ids in exp.candidate_groups.items() if any(exp.net.edges.edge_id.iloc[i] in selected_edges for i in ids)]
        for scenario in ['normal','disaster','optimized']:
            result=simulate(exp,directory,scenario,local_selection,s['effect']);result.update(region=region,**planning)
            result['unrouted_planned']=int(plan.status.ne('routed').sum());result['selected_road_groups']=local_selection
            routed=int(plan.status.eq('routed').sum());result['routed_plan_balance']=routed-result['arrived']-result['running_at_end']-result['waiting_to_depart_at_end']
            if result['routed_plan_balance']!=0 or result['vehicle_balance_departed_minus_arrived_running']!=0:raise ValueError('SUMO vehicle accounting failed')
            reports.append(result);print(f'SUMO {region}/{scenario}: '+json.dumps(result),flush=True)
        pd.DataFrame(reports).to_csv(run.path/'raw/sumo_comparison.csv',index=False)
    plot_sumo(run,reports)
    return {'results':reports,'sumo_version':subprocess.check_output([str(sumo_binary('sumo')),'--version'],text=True).splitlines()[0],
        'mapping':'plain XML from actual OSM-derived directed MultiDiGraph, exact edge IDs, projected geometry; SUMO generates junction/lane connections',
        'limitations':['No measured signal plans, turn restrictions, lane-level geometry or calibrated car following','BPR capacity was not assigned as SUMO capacity','Full Nanshan SUMO is a resource-limited fixed OD sample; unrouted/intrazonal plans are retained in counts','Nanshan optimized scenario uses only overlap of the small optimized physical roads with full-risk arcs; it is not a Nanshan optimization result']}


def plot_sumo(run,reports):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    table=pd.DataFrame(reports);fig,axes=plt.subplots(1,len(table.region.unique()),figsize=(12,5),layout='constrained',squeeze=False)
    for ax,(region,q) in zip(axes.ravel(),table.groupby('region')):
        bottom=np.zeros(len(q))
        for name in ['arrived','running_at_end','waiting_to_depart_at_end','unrouted_planned']:
            ax.bar(q.scenario,q[name],bottom=bottom,label=name);bottom+=q[name].to_numpy()
        ax.set(title=region+' | fixed sampled departure plan',ylabel='Vehicles, all planned outcomes');ax.legend(fontsize=7)
    p=run.path/'figures/sumo_vehicle_accounting.png';fig.savefig(p,dpi=160);plt.close(fig)
    run.add_artifact(p,title='SUMO固定发车计划与全部车辆去向',kind='figure',data_kind='mixed',source_paths=[run.path/'raw/sumo_comparison.csv'])
    # Actual vehicle states from the simulator, plotted on source road geometry.
    for region in table.region.unique():
        data=run.path/'raw'/region/'disaster/vehicle_snapshots.csv'
        if not data.is_file() or data.stat().st_size<20:continue
        try:q=pd.read_csv(data)
        except pd.errors.EmptyDataError:continue
        if q.empty:continue
        from .assignment import load_osm
        import geopandas as gpd
        config=json.loads((run.path/'config.json').read_text());roads=gpd.read_file(run.project_root/config['research']['network_root']/region/'road_edges.geojson').to_crs(32650)
        t=q.groupby('time_s').size().idxmax();q=q[q.time_s.eq(t)]
        fig,ax=plt.subplots(figsize=(9,7),layout='constrained');roads.plot(ax=ax,color='#aebcc5',linewidth=.4);ax.scatter(q.x_m,q.y_m,s=8,c='#d33e43')
        ax.set_title(f'Actual SUMO vehicle positions | {region} | t={t/3600:g} h');ax.ticklabel_format(style='plain',useOffset=False)
        p=run.path/'figures'/f'sumo_vehicles_{region}.png';fig.savefig(p,dpi=140);plt.close(fig)
        run.add_artifact(p,title=f'SUMO实际车辆状态 {region}',kind='figure',data_kind='mixed',source_paths=[data],simulation_time_s=float(t))
