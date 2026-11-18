"""Publish result-derived road-performance evidence to shared report content."""
from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args()
run=args.run.resolve();run.relative_to(ROOT);source=run.relative_to(ROOT).as_posix()
report=json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'));assert report['all_checks_passed']
test_path='docs/validation/road_performance/tests.xml';suite=ET.parse(ROOT/test_path).getroot().find('testsuite')
assert int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
tests=int(suite.attrib['tests']);b=report['baseline']
sections=[
 {'title':'道路模型 速度与通行容量','paragraphs':[
    '以合成路段水深h（m）驱动道路退化。Pregnolato等2017的PDF第7页Eq.4给出v_limit=0.0009w²-0.5529w+86.9448，w=1000h为mm，速度单位km/h；DOI 10.1016/j.trd.2017.06.020。',
    '工程适配保留零水深正常速度v0，未中断时v=min(v0,max(0,v_limit))。通行容量独立假设C=C0×max(0.20,1-0.80h/0.30)，单位veh/h；达到0.30 m时速度与容量均置0。容量函数与中断阈值不属于原论文实测结论。',
    '自由流时间t0=3.6L/v，L为m、t0为秒。关闭边导出时间为inf并移出可通行边集；容量不等于实际车流，当前没有重新分配交通或加入拥堵效应。'],
  'figure':source+'/figures/depth_road_response.png','caption':'道路退化函数 文献速度适配与独立容量假设','ppt_native':True},
 {'title':'道路模型 中断与恢复过程','paragraphs':[
    f'把四种降雨、五组排水消退参数的97端点积水映射至54条有向边，生成{report["state_rows"]}行道路状态。基准一般/严重/极端同时中断最多为{b["general"]["max_closed_edges"]}/{b["severe"]["max_closed_edges"]}/{b["extreme"]["max_closed_edges"]}条。',
    f'基准严重、极端情景的单边最长累计中断约{b["severe"]["longest_closure_h"]:.2f}和{b["extreme"]["longest_closure_h"]:.2f}小时。深度达到0.30 m即封路，下降至阈值以下即模型重开；按端点线性插值记录穿越时刻，窗口末仍关闭记右删失。未加入检查放行延迟或滞回。',
    '图中容量保留率为54条关联边容量属性之和相对正常值，不是网络吞吐量、交通服务率或韧性。与上轮1厘米退水阈值的含义不同，模型重开也不证明道路实际安全。'],
  'figure':source+'/figures/road_impact_process.png','caption':'道路退化过程 基准参数下的封闭数量与关联边容量属性','ppt_native':True},
 {'title':'道路模型 南山道路状态','paragraphs':[
    '真实路网40105条有向边均保留，方向及平行边键从原GraphML按edge_id关联恢复，不从几何线猜测。55个候选点关联54条边，5个未匹配点在上游保留；其余40051边假设原状，不表示实测无积水。',
    '图示为基准参数10.5小时的道路状态。极端情景此时41条弧中断，可通行边集保留40064条；原始全网快照仍有40105条边。几何重叠不改变按独立有向edge_id计数。',
    f'{tests}项测试、14项道路状态核验通过；完整状态、封闭事件、四时刻全网快照、PNG/SVG与源码配置已归档。合成深度及道路基础速度、容量未实测校准；尚未以新输入重跑用户均衡、韧性与治理。'],
  'figure':source+'/figures/road_states_map.png','caption':'南山三情景道路状态 10.5小时 有向边计数','ppt_native':False}]
for section in sections:section['source_label']='道路退化实验 '+run.name+' / '+Path(section['figure']).name
target=ROOT/'docs/deliverables/content.json';data=json.loads(target.read_text(encoding='utf-8'))
data['final']['sections']=[s for s in data['final']['sections'] if not s['title'].startswith('道路模型 ')]+sections
data['road_performance']={'path':source,'report':report,'tests_report':test_path,'tests_passed':tests,'sections_added':3}
target.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
text=(run/'README.md').read_text(encoding='utf-8')+'\n当前结果目录：`'+source+'`。\n\n运行命令：`.conda-env/python.exe scripts/run_road_performance_process.py --config configs/road_performance_process.yaml`。\n'
(ROOT/'docs/ROAD_PERFORMANCE_MODEL.md').write_text(text,encoding='utf-8')
stage='# 道路交通性能退化阶段报告\n\n运行：`'+source+'`。\n\n'
for s in sections:stage+='## '+s['title']+'\n\n'+'\n\n'.join(s['paragraphs'])+'\n\n源图：`'+s['figure']+'`。\n\n'
(ROOT/'docs/PHASE_ROAD_PERFORMANCE_REPORT.md').write_text(stage.rstrip()+'\n',encoding='utf-8')
print(f'{len(data["final"]["sections"])} sections; {tests} tests')
