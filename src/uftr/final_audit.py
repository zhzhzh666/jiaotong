"""Independent saved-result audit and a fresh small-network numerical replay."""
from pathlib import Path
from collections import Counter
import json
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from PIL import Image
from .archive import file_hash,verify_recorded_input,write_json
from .research import Experiment


def latest_success(root,phase,region=None):
    for m in sorted((root/'results/runs').glob(f'*_p{phase}_*/manifest.json'),reverse=True):
        info=json.loads(m.read_text(encoding='utf-8'))
        if info['status']!='success':continue
        c=json.loads((m.parent/'config.json').read_text(encoding='utf-8'))
        if region is None or c.get('research',{}).get('region')==region:return m.parent
    raise FileNotFoundError(f'no successful Phase {phase} for {region}')


def audit_archive(root,folder):
    m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));kinds=Counter()
    assert m['status']=='success' and file_hash(folder/'config.json')==m['config_sha256']
    for item in m['inputs']:kinds[verify_recorded_input(root,item,m['git'])]+=1
    for item in m.get('outputs',[]):assert file_hash(folder/item['path'])==item['sha256']
    for item in m['artifacts']:
        assert file_hash(folder/item['path'])==item['sha256']
        for source in item['sources']:assert file_hash(root/source['path'])==source['sha256']
        if (folder/item['path']).suffix.lower() in {'.png','.jpg','.gif'}:
            with Image.open(folder/item['path']) as image:image.verify()
    return {'run_id':m['run_id'],'inputs':len(m['inputs']),'artifacts':len(m['artifacts']),'input_verification_basis':dict(kinds),'git':m['git'],'elapsed_s':m['elapsed_s']}


def final_audit(root,config,run):
    reports={};runs={p:latest_success(root,p) for p in ['04','05','06','08','09','10','11','12']}
    runs['07_small']=latest_success(root,'07','small');runs['07_nanshan']=latest_success(root,'07','nanshan')
    for phase,folder in runs.items():reports[phase]=audit_archive(root,folder)
    foundation={p:audit_archive(root,latest_success(root,p)) for p in ['01','02','03']}
    # Freeze present dataset bytes independently, including raster inputs omitted
    # from some early run inventories. This is a final audit, not a retroactive
    # claim that old runs originally recorded these additional fingerprints.
    data_inputs=[]
    for value in config.get('audit_data',{}).values():
        path=(root/value).resolve();path.relative_to(root.resolve())
        files=[path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
        assert files, value
        data_inputs.extend({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':file_hash(p)} for p in files)
    write_json(root/'docs/validation/final_data_inventory.json',{'timing':'Frozen at final audit, not at original historical run','files':data_inputs})
    f=json.loads((runs['04']/'raw/flood_report.json').read_text(encoding='utf-8'))
    depth=pd.read_parquet(root/f['output_directory']/'edge_depth_timeseries.parquet')
    assert depth.depth_m.ge(0).all() and np.isfinite(depth.depth_m).all()
    assert depth[depth.scenario.eq('normal')].depth_m.eq(0).all()
    assert depth.groupby('scenario').time_s.nunique().eq(97).all()
    a=json.loads((runs['06']/'raw/assignment_report.json').read_text(encoding='utf-8'))
    for r in [a['sioux'],*a['osm'].values()]:
        assert r['converged'] and r['relative_gap']<=1e-4 and r['node_balance_max_error']<1e-5
        assert abs(r['total_veh_h']-r['served_veh_h']-r['unserved_veh_h']-r['intrazonal_veh_h'])<1e-6
    assert a['sioux']['relative_flow_rmse']<.01
    resilience={}
    for key in ['07_small','07_nanshan']:
        q=pd.read_csv(runs[key]/'raw/resilience_timeseries.csv')
        assert q[['Qs','Qp','Q']].notna().all().all() and np.isfinite(q.Q).all()
        assert np.allclose(q[q.scenario.eq('normal')].Q,1)
        assert (q.relative_gap<=1e-4+1e-12).all() and q.converged.all() and q.node_balance_error.max()<1e-5
        assert np.allclose(q.total_veh_h,q.served_veh_h+q.unserved_veh_h+q.intrazonal_veh_h)
        assert np.allclose(q.groupby('time_s').total_veh_h.std().fillna(0),0,atol=1e-7)
        resilience[key]={'rows':len(q),'min_Q':float(q.Q.min()),'max_gap':float(q.relative_gap.max())}
    strategy=pd.read_csv(runs['09']/'raw/strategy_comparison.csv')
    assert (strategy.spent<=strategy.budget).all() and (strategy.selected_count<=strategy.K).all()
    optimum=json.loads((runs['09']/'raw/optimized_road_selection.json').read_text())
    assert optimum['greedy_absolute_gap']>=-1e-12
    sumo=pd.read_csv(runs['10']/'raw/sumo_comparison.csv')
    assert sumo.routed_plan_balance.eq(0).all() and sumo.vehicle_balance_departed_minus_arrived_running.eq(0).all() and sumo.teleport_events.eq(0).all()
    assert (sumo.sampled_total_planned==sumo.arrived+sumo.running_at_end+sumo.waiting_to_depart_at_end+sumo.unrouted_planned).all()
    assert sumo.groupby('region').shared_departure_plan_sha256.nunique().eq(1).all()
    experiments=pd.read_csv(runs['11']/'raw/experiment_results.csv')
    for group in ['B_strategies','F_heldout']:assert experiments[experiments.experiment.eq(group)].groupby('strategy').seed.nunique().eq(10).all()
    assert not set(experiments[experiments.experiment.eq('B_strategies')].seed).intersection(set(experiments[experiments.experiment.eq('F_heldout')].hazard_seed))
    assert len(experiments.experiment.unique())==6 # G is a separately sourced timing table
    stats=pd.read_csv(runs['11']/'raw/experiment_statistics.csv');assert stats.n.eq(10).all()
    s=json.loads((runs['09']/'config.json').read_text())['research'];exp=Experiment(root,s,42)
    replay_base=exp.evaluate();replay_selected=exp.evaluate(optimum['selected'])
    reference=float(strategy.loc[strategy.strategy.eq('resilience_greedy'),'R'].iloc[0]);base=float(strategy.loc[strategy.strategy.eq('none'),'R'].iloc[0])
    assert abs(replay_base-base)<1e-12 and abs(replay_selected-reference)<1e-12
    tests=ET.parse(root/'docs/validation/current-tests.xml').getroot().find('testsuite')
    assert int(tests.attrib['errors'])==0 and int(tests.attrib['failures'])==0
    ui=json.loads((root/'docs/validation/phase12/browser-verification.json').read_text(encoding='utf-8'))
    assert len(ui['pages_verified'])==8 and ui['csv_download_verified']
    assert ui['app_sha256']==file_hash(root/'app.py')
    for shot in ui['screenshots']:assert file_hash(root/shot['path'])==shot['sha256']
    delivery=json.loads((root/'docs/deliverables/delivery_manifest.json').read_text(encoding='utf-8'))
    assert delivery['verification']['final_content_checked'] and delivery['verification']['all_pages_and_slides_visually_reviewed']
    for original in delivery['originals_preserved']:assert file_hash(root/original['path'])==original['sha256']
    for doc in delivery.get('deliverables',[]):assert file_hash(root/doc['path'])==doc['sha256']
    report={'status':'passed','runs':reports,'foundation_runs':foundation,'final_data_files':len(data_inputs),'resilience':resilience,'tests_passed':int(tests.attrib['tests']),
        'replay':{'base_R':replay_base,'selected_R':replay_selected,'max_absolute_error':max(abs(replay_base-base),abs(replay_selected-reference))},
        'sumo_vehicle_accounting':'all six runs balance; zero teleports; shared planned departures verified',
        'scope':'Research prototype validated on small real network and selected full-Nanshan computations; not a calibrated city flood forecast or full-Nanshan optimization',
        'limitations':['Full Nanshan optimization was not performed; six-road governance and ten-seed suites apply only to small three-TAZ subset','Nanshan SUMO overlap with small optimized risk roads is empty, so its disaster/optimized outputs coincide','Shelters missing, facility entrances/address geocodes and SW zero datum unverified','Network efficiency and betweenness use explicitly labeled origin sampling','OD, capacities, flood, effect and cost parameters uncalibrated; C/D/E deterministic sensitivities use seed 42']}
    write_json(root/'docs/validation/final_audit.json',report)
    return report
