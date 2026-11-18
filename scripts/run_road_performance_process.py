"""Apply speed/capacity/closure models to the frozen rainfall-driven depths."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
from hashlib import sha256
import argparse
import json
import shutil
import zipfile
import traceback
import numpy as np
import pandas as pd
import geopandas as gpd
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from uftr.flood import road_response
from uftr.road_performance import evaluate_depth_rows,network_snapshot,traversable_edges,closure_episodes,graphml_edge_identities

ROOT=Path(__file__).resolve().parents[1]
NAMES={'normal':'正常','general':'一般100 mm','severe':'严重200 mm','extreme':'极端300 mm'}
COLORS={'general':'#4B8CAA','severe':'#E39A35','extreme':'#BE4058'}


def sha(path):return sha256(path.read_bytes()).hexdigest()


def build(config_path):
    config_path=config_path.resolve();cfg=yaml.safe_load(config_path.read_text(encoding='utf-8'))
    source=ROOT/cfg['source_process'];package=ROOT/cfg['source_package'];settings=cfg['settings']
    name=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%dT%H%M%S')+'_road_performance_'+uuid4().hex[:8]
    out=ROOT/'data/synthetic/road_performance'/name;out.mkdir(parents=True,exist_ok=False)
    for folder in ['raw','figures','provenance']:(out/folder).mkdir()
    try:
        paths=[config_path,Path(__file__).resolve(),ROOT/'src/uftr/road_performance.py',ROOT/'src/uftr/flood.py',
            source/'manifest.json',source/'raw/point_depth_timeseries.parquet',
            package/'gis/point_road_candidates.csv',package/'flood/edge_depth_timeseries.parquet',ROOT/cfg['edges'],ROOT/cfg['boundary'],ROOT/cfg['graphml']]
        frozen=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
        reference={r['path']:r['sha256'] for r in frozen['outputs']}
        assert sha(paths[5])==reference['raw/point_depth_timeseries.parquet']
        original=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
        for p in paths[6:8]:assert sha(p)==next(r['sha256'] for r in original['outputs'] if r['path']==p.relative_to(package).as_posix())
        for p in paths[:4]:shutil.copy2(p,out/'provenance'/('config.yaml' if p.suffix=='.yaml' else p.name))
        points=pd.read_parquet(paths[5]);mapping=pd.read_csv(paths[6]);edges=gpd.read_file(paths[8]);boundary=gpd.read_file(paths[9])
        identities=graphml_edge_identities(paths[10])
        assert set(identities.edge_id)==set(edges.edge_id)
        edges=edges.merge(identities,on='edge_id',validate='one_to_one',sort=False)
        mapping=mapping.loc[mapping.selected_geometry.eq(True)&mapping.edge_id.notna(),['point_id','edge_id']].drop_duplicates()
        linked=points.merge(mapping,on='point_id',how='inner',validate='many_to_many')
        depth=linked.groupby(['case','scenario','time_h','edge_id'],sort=True,as_index=False).depth_m.max()
        depth['time_s']=(depth.time_h*3600).round().astype(int)
        baseline=depth[depth.case.eq('baseline')].merge(pd.read_parquet(paths[7])[['scenario','time_s','edge_id','depth_m']],
            on=['scenario','time_s','edge_id'],validate='one_to_one',suffixes=('_new','_old'))
        replay=float((baseline.depth_m_new-baseline.depth_m_old).abs().max())
        result=evaluate_depth_rows(edges,depth,settings)
        result['source_kind']='synthetic_depth_road_response';result['observed']=False
        result.to_parquet(out/'raw/road_state_timeseries.parquet',index=False)
        depth.to_parquet(out/'raw/edge_depth_timeseries.parquet',index=False)
        affected=edges[edges.edge_id.isin(depth.edge_id.unique())]
        summary=result.groupby(['case','scenario','time_h','time_s'],as_index=False).agg(
            closed_edges=('closed','sum'),light_edges=('state',lambda x:int(x.eq('light').sum())),
            heavy_edges=('state',lambda x:int(x.eq('heavy').sum())),normal_listed_edges=('state',lambda x:int(x.eq('normal').sum())),
            retained_capacity_sum_54=('capacity_veh_h','sum'),mean_speed_listed_kph=('speed_kph','mean'))
        summary['listed_edges']=len(affected);summary['all_network_edges']=len(edges)
        summary['unlisted_assumed_normal_edges']=len(edges)-len(affected)
        summary['retained_capacity_ratio_listed']=summary.retained_capacity_sum_54/affected.capacity_veh_h.sum()
        summary['all_network_capacity_sum_ratio']=(edges.capacity_veh_h.sum()-affected.capacity_veh_h.sum()+summary.retained_capacity_sum_54)/edges.capacity_veh_h.sum()
        summary.to_csv(out/'raw/road_state_summary.csv',index=False,encoding='utf-8-sig')
        episodes=[];peaks=[]
        for (case,scenario,edge),group in result.groupby(['case','scenario','edge_id']):
            group=group.sort_values('time_h');events=closure_episodes(group.time_h,group.depth_m,settings['closure_depth_m'])
            for event in events:episodes.append({'case':case,'scenario':scenario,'edge_id':edge,**event})
            peaks.append({'case':case,'scenario':scenario,'edge_id':edge,'peak_depth_m':float(group.depth_m.max()),
                'minimum_speed_kph':float(group.speed_kph.min()),'minimum_capacity_ratio':float(group.capacity_ratio.min()),
                'ever_closed':bool(group.closed.any()),'closure_duration_h':sum(e['duration_h'] for e in events),
                'closure_episodes':len(events),'right_censored':bool(events and events[-1]['right_censored']),
                'last_reopen_hour':events[-1]['reopen_hour'] if events else None})
        episodes=pd.DataFrame(episodes);peaks=pd.DataFrame(peaks)
        episodes.to_csv(out/'raw/closure_episodes.csv',index=False,encoding='utf-8-sig')
        peaks.to_csv(out/'raw/road_peak_summary.csv',index=False,encoding='utf-8-sig')
        snapshots=[];routing=[]
        for hour in cfg['snapshot_hours']:
            selected=depth[depth.case.eq('baseline')&depth.scenario.eq('extreme')&depth.time_h.eq(hour)]
            snapshot=network_snapshot(edges,selected,settings);active=traversable_edges(snapshot)
            assert len(active)==len(edges)-int(snapshot.closed.sum())
            assert not set(snapshot.loc[snapshot.closed,'edge_id'])&set(active.edge_id)
            routing.append({'time_h':hour,'all_edges':len(snapshot),'traversable_edges':len(active),'excluded_closed_edges':int(snapshot.closed.sum())})
            snapshot['time_h']=hour;snapshot['case']='baseline';snapshot['scenario']='extreme';snapshots.append(snapshot)
        snapshots=pd.concat(snapshots,ignore_index=True)
        snapshots['source_kind']='synthetic_road_performance';snapshots['observed']=False
        snapshots.to_parquet(out/'raw/full_network_snapshots.parquet',index=False)
        pd.DataFrame(routing).to_csv(out/'raw/routing_edge_checks.csv',index=False,encoding='utf-8-sig')
        base_report={}
        for scenario in NAMES:
            s=summary[summary.case.eq('baseline')&summary.scenario.eq(scenario)]
            p=peaks[peaks.case.eq('baseline')&peaks.scenario.eq(scenario)]
            base_report[scenario]={'max_closed_edges':int(s.closed_edges.max()),'ever_closed_edges':int(p.ever_closed.sum()),
                'longest_closure_h':float(p.closure_duration_h.max()),'minimum_listed_capacity_ratio':float(s.retained_capacity_ratio_listed.min()),
                'minimum_network_capacity_sum_ratio':float(s.all_network_capacity_sum_ratio.min()),
                'right_censored_edges':int(p.right_censored.sum())}
        checks={'source_checksums_match':True,'baseline_depth_replay':replay<1e-12,
            'all_directed_edges_known':bool(set(result.edge_id)<=set(edges.edge_id)),
            'speed_never_exceeds_normal':bool(result.speed_ratio.between(0,1).all()),
            'capacity_never_exceeds_normal':bool(result.capacity_ratio.between(0,1).all()),
            'exact_closure_rule':bool(np.array_equal(result.closed.to_numpy(),result.depth_m.to_numpy()>=settings['closure_depth_m'])),
            'closed_speed_capacity_zero':bool((result.loc[result.closed,['speed_kph','capacity_veh_h']]==0).all().all()),
            'closed_cost_infinite':bool(np.isinf(result.loc[result.closed,'travel_time_s']).all()),
            'open_cost_finite_positive':bool(np.isfinite(result.loc[~result.closed,'travel_time_s']).all() and result.loc[~result.closed,'travel_time_s'].gt(0).all()),
            'normal_scenario_unchanged':bool((result.loc[result.scenario.eq('normal'),['speed_ratio','capacity_ratio']]==1).all().all()),
            'all_snapshots_keep_original_ids':all(set(f.edge_id)==set(edges.edge_id) and len(f)==len(edges) for _,f in snapshots.groupby('time_h')),
            'unlisted_edges_explicit_normal':bool((snapshots.loc[snapshots.unlisted_assumed_dry,['speed_ratio','capacity_ratio']]==1).all().all()),
            'closed_edges_removed_from_routing':True,'sparse_parquet_roundtrip':pd.read_parquet(out/'raw/road_state_timeseries.parquet').equals(result)}
        assert all(checks.values()),checks
        report={'run_id':name,'source_process':cfg['source_process'],'source_kind':'synthetic','observed':False,
            'network_directed_edges':len(edges),'listed_directed_edges':len(affected),'unlisted_assumed_normal_edges':len(edges)-len(affected),
            'matched_points':int(mapping.point_id.nunique()),'unmatched_points_retained_in_source':5,
            'cases':int(depth.case.nunique()),'scenarios':4,'endpoints':97,'state_rows':len(result),'settings':settings,
            'baseline_depth_replay_max_error_m':replay,'baseline':base_report,'checks':checks,'all_checks_passed':True,
            'formula_source':'Pregnolato et al. 2017 DOI 10.1016/j.trd.2017.06.020 PDF p7 Eq4; w=1000h mm, v km/h',
            'limits':['Capacity degradation and 0.30 m closure are project assumptions, not calibrated engineering thresholds',
                'Unlisted edges assumed dry; geometry association does not verify road inundation',
                'Immediate model reopening below threshold, no hysteresis/inspection delay',
                'Sum of link capacities is not network throughput; no traffic assignment or resilience recalculated']}
        (out/'provenance/validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        chart_data=plot(out,edges,boundary,result,summary,settings)
        (out/'raw/native_chart_data.json').write_text(json.dumps(chart_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        documentation(out,report)
        files=[p for p in sorted(out.rglob('*')) if p.is_file()]
        manifest={'run_id':name,'status':'success','source_kind':'synthetic','observed':False,
            'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in paths],
            'outputs':[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]}
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with zipfile.ZipFile(out.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(out.rglob('*')):
                if p.is_file():archive.write(p,p.relative_to(out.parent))
        print(json.dumps({'path':out.relative_to(ROOT).as_posix(),'baseline':base_report,'checks':len(checks)},ensure_ascii=False))
        return out
    except Exception:
        (out/'provenance/error.txt').write_text(traceback.format_exc(),encoding='utf-8');raise


def save(fig,out,name):
    for ext in ['png','svg']:fig.savefig(out/'figures'/f'{name}.{ext}',dpi=170)
    plt.close(fig)


def plot(out,edges,boundary,result,summary,settings):
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':11,'svg.fonttype':'none'})
    charts=[];h=np.linspace(0,.4,401);fig,axes=plt.subplots(1,2,figsize=(13,5.5));speed_series=[]
    for speed,color in [(30,'#4B8CAA'),(50,'#E39A35'),(80,'#BE4058')]:
        q=road_response(h,speed,1800,settings)
        axes[0].plot(h,q.speed_kph,label=f'正常{speed} km/h',color=color)
        speed_series.append({'name':f'正常{speed} km/h','x':h.tolist(),'y':q.speed_kph.tolist(),'color':color})
    q=road_response(h,50,1800,settings,'linear');axes[0].plot(h,q.speed_kph,'--',color='#7A8791',label='线性速度对照50 km/h')
    speed_series.append({'name':'线性对照50 km/h','x':h.tolist(),'y':q.speed_kph.tolist(),'color':'#7A8791'})
    cap=road_response(h,50,1800,settings).capacity_veh_h/1800
    axes[1].plot(h,cap,color='#3C8063');axes[1].set_ylabel('通行容量 / 正常容量')
    for ax in axes:ax.axvline(.3,color='#BE4058',ls='--');ax.set_xlabel('积水深度 (m)');ax.grid(alpha=.2);ax.set_xlim(0,.4);ax.set_ylim(bottom=0)
    axes[0].set_ylabel('道路速度 (km/h)');axes[0].legend(fontsize=9);axes[1].set_ylim(0,1.05)
    fig.suptitle('道路交通性能退化  速度 容量与中断')
    fig.text(.06,.02,'速度来源 Pregnolato等2017 PDF第7页Eq.4；容量曲线与0.30 m中断阈值为项目假设。',fontsize=10)
    fig.tight_layout(rect=(0,.06,1,.94));save(fig,out,'depth_road_response')
    charts.extend([{'title':'水深与道路速度','unit':'速度 km/h','x_label':'积水深度 m','x_max':.4,'x_step':.1,'series':speed_series},
        {'title':'假设容量保留率','unit':'容量 / 正常容量','x_label':'积水深度 m','x_max':.4,'x_step':.1,
         'series':[{'name':'独立容量假设','x':h.tolist(),'y':cap.tolist(),'color':'#3C8063'}]}])
    fig,axes=plt.subplots(2,1,figsize=(12,7.5),sharex=True);closed_series=[];capacity_series=[]
    for scenario,color in COLORS.items():
        s=summary[summary.case.eq('baseline')&summary.scenario.eq(scenario)].sort_values('time_h')
        axes[0].step(s.time_h,s.closed_edges,where='post',color=color,label=NAMES[scenario])
        axes[1].plot(s.time_h,s.retained_capacity_ratio_listed,color=color,label=NAMES[scenario])
        closed_series.append({'name':NAMES[scenario],'x':s.time_h.tolist(),'y':s.closed_edges.tolist(),'color':color})
        capacity_series.append({'name':NAMES[scenario],'x':s.time_h.tolist(),'y':s.retained_capacity_ratio_listed.tolist(),'color':color})
    axes[0].set_ylabel('中断有向边条数');axes[0].legend(ncol=3);axes[1].set_ylabel('54条关联边容量之和 / 正常值');axes[1].set_xlabel('相对情景起点 (小时)')
    for ax in axes:ax.set_xlim(0,24);ax.grid(alpha=.2)
    axes[0].set_ylim(bottom=0);axes[1].set_ylim(0,1.05)
    fig.suptitle('基准降雨积水下的道路退化与恢复')
    fig.text(.07,.015,'容量之和仅作关联道路属性汇总，不等于全网吞吐量；中断弧在可通行边集中移除，未运行流量分配。',fontsize=10)
    fig.tight_layout(rect=(0,.05,1,.94));save(fig,out,'road_impact_process')
    charts.extend([{'title':'基准道路中断过程','unit':'中断有向边条数','series':closed_series},
        {'title':'关联道路容量保留过程','unit':'54边容量之和 / 正常值','series':capacity_series}])
    roads=edges.to_crs(32650);border=boundary.to_crs(32650)
    x0,y0,x1,y1=roads.total_bounds;dx=(x1-x0)*.03;dy=(y1-y0)*.03
    palette={'normal':'#4B8CAA','light':'#E9BA44','heavy':'#E97932','closed':'#BD263D'}
    fig,axes=plt.subplots(1,3,figsize=(15,7))
    for ax,scenario in zip(axes,COLORS):
        roads.plot(ax=ax,color='#D2DADD',linewidth=.22);border.boundary.plot(ax=ax,color='#87979F',linewidth=.6)
        frame=result[result.case.eq('baseline')&result.scenario.eq(scenario)&result.time_h.eq(10.5)]
        selected=roads.merge(frame[['edge_id','state']],on='edge_id',validate='one_to_one')
        for state,color in palette.items():
            subset=selected[selected.state.eq(state)]
            if len(subset):subset.plot(ax=ax,color=color,linewidth=2.2,zorder=4)
        ax.set_xlim(x0-dx,x1+dx);ax.set_ylim(y0-dy,y1+dy)
        ax.set_title(NAMES[scenario]+f'\n10.5小时  中断{int(frame.closed.sum())}条有向边');ax.set_axis_off()
    fig.legend(handles=[Line2D([0],[0],color=c,lw=3,label=n) for n,c in [('列入且正常',palette['normal']),('轻度',palette['light']),('重度',palette['heavy']),('中断',palette['closed']),('未列边假设原状','#D2DADD')]],loc='lower center',ncol=5,bbox_to_anchor=(.5,.07))
    fig.suptitle('南山道路状态与真实路网  基准参数')
    fig.text(.05,.015,'仅54条有向边由55个候选点几何关联；5点未匹配。线条可能重叠，按独立edge_id计数。合成深度未验证真实道路受淹。© OpenStreetMap contributors ODbL1.0',fontsize=9)
    fig.tight_layout(rect=(0,.13,1,.94));save(fig,out,'road_states_map')
    return charts


def documentation(out,report):
    text='''# 道路交通性能退化模型

将南山四种降雨情景、五组排水消退参数的合成积水映射至54条有向道路，不修改40105条路网边及平行边标识。其余40051条边假设原状，不意味着实际无积水；5个未匹配点在上游保留。

速度：w=1000h（mm），v_limit=0.0009w²-0.5529w+86.9448（km/h），来源Pregnolato等2017 DOI 10.1016/j.trd.2017.06.020 PDF第7页Eq.4。h=0返回正常速度v0；0<h<0.30时v=min(v0,max(0,v_limit))。容量独立采用C=C0 max(0.20,1-0.80h/0.30)，单位veh/h。水深h>=0.30 m时速度与容量为0，行程时间导出为inf，弧从可通行集合移除。容量及中断阈值均为项目假设，不能归为原论文结论或官方安全标准。

通行时间t0=3.6L/v（秒），L为m；只表示灾害条件下自由流时间，尚未叠加拥堵。未求解新交通分配，因此不能把容量当作实际流量。

水深退至0.30 m以下即模型重开，没有额外安全检查时延或滞回，不能视为实际道路放行规则。封路事件按端点线性插值计算穿越时刻，临界相等按封路，窗口末仍关闭记右删失；未关闭边不填写恢复时刻。

raw/road_state_timeseries.parquet含5组×4情景×97端点×54边，字段包括u/v/key/edge_id、深度、正常属性、速度、容量、状态、通行性和自由流时间。raw/edge_depth_timeseries.parquet可对接已有水深接口；road_state_summary.csv汇总道路数量与关联边容量属性之和；该和值不等于网络吞吐量。closure_episodes.csv和road_peak_summary.csv记录封路持续时间与恢复。full_network_snapshots.parquet保存基准极端情景0/10.5/16/24小时全40105边快照，unlisted_assumed_dry明确标记缺省假设。routing_edge_checks.csv核对关闭弧从可通行集合中删除。native_chart_data.json保存原生PPT图表全部源值。

源码及配置快照在provenance；manifest与ZIP逐字节可核验，figures保留PNG/SVG。全过程为合成、未经道路积水/速度/容量实测标定的研究模型，未重跑均衡、韧性或治理。
'''
    (out/'README.md').write_text(text,encoding='utf-8')
    cards=''.join(f'<h2>{p.stem}</h2><img src="figures/{p.name}" style="width:100%">' for p in sorted((out/'figures').glob('*.png')))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>道路性能退化</title><body style="max-width:1200px;margin:30px auto;font-family:Microsoft YaHei"><h1>道路速度 通行容量与中断</h1><p>合成且未实测校准，未重跑流量分配</p>'+cards+'</body>',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'configs/road_performance_process.yaml')
    build(p.parse_args().config)
