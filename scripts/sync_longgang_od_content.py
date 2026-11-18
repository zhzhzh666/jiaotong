"""Synchronize calculated Longgang OD facts into the maintained shared content."""
from pathlib import Path
import argparse
import json
import shutil
import yaml

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args()
run=args.run.resolve();relative=run.relative_to(ROOT).as_posix()
r=json.loads((run/'demand_report.json').read_text(encoding='utf-8'))
assert r['region']=='longgang' and not r['observed_od'] and not r['include_dapeng']
v=ROOT/'docs/validation/longgang_od';v.mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'.cache/longgang_od_tests.xml',v/'tests.xml')
status='龙岗不含大鹏的合成OD已生成；推定拓扑待核，交通分配与韧性待重算。南山结果作为历史保留。'
target=ROOT/'docs/deliverables/content.json'
data=json.loads(target.read_text(encoding='utf-8'))
data['status']=status
data['cover_subtitle']='龙岗不含大鹏 合成交通需求计算完成'
data['active_research']['status']=status
data['active_research']['synthetic_od_path']=relative
data['longgang_od']={'path':relative,'report':r,'tests_passed':136,'tests_report':'docs/validation/longgang_od/tests.xml',
                    'audit':'docs/validation/longgang_od/numerical_audit.json','observed':False,'assignment_rerun':False}
sections=data['final']['sections']
sections[0]['paragraphs'][0]='2026年11月18日：龙岗不含大鹏的483×483合成OD已生成，包含471个区内分区和12个外部网关。拓扑为线几何推定，尚未核准；南山交通与韧性结果保留为历史。'
sections[0]['slide_points'][-1]='龙岗不含大鹏 合成OD完成，拓扑待核'
for section in sections:
    if section['title']=='龙岗研究区 数据接收与迁移范围':
        section['paragraphs'][-1]='本页记录OD计算前的数据接收状态。本批未提供实测雨量、官方OD或实测车流。随后完成的人口裁剪、推定路网和合成需求见后两节；龙岗积水、交通分配与韧性尚未重算。'
        section['slide_points'][-1]='接收时点记录，后续合成OD见第32—33张。'
new=[
 {'title':'龙岗交通需求 合成OD计算',
  'paragraphs':[
   '范围沿用随包龙岗主面，不含大鹏，面积386.96 km²。在EPSG32650中按1 km网格裁剪为471个分区，另设12个真实跨界道路弧对应的外侧顶点网关，形成483×483矩阵。网关节点身份由线几何推定。',
   'WorldPop 2020模型人口按“原始像元人数×与分区重叠面积÷整个原始像元面积”分摊，合计3,172,796.99人。假设像元内人口均匀，边界像元不向区内重新归一。产生与吸引均使用人口代理，缺少就业和商业POI，不能解释真实通勤方向。',
   '基础内部需求Q=P×0.05×0.50÷1.25=63,455.94 veh/h。0.05为每人每小时出行率，0.50为机动车比例，1.25为平均载客率，均属未标定假设。流入和流出各增加0.10Q，12个网关等额设置边际总量。',
   '采用exp(−t/1200)重力核，对区内、流入、流出三个块分别IPF配平。最大相对误差8.77×10⁻¹⁰。外部到外部需求不在本次建模范围，其零值不能视为实测无过境交通。'],
  'figure':relative+'/longgang_zones_od.png','caption':'龙岗分区人口与早高峰合成OD，行表示起点、列表示终点',
  'source_label':run.name+' / 本地所供OSM线几何与WorldPop 2020模型人口；OD为未标定合成估计','ppt_native':False,
  'slide_points':['471个分区＋12个网关，483×483矩阵','模型人口317.28万人，人口同时代理产生与吸引','重力模型＋IPF，最大相对配平误差8.77×10⁻¹⁰']},
 {'title':'龙岗交通需求 时间变化与使用限制',
  'paragraphs':[
   '基准平峰76,147.13 veh/h；07:00—10:00采用2倍，为152,294.26 veh/h；17:00—20:00采用1.8倍，为137,064.83 veh/h。其余18小时为平峰。共输出96个15分钟完整方阵，区间车次数=小时流率×0.25，保留小数期望值。',
   '全天基准2,238,725.56车次，低/高需求取0.7/1.3倍，分别1,567,107.89和2,910,343.23车次。峰值时段与倍数均为仿真假设；本次人口吸引与产生相同，早晚高峰只改变总量，不构造通勤方向差异。',
   '全深圳线几何推定图含307,426节点、451,801条有向弧，保留平行边和单行方向。仅连接相同已有顶点，同层连接及异层共同端点衔接均待核；不自动打断几何交叉线。道路缺少原始节点ID、转向限制等，拓扑尚未认证。',
   '401个区内分区已连接，70个未接入。平峰可路由70,707.89、不可达3,492.31、区内1,946.93 veh/h，全部需求保留。不可达阻抗7200秒仅用于需求生成；区内300秒为假设，均不能当成实际通行时间。136项测试通过，13项运行检查及独立数值审计通过。未重算积水、交通分配、韧性或SUMO。'],
  'figure':relative+'/longgang_daily_demand.png','caption':'假设的15分钟需求及低中高敏感性，并非观测曲线或置信区间',
  'source_label':run.name+' / interval_totals.csv；docs/LONGGANG_OD_MODEL.md','ppt_native':False,
  'slide_points':['平峰7.61万，早峰15.23万，晚峰13.71万车次/小时','全天基准223.87万车次，低/高为0.7/1.3倍','保留4.59%不可达和2.56%区内需求，拓扑待核']}
]
data['final']['sections']=[s for s in sections if not s['title'].startswith('龙岗交通需求 ')]+new
target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
cfg_path=ROOT/'configs/active_research.yaml';cfg=yaml.safe_load(cfg_path.read_text(encoding='utf-8'))
cfg.update(status='synthetic_OD_complete_inferred_topology_uncertified_assignment_pending',synthetic_od_ready=True,
           accepted_synthetic_od=relative,od_config='configs/longgang_od.yaml',assignment_ready=False)
cfg['next_required']=['boundary_datum_and_topology_audit','station_location_and_vertical_reference_review',
                      'employment_POI_and_observed_flow_calibration','new_inundation_assignment_and_resilience_runs']
cfg_path.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding='utf-8')
common=f'''## 2026-11-18 龙岗合成OD计算

龙岗不含大鹏的483×483合成OD已生成：471个1 km区内分区、12个外部网关，WorldPop 2020面积分摊人口3,172,796.99人。平峰76,147.13、早峰152,294.26、晚峰137,064.83 veh/h；基准全天2,238,725.56车次，低/高为0.7/1.3倍。已输出96个15分钟完整方阵。

出行率0.05、机动车比例0.50、载客率1.25及双向各10%跨界量均为假设。人口同时代理产生与吸引，以重力核exp(−t/1200)和分块IPF配平；早晚峰不代表实测通勤方向。推定深圳图307,426节点/451,801有向弧，尚未认证拓扑。401个分区接入、70个未接入，平峰不可达3,492.31、区内1,946.93 veh/h均保留。外部—外部过境交通不在范围。

136项测试、13项运行检查及独立矩阵/96区间/SHA/ZIP审计通过；并非实测校准。当前包`{relative}`，方法见[LONGGANG_OD_MODEL.md](docs/LONGGANG_OD_MODEL.md)，阶段报告见docs/PHASE_LONGGANG_OD_REPORT.md。Word/PPT通过共享content.json同步。龙岗积水、分配和韧性尚未重算，历史南山结果保持原范围。

以下内容为此前阶段记录，当前需求状态以上述新包为准。
'''
for name in ['AGENTS.md','README.md','DATA_SOURCES.md','MODEL_ASSUMPTIONS.md','PLAN.md','PROGRESS.md','EXPERIMENT_LOG.md','docs/USER_GUIDE.md','docs/deliverables/README.md','docs/FINAL_REPORT.md']:
    path=ROOT/name;text=path.read_text(encoding='utf-8')
    if '## 2026-11-18 龙岗合成OD计算' in text:continue
    first,rest=text.split('\n',1)
    entry=common.replace('(docs/LONGGANG_OD_MODEL.md)', '(LONGGANG_OD_MODEL.md)' if name.startswith('docs/') and not name.startswith('docs/deliverables/') else '(../LONGGANG_OD_MODEL.md)' if name.startswith('docs/deliverables/') else '(docs/LONGGANG_OD_MODEL.md)')
    path.write_text(first+'\n\n'+entry+rest,encoding='utf-8')
print('Updated shared content:',len(data['final']['sections']),'sections')
