"""Append actual new traffic-assignment results to the shared Word/PPT content."""
from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args()
run=args.run.resolve();run.relative_to(ROOT);source=run.relative_to(ROOT).as_posix()
r=json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'));assert r['all_checks_passed']
test='docs/validation/traffic_process/tests.xml';suite=ET.parse(ROOT/test).getroot().find('testsuite')
assert int(suite.attrib['failures'])==int(suite.attrib['errors'])==0;tests=int(suite.attrib['tests'])
b={s['scenario']:s for s in r['scenario_summary']};weather=['general','severe','extreme']
res=' / '.join(f'{b[s]["R"]:.8f}' for s in weather)
unserved=' / '.join(f'{b[s]["unserved_vehicles"]:.2f}' for s in weather)
sections=[
 {'title':'交通评估 时片分配与综合韧性','paragraphs':[
  f'在基准排水与消退参数下，将完整574×574合成OD的96个出发区间与冻结道路状态接入南山{r["directed_edges"]}条有向边。四情景共384条区间记录，完成{r["unique_solved_states"]}次独立用户均衡求解，最大相对间隙{r["max_gap"]:.3g}；全部满足1e-4目标，节点守恒最大误差{r["max_node_balance_error"]:.3g} veh/h。',
  f'正常R=1，一般/严重/极端R分别为{res}。每个区间对照完全相同OD的正常道路基准，R=ΣQ[k]×0.25/24，使用区间起点道路状态保持。该定义与旧97端点梯形积分不同，旧值不能直接替换或当作此次结果。',
  'BPR与Frank–Wolfe重新分配，有向平行边独立保留，关闭弧不进入最短路图且流量为0。96个区间独立求解，不传递排队，尚不属于完整动态交通分配；合成OD与道路水深未实测标定。'],
  'figure':'docs/validation/traffic_process/traffic_resilience_process.png','caption':'新输入下时片用户均衡 综合性能与已服务出行平均道路时间','ppt_native':True},
 {'title':'交通评估 需求去向与拥堵','paragraphs':[
  f'所有天气使用同一外生需求，全天{b["normal"]["total_vehicles"]:.2f}期望车次。每15分钟矩阵的车次除以0.25换算为veh/h，96个矩阵逐个重放核验，未将97个积水端点当作97次发车。',
  f'一般/严重/极端全天未服务需求分别为{unserved}期望车次；所有情景同时保留区内出行。每个时片满足已服务＋未服务＋区内＝总需求，全天记账最大误差{r["daily_accounting_max_error_vehicles"]:.3g}车次。未服务按14400秒、区内按300秒计成本，不能把未服务需求视为已完成出行。',
  '各雨量下的未服务量均与正常基准相同，医院与消防覆盖率也未变化，本次影响主要来自通行时间。拥堵比例使用当时退化容量，统计开放有向边中v/c>0.9的比例。只有完整需求与全部道路属性字节哈希相同时才复用求解，逐OD去向和边流量均可查。'],
  'figure':source+'/figures/traffic_demand_process.png','caption':'各天气未服务需求与按退化容量计算的道路拥堵比例','ppt_native':True},
 {'title':'交通评估 南山流量变化','paragraphs':[
  '图示10.5小时相对同需求正常基准的道路流量变化，黑色为关闭弧，彩色为流量变化绝对值超过1 veh/h的道路。色标截至±100 veh/h，原始数值完整保留。几何重叠不合并正反向或平行弧。',
  f'可达性保留全部568个人口分区，分母为{r["population_denominator"]:.2f}模型人口，未接入人口继续计入。时间效率按固定{r["efficiency_sample_origins"]}个起点到全部节点抽样；医院与消防采用既有OSM设施，缺失避难所不补造。',
  f'{tests}项测试、{r["check_count"]}项运行核验及全部独立求解的数值审计通过。54条关联边由合成积水驱动，其余40051边假设原状。结果未实测校准，本轮未实施南山全尺度治理优化或新SUMO仿真。'],
  'figure':source+'/figures/traffic_flow_change_map.png','caption':'南山道路流量相对正常基准的变化 10.5小时','ppt_native':False}]
for s in sections:s['source_label']='交通评估实验 '+run.name+' / '+Path(s['figure']).name
target=ROOT/'docs/deliverables/content.json';data=json.loads(target.read_text(encoding='utf-8'))
data['final']['sections']=[s for s in data['final']['sections'] if not s['title'].startswith('交通评估 ')]+sections
data['traffic_process']={'path':source,'report':r,'tests_report':test,'tests_passed':tests,'sections_added':3}
target.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
text=(run/'README.md').read_text(encoding='utf-8')+'\n当前运行：`'+source+'`。\n\n命令：`.conda-env/python.exe scripts/run_traffic_process.py --config configs/traffic_process.yaml`。\n'
(ROOT/'docs/TRAFFIC_PROCESS_MODEL.md').write_text(text,encoding='utf-8')
text='# 南山合成情景交通分配与韧性阶段报告\n\n运行`'+source+'`。\n\n'
for s in sections:text+='## '+s['title']+'\n\n'+'\n\n'.join(s['paragraphs'])+'\n\n源图：`'+s['figure']+'`。\n\n'
(ROOT/'docs/PHASE_TRAFFIC_PROCESS_REPORT.md').write_text(text,encoding='utf-8')
print(f'{len(data["final"]["sections"])} sections; {tests} tests')
