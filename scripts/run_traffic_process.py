"""Reassign the frozen synthetic OD and road process, with exact-state checkpoints."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
from hashlib import sha256
import argparse
import json
import shutil
import time
import traceback
import zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from uftr.assignment import load_osm,result_summary
from uftr.resilience import evaluate_metrics
from uftr.traffic_process import validate_profile,interval_od,state_arrays,integrate_intervals,congestion_fraction

ROOT=Path(__file__).resolve().parents[1]
LABELS={'normal':'正常','general':'一般100 mm','severe':'严重200 mm','extreme':'极端300 mm'}
COLORS={'normal':'#71808A','general':'#4B8CAA','severe':'#E39A35','extreme':'#BE4058'}


def sha(p):return sha256(p.read_bytes()).hexdigest()


def write(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,
        default=lambda v:v.item() if isinstance(v,np.generic) else str(v))+'\n',encoding='utf-8')


def assert_frozen(base,names):
    manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    items={r['path']:r for r in manifest['outputs']}
    for name in names:
        assert sha(base/name)==items[name]['sha256'],name


def prepare_access(cfg,graph,connectors):
    s=cfg['metrics'];pop=pd.read_csv(ROOT/cfg['population'])
    origins=pd.read_csv(connectors,dtype={'node_id':'Int64'}).merge(
        pop[['zone_id','population_estimate']],on='zone_id',how='outer',validate='one_to_one')
    assert len(origins)==len(pop) and origins.population_estimate.notna().all()
    origins['access_time_s']=origins.connector_distance_m.fillna(0)*3.6/s['access_speed_kph']
    efficiency=sorted(set(origins.node_id.dropna().astype(int)))
    efficiency=efficiency[::max(1,int(np.ceil(len(efficiency)/s['efficiency_sample_origins'])))]
    nodes=gpd.GeoDataFrame({'node_id':list(graph.nodes)},geometry=gpd.points_from_xy(
        [graph.nodes[n]['x'] for n in graph],[graph.nodes[n]['y'] for n in graph]),crs=4326).to_crs(32650)
    fac=gpd.read_file(ROOT/cfg['facilities']).to_crs(32650)
    distance,idx=cKDTree(np.array([(p.x,p.y) for p in nodes.geometry])).query(np.array([(p.x,p.y) for p in fac.geometry]))
    fac['node_id']=nodes.node_id.to_numpy()[idx];fac['snap_distance_m']=distance
    fac['access_time_s']=distance*3.6/s['access_speed_kph']
    return origins,fac[distance<=s['facility_max_snap_m']].copy(),fac[distance>s['facility_max_snap_m']].copy(),efficiency


def run(config_path,resume=None):
    started=time.perf_counter();config_path=config_path.resolve();cfg=yaml.safe_load(config_path.read_text(encoding='utf-8'))
    assert cfg['case']=='baseline' and cfg['scenarios']==list(LABELS) and cfg['workers']==1
    package=ROOT/cfg['source_package'];road=ROOT/cfg['road_process'];network_path=ROOT/cfg['network_directory']
    names=['demand/od_all_periods_long.csv','demand/departure_profile_15min.csv','demand/od_15min_expected_vehicles.npz',
        'demand/zone_index.csv','gis/all_zone_connectors.csv']
    assert_frozen(package,names);assert_frozen(road,['raw/road_state_timeseries.parquet'])
    road_manifest=json.loads((road/'manifest.json').read_text(encoding='utf-8'))
    road_inputs={i['path']:i['sha256'] for i in road_manifest['inputs']}
    for p in [network_path/'road_network.graphml',network_path/'road_edges.geojson']:
        assert sha(p)==road_inputs[p.relative_to(ROOT).as_posix()]
    paths=[config_path,Path(__file__).resolve(),*[ROOT/'src/uftr'/n for n in ['traffic_process.py','assignment.py','resilience.py']],
        package/'manifest.json',road/'manifest.json',*[package/n for n in names],road/'raw/road_state_timeseries.parquet',
        network_path/'road_network.graphml',network_path/'road_edges.geojson',ROOT/cfg['population'],ROOT/cfg['facilities']]
    inputs=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in paths]
    if resume:
        out=resume.resolve();out.relative_to(ROOT/'data/synthetic/traffic_evaluation')
        previous=json.loads((out/'run_metadata.json').read_text(encoding='utf-8'))
        assert previous['inputs']==inputs,'resume requires exact original inputs and source bytes'
        if (out/'manifest.json').exists():raise ValueError('completed run cannot be resumed or overwritten')
    else:
        name=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%dT%H%M%S')+'_traffic_process_'+uuid4().hex[:8]
        out=ROOT/'data/synthetic/traffic_evaluation'/name;out.mkdir(parents=True,exist_ok=False)
        for folder in ['raw/states','raw/od_service','raw/accessibility','raw/traces','figures','provenance']:(out/folder).mkdir(parents=True)
        for p in paths[:5]:shutil.copy2(p,out/'provenance'/('config.yaml' if p.suffix=='.yaml' else p.name))
        write(out/'run_metadata.json',{'run_id':name,'inputs':inputs,'traffic_assignment_rerun':True,'observed':False})
    print('RUN '+out.relative_to(ROOT).as_posix(),flush=True)
    try:
        net,graph=load_osm(network_path)
        profile=pd.read_csv(package/names[1]);validate_profile(profile)
        source_od=pd.read_csv(package/names[0],dtype={'origin_node':'Int64','destination_node':'Int64'})
        od_base={p:f.reset_index(drop=True) for p,f in source_od.groupby('period')}
        archive=np.load(package/names[2],allow_pickle=False);zone_ids=archive['zone_ids'].astype(str)
        trips=archive['expected_vehicles'];assert trips.shape==(96,len(zone_ids),len(zone_ids))
        matrix_error=0.
        for row in profile.itertuples():
            q=interval_od(od_base[row.base_period],row.rate_multiplier)
            matrix=q.pivot(index='origin_zone',columns='destination_zone',values='flow_veh_h').reindex(index=zone_ids,columns=zone_ids).fillna(0).to_numpy()
            matrix_error=max(matrix_error,float(np.max(np.abs(matrix*.25-trips[row.interval_index]))))
            assert np.allclose(matrix*.25,trips[row.interval_index],rtol=1e-10,atol=1e-10)
            assert np.isclose(q.flow_veh_h.sum(),row.total_rate_veh_h,rtol=1e-12)
        del archive,trips,matrix
        source=pd.read_parquet(road/'raw/road_state_timeseries.parquet')
        source=source[source.case.eq(cfg['case'])]
        assert len(source)==4*97*54 and not source.duplicated(['scenario','time_s','edge_id']).any()
        states={(s,int(t)):f for (s,t),f in source.groupby(['scenario','time_s'])}
        baseline_state=state_arrays(net,states['normal',0])
        origins,fac,rejected,efficiency=prepare_access(cfg,graph,package/'gis/all_zone_connectors.csv')
        origins.to_csv(out/'raw/population_origins.csv',index=False,encoding='utf-8-sig')
        fac.drop(columns='geometry').to_csv(out/'raw/facility_connections.csv',index=False,encoding='utf-8-sig')
        rejected.drop(columns='geometry').to_csv(out/'raw/facility_rejections.csv',index=False,encoding='utf-8-sig')
        cache={};normal={};rows=[];cache_hits=0;new_solves=0

        def evaluate(q,state,baseline=None):
            nonlocal cache_hits,new_solves
            t0,cap,closed=state
            token=sha256(q.flow_veh_h.to_numpy(float).tobytes()+t0.tobytes()+cap.tobytes()+closed.tobytes()).hexdigest()
            if token in cache:cache_hits+=1;return cache[token]
            record=out/'raw/states'/f'{token}.json'
            if record.exists():
                saved=json.loads(record.read_text(encoding='utf-8'))
                for p in saved['artifacts']:assert sha(out/p['path'])==p['sha256']
                cache[token]=saved;cache_hits+=1;return saved
            print(f'SOLVE {len(cache)+1} demand={q.flow_veh_h.sum():.3f} closed={closed.sum()}',flush=True)
            a=cfg['assignment'];r=net.solve(q,t0=t0,capacity=cap,closed=closed,tolerance=a['gap_target'],
                max_iterations=a['max_iterations'],alpha=a['bpr_alpha'],beta=a['bpr_beta'])
            if not r.converged:raise RuntimeError(f'UE did not converge: {r.relative_gap}')
            assert r.node_balance_max_error<1e-5 and np.all(r.flow[closed]==0)
            assert np.isclose(r.served_veh_h+r.unserved_veh_h+r.intrazonal_veh_h,r.total_veh_h,rtol=1e-12)
            m,access=evaluate_metrics(net,r,closed,origins,fac,efficiency,baseline,
                cfg['metrics']['rho_s'],cfg['metrics']['weights'])
            m['congested_open_edge_fraction']=congestion_fraction(r.flow,cap,closed)
            m['closed_edges']=int(closed.sum());m['source_kind']='synthetic_OD_road_UE';m['observed']=False
            state_file=out/'raw/states'/f'{token}.parquet'
            pd.DataFrame({'edge_id':net.edges.edge_id,'flow_veh_h':r.flow,'travel_time_s':r.time,
                'free_flow_time_s':t0,'effective_capacity_veh_h':cap,'closed':closed,
                'volume_capacity_ratio':np.divide(r.flow,cap,out=np.zeros(len(cap)),where=cap>0)}).to_parquet(state_file,index=False)
            service=q[['origin_zone','destination_zone','origin_node','destination_node','flow_veh_h','route_status']].copy()
            service['served_network']=r.od_served;service['shortest_network_time_s']=r.od_cost_s
            service.to_parquet(out/'raw/od_service'/f'{token}.parquet',index=False)
            access.to_parquet(out/'raw/accessibility'/f'{token}.parquet',index=False)
            r.trace.to_csv(out/'raw/traces'/f'{token}.csv',index=False)
            files=[state_file,out/'raw/od_service'/f'{token}.parquet',out/'raw/accessibility'/f'{token}.parquet',out/'raw/traces'/f'{token}.csv']
            saved={'state_id':token,'metrics':m,'assignment':result_summary(r),
                'artifacts':[{'path':p.relative_to(out).as_posix(),'sha256':sha(p)} for p in files]}
            write(record,saved);cache[token]=saved;new_solves+=1
            print(f'DONE gap={r.relative_gap:.3g} iterations={len(r.trace)-1} seconds={r.elapsed_s:.1f}',flush=True)
            return saved

        for p in profile[['base_period','rate_multiplier']].drop_duplicates().itertuples(index=False):
            normal[p.base_period,float(p.rate_multiplier)]=evaluate(interval_od(od_base[p.base_period],p.rate_multiplier),baseline_state)
        for scenario in cfg['scenarios']:
            for row in profile.itertuples():
                q=interval_od(od_base[row.base_period],row.rate_multiplier)
                b=normal[row.base_period,float(row.rate_multiplier)]
                state=state_arrays(net,states[scenario,int(row.start_hour*3600)])
                current=evaluate(q,state,b['metrics'])
                rows.append({'scenario':scenario,'interval_index':row.interval_index,'start_hour':row.start_hour,
                    'end_hour':row.end_hour,'duration_hours':row.duration_hours,'period':row.base_period,
                    'rate_multiplier':row.rate_multiplier,'state_id':current['state_id'],'baseline_state_id':b['state_id'],**current['metrics']})
                pd.DataFrame(rows).to_csv(out/'raw/interval_metrics.checkpoint.csv',index=False,encoding='utf-8-sig')
                write(out/'progress.json',{'status':'running','completed_intervals':len(rows),'total_intervals':384,
                    'unique_solved_states':len(cache),'new_solves_this_invocation':new_solves,'cache_hits':cache_hits,
                    'scenario':scenario,'interval_index':row.interval_index,'elapsed_s_this_invocation':time.perf_counter()-started})
            print(f'SCENARIO {scenario} finished, {len(rows)}/384 intervals',flush=True)
        frame=pd.DataFrame(rows);frame.to_csv(out/'raw/interval_metrics.csv',index=False,encoding='utf-8-sig')
        totals=[]
        for scenario,part in frame.groupby('scenario',sort=False):
            part=part.sort_values('interval_index');r={k:integrate_intervals(profile,part[k]) for k in ['Qs','Qp','Qf','Q']}
            totals.append({'scenario':scenario,'R':r['Q'],'Rs':r['Qs'],'Rp':r['Qp'],'Rf':r['Qf'],
                **{k.replace('_veh_h','_vehicles'):float(np.dot(part[k],part.duration_hours)) for k in ['served_veh_h','unserved_veh_h','intrazonal_veh_h','total_veh_h']},
                'minimum_Q':float(part.Q.min()),'minimum_Q_hour':float(part.loc[part.Q.idxmin(),'start_hour']),
                'maximum_unserved_rate_veh_h':float(part.unserved_veh_h.max()),'max_closed_edges':int(part.closed_edges.max())})
        totals=pd.DataFrame(totals);totals.to_csv(out/'raw/scenario_summary.csv',index=False,encoding='utf-8-sig')
        solvers=pd.DataFrame([{'state_id':v['state_id'],**v['assignment']} for v in cache.values()])
        solvers.to_csv(out/'raw/assignment_summary.csv',index=False,encoding='utf-8-sig')
        demand_error=float(np.max(np.abs(totals.served_vehicles+totals.unserved_vehicles+totals.intrazonal_vehicles-totals.total_vehicles)))
        checks={'frozen_inputs_verified':True,'OD_96_matrices_replayed':matrix_error<1e-9,
            'all_384_intervals':len(frame)==384,'same_demand_across_scenarios':frame.groupby('interval_index').total_veh_h.nunique().eq(1).all(),
            'all_unique_assignments_converged':solvers.converged.all(),'maximum_gap_target':solvers.relative_gap.max()<=cfg['assignment']['gap_target'],
            'node_flow_conservation':solvers.node_balance_max_error.max()<1e-5,'daily_demand_accounting':demand_error<1e-6,
            'daily_trips_match_profile':np.allclose(totals.total_vehicles,profile.expected_vehicles_interval.sum(),rtol=1e-12),
            'normal_Q_is_one':np.allclose(frame.loc[frame.scenario.eq('normal'),['Qs','Qp','Qf','Q']],1,rtol=0,atol=1e-12),
            'closed_arcs_carry_no_flow':True,'population_denominator_retained':len(origins)==568,
            'positive_intra_and_unserved_retained':(totals.intrazonal_vehicles>0).all() and (totals.unserved_vehicles>0).all(),
            'metrics_finite':np.isfinite(frame[['Qs','Qp','Qf','Q','total_cost_veh_s_h']]).all().all()}
        assert all(checks.values()),checks
        report={'run_id':out.name,'source_kind':'synthetic','observed':False,'traffic_assignment_rerun':True,
            'case':cfg['case'],'intervals_per_scenario':96,'road_depth_endpoints':97,'metric_rows':len(frame),
            'network_nodes':len(net.nodes),'directed_edges':len(net.edges),'OD_zones_in_full_matrix':len(zone_ids),
            'OD_rows_per_base_period':{k:len(v) for k,v in od_base.items()},'unique_solved_states':len(cache),'cache_hits':cache_hits,
            'max_gap':float(solvers.relative_gap.max()),'max_node_balance_error':float(solvers.node_balance_max_error.max()),
            'sum_assignment_seconds':float(solvers.elapsed_s.sum()),'OD_matrix_replay_max_error_vehicles':matrix_error,
            'daily_accounting_max_error_vehicles':demand_error,'population_denominator':float(origins.population_estimate.sum()),
            'efficiency_sample_origins':len(efficiency),'facility_counts':fac.category.value_counts().to_dict(),
            'facility_rejections':len(rejected),'scenario_summary':totals.to_dict('records'),
            'integration':'96 left-endpoint hold intervals, duration-weighted mean of Q over 24 h; same-interval dry-road baseline',
            'checks':checks,'check_count':len(checks),'all_checks_passed':True,
            'limits':['Synthetic uncalibrated OD and inundation; 54 exposed directed edges, 40051 assumed original',
                'Static UE per departure interval; no queue carryover, no full dynamic traffic assignment',
                'Time efficiency uses fixed sampled origins; missing shelters not invented',
                'New 96-interval integral differs from historical 97-endpoint trapezoid; old results not directly substituted',
                'No full Nanshan mitigation optimization or new SUMO run in this evaluation']}
        write(out/'provenance/validation_report.json',report)
        plot(out,frame,totals,cfg,network_path)
        documentation(out,report)
        assert all(sha(ROOT/i['path'])==i['sha256'] for i in inputs),'input changed during run'
        write(out/'progress.json',{'status':'complete','completed_intervals':384,'unique_solved_states':len(cache)})
        files=sorted(p for p in out.rglob('*') if p.is_file())
        write(out/'manifest.json',{'run_id':out.name,'status':'success','source_kind':'synthetic','observed':False,
            'traffic_assignment_rerun':True,'inputs':inputs,'outputs':[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]})
        with zipfile.ZipFile(out.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(out.parent))
        print(json.dumps({'path':out.relative_to(ROOT).as_posix(),'results':report['scenario_summary'],'checks':len(checks)},ensure_ascii=False),flush=True)
        return out
    except Exception:
        stamp=datetime.now().strftime('%Y%m%dT%H%M%S')
        (out/'provenance'/f'error_{stamp}.txt').write_text(traceback.format_exc(),encoding='utf-8');raise


def plot(out,frame,totals,cfg,network_path):
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':11,'svg.fonttype':'none'})
    charts=[]
    for file,fields in [('traffic_resilience_process',[('Q','综合交通性能 Q'),('mean_served_network_time_s','已服务出行平均道路时间 s')]),
                        ('traffic_demand_process',[('unserved_veh_h','未服务需求 veh/h'),('congested_open_edge_fraction','开放道路中 v/c > 0.9 比例')])]:
        fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
        for ax,(field,title) in zip(axes,fields):
            series=[]
            for scenario,color in COLORS.items():
                part=frame[frame.scenario.eq(scenario)].sort_values('interval_index')
                x=np.r_[part.start_hour,24.];y=np.r_[part[field],part[field].iloc[-1]]
                ax.step(x,y,where='post',label=LABELS[scenario],color=color)
                series.append({'name':LABELS[scenario],'x':part.start_hour.tolist(),'y':part[field].tolist(),'color':color})
            ax.set_ylabel(title);ax.grid(alpha=.2);charts.append({'title':title,'unit':title,'series':series})
        axes[0].legend(ncol=4);axes[1].set_xlabel('相对情景起点 小时');axes[1].set_xlim(0,24)
        fig.suptitle('南山合成情景 时片用户均衡与交通评估')
        fig.text(.07,.015,'96个15分钟出发区间；使用区间起点道路状态与同需求正常基准。合成且未标定，时片之间不传递排队。',fontsize=10)
        fig.tight_layout(rect=(0,.05,1,.94));save(fig,out,file)
    write(out/'raw/native_chart_data.json',charts)
    roads=gpd.read_file(network_path/'road_edges.geojson').to_crs(32650)
    fig,axes=plt.subplots(1,3,figsize=(15,7));x0,y0,x1,y1=roads.total_bounds
    for ax,scenario in zip(axes,['general','severe','extreme']):
        row=frame[frame.scenario.eq(scenario)&frame.start_hour.eq(cfg['map_hour'])].iloc[0]
        state=pd.read_parquet(out/'raw/states'/f'{row.state_id}.parquet')
        baseline=pd.read_parquet(out/'raw/states'/f'{row.baseline_state_id}.parquet')
        state['delta_flow_veh_h']=state.flow_veh_h-baseline.flow_veh_h
        merged=roads.merge(state,on='edge_id',validate='one_to_one')
        roads.plot(ax=ax,color='#D4DDE0',linewidth=.25)
        changed=merged[merged.delta_flow_veh_h.abs()>1.]
        if len(changed):changed.plot(ax=ax,column='delta_flow_veh_h',cmap='RdBu_r',vmin=-100,vmax=100,linewidth=1.1,legend=False)
        blocked=merged[merged.closed]
        if len(blocked):blocked.plot(ax=ax,color='#211B2B',linewidth=2.2)
        ax.set_xlim(x0-300,x1+300);ax.set_ylim(y0-300,y1+300);ax.set_axis_off()
        ax.set_title(LABELS[scenario]+f'\nQ={row.Q:.6f}  封闭{row.closed_edges}条')
    sm=plt.cm.ScalarMappable(norm=plt.Normalize(-100,100),cmap='RdBu_r')
    fig.colorbar(sm,ax=axes.tolist(),fraction=.018,pad=.015,label='相对同需求正常基准流量变化 veh/h（色标截至±100）')
    fig.suptitle(f'南山道路分配流量变化 {cfg["map_hour"]}小时')
    fig.text(.05,.035,'黑色为关闭有向边，彩色显示流量变化绝对值超过1 veh/h的道路。方向与平行边独立计算，几何可能重叠。',fontsize=10)
    fig.text(.05,.008,'真实OSM路网上的合成OD与积水实验，未实测校准。© OpenStreetMap contributors ODbL 1.0',fontsize=10)
    fig.subplots_adjust(left=.015,right=.88,bottom=.11,top=.87,wspace=.08);save(fig,out,'traffic_flow_change_map')


def save(fig,out,name):
    for ext in ['png','svg']:fig.savefig(out/'figures'/f'{name}.{ext}',dpi=170)
    plt.close(fig)


def documentation(out,report):
    text='# 南山合成积水与OD交通评估\n\n'+report['integration']+'。\n\n'
    text+='四情景使用完整574×574矩阵的非零OD长表（每时段58528对）；零需求分区在原矩阵/zone_index保留。96个矩阵逐个重放，区间车次除以0.25才是veh/h，未删区内或不可达需求。568个人口区全部保留，可达性分母不删除未接入人口。\n\n'
    text+='每个区间使用已冻结道路状态，正常基准使用完全相同OD。BPR与Frank–Wolfe重新分配，关闭弧不加入最短路图且流量为0。有向平行边独立保留。相同OD和全部道路状态的字节哈希相同时才复用结果，不近似相邻时片。\n\n'
    text+='R=ΣQ[k]Δt/24，采用区间起点保持，与历史97端点梯形积分定义不同。时片间不传递队列，不是完整动态分配。Qs/Qp/Qf沿用项目定义和权重，未服务惩罚14400秒、区内300秒，缺失避难所不补造。v/c使用本时片退化后的容量。\n\n'
    text+='raw/interval_metrics.csv为384区间指标，scenario_summary.csv为R及全天需求去向，assignment_summary.csv为独立求解检查；states保留每次独立求解的边流量/时间/容量/封闭状态，od_service保留逐OD服务与最短路时间，accessibility保留人口区可达性，traces保留迭代过程。state_id与baseline_state_id可追溯同需求正常基准。\n\n'
    text+='中断后可用原配置和--resume 当前目录继续，严格要求全部原输入/源码SHA一致；完整成功运行禁止覆盖。源码、配置、manifest、ZIP和PNG/SVG均保留。\n\n'
    text+='\n'.join('- '+s for s in report['limits'])+'\n'
    (out/'README.md').write_text(text,encoding='utf-8')
    cards=''.join(f'<h2>{p.stem}</h2><img src="figures/{p.name}" style="width:100%">' for p in sorted((out/'figures').glob('*.png')))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>南山合成情景交通评估</title><body style="font-family:Microsoft YaHei;max-width:1200px;margin:30px auto"><h1>交通流重分配与韧性</h1><p>合成且未经实测标定，96时片独立UE，非完整动态分配</p>'+cards+'</body>',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'configs/traffic_process.yaml');p.add_argument('--resume',type=Path)
    args=p.parse_args();run(args.config,args.resume)
