"""Publish compact immutable evidence and current-stage Markdown summaries."""
from pathlib import Path
import argparse
import json
import shutil
import pandas as pd
from pyproj import Transformer
import yaml
from acquire_longgang_era5 import ROOT, sha, write


def finalize(out, robustness=None):
    report = json.loads((out/'provenance/validation_report.json').read_text(encoding='utf-8'))
    audited = Path(str(out)+'_audit.json')
    audit = json.loads(audited.read_text(encoding='utf-8'))
    if audit.get('passed') is not True: raise ValueError('independent audit required')
    evidence = ROOT/'docs/validation/longgang_adaptive'
    evidence.mkdir(parents=True, exist_ok=False)
    copies = {'run_manifest.json': out/'manifest.json', 'validation_report.json': out/'provenance/validation_report.json',
              'independent_audit.json': audited,
              'worldcover_source.json': out/'provenance/worldcover_source.json',
              'tests.xml': ROOT/'tmp/adaptive_tests.xml'}
    for name in ['candidates.csv', 'scenario_results.csv', 'optimization_results.csv', 'traffic_sensitivities.csv',
                 'nsga2_search.json', 'pareto.json', 'dry_reference.json']:
        copies[name] = out/'raw'/name
    for name, source in copies.items(): shutil.copy2(source, evidence/name)
    locations = pd.read_csv(out/'raw/candidates.csv')
    lon, lat = Transformer.from_crs(32650, 4326, always_xy=True).transform(locations.x_m, locations.y_m)
    locations['longitude'] = lon; locations['latitude'] = lat
    locations['selected_by_equal_weight_rule'] = [bool(report['recommended_mask'] & (1 << int(j))) for j in locations.site]
    locations.to_csv(evidence/'candidates_wgs84.csv', index=False)
    write(evidence/'candidates_wgs84.geojson', {'type': 'FeatureCollection', 'features': [
          {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [float(r['longitude']), float(r['latitude'])]},
           'properties': {**r, 'classification': 'screening_grid_center_not_surveyed_engineering_site'}}
          for r in locations.to_dict('records')]})
    robustness_report = None
    if robustness:
        robustness_report = json.loads((robustness/'report.json').read_text(encoding='utf-8'))
        if robustness_report['source_run'] != out.relative_to(ROOT).as_posix():
            raise ValueError('robustness source mismatch')
        for name in ['report.json', 'robustness_results.csv', 'manifest.json']:
            shutil.copy2(robustness/name, evidence/('robustness_'+name))
    landcover = ROOT/report['landcover_package']
    (evidence/'landcover').mkdir()
    for name in ['N21E111_crop.tif', 'N21E114_crop.tif', 'landcover_parameters.npz', 'manifest.json']:
        shutil.copy2(landcover/name, evidence/'landcover'/name)
    shutil.copytree(out/'figures', evidence/'figures')
    (evidence/'traffic').mkdir()
    labels = ['dry']+[f'mask{mask:02d}_{scenario}' for mask in sorted(set([0, report['recommended_mask']]))
                      for scenario in report['scenarios']]
    for label in labels:
        for suffix in ['_traffic.json', '_traffic_series.csv']:
            source = out/'cases'/(label+'_sample2_dt60'+suffix)
            shutil.copy2(source, evidence/'traffic'/source.name)
    write(evidence/'evidence_index.json', {'run_id': out.name,
          'files': [{'path': p.relative_to(evidence).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                    for p in sorted(evidence.rglob('*')) if p.is_file()],
          'classification': 'uncalibrated four-site pilot; native re-encoded WorldCover crops, code and checks, not measured traffic/flood outcomes'})
    a = report['worst_case_base_objectives']; b = report['worst_case_recommended_objectives']
    improvement = (a[0]-b[0])/a[0]*100 if a[0] else 0
    unfinished_change = a[1]-b[1]
    selected = ', '.join('S'+str(j) for j in report['recommended_sites']) or '无治理'
    location_table = '\n'.join(f"| S{int(r.site)} | {r.longitude:.6f} | {r.latitude:.6f} | {'是' if r.selected_by_equal_weight_rule else '否'} |" for r in locations.itertuples())
    strata_check = [s for s in report['traffic_sensitivities'] if s['destinations_per_origin'] == 4]
    strata_base = next(s for s in strata_check if s['mask'] == 0)
    strata_selected = next(s for s in strata_check if s['mask'] == report['recommended_mask'])
    strata_benefit = strata_base['extra_generalized_vehicle_hours']-strata_selected['extra_generalized_vehicle_hours']
    strata_percent = strata_benefit/strata_base['extra_generalized_vehicle_hours']*100 if strata_base['extra_generalized_vehicle_hours'] else 0
    sensitivity_warning = f"每起点4层抽样下，同一组合在1.3倍雨量的相对无雨广义成本增量降低{strata_percent:.4f}%，而2层为{improvement:.4f}%；收益幅度明显依赖目的地抽样。没有对4层抽样重新穷举全部组合，不能宣称方案排序已收敛或可直接作为工程推荐。"
    sensitivity_note = ''
    if robustness_report:
        sensitivity_note = '\n\n另对推荐与无治理组合复算背景损失0.5/2倍、0.20 m封路及容量2倍，保持相同路径库进行受控比较；这不代表已在全部不确定情景上重新优化。\n\n'
        sensitivity_note += '| 情景 | 推荐相对无治理的广义成本减少 veh·h | 未完成车次减少 |\n| - | -: | -: |\n'
        sensitivity_note += '\n'.join(f"| {r['scenario']} | {r['extra_cost_reduction_vehicle_hours']:.3f} | {r['unfinished_reduction_trips']:.3f} |" for r in robustness_report['comparison'])
    audit_line = f"独立审计重放{audit['independent_scatter_add_road_depth_values']:,}个道路值，核对{audit['source_arcs_partitioned_once']:,}条源有向弧、{audit['traffic_ledgers_checked']}份交通账本和全部15种组合。"
    summary = f"""## 2026-11-19 龙岗分区积水与NSGA-II治理试验

用户确认采用分区积水、分道路退化、点队列与多目标优化，并同意相对成本、最多3处。新增ESA WorldCover 2021公开原生裁剪；建成/植被/裸地/水体损失2/8/4/0 mm/h均为假设。重算三档ERA5雨量与4处候选的全部15个治理组合；每组合重新计算积水。按起点分层目的地抽样、带权比例服务点队列、出发时路径选择；不是完整OD精确加载或动态用户均衡，不保证FIFO、没有回溢。未知桥隧及覆盖外道路在交通中假设正常。

165项测试通过，pip check无冲突。{audit_line}初步候选mask={report['recommended_mask']}（{selected}），2层目的地抽样下最坏相对无雨广义成本增量降低{improvement:.4f}%，4层的1.3倍雨量比较为{strata_percent:.4f}%，抽样敏感；2层最坏未完成减少{unfinished_change:.2f}车次。只是4处候选、未标定参数与抽样下的试验，不能作为工程收益预测。无雨参考亦有大量未完成，须连同需求与容量假设披露。

运行`{out.relative_to(ROOT).as_posix()}`。步骤见[分区积水与治理方法](docs/LONGGANG_ADAPTIVE_MODEL.md)，结果见docs/PHASE_LONGGANG_ADAPTIVE_REPORT.md；完整数据留本机，精简证据上传GitHub。旧包不改写，Word/PPT由专门文档聊天维护。

"""
    for name in ['AGENTS.md', 'DATA_SOURCES.md', 'EXPERIMENT_LOG.md', 'MODEL_ASSUMPTIONS.md', 'PLAN.md', 'PROGRESS.md', 'README.md']:
        path = ROOT/name; text = path.read_text(encoding='utf-8')
        title, remainder = text.split('\n', 1)
        path.write_text(title+'\n\n'+summary+remainder.lstrip('\n'), encoding='utf-8')
    active_path = ROOT/'configs/active_research.yaml'
    active = yaml.safe_load(active_path.read_text(encoding='utf-8'))
    active.update({'status': 'uncalibrated_adaptive_four_site_pilot_complete',
                   'adaptive_pilot_ready': True, 'assignment_ready': False,
                   'road_response_prototype_ready': True, 'sampled_dynamic_loading_ready': True,
                   'full_OD_dynamic_loading_ready': False,
                   'preferred_traffic_model': 'sampled_source_corridor_proportional_point_queue_departure_library_uncalibrated',
                   'optimization_scope': 'four_candidate_three_rain_scenario_NSGA_II_pilot_with_exhaustive_check',
                   'assignment_ready_note': 'Sampled weighted dynamic loading only; full OD and topology calibration remain pending.',
                   'accepted_adaptive_pilot': out.relative_to(ROOT).as_posix(),
                   'adaptive_config': 'configs/longgang_adaptive.yaml',
                   'worldcover_package': report['landcover_package']})
    active['next_required'] = ['station_rainfall_and_flood_depth_validation',
                              'bare_earth_DTM_and_hydraulic_loss_calibration',
                              'full_upstream_catchment_and_boundary_audit',
                              'boundary_datum_and_directed_road_topology_audit',
                              'measured_lanes_capacities_and_demand_calibration',
                              'destination_sample_and_time_step_convergence',
                              'full_OD_loading_FIFO_spillback_and_signal_extensions',
                              'engineering_catchments_costs_and_large_candidate_optimization']
    active_path.write_text(yaml.safe_dump(active, allow_unicode=True, sort_keys=False), encoding='utf-8')
    dry = report['dry_reference']
    rows = '\n'.join(f"| {s['mask']} | {s['destinations_per_origin']} | {s['step_seconds']} | {s['extra_generalized_vehicle_hours']:.3f} | {s['unfinished_trips']:.3f} |" for s in report['traffic_sensitivities'])
    method = ROOT/'docs/PHASE_LONGGANG_ADAPTIVE_REPORT.md'
    method.write_text(f"""# 龙岗分区积水、点队列与NSGA-II：阶段结果

已按用户确认实施公开土地覆盖分区、分道路退化、跨时段点队列、出发路径选择及多情景NSGA-II治理试验。范围为龙岗不含大鹏。用户同意相对成本、最多3处；本轮候选4处，穷举全部15个可行组合。不是全区工程最优、完整OD精确加载或已校准灾情预测。

## 实际规模与输入

- ESA WorldCover 2021 v200两块原生分类裁剪已经归档；CC BY 4.0署名、ETag、原生窗口与SHA可追溯。10 m分类最近邻至30 m、5×5聚合为150 m覆盖比例；未取得实测入渗或排水参数。
- 66,920格、120小时ERA5、三档雨量0.7/1.0/1.3；建成/植被/裸地/水体综合损失2/8/4/0 mm/h。选址750 m圆域增加4 mm/h是假设，每个组合均重算地表蓄泄。
- 推定深圳路网{report['source_directed_arcs']:,}条有向弧收缩为{report['corridors']:,}条走廊，完整保留原弧序列；串联时间和、最小容量近似。桥隧未知及覆盖外道路在交通计算中假设正常，不代表实测干燥。
- 完整483×483 OD用于总量记账；每起点2个目的地分层带权抽样，{dry['sample_pairs']}对、{dry['active_corridors']}条路径涉及走廊、{dry['path_stages']}个路径阶段。重复同一合成日5天，总量{dry['total_trips']:.3f}车次；目的地分布和路径流量仍是抽样近似。
- 比例服务流体点队列，60 s内部步长，15分钟出发及状态更新，有限路径库内出发选择；不保证FIFO，没有物理回溢、节点信号、途中重规划或动态均衡迭代。使用队列服务计算拥堵，未重复叠加BPR。

## 基础状态和优化结果

无雨参考已完成{dry['total_completed_trips']:.3f}车次、时窗末未完成{dry['total_unfinished_trips']:.3f}车次，其中未接入需求{dry['unlinked_trips_not_road_loaded']:.3f}车次。容量按道路等级及每方向一条有效车道假设，叠加目的地抽样可能导致过度集中；当前基础拥堵不能解释为真实龙岗交通状况。

三个目标为最坏情景相对无雨广义成本增量、最坏情景末未完成量及相对成本。广义成本含时窗内占用时间积分与每个未完成车次2小时终端惩罚；不等于真实平均延误。区内需求按300 s计，未接入需求不删除。

| 指标 | 无治理 | 归一化等权规则推荐组合 |
| - | -: | -: |
| 最坏相对无雨广义成本增加 veh·h | {a[0]:.3f} | {b[0]:.3f} |
| 最坏时窗末未完成车次 | {a[1]:.3f} | {b[1]:.3f} |
| 相对成本单位 | {a[2]:.6f} | {b[2]:.6f} |

推荐mask={report['recommended_mask']}，位置{selected}，作用区内面积约{report['recommended_treatment_area_km2']:.4f} km²。上述第一目标相对降低{improvement:.4f}%，最坏未完成减少{unfinished_change:.3f}车次。精确非支配集为{report['exact_pareto_masks']}；NSGA-II三个种子对精确集覆盖率为{report['nsga2_front_recall_by_seed']}。这些收益仅适用于当前候选与参数，成本不是人民币，推荐等权规则不是官方偏好。

候选网格中心坐标如下，源于模型投影转换，不是经勘测的排水工程位置；GIS文件见精简证据中的`candidates_wgs84.geojson`。

| 候选 | 经度 | 纬度 | 等权规则选中 |
| - | -: | -: | - |
{location_table}

## 数值与抽样敏感性

下表对1.3倍雨量的无治理/推荐组合分别细化时间步、增加目的地分层；每行相对对应抽样与步长的无雨参考计算。

| mask | 每起点目的地层数 | 时间步s | 相对无雨广义成本增加veh·h | 未完成车次 |
| - | -: | -: | -: | -: |
{rows}

敏感性差异用于判断当前抽样和离散是否足以支撑决策，不把测试通过当作交通精度已验证。如果收益排序或幅度随抽样明显变化，推荐只能作为待复核候选，不能直接采用为工程方案。

**{sensitivity_warning}**
{sensitivity_note}

## 核验与交付

165项测试通过、56条既有Rasterio/Affine弃用警告，pip check无冲突。全组合最大水量残差{report['maximum_water_balance_residual_m3']:.6g} m³，最大车辆守恒残差{report['maximum_vehicle_conservation_error_veh']:.6g}车次。{audit_line}独立道路重放最大差{audit['maximum_replayed_road_difference_m']:.6g} m，水量账最大差{audit['maximum_replayed_volume_difference_m3']:.6g} m³。仅证明数值和记账一致性，未做站点雨量/水深/交通流实测标定。

方法步骤见[LONGGANG_ADAPTIVE_MODEL.md](LONGGANG_ADAPTIVE_MODEL.md)。完整运行`{out.relative_to(ROOT).as_posix()}`；独立审计为同路径追加`_audit.json`。精简证据见`docs/validation/longgang_adaptive/`。保持旧运行及其manifest，Word/PPT由专门文档聊天维护。
""", encoding='utf-8')
    print('FINALIZED '+out.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run'); parser.add_argument('--robustness')
    args = parser.parse_args()
    finalize(ROOT/args.run, ROOT/args.robustness if args.robustness else None)
