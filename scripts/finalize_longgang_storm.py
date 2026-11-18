"""Publish checked run metadata and Chinese steps, leaving Word/PPT untouched."""
from pathlib import Path
import argparse
import json
import yaml

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args();run=args.run.resolve()
relative=run.relative_to(ROOT).as_posix()
report=json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'))
audit=json.loads((ROOT/'docs/validation/longgang_storm/numerical_audit.json').read_text(encoding='utf-8'))
assert report['run_id']==audit['run_id'] and report['all_checks_passed'] and audit['all_checks_passed']
assert report['region']=='longgang' and not report['include_dapeng'] and not report['observed']
cfg_path=ROOT/'configs/active_research.yaml';cfg=yaml.safe_load(cfg_path.read_text(encoding='utf-8'))
cfg.update(synthetic_storm_ready=True,accepted_synthetic_storm=relative,storm_config='configs/longgang_storm.yaml',
    storm_model='synthetic_road_grid_bucket_no_surface_routing',
    status='synthetic_OD_and_storm_complete_uncalibrated_topology_and_road_response_pending')
cfg['next_required']=['boundary_datum_and_topology_audit','station_location_and_vertical_reference_review',
    'employment_POI_and_observed_flow_calibration','longgang_depth_to_road_response',
    'longgang_assignment_and_resilience_runs']
cfg_path.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding='utf-8')
base={r['scenario']:r for r in report['baseline_summary']}
rows='\n'.join(f'| {base[s]["reference_rain_mm"]} | {base[s]["peak_depth_m"]:.4f} | {base[s]["max_site_duration_above_015_h"]:.2f} | {base[s]["latest_recovery_h_001"]-13:.2f} | {base[s]["max_source_features_atleast_030"]:,} |' for s in ['general','severe','extreme'])
stage=f'''# 龙岗暴雨内涝情景阶段报告

2026-11-18完成龙岗不含大鹏的合成道路网格积水情景。当前运行：`{relative}`。

方法定位为“合成道路低点＋合成降雨驱动的动态积水假设”，更接近方案A的参数化扩展，但没有已核实历史积水点。没有实现B的地表汇流或C的管网二维耦合，不能用于真实积水预测。逐步方法、公式、参数与输入输出见[LONGGANG_STORM_MODEL.md](LONGGANG_STORM_MODEL.md)。

## 规模与范围

沿用龙岗OD边界，按不超过100 m道路间距采样{report['sample_count']:,}点，地形无缺测，250 m道路网格内选出{report['site_count']:,}个合成低点代理。{report['accepted_source_features_in_scope']:,}个接受的源道路要素中，{report['modelled_source_features']:,}个参与地面积水模型，952个桥隧或非零layer保持未建模NaN。

从既有推定OD图读出{report['directed_arc_mapping_rows']:,}条有向弧的精确保存ID与u/v/key，426条跨研究边界弧单独标记；图拓扑本身仍未认证。源线暴露取其所有关联代理水深最大值，是偏保守的几何关联，不是实测整条路水深。

## 基准结果

| 参考总雨量 mm | 代理单元最大水深 m | 单点水深大于0.15 m最长持续 h | 雨停后全部曾超1 cm单元恢复 h | 同时达到0.30 m源要素数最大值 |
|---|---:|---:|---:|---:|
{rows}

三档基准峰值均在第10.5小时。雨停为第13小时；基准在24小时内均退至分析阈值以下。道路要素数不表示实测封路、独立道路数、淹没面积或全有向路网比例。

正常/100/200/300 mm四档×排水或退水五组参数，共20组过程，每组96区间及97端点。慢退水τ=8 h的三档雨量分别有38/925/1833个单元在24小时仍超过1 cm，已记右删失，未填虚构恢复时刻。参数变化不等同于真实工程改造效果。

## 验证

141项测试通过，56条Rasterio/Affine待弃用警告，pip check无冲突。{len(report['checks'])}项运行检查通过。区间/事件水量平衡最大误差为{report['max_interval_balance_residual_mm']:.3e}/{report['max_event_balance_residual_mm']:.3e} mm。所有代理点边界偏差最大{report['maximum_site_boundary_error_m']:.3e} m，仅允许1微米数值容差。

独立审计覆盖20组共{audit['site_endpoint_values_audited']:,}个单元端点值，逐项复核降雨、水量递推、无雨离散闭式解及道路最大值聚合；复核{audit['hashes_verified']}个输入输出SHA和ZIP内{audit['zip_files_verified']}个文件。道路聚合最大误差0，递推误差{audit['max_recurrence_error_m']:.3e} m。

5分钟复核将原15分钟雨量均分，三档共同端点最大差异0.00394/0.00813/0.01232 m。这是数值敏感性结果，不能代替实测校准或证明连续解收敛。图像PNG已逐张查看，SVG留在本地运行包。

ZIP SHA256：`{audit['zip_sha256']}`。审计证据：`docs/validation/longgang_storm/`。

## 交付与后续

提供参考雨量、点参数、点水深、水量账本、源线水深NPZ和基准Parquet、阈值时长与恢复、道路覆盖状态、精确图弧映射、DSM裁剪、三张过程与空间图。源码、配置和SHA可追溯，历史失败与旧运行目录均保留。

缺少事件雨量、已核实历史点、路面水深、管网及流量，DSM包含建筑植被；独立桶之间没有地表汇流、水交换或河潮顶托。降雨、汇水面积比、排水和退水参数均为假设。

本次没有计算龙岗速度/容量退化、封路、交通分配、韧性或SUMO。后续先将水深映射到道路性能并保留未知道路状态，再使用龙岗OD计算交通影响。开发聊天仅更新项目和GitHub，Word/PPT由专门文档聊天负责，本轮未改写。
'''
(ROOT/'docs/PHASE_LONGGANG_STORM_REPORT.md').write_text(stage,encoding='utf-8')
block=f'''## 2026-11-18 龙岗暴雨内涝情景

已完成龙岗不含大鹏的合成降雨—蓄水—退水情景：{report['site_count']:,}个250 m道路网格代理，6,848个地面源线要素建模，952个桥隧或非零layer保持未知NaN。四档参考雨量0/100/200/300 mm，五组参数，96区间/97端点；基准最大水深0.2613/0.5439/0.8266 m。与OD推定图86,807条弧的保存ID精确对应，426条跨界弧标记。

方法是合成道路低点＋动态蓄水桶，更接近A的参数化扩展，未使用已核实历史积水点，未实现B地表汇流或C管网二维耦合。所有参数未经实测标定。141项测试、{len(report['checks'])}项运行核验与20组独立水量/道路聚合/SHA/ZIP审计通过，5分钟复核最大端点差异1.23 cm。仅完成情景输入，未重算道路速度/容量、交通分配、韧性或SUMO。

当前包`{relative}`。方法步骤见`docs/LONGGANG_STORM_MODEL.md`，阶段报告见`docs/PHASE_LONGGANG_STORM_REPORT.md`。大型数据保留本机，代码、配置、说明与核验记录上传GitHub；Word/PPT由专门文档聊天负责，本轮不改写。以下保留此前阶段记录。
'''
for name in ['AGENTS.md','README.md','DATA_SOURCES.md','MODEL_ASSUMPTIONS.md','PLAN.md','PROGRESS.md','EXPERIMENT_LOG.md','docs/USER_GUIDE.md','docs/FINAL_REPORT.md']:
    path=ROOT/name;text=path.read_text(encoding='utf-8')
    if '## 2026-11-18 龙岗暴雨内涝情景' in text:continue
    first,rest=text.split('\n',1);path.write_text(first+'\n\n'+block+rest,encoding='utf-8')
print('Published stage report and active config:',relative)
