"""Independent arithmetic audit of every solved road/OD state and interval."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import numpy as np
import pandas as pd
import yaml
from uftr.assignment import load_osm

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();run=args.run.resolve();cfg=yaml.safe_load((run/'provenance/config.yaml').read_text(encoding='utf-8'))
net,_=load_osm(ROOT/cfg['network_directory']);frame=pd.read_csv(run/'raw/interval_metrics.csv')
totals=pd.read_csv(run/'raw/scenario_summary.csv');reports={};max_cost_error=0.;max_balance=0.;max_gap_error=0.
for record in sorted((run/'raw/states').glob('*.json')):
    data=json.loads(record.read_text(encoding='utf-8'));token=data['state_id']
    for item in data['artifacts']:
        assert sha256((run/item['path']).read_bytes()).hexdigest()==item['sha256']
    state=pd.read_parquet(record.with_suffix('.parquet'))
    assert state.edge_id.tolist()==net.edges.edge_id.tolist()
    assert len(state)==len(net.edges)
    q=pd.read_parquet(run/'raw/od_service'/f'{token}.parquet')
    closed=state.closed.to_numpy(bool);active=~closed;flow=state.flow_veh_h.to_numpy()
    assert (flow>=0).all() and np.all(flow[closed]==0)
    assert np.isinf(state.travel_time_s[closed]).all() and (state.effective_capacity_veh_h[closed]==0).all()
    a=cfg['assignment'];expected=state.free_flow_time_s[active]*(1+a['bpr_alpha']*(flow[active]/state.effective_capacity_veh_h[active])**a['bpr_beta'])
    max_cost_error=max(max_cost_error,float(np.max(np.abs(np.asarray(expected-state.travel_time_s[active])),initial=0)))
    assert np.allclose(expected,state.travel_time_s[active],rtol=1e-12,atol=1e-9)
    served=q.served_network.to_numpy(bool);intra=q.route_status.eq('intrazonal_not_graph_loaded').to_numpy()
    assert not (served&intra).any() and np.isfinite(q.shortest_network_time_s[served]).all()
    rates=q.flow_veh_h.to_numpy();s=float(rates[served].sum());u=float(rates[~served&~intra].sum());i=float(rates[intra].sum())
    m=data['metrics'];r=data['assignment']
    assert np.allclose([s,u,i,rates.sum()],[m['served_veh_h'],m['unserved_veh_h'],m['intrazonal_veh_h'],m['total_veh_h']],rtol=1e-12)
    travel=float(np.dot(flow[active],state.travel_time_s[active]))
    cost=travel+300*i+cfg['metrics']['rho_s']*u
    assert np.isclose(cost,m['total_cost_veh_s_h'],rtol=1e-12)
    shortest=float(np.dot(rates[served],q.shortest_network_time_s[served]))
    gap=max(0.,(travel-shortest)/travel) if travel>0 else 0.
    max_gap_error=max(max_gap_error,abs(gap-r['relative_gap']))
    assert abs(gap-r['relative_gap'])<1e-10 and gap<=a['gap_target']+1e-10
    departure=q.loc[served,'origin_node'].astype('int64').map(net.node_index).to_numpy()
    arrival=q.loc[served,'destination_node'].astype('int64').map(net.node_index).to_numpy()
    balance=np.bincount(net.u,weights=flow,minlength=len(net.nodes))-np.bincount(net.v,weights=flow,minlength=len(net.nodes))
    wanted=np.bincount(departure,weights=rates[served],minlength=len(net.nodes))-np.bincount(arrival,weights=rates[served],minlength=len(net.nodes))
    max_balance=max(max_balance,float(np.max(np.abs(balance-wanted),initial=0)))
    assert np.max(np.abs(balance-wanted),initial=0)<1e-5
    vc=float(np.mean(flow[active]/state.effective_capacity_veh_h[active]>.9)) if active.any() else 0.
    assert np.isclose(vc,m['congested_open_edge_fraction'],rtol=0,atol=1e-12)
    reports[token]=data
for row in frame.itertuples():
    current=reports[row.state_id]['metrics'];baseline=reports[row.baseline_state_id]['metrics']
    assert current['total_veh_h']==baseline['total_veh_h']
    assert np.isclose(row.Qp,baseline['total_cost_veh_s_h']/current['total_cost_veh_s_h'],rtol=1e-12)
    assert np.isclose(row.Q,.2*row.Qs+.5*row.Qp+.3*row.Qf,rtol=1e-12)
for scenario,part in frame.groupby('scenario'):
    assert part.interval_index.tolist()==list(range(96))
    assert np.allclose(part.end_hour-part.start_hour,.25)
    total=totals[totals.scenario.eq(scenario)].iloc[0]
    assert np.isclose(total.R,float(np.sum(part.Q*.25)/24),rtol=1e-12)
    assert np.isclose(total.total_vehicles,float(np.sum(part.total_veh_h*.25)),rtol=1e-12)
assert np.allclose(totals.total_vehicles,totals.served_vehicles+totals.unserved_vehicles+totals.intrazonal_vehicles,rtol=1e-12)
result={'all_checks_passed':True,'run_id':run.name,
 'run_manifest_sha256':sha256((run/'manifest.json').read_bytes()).hexdigest(),
 'auditor_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
 'unique_states_audited':len(reports),'intervals_audited':len(frame),
 'artifact_SHA_checked':4*len(reports),'max_BPR_time_error_s':max_cost_error,'max_node_balance_error_veh_h':max_balance,
 'max_relative_gap_replay_error':max_gap_error,'closed_arc_flows_zero':True,'served_unserved_intrazonal_retained':True,
 'effective_capacity_vc_checked':True,'same_demand_baselines_checked':True,'daily_demand_and_integrals_replayed':True,
 'scope':'Independent numerical accounting of stored new UE results; no empirical validation'}
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
