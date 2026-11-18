"""Add result-derived storm-process sections to shared report content."""
from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
run=args.run.resolve();run.relative_to(ROOT)
report=json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'))
assert report['all_checks_passed']
source=run.relative_to(ROOT).as_posix()
target=ROOT/'docs/deliverables/content.json';data=json.loads(target.read_text(encoding='utf-8'))
test_path='docs/validation/storm_process/tests.xml'
suite=ET.parse(ROOT/test_path).getroot().find('testsuite')
assert int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
tests=int(suite.attrib['tests'])
baseline={r['scenario']:r for r in report['baseline_summary']}
sections=[
 {'title':'情景建模 降雨与积水全过程','paragraphs':[
    '在已冻结南山合成数据上新增可复用的降雨蓄水与退水模块。以15分钟步长复算60点，参考雨量0/100/200/300 mm；5—13小时降雨，8和10小时附近双峰。实验强度与参数未经实测标定。',
    '以mm计储量H，区间有效雨输入I=R×径流系数×假设汇水与积水面积比；排水D=min(H+I,c×Δt+H×Δt/τ)，H_next=H+I-D。基准τ=4小时，输出水深为H/1000 m。各点独立，不解析管网和水交换。',
    '基准一般/严重/极端峰值为0.215/0.453/0.691 m，均在10.5小时出现。深度>0.15 m的单点最长持续时间分别为'+
       '/'.join(f'{baseline[s]["max_duration_above_015_h"]:.2f}' for s in ['general','severe','extreme'])+'小时；图中点数只针对60个合成候选点。'],
  'figure':source+'/figures/storm_process.png','caption':'情景过程 合成降雨 最大积水与超阈值点数',
  'source_label':'退水实验 '+run.name+' / storm_process.png','ppt_native':True},
 {'title':'情景建模 积水消退与敏感性','paragraphs':[
    '13小时雨停后，离散退水为H_next=max((1-Δt/τ)H-c×Δt,0)。这是一阶显式离散式，Δt不得超过τ；c为mm/h、τ为小时，不能把τ直接当作实际退水时长。',
    '本轮定义退至0.01 m为分析恢复阈值，并按相邻15分钟端点线性插值。基准三种暴雨在雨停后约'+
       '/'.join(f'{baseline[s]["latest_recovery_hour_001"]-13:.2f}' for s in ['general','severe','extreme'])+
       '小时完成全部曾超阈值点的恢复。未超阈值不填写恢复时刻；24小时仍超阈值记右删失，不外推成已恢复。1厘米不是安全通行标准。',
    f'五组单因素参数比较排水能力0.5/1/1.5倍及τ=2/4/8小时。τ=8小时的极端情景有32点在24小时仍超1厘米；这些是参数敏感性，不代表真实工程效果。{tests}项测试、11项过程一致性检查通过，基准重放最大差异{report["baseline_replay_max_error_m"]:.2e} m；未重跑交通分配。'],
  'figure':source+'/figures/flood_recession.png','caption':'消退过程 极端情景固定候选点参数对照与基准恢复时间',
  'source_label':'退水实验 '+run.name+' / flood_recession.png','ppt_native':True}]
data['final']['sections']=[s for s in data['final']['sections'] if not s['title'].startswith('情景建模 ')]+sections
data['storm_process']={'path':source,'report':report,'tests_report':test_path,'tests_passed':tests,'sections_added':2}
target.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
(ROOT/'docs/STORM_FLOOD_MODEL.md').write_text((run/'README.md').read_text(encoding='utf-8')+
    '\n当前运行：`'+source+'`。\n\n运行命令：`.conda-env/python.exe scripts/run_storm_flood_process.py --config configs/storm_flood_process.yaml`。每次新目录，旧包与OD保持原样。\n'+
    '\n基准结果\n\n'+ '\n'.join('- '+s['title']+'：'+' '.join(s['paragraphs']) for s in sections)+'\n',encoding='utf-8')
print(f'{len(data["final"]["sections"])} sections; {tests} tests')
