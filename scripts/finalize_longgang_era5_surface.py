"""Publish reviewable Method B evidence/docs without rewriting frozen run files."""
from pathlib import Path
import argparse
import difflib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
import yaml
from acquire_longgang_era5 import ROOT,sha,write


def finalize(run):
    report=json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'))
    ev=ROOT/'docs/validation/longgang_era5_surface';ev.mkdir(parents=True,exist_ok=True)
    audit=json.loads((ev/'independent_audit.json').read_text(encoding='utf-8'))
    assert report['all_checks_passed'] and audit['passed'] and report['run_id']==audit['run_id']
    assert sha(run/'manifest.json')==audit['manifest_sha256']
    tests=ET.parse(ROOT/'docs/validation/rainfall/era5_surface_tests.xml').getroot()
    suites=list(tests.iter('testsuite'))
    test_count=sum(int(s.get('tests',0)) for s in suites)
    assert all(int(s.get('failures',0))+int(s.get('errors',0))==0 for s in suites)
    rain=ROOT/report['rainfall_package']
    (ev/'figures').mkdir(exist_ok=True)
    for name in ['request.json','response.json','response_metadata.json','grid_metadata.json','attribution.json','manifest.json']:
        shutil.copy2(rain/name,ev/('era5_'+name))
    shutil.copy2(run/'manifest.json',ev/'run_manifest.json')
    shutil.copy2(run/'provenance/validation_report.json',ev/'validation_report.json')
    for name in ['scenario_summary.csv','hourly_rainfall.csv']:
        shutil.copy2(run/'raw'/name,ev/name)
    for path in sorted((run/'figures').iterdir()):shutil.copy2(path,ev/'figures'/path.name)
    evidence={'run_id':report['run_id'],'files':[{'path':p.relative_to(ev).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
              for p in sorted(ev.rglob('*')) if p.is_file() and p.name!='evidence_index.json'],
              'visual_review':'Three PNG figures individually viewed; Chinese labels and numerical meaning checked. SVG companions preserved.',
              'raw_data_attribution':'Weather data by Open-Meteo.com; Copernicus Climate Change Service / ECMWF ERA5. CC BY 4.0.',
              'raw_data_changes':'ERA5 response.json copied byte-for-byte; hourly/scenario CSVs are derived model products.'}
    write(ev/'evidence_index.json',evidence)
    active_path=ROOT/'configs/active_research.yaml';active=yaml.safe_load(active_path.read_text(encoding='utf-8'))
    active.update({'status':'ERA5_method_B_surface_complete_uncalibrated_road_response_pending',
        'assignment_ready':False,'method_B_surface_ready':True,
        'preferred_flood_model':'ERA5_DSM_D8_linear_storage_method_B_uncalibrated',
        'accepted_era5_surface':run.relative_to(ROOT).as_posix(),'era5_rainfall_package':report['rainfall_package'],
        'era5_surface_config':'configs/longgang_era5_surface.yaml',
        'next_required':['station_rainfall_and_flood_depth_validation','bare_earth_DTM_and_land_cover_calibration',
            'full_upstream_catchment_and_boundary_audit','boundary_datum_and_road_topology_audit',
            'longgang_depth_to_road_response','longgang_assignment_and_resilience_runs']})
    active_path.write_text(yaml.safe_dump(active,allow_unicode=True,sort_keys=False),encoding='utf-8')
    section=f'''\n## 2026-11-18 ERA5驱动B方案地形汇流原型\n\n已采用用户选择的ERA5/Open-Meteo：9个网格×120小时（北京时间2023-09-06 00:00至09-11 00:00），龙岗不含大鹏面积加权累计{report['district_mean_rain_total_mm']:.2f} mm。150 m DSM计算域{report['domain_cells']:,}格，固定D8地形蓄泄与洼地储量；8组情景、481端点，6,848条地面源线建模、952条桥隧等保持未知。基准道路样点最大估计深度1.0309 m，损失能力减半/加倍为4.0988/0.0113 m，显示强假设敏感性，不能作为实测灾情预测。\n\n{test_count}项测试与独立水量/原始降雨/32,188,520网格端点/26,351,104道路值/SHA/ZIP核验通过；180→60 s最大道路端点差2.315 cm，5→10 km外扩差3.935 cm。B是简化地形汇流，非SWMM或二维浅水方程；未标定、未完成全上游认证，未重跑交通分配或韧性。方法步骤见[ERA5 B方案](docs/LONGGANG_ERA5_SURFACE_MODEL.md)，阶段报告见docs/PHASE_LONGGANG_ERA5_SURFACE_REPORT.md。新包`{run.relative_to(ROOT).as_posix()}`；原合成包与历史manifest保留。Word/PPT由专门文档聊天维护。\n\n'''
    names=['README.md','PROGRESS.md','PLAN.md','DATA_SOURCES.md','MODEL_ASSUMPTIONS.md','EXPERIMENT_LOG.md','AGENTS.md']
    for name in names:
        path=ROOT/name;old=path.read_text(encoding='utf-8')
        if '## 2026-11-18 ERA5驱动B方案地形汇流原型' in old:raise ValueError('phase already finalized')
        h,sep,tail=old.partition('\n');path.write_text(h+'\n'+section+tail,encoding='utf-8',newline='\n')
    # Preserve unrelated worktree edits when staging this phase's AGENTS hunk.
    git=['git','-c','safe.directory=C:/Users/zh/Desktop/git/jiaotong']
    base=subprocess.check_output(git+['show','HEAD:AGENTS.md'],cwd=ROOT).decode('utf-8')
    h,s,r=base.partition('\n');desired=h+'\n'+section+r
    patch=''.join(difflib.unified_diff(base.splitlines(True),desired.splitlines(True),fromfile='a/AGENTS.md',tofile='b/AGENTS.md'))
    (ROOT/'tmp').mkdir(exist_ok=True)
    (ROOT/'tmp/era5_surface_agents.patch').write_text(patch,encoding='utf-8',newline='\n')
    base_summary=next(r for r in report['scenarios'] if r['case']=='era5_baseline')
    phase=f'''# 龙岗 ERA5 B方案阶段报告\n\n用户选择ERA5/Open-Meteo作为降雨源后，完成数据获取、地形汇流原型运行与数值审计。本阶段是B方案简化原型，不是已校准历史内涝重建。\n\n## 数据与范围\n\n- 时间：北京时间2023-09-06 00:00至09-11 00:00，共120个完整小时；每条ERA5降水对应前一小时累计。\n- 获取9个不同的0.25°网格，1,080条有效雨量；主域使用6个、龙岗面积加权使用4个。区内累计{report['district_mean_rain_total_mm']:.6f} mm，最大面积平均1小时量{report['district_mean_max_hour_mm']:.6f} mm。不是雨量站观测。\n- 龙岗（不含大鹏）{report['district_area_km2']:.6f} km²；30 m DSM平均至150 m，主域239×280={report['domain_cells']:,}格，行政边界外扩5 km矩形，外围为无外来流入的开放出口；10 km外扩做敏感性检查，不代表上游汇水区完整认证。\n- 33,597个既有地面道路采样位置映射到8,530个模型网格；6,848条地面源线有估计值，952条桥隧等保持NaN，保留86,807条推定OD图有向弧的原ID映射。\n\n## 运行结果\n\n8组参数、481个15分钟输出端点。基准道路样点最大估计深度{base_summary['maximum_ground_road_sample_depth_m']:.6f} m；同时超过0.15 m的源线最多45条，达到0.30 m的最多2条。这些是模型暴露统计，不代表45条实测积水道路或真实封路。区内估计深度>0.15 m同时最大面积{base_summary['maximum_simultaneous_area_over_015_km2']:.6f} km²，各时刻峰值并集面积{base_summary['district_area_ever_over_015_km2']:.6f} km²。\n\n合并损失假设2/4/8 mm/h时，道路样点最大估计深度4.098790/1.030854/0.011329 m；雨量0.7/1/1.3倍为0.165155/1.030854/2.498684 m。输出强烈依赖未标定假设，不能据此确定真实积水深度。\n\n全计算域基准累计降雨{base_summary['domain_rain_m3']:.3f} m³，合并损失{base_summary['domain_loss_m3']:.3f} m³，边界排出{base_summary['domain_boundary_outflow_m3']:.3f} m³，末端蓄水{base_summary['domain_final_storage_m3']:.3f} m³。损失占降雨约{100*base_summary['domain_loss_m3']/base_summary['domain_rain_m3']:.3f}%，反映参数设定；不是测得排水效率。时窗末端仍有蓄水，不能宣称全部退水。\n\n## 验证与局限\n\n{test_count}项测试通过（56条既有Rasterio/Affine待弃用警告），pip check无冲突。10项运行检查通过。独立核验1,080条原始响应雨量、32,188,520网格端点、26,351,104个已建模道路值、16个输入SHA、57个输出SHA及58个ZIP文件。最大独立基准重放误差5.92e-8 m（float32归档）；8组全域累计水量残差最大1.43e-6 m³。\n\n180→60 s内部时间步最大道路端点差0.023146 m；按本原型的绝对0.02 m＋峰值5%容差通过，这不是高精度水动力收敛证明。5→10 km外扩最大道路端点差0.039351 m。图中网格峰值可来自不同时刻，面积只按150 m像元估算；没有模拟像元内部分淹没。\n\nDSM含建筑与植被，不是裸地DTM；最大地形洼地储量阈值约29.38 m，可能混有DSM及聚合伪洼地，不能当作真实洼地深度。固定D8树、逐格储量和合并损失只构成简化汇流，没有二维动量、回水、管网或动态流向；干初始条件和小时内均匀降雨均为假设。未接入站点水深校准，未更新交通速度/容量、分配、韧性或SUMO。\n\n## 交付\n\n模型包：`{run.relative_to(ROOT).as_posix()}`；降雨原件：`{report['rainfall_package']}`；包ZIP SHA256：`{audit['zip_sha256']}`。完整数据与环境留本机，源码、配置、说明、精简降雨原件及图件证据上传GitHub。原合成包和失败/早期获取包保留。\n\n步骤与重现命令见[方法说明](LONGGANG_ERA5_SURFACE_MODEL.md)，核验记录见`docs/validation/longgang_era5_surface/`。本轮未改写Word/PPT。\n'''
    (ROOT/'docs/PHASE_LONGGANG_ERA5_SURFACE_REPORT.md').write_text(phase,encoding='utf-8')
    print('Finalized '+report['run_id'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');finalize((ROOT/parser.parse_args().run).resolve())
