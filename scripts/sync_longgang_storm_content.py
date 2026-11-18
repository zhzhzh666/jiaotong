"""Add verified Longgang storage-proxy results to the maintained shared content."""
from pathlib import Path
import json
import hashlib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'docs/deliverables/content.json'
run_path = 'data/synthetic/longgang_storm/20261118T124853_longgang_storm_7e7668c1'
run = ROOT / run_path
validation = ROOT / 'docs/validation/longgang_storm'
report = json.loads((validation / 'validation_report.json').read_text(encoding='utf-8'))
audit = json.loads((validation / 'numerical_audit.json').read_text(encoding='utf-8'))
assert report['run_id'] == audit['run_id'] == run.name
assert report['all_checks_passed'] and audit['all_checks_passed']
assert not report['observed'] and not report['include_dapeng']
suite = ET.parse(validation / 'tests.xml').getroot().find('testsuite')
assert int(suite.attrib['tests']) == 141 and int(suite.attrib['errors']) == int(suite.attrib['failures']) == 0
for name in ['rainfall_ponding_process.png', 'proxy_peak_map.png', 'sensitivity_road_exposure.png']:
    assert hashlib.sha256((validation / name).read_bytes()).digest() == hashlib.sha256((run / 'figures' / name).read_bytes()).digest()

data = json.loads(target.read_text(encoding='utf-8'))
status = '龙岗不含大鹏的合成OD与独立蓄水桶情景完成，交通影响待重算。真实管网尚未取得，C方案未实施。南山结果保留为历史。'
data['status'] = status
data['cover_subtitle'] = '龙岗不含大鹏 合成OD与暴雨积水情景'
data['active_research']['status'] = status
data['active_research']['synthetic_storm_path'] = run_path
data['longgang_storm'] = {'path': run_path, 'report': report,
    'audit': 'docs/validation/longgang_storm/numerical_audit.json',
    'tests_report': 'docs/validation/longgang_storm/tests.xml', 'tests_passed': 141,
    'observed': False, 'hydrodynamic': False, 'traffic_assignment_rerun': False}
data['longgang_drainage'] = {'source': 'docs/LONGGANG_DRAINAGE_DATA_AVAILABILITY.md',
    'checked': '2026-11-18', 'real_network_obtained': False, 'coupled_model_run': False}
sections = data['final']['sections']
sections[0]['paragraphs'][0] = '2026年11月18日：龙岗不含大鹏的483×483合成OD及降雨蓄水退水情景已完成。积水由4,139个独立道路网格代理生成，参数未经实测标定。龙岗道路速度容量、交通分配与韧性尚未重算，真实管网尚未取得。南山及小型路网结果保留为历史。'
sections[0]['slide_points'][-1] = '龙岗不含大鹏 合成OD与蓄水情景完成'
for section in sections:
    if section['title'] == '龙岗交通需求 时间变化与使用限制':
        section['paragraphs'][-1] = section['paragraphs'][-1].replace('未重算积水、交通分配、韧性或SUMO。', '本节记录OD计算时点，后续积水情景见第34—36节。尚未重算龙岗交通分配、韧性或SUMO。')

def section(title, paragraphs, figure=None, caption='', points=None):
    item = {'title': title, 'paragraphs': paragraphs, 'ppt_native': False,
            'slide_points': points or [], 'source_label': run.name + ' / docs/LONGGANG_STORM_MODEL.md'}
    if figure:
        item.update(figure='docs/validation/longgang_storm/' + figure, caption=caption)
    return item

new = [
section('龙岗暴雨情景 降雨与蓄水步骤', [
    '本情景采用合成道路低点与独立蓄水桶，接近方案A的参数化扩展。位置来自道路和DSM，不是已核实历史积水点。没有相邻单元地表汇流，未实施B的汇流计算或C的SWMM与二维水动力耦合。',
    '先固定龙岗主面和既有OD推定图，按道路不超过100 m间距采样，在250 m网格内选择DSM相对低点。再构造0、100、200、300 mm参考总雨量，模拟24小时、96个15分钟区间及97个水深端点。双峰降雨设在第5—13小时，不对应官方等级或重现期。',
    '单元储量H以mm计。每步输入I=R×g×C×α，排水D=min(H+I,cΔt+HΔt/τ)，下一步H新=H+I−D，输出水深h=H/1000 m。R为区间雨量，g为空间乘数。C=0.8，α为2至4.5，c为8至18 mm/h，τ=4 h，参数均未标定。',
    '雨停后输入为零，储量继续消退。三档基准最大水深为0.2613、0.5439、0.8266 m，峰值均在第10.5小时。曲线表达假想道路单元的合成压力情景，不能解释为真实暴雨预测。'],
    'rainfall_ponding_process.png', '四档合成情景中的三档暴雨过程及代理水深，虚线为第13小时雨停',
    ['合成道路低点与独立蓄水桶', '参考总雨量0／100／200／300 mm', '最大代理水深0.2613／0.5439／0.8266 m']),
section('龙岗暴雨情景 空间覆盖与道路关联', [
    '龙岗主面不含大鹏，约386.96 km²。33,597个道路采样点形成4,139个250 m网格代理。本轮按道路权限筛选接受7,800个源线要素，6,848个地面要素建模，952个桥隧或非零layer要素保留未知NaN。此数与此前7,837条几何候选的统计口径不同。',
    'DSM采用Copernicus GLO-30，包含建筑和植被影响，不能当作裸地精细地形或排水管网。代理低点不等于真实洼地，250 m网格也不意味着整格被淹；未覆盖道路区域不在本模型表达范围。',
    '每个源线要素取其关联单元的最大水深，作为保守暴露代理。较长源线可能把局部影响传播到其他路段。直接读取OD图已保存的edge_id及u/v/key，共映射86,807条有向弧，426条跨研究边界弧另作标记。图拓扑仍待认证。',
    '桥隧等未知值不能填为0或解释为安全。交通模型应按源要素位置与精确图弧标识连接水深。本轮仅形成水深输入，没有计算速度容量下降、封路、交通分配、韧性或SUMO。'],
    'proxy_peak_map.png', '龙岗三档基准暴雨的各代理单元峰值，非实测淹没图',
    ['4,139个道路网格代理', '6,848个地面源要素建模，952个未知', '86,807条推定图弧对应，拓扑待核']),
section('龙岗暴雨情景 恢复与参数敏感性', [
    '100、200、300 mm基准情景中，单点水深大于0.15 m的最长时长分别为5.13、8.27、10.03 h。第13小时雨停后，全部曾超1 cm单元在5.93、8.56、10.11 h后恢复至分析阈值以下。1 cm不是行车安全标准。',
    '同时水深达到0.30 m的源线要素数最大为0、2,477、5,749。该阈值在本轮仅用于暴露统计，不能把数量当作已实施封路或独立道路条数。恢复时刻按峰后最后一次下降穿越1 cm且此后不再超过定义，24小时仍超过的单元保留右删失。',
    '比较基准、排水能力0.5倍与1.5倍、τ=2 h与8 h，共20组过程。慢退水τ=8 h时，三档情景分别有38、925、1,833个单元在24小时仍超过1 cm。参数变化用于敏感性分析，不直接代表真实排水工程收益。',
    '141项测试与17项运行检查通过。独立审计回读20组共8,029,660个单元端点值，复核水量递推、道路聚合、104个文件SHA及ZIP。将15分钟雨量均分为5分钟复算，共同端点最大差异约0.00394、0.00813、0.01232 m，仅说明时间离散敏感性。'],
    'sensitivity_road_exposure.png', '排水退水参数对恢复和源线暴露的影响，未知桥隧不计作干燥道路',
    ['雨停后恢复5.93／8.56／10.11 h', '慢退水组24小时仍有未恢复单元', '20组独立审计通过，参数尚未实测标定']),
section('龙岗管网耦合方案 数据条件与实施步骤', [
    '截至2026年11月18日，公开渠道核查尚未取得可直接下载、覆盖龙岗且字段完整的真实雨水管网。此结论仅表示本轮未取得，不能据此断言数据不存在。已核实的管渠汇总统计和数据质检工具入口均不能替代逐管井空间数据。',
    'C方案需要管线与检查井的唯一编号、几何、连接关系、断面管径及井底井盖高程，并需要雨水口、排口、泵闸与下游水位资料。资料还须说明坐标和垂直基准、测绘日期、覆盖及使用许可。现有30 m DSM不能视为已满足街道路缘与微地形要求。',
    '深圳市水务局政府信息公开指南提供正式申请渠道。项目已保存字段清单和未提交的申请草案。取得资料后，先归档核对元数据与管井拓扑，再选完整排水分区建立SWMM一维模型，构建二维地表网格，通过雨水口和检查井实现双向交换并逐步核验质量守恒。',
    '耦合后须用历史降雨及独立积水流量记录标定和验证，再输出道路水深连接交通模块。本轮未取得真实管井、未提交申请、未运行SWMM或二维模型。既有独立桶情景继续作为未标定压力实验输入，保留原有结果与运行编号。'],
    points=['真实管网尚未取得，C方案未实施', '现有统计与质检工具不能替代管井数据', '管网核查后分区建模，耦合交换并标定验证'])
]
new[-1]['source_label'] = 'docs/LONGGANG_DRAINAGE_DATA_AVAILABILITY.md / 深圳市水务局政府信息公开指南 https://swj.sz.gov.cn/xxgk/zfxxgkzn/'
new[0]['figure_width_cm'] = 15.0
new[-1]['paragraphs'].append('来源为项目真实排水管网公开数据核查及深圳市水务局政府信息公开指南（https://swj.sz.gov.cn/xxgk/zfxxgkzn/）。申请材料尚未提交。')
prefixes = ('龙岗暴雨情景 ', '龙岗管网耦合方案 ')
data['final']['sections'] = [s for s in sections if not s['title'].startswith(prefixes)] + new
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Shared sections:', len(data['final']['sections']))
