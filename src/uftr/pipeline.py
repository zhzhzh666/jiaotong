"""Executable later-stage orchestration, with explicit scope and evidence."""
from pathlib import Path
import json
import time
import sys
import numpy as np
import pandas as pd
from .archive import RunArchive,write_json
from .assignment import TrafficNetwork,load_osm,result_summary
from .config import load_config


def archive_inputs(root,config_path,extra=()):
    inputs=[config_path,*sorted((root/'src/uftr').glob('*.py')),*extra]
    config=load_config(config_path)
    def visit(value):
        if isinstance(value,dict):
            for v in value.values():visit(v)
        elif isinstance(value,str):
            p=(root/value).resolve()
            try:p.relative_to(root)
            except ValueError:return
            if p.is_file():inputs.append(p)
            elif p.is_dir() and ('data/' in value or value.startswith('results/')):
                inputs.extend(f for f in p.rglob('*') if f.is_file() and f.suffix in {'.csv','.parquet','.graphml','.geojson','.json'})
    visit(config)
    return list(dict.fromkeys(inputs))


def save_assignment(run,label,network,result):
    edges=network.edges[['edge_id','u','v']].copy();edges['flow_veh_h']=result.flow;edges['travel_time_s']=result.time
    edges.to_parquet(run.path/'raw'/f'{label}_flows.parquet',index=False)
    result.trace.to_csv(run.path/'raw'/f'{label}_convergence.csv',index=False)
    write_json(run.path/'raw'/f'{label}_assignment.json',result_summary(result))


def stage06(root,config_path,config,run):
    s=config['assignment'];sf=root/s['sioux_directory']; links=pd.read_csv(sf/'sioux_links.csv')
    edges=links.rename(columns={'free_flow_time_original':'free_flow_time_s','capacity_original':'capacity_veh_h'}).copy()
    # TNTP time unit 0.01 h = 36 s; keep original flow units for benchmark.
    edges.free_flow_time_s*=36;edges['edge_id']=[f'sioux_{u}_{v}' for u,v in zip(edges.u,edges.v)]
    net=TrafficNetwork(edges);od=pd.read_csv(sf/'sioux_od.csv').rename(columns={'origin':'origin_node','destination':'destination_node','demand_original':'flow_veh_h'})
    od=od[od.flow_veh_h>0].copy()
    result=net.solve(od,tolerance=config['models']['relative_gap_target'],max_iterations=s['sioux_max_iterations'])
    save_assignment(run,'sioux',net,result)
    reference=pd.read_csv(sf/'sioux_reference_flow.csv');joined=net.edges[['u','v']].assign(model_flow=result.flow).merge(reference,on=['u','v'],validate='one_to_one')
    joined.to_csv(run.path/'raw/sioux_comparison.csv',index=False)
    summary={'sioux':{**result_summary(result),'relative_flow_rmse':float(np.sqrt(np.mean((joined.model_flow-joined.volume_original)**2))/joined.volume_original.mean()),
        'time_unit':'original TNTP time multiplied by 36 s, flow kept original benchmark unit'},'osm':{}}
    print('Sioux Falls: '+json.dumps(summary['sioux']),flush=True)
    if not result.converged or result.node_balance_max_error>1e-5:raise ValueError('Sioux Falls acceptance failed')
    for region in ['small','nanshan']:
        network,graph=load_osm(root/s['network_root']/region)
        demand=pd.read_csv(root/s['od'],dtype={'origin_node':'Int64','destination_node':'Int64'})
        if region=='small':
            # A separate, explicitly scoped small-network subset. Excluded demand is recorded.
            mask=demand.origin_node.isin(network.nodes)&demand.destination_node.isin(network.nodes)
            omitted=float(demand.loc[~mask,'flow_veh_h'].sum());demand=demand[mask].copy()
        else:omitted=0.
        result=network.solve(demand,tolerance=config['models']['relative_gap_target'],max_iterations=s[region+'_max_iterations'])
        save_assignment(run,region,network,result)
        summary['osm'][region]={**result_summary(result),'nodes':len(network.nodes),'edges':len(network.edges),'od_rows':len(demand),'excluded_outside_small_scope_veh_h':omitted}
        print(region+': '+json.dumps(summary['osm'][region]),flush=True)
    write_json(run.path/'raw/assignment_report.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for label in ['sioux','small','nanshan']:
        q=pd.read_csv(run.path/'raw'/f'{label}_convergence.csv');axes[0].semilogy(q.iteration,np.maximum(q.relative_gap,1e-12),label=label)
    axes[0].axhline(config['models']['relative_gap_target'],color='black',ls='--');axes[0].set(xlabel='Frank-Wolfe iteration',ylabel='Relative gap');axes[0].legend()
    axes[1].scatter(joined.volume_original,joined.model_flow,s=15);m=max(joined.volume_original.max(),joined.model_flow.max());axes[1].plot([0,m],[0,m],color='black',ls='--')
    axes[1].set(xlabel='Upstream reference arc flow',ylabel='Model arc flow',title='Sioux Falls: original benchmark flow units')
    p=run.path/'figures/assignment_validation.png';fig.savefig(p,dpi=160);plt.close(fig)
    run.add_artifact(p,title='用户均衡收敛与Sioux Falls参考流量',kind='figure',data_kind='mixed',source_paths=[run.path/'raw/sioux_comparison.csv',run.path/'raw/assignment_report.json'])
    return summary


def run_stage(root,config_path):
    root=root.resolve();config=load_config(config_path);phase=config['phase']
    with RunArchive(root,config,archive_inputs(root,config_path)) as run:
        run.manifest['command']=[sys.executable,*sys.argv];run.flush()
        if phase=='06':report=stage06(root,config_path,config,run)
        elif phase in {'07','08','09','11'}:
            from .research import research_stage
            report=research_stage(root,config,run)
        elif phase=='10':
            from .sumo_run import run_sumo
            report=run_sumo(root,config,run)
        elif phase=='12':
            import shutil
            evidence=root/'docs/validation/phase12/browser-verification.json'
            report=json.loads(evidence.read_text(encoding='utf-8'))
            if len(report['pages_verified'])!=8 or not report['csv_download_verified']:raise ValueError('browser acceptance incomplete')
            for path in sorted(evidence.parent.glob('*.jpg')):
                target=run.path/'screenshots'/path.name;shutil.copy2(path,target)
                run.add_artifact(target,title='中文交互系统 '+path.stem,kind='screenshot',data_kind='mixed',source_paths=[root/'app.py',evidence])
        elif phase=='13':
            from .final_audit import final_audit
            report=final_audit(root,config,run)
        else:raise ValueError('unsupported phase')
        write_json(run.path/'raw/stage_report.json',report)
        print(json.dumps({'run_id':run.run_id,'phase':phase,'report':report},ensure_ascii=False),flush=True)
    return run.path
