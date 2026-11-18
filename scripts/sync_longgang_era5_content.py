"""Synchronize independently audited ERA5 method B evidence into shared reports."""
from pathlib import Path
import json
import hashlib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'docs/deliverables/content.json'
base = ROOT / 'docs/validation/longgang_era5_surface'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
report = read(base / 'validation_report.json')
audit = read(base / 'independent_audit.json')
run_path = 'data/processed/longgang_era5_surface/' + report['run_id']
assert report['run_id'] == audit['run_id'] and report['all_checks_passed'] and audit['passed']
assert not report['calibrated'] and not report['observed_rain_gauges'] and not report['include_dapeng']
suite = ET.parse(ROOT / 'docs/validation/rainfall/era5_surface_tests.xml').getroot().find('testsuite')
assert int(suite.attrib['tests']) == 151 and int(suite.attrib['errors']) == int(suite.attrib['failures']) == 0
for name in ['era5_surface_process.png', 'era5_surface_map.png', 'era5_surface_sensitivity_balance.png']:
    assert hashlib.sha256((base / 'figures' / name).read_bytes()).digest() == hashlib.sha256((ROOT / run_path / 'figures' / name).read_bytes()).digest()

data = read(target)
status = '龙岗不含大鹏的ERA5驱动B方案简化地形汇流原型完成，参数未实测标定，交通影响待重算。独立桶与南山结果保留历史，C方案未实施。'
data['status'] = data['active_research']['status'] = status
data['cover_subtitle'] = '龙岗不含大鹏 ERA5降雨与简化地形汇流'
data['active_research']['era5_surface_path'] = run_path
data['longgang_era5_surface'] = {
    'path': run_path, 'report': report, 'audit': 'docs/validation/longgang_era5_surface/independent_audit.json',
    'tests_report': 'docs/validation/rainfall/era5_surface_tests.xml', 'tests_passed': 151,
    'attribution': read(base / 'era5_attribution.json'), 'calibrated': False,
    'traffic_assignment_rerun': False, 'two_dimensional_hydrodynamics': False}
sections = data['final']['sections']
sections[0]['paragraphs'][0] = '2026年11月18日：龙岗不含大鹏已完成483×483合成OD及ERA5驱动B方案简化地形汇流原型。120小时再分析降雨接入150 m DSM固定D8蓄泄模型，参数未经实测标定，不能视为真实内涝重建。龙岗道路速度容量、分配与韧性尚未重算。此前独立桶、南山及小型路网结果保留为历史。'
sections[0]['slide_points'][-1] = '龙岗不含大鹏 ERA5地形汇流原型完成'
for s in sections:
    if s['title'] == '龙岗暴雨情景 降雨与蓄水步骤':
        s['paragraphs'][0] = '本节为较早的独立桶运行，新B方案见第38—41节。合成道路低点来自道路和DSM，非历史积水实测。该运行没有单元间汇流或管网二维耦合，属于A方案的参数化扩展。'

source = report['run_id'] + ' / docs/LONGGANG_ERA5_SURFACE_MODEL.md'
def section(title, paragraphs, figure=None, caption='', points=None, width=None):
    item = {'title': title, 'paragraphs': paragraphs, 'ppt_native': False,
            'slide_points': points or [], 'source_label': source}
    if figure:
        item.update(figure='docs/validation/longgang_era5_surface/figures/' + figure, caption=caption)
    if width:
        item['figure_width_cm'] = width
    return item

new = [
section('龙岗ERA5方案 降雨数据与时间过程', [
    '通过Open-Meteo历史接口固定models=era5和最近网格，获取9个不同0.25°网格，每格120个完整小时，共1,080条非负且无缺失雨量。模拟时窗为北京时间2023年9月6日00时至11日00时；ERA5标记时刻t的降水属于此前一小时，实际选取9月6日01时至11日00时。',
    '主5 km外扩域使用6个ERA5网格，龙岗面积加权使用4个；区内累计180.100249 mm，最大区均1小时量5.964334 mm。ERA5约25 km再分析不是站点实测。原网格分片常数赋值，小时内均匀分配，不制造精细空间或分钟级降雨信息。',
    '署名 Weather data by Open-Meteo.com; Copernicus Climate Change Service / ECMWF ERA5。数据许可CC BY 4.0，另遵守提供方使用条件。原响应不改，提取完整时段并封装NPZ。来源 https://open-meteo.com/；许可 https://creativecommons.org/licenses/by/4.0/；条件 https://open-meteo.com/en/licence。'],
    'era5_surface_process.png', '120小时区均ERA5降雨及基准估计水深过程 末端仍有蓄水',
    ['9个网格 × 120小时，1,080条有效雨量', '龙岗区均累计180.10 mm', '再分析估计，小时内均匀降雨假设'], 14.0),
section('龙岗ERA5方案 地形蓄泄计算方法', [
    '龙岗主面不含大鹏，面积386.957601 km²。Copernicus约30 m DSM以面积平均聚合至150 m，EPSG32650；边界外扩5 km的矩形主域239×280，共66,920格。DSM包含建筑和植被，不是裸地DTM；无外部入流、河道或潮汐回水。10 km外扩仅作敏感性，尚未认证完整上游汇水区。',
    'priority-flood从边界向内遍历8邻格，建立固定无环D8父格树。保留原高程z，填洼高程F仅用于储量阈值d=max(F−z,0)。最大阈值29.38 m可能含DSM与聚合伪洼地，不能视为真实洼地深度；逐格阈值也未表达连通洼地共同水面。',
    '内部步长Δt=180 s，初始干燥，15分钟输出一次，共481端点。步内雨深R=P(mm)×Δt/3600/1000；加雨后h̃=h+R；损失ℓ=min(h̃,cΔt/3600/1000)。基准c=4 mm/h合并入渗与未解析排水，是假设容量。',
    '向下游转移q=max(h̃−ℓ−d,0)×(1−exp(−Δt/τ))，更新h新=h̃−ℓ−q+Σ上游q。网格同时转移，接收水下一步才继续下传。边界q计为出域，所有深度乘150² m²记账：全域降雨−损失−边界排出=储量变化，不能冒称区内水量平衡。',
    '停留时间τ=clip(L/v,900,21600) s；v=0.04×√[max(s,0.0001)/0.01] m/s，L为邻格距离、s为填洼面坡度。此为假设流动尺度，非实测流速或Manning求解。固定D8没有二维动量、动态流向、管井交换或顶托，不能称为SWMM或二维浅水模型。',
    '八组计算包括无雨、ERA5基准、雨量0.7/1.3倍、损失能力0.5/2倍、停留时间0.5/2倍。倍率仅用于未标定参数敏感性；下一步需要站点降雨和水深、裸地地形、土地覆盖与排水约束，再进行标定验证。'],
    points=['150 m DSM，66,920格，固定D8树', '180秒内部步长，481个输出端点', '降雨、损失、储量与出域逐步守恒']),
section('龙岗ERA5方案 空间结果与道路暴露', [
    '33,597个既有地面道路采样位置映射至8,530个模型网格，源线取采样网格最大估计深度。6,848个地面源线要素建模，952个桥隧或非零layer等保持未知NaN；保留86,807条推定OD图有向弧原ID。源线不是独立道路条数，图拓扑仍待认证。',
    '基准道路样点最大估计深度1.030854 m；同时超过0.15 m的源线最多45个，达到0.30 m的最多2个。这是暴露统计，不代表实测积水或实际封路。本轮没有由此更新速度、容量、交通分配、韧性或SUMO。',
    '区内估计深度大于0.15 m的同时最大面积0.608831 km²，所有时刻峰值并集面积0.676331 km²。地图展示各格各自峰值，非同一时刻淹没图；颜色上限按99.5分位截色，不能从色标读取全域最大值。',
    '面积按150 m像元及行政区相交面积估算，未模拟像元内部分淹没，不能解析路缘、雨水口及下穿通道。未知桥隧不填零，参数化水深不得解释为精细街道路面或历史灾情预测。'],
    'era5_surface_map.png', 'DSM计算域与逐格峰值图 右图非同一时刻且色标截至99.5分位',
    ['基准道路样点最大估计深度1.0309 m', '同时暴露源线45个 >0.15 m，2个 ≥0.30 m', '952个桥隧等未知，不作干燥零值']),
section('龙岗ERA5方案 敏感性与数值核验', [
    '损失能力c为2/4/8 mm/h时，道路样点峰值4.098790/1.030854/0.011329 m；雨量倍率0.7/1/1.3时为0.165155/1.030854/2.498684 m。绝对水深强烈依赖未标定假设，不能直接确定真实灾情或工程收益。',
    '基准全域累计降雨266,202,702.000 m³，损失265,470,787.331 m³，边界排出119,605.938 m³，末端蓄水612,308.731 m³。损失占99.725%体现参数设定，不是实测排水效率；120小时末仍有蓄水，不能宣称全部退水。',
    '151项既有及新增测试、10项运行检查通过。独立审计核验1,080条原始雨量、32,188,520个网格端点、26,351,104个已建模道路值、16输入SHA、57输出SHA及58个ZIP成员；最大重放差5.92×10⁻⁸ m，累计水量残差1.43×10⁻⁶ m³以内。本轮文档维护引用既有验收，未重跑模型。',
    '180→60 s最大道路端点差0.023146 m，按绝对0.02 m加峰值5%的原型容差通过，不是水动力收敛证明；5→10 km外扩差0.039351 m，不能保证全上游完整。原型须补齐实测标定与边界认证，尚未接入交通影响计算。'],
    'era5_surface_sensitivity_balance.png', '八组参数敏感性与全计算域水量记账 数值平衡不能替代实测标定',
    ['损失能力2／4／8 mm/h的峰值差异显著', '151项测试，10项检查及独立数值审计通过', '末端仍有蓄水，交通影响尚未计算'])
]
data['final']['sections'] = [s for s in sections if not s['title'].startswith('龙岗ERA5方案 ')] + new
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Shared sections:', len(data['final']['sections']))
