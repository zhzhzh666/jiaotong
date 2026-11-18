"""Replay frozen synthetic rainfall and quantify ponding/recession sensitivity."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
from hashlib import sha256
import argparse
import json
import shutil
import traceback
import zipfile

import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from uftr.storm_process import simulate_ponding, threshold_metrics

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ['normal', 'general', 'severe', 'extreme']
LABELS = ['正常', '一般100 mm', '严重200 mm', '极端300 mm']
COLORS = ['#80909B', '#4B8CAA', '#E39A35', '#BE4058']


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def build(config_path):
    config_path = config_path.resolve()
    cfg = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    source = ROOT / cfg['source_package']
    name = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%dT%H%M%S') + '_storm_process_' + uuid4().hex[:8]
    out = ROOT / 'data/synthetic/storm_process' / name
    out.mkdir(parents=True, exist_ok=False)
    for folder in ['raw', 'figures', 'provenance']:
        (out / folder).mkdir()
    try:
        input_paths = [config_path, Path(__file__).resolve(), ROOT/'src/uftr/storm_process.py', source/'manifest.json',
                       source/'rainfall/areal_reference_rainfall_15min.csv', source/'flood/point_parameters.csv',
                       source/'flood/point_depth_timeseries.csv']
        frozen = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
        recorded = {r['path']:r['sha256'] for r in frozen['outputs']}
        for p in input_paths[4:]:
            assert digest(p) == recorded[p.relative_to(source).as_posix()]
        shutil.copy2(config_path, out/'provenance/config.yaml')
        shutil.copy2(__file__, out/'provenance/run_storm_flood_process.py')
        shutil.copy2(ROOT/'src/uftr/storm_process.py', out/'provenance/storm_process.py')
        rain = pd.read_csv(input_paths[4])
        params = pd.read_csv(input_paths[5]).sort_values('point_id').reset_index(drop=True)
        previous = pd.read_csv(input_paths[6])
        ids = params.point_id.to_numpy()
        dt = cfg['interval_minutes']/60
        assert np.isclose(dt, .25)  # Frozen source has 15-minute intervals.
        time_h = np.arange(97)*dt
        metrics, traces, accounting, summaries = [], [], [], []
        arrays = {}
        max_replay_error = max_residual = max_event_residual = 0.
        for case, settings in cfg['cases'].items():
            for scenario in SCENARIOS:
                frame = rain[rain.scenario.eq(scenario)].sort_values('interval_index')
                assert len(frame)==96 and np.allclose(frame.start_hour, time_h[:-1]) and np.allclose(frame.end_hour, time_h[1:])
                rainfall = frame.rainfall_mm_interval.to_numpy()[:,None]*params.rain_spatial_factor.to_numpy()[None,:]
                result = simulate_ponding(rainfall, dt, params.runoff_coefficient.to_numpy(),
                    params.hypothetical_concentration_ratio.to_numpy(),
                    params.drainage_mm_h.to_numpy()*settings['drainage_multiplier'],
                    params.recession_tau_h.to_numpy()*settings['recession_multiplier'])
                h = result['depth_m']; arrays[case,scenario] = h
                max_residual = max(max_residual, float(np.abs(result['balance_residual_mm']).max()))
                event = 1000*(h[-1]-h[0])-result['inflow_mm'].sum(0)+result['drained_mm'].sum(0)
                max_event_residual = max(max_event_residual, float(np.abs(event).max()))
                if case=='baseline':
                    expected = previous[previous.scenario.eq(scenario)].pivot(index='time_s',columns='point_id',values='depth_m').reindex(columns=ids).to_numpy()
                    max_replay_error = max(max_replay_error, float(np.abs(expected-h).max()))
                for j,pid in enumerate(ids):
                    peak = int(h[:,j].argmax())
                    for threshold in cfg['thresholds_m']:
                        m = threshold_metrics(time_h,h[:,j],threshold)
                        metrics.append({'case':case,'scenario':scenario,'point_id':pid,'peak_depth_m':float(h[peak,j]),
                            'first_peak_hour':float(time_h[peak]),**m,'source_kind':'synthetic','observed':False})
                traces.append(pd.DataFrame({'case':case,'scenario':scenario,'time_h':np.repeat(time_h,len(ids)),
                    'point_id':np.tile(ids,len(time_h)),'depth_m':h.ravel(),'source_kind':'synthetic','observed':False}))
                accounting.append(pd.DataFrame({'case':case,'scenario':scenario,'interval_start_h':np.repeat(time_h[:-1],len(ids)),
                    'point_id':np.tile(ids,96),'rain_mm_interval':rainfall.ravel(),
                    'inflow_mm_interval':result['inflow_mm'].ravel(),'drained_mm_interval':result['drained_mm'].ravel(),
                    'storage_change_mm':(np.diff(h,axis=0)*1000).ravel()}))
        metrics = pd.DataFrame(metrics)
        for (case,scenario),frame in metrics.groupby(['case','scenario'],sort=False):
            dry = frame[np.isclose(frame.threshold_m,cfg['recovery_threshold_m'])]
            recovered = dry[dry.status.eq('recovered')]
            wet = dry[~dry.status.eq('not_exceeded')]
            risk = frame[np.isclose(frame.threshold_m,.15)]
            h = arrays[case,scenario]
            peak_index = np.unravel_index(h.argmax(),h.shape)
            summaries.append({'case':case,'scenario':scenario,'peak_depth_m':float(h.max()),
                'first_peak_hour':float(time_h[peak_index[0]]),'peak_point_id':ids[peak_index[1]],
                'ponded_points_001':len(wet),'recovered_points_001':len(recovered),
                'censored_points_001':int(dry.status.eq('right_censored').sum()),
                'latest_recovery_hour_001':float(recovered.recovery_hour.max()) if len(recovered) else None,
                'max_duration_above_015_h':float(risk.duration_above_h.max()),
                'max_points_above_015':int((h>.15).sum(1).max())})
        summary = pd.DataFrame(summaries)
        metrics.to_csv(out/'raw/point_threshold_metrics.csv',index=False,encoding='utf-8-sig')
        summary.to_csv(out/'raw/scenario_summary.csv',index=False,encoding='utf-8-sig')
        pd.concat(traces,ignore_index=True).to_parquet(out/'raw/point_depth_timeseries.parquet',index=False)
        pd.concat(accounting,ignore_index=True).to_parquet(out/'raw/interval_water_balance.parquet',index=False)
        checks = {'frozen_inputs_match':True,'baseline_matches_frozen_depth':max_replay_error<1e-12,
            'interval_water_balance':max_residual<1e-10,'event_water_balance':max_event_residual<1e-8,
            'finite_nonnegative_depths':all(np.isfinite(h).all() and (h>=0).all() for h in arrays.values()),
            'dry_normal_for_all_cases':all((arrays[c,'normal']==0).all() for c in cfg['cases']),
            'dry_recession_nonincreasing':all((np.diff(h[52:],axis=0)<=1e-14).all() for h in arrays.values()),
            'drainage_ordering':all((arrays['drainage_half',s]>=arrays['baseline',s]-1e-12).all() and
                (arrays['baseline',s]>=arrays['drainage_1p5',s]-1e-12).all() for s in SCENARIOS),
            'recession_ordering':all((arrays['recession_slow',s]>=arrays['baseline',s]-1e-12).all() and
                (arrays['baseline',s]>=arrays['recession_fast',s]-1e-12).all() for s in SCENARIOS),
            'durations_within_window':bool(metrics.duration_above_h.between(0,24).all()),
            'censored_not_given_recovery':bool(metrics.loc[metrics.status.ne('recovered'),'recovery_hour'].isna().all())}
        assert all(checks.values()), checks
        report={'run_id':name,'source_package':cfg['source_package'],'source_kind':'synthetic','observed':False,
            'cases':len(cfg['cases']),'scenarios':4,'points':len(ids),'interval_minutes':15,
            'rain_end_hour':13,'recovery_threshold_m':cfg['recovery_threshold_m'],
            'metric_method':'Piecewise linear endpoints; strict depth > threshold; final downward crossing; right-censor at 24h',
            'baseline_replay_max_error_m':max_replay_error,'max_interval_balance_residual_mm':max_residual,
            'max_event_balance_residual_mm':max_event_residual,'checks':checks,'all_checks_passed':True,
            'baseline_summary':json.loads(summary[summary.case.eq('baseline')].to_json(orient='records',double_precision=15)),
            'limits':['Independent hypothetical ponds; no drainage network, lateral exchange or tidal backwater',
                      'Rainfall and drainage/recession parameters uncalibrated; sensitivity is not engineering efficacy',
                      'No new traffic assignment, resilience or optimization run']}
        (out/'provenance/validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        charts = make_figures(out, cfg, rain, arrays, time_h, ids, summary)
        (out/'raw/native_chart_data.json').write_text(json.dumps(charts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        write_docs(out,report,summary,cfg)
        files=[p for p in sorted(out.rglob('*')) if p.is_file()]
        manifest={'run_id':name,'status':'success','source_kind':'synthetic','observed':False,
            'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in input_paths],
            'outputs':[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in files]}
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with zipfile.ZipFile(out.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(out.parent))
        print(summary[summary.case.eq('baseline')].to_string(index=False))
        print(out)
        return out
    except Exception:
        (out/'provenance/error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


def make_figures(out,cfg,rain,arrays,time_h,ids,summary):
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':11,'svg.fonttype':'none'})
    charts=[]
    fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True)
    rain_series=[]; depth_series=[]
    for i,s in enumerate(SCENARIOS[1:],1):
        frame=rain[rain.scenario.eq(s)].sort_values('interval_index')
        x=frame.start_hour.to_numpy(); y=frame.intensity_mm_h.to_numpy()
        axes[0].stairs(y,np.r_[x,24],color=COLORS[i],label=LABELS[i])
        h=arrays['baseline',s]
        axes[1].plot(time_h,h.max(1),color=COLORS[i],label=LABELS[i])
        axes[2].step(time_h,(h>.15).sum(1),where='post',color=COLORS[i],label=LABELS[i])
        rain_series.append({'name':LABELS[i],'x':x.tolist(),'y':y.tolist(),'color':COLORS[i]})
        depth_series.append({'name':LABELS[i],'x':time_h.tolist(),'y':h.max(1).tolist(),'color':COLORS[i]})
    for ax,label in zip(axes,['参考雨强 (mm/h)','60点最大积水深度 (m)','深度 > 0.15 m点数']):
        ax.set_ylabel(label);ax.axvline(13,color='#697A86',ls='--',lw=1);ax.grid(alpha=.2);ax.set_xlim(0,24);ax.set_ylim(bottom=0)
    axes[0].legend(ncol=3);axes[1].axhline(.15,color='#697A86',ls=':',lw=1)
    axes[-1].set_xlabel('相对情景起点 (小时)')
    fig.suptitle('南山合成暴雨内涝全过程  降雨 积水 消退')
    fig.text(.08,.015,'虚线为13小时雨停；点数仅表示60个合成候选点，不代表面积、路网比例或历史灾情。',fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.96)); save(fig,out,'storm_process')
    charts.extend([{'title':'参考降雨过程','unit':'雨强 mm/h','series':rain_series},
                   {'title':'基准最大积水深度','unit':'水深 m','series':depth_series}])
    ref=int(arrays['baseline','extreme'].max(0).argmax())
    fig,axes=plt.subplots(1,2,figsize=(14,6))
    series=[];palette=['#172C3B','#BE4058','#3B9165','#407EAD','#CC9237']
    for (case,settings),color in zip(cfg['cases'].items(),palette):
        y=arrays[case,'extreme'][:,ref]
        axes[0].plot(time_h[52:]-13,y[52:],color=color,label=settings['label'])
        series.append({'name':settings['label'],'x':time_h[52:].tolist(),'y':y[52:].tolist(),'color':color})
    axes[0].axhline(.01,color='#697A86',ls=':',label='退至0.01 m阈值');axes[0].set_xlim(0,11)
    axes[0].set_xlabel('13小时雨停后的时间 (小时)');axes[0].set_ylabel('同一候选点积水深度 (m)');axes[0].legend(fontsize=9)
    axes[0].set_title('极端情景固定点 '+str(ids[ref]))
    baseline=summary[summary.case.eq('baseline') & summary.scenario.ne('normal')]
    axes[1].bar(range(3),baseline.latest_recovery_hour_001-13,color=COLORS[1:])
    axes[1].set_xticks(range(3),LABELS[1:]);axes[1].set_ylabel('雨停后至全部曾超1 cm点恢复 (小时)')
    for i,row in enumerate(baseline.itertuples()):
        assert row.censored_points_001==0
        axes[1].text(i,row.latest_recovery_hour_001-13+.1,f'{row.latest_recovery_hour_001-13:.2f}',ha='center')
    axes[1].set_title('基准参数  最后恢复时刻按线性插值')
    for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_ylim(bottom=0)
    fig.suptitle('积水消退与参数敏感性')
    fig.text(.06,.02,'独立假设蓄水桶，未实测校准；24小时仍超阈值记右删失，不填虚构恢复时刻。',fontsize=10)
    fig.tight_layout(rect=(0,.07,1,.94));save(fig,out,'flood_recession')
    charts.append({'title':'极端情景同一候选点雨停后消退','unit':'水深 m','point_id':str(ids[ref]),'series':series})
    return charts


def save(fig,out,name):
    for ext in ['png','svg']:fig.savefig(out/'figures'/f'{name}.{ext}',dpi=170)
    plt.close(fig)


def write_docs(out,report,summary,cfg):
    text='''# 暴雨内涝情景建模

基于已冻结南山合成雨量与60点参数，形成降雨、积水、退水的独立可复现模块。全部结果为未标定的合成实验，未重跑交通评估。

降雨采用0/100/200/300 mm参考总量、5—13小时双峰，60点空间乘数保持原包不变。雨量单位mm/区间，水深输出m，时间15分钟。

H以mm计，输入I=R×径流系数×假设汇水/积水面积比。D=min(H+I,c×Δt+H×Δt/τ)，H_next=H+I-D。c为mm/h，τ为小时。雨停后为H_next=max((1-Δt/τ)H-cΔt,0)，采用显式离散式，不当作连续精确解。

基准τ=4小时。另比较排水能力0.5/1.5倍、τ=2/8小时，均为单因素参数敏感性，不等同于工程改造效果。

raw/point_threshold_metrics.csv记录每点峰值、首次达峰时刻及水深严格超过0/0.01/0.15/0.30/0.40 m的持续时间。阈值穿越按相邻端点线性插值；恢复是事件峰值后最后一次下降穿越，且截至24小时不再超阈值。status区分not_exceeded、recovered、right_censored，未超阈值或未恢复的时刻留空。0.01 m为本轮分析定义，不是安全通行标准。

raw/point_depth_timeseries.parquet保存四情景五参数组的97端点水深；interval_water_balance.parquet保存96区间的点雨量、输入、排水与储量变化。scenario_summary.csv汇总峰值、>0.15 m最长持续时间和恢复/删失点数。native_chart_data.json保留PPT可编辑图表全部数值。figures/保留PNG与SVG。源码、配置和数值核验在provenance/。

DSM和独立蓄水桶不识别真实排水管网、汇水区、水交换及河潮顶托。基准与旧包一致只验证数值重放，不验证真实水动力过程；SW观测不用于路面零点标定。
'''
    (out/'README.md').write_text(text,encoding='utf-8')
    cards=''.join(f'<h2>{p.stem}</h2><img src="figures/{p.name}" style="width:100%">' for p in sorted((out/'figures').glob('*.png')))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>暴雨内涝情景过程</title><body style="max-width:1200px;margin:30px auto;font-family:Microsoft YaHei"><h1>南山合成暴雨内涝过程</h1><p>降雨 积水 消退 · 合成且未实测校准</p>'+cards+'</body>',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,default=ROOT/'configs/storm_flood_process.yaml')
    build(parser.parse_args().config)
