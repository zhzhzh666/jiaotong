"""Append accepted Longgang SUMO evidence without rerunning the model."""
from pathlib import Path
from hashlib import sha256
import json
import shutil
import csv
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.cache/document-sync-20261119-sumo'
target = ROOT / 'docs/deliverables'
before = BUILD / 'before'
before.mkdir(parents=True, exist_ok=True)
for name in ['content.json', '研究方案与阶段进展.docx', '开题与阶段进展汇报.pptx', 'delivery_manifest.json']:
    assert not (before / name).exists(), 'Do not overwrite reviewed backup'
    shutil.copy2(target / name, before / name)
for name in ['final_visual_review.json', 'document_sync_state.json']:
    shutil.copy2(ROOT / 'docs/validation' / name, before / name)
evidence = ROOT / 'docs/validation/longgang_sumo'
index = json.loads((evidence / 'evidence_index.json').read_text(encoding='utf-8'))
for item in index['files']:
    assert sha256((evidence / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
inputs = json.loads((evidence / 'inputs.json').read_text(encoding='utf-8'))
for item in inputs:
    assert sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
audit = json.loads((evidence / 'independent_audit.json').read_text(encoding='utf-8'))
cases = ['dry','rain_departure','rain_rolling','governed_departure','governed_rolling']
results = {c: json.loads((evidence / f'cases/{c}/result.json').read_text(encoding='utf-8')) for c in cases}
for c, arrived in zip(cases, [3588,877,877,1230,1230]):
    r = results[c]
    assert r['planned'] == 3588 and r['arrived'] == arrived
    assert r['planned'] == sum(r[k] for k in ['invalid','external_pending','sumo_pending','running','arrived'])
    assert all(r[k] == 0 for k in ['balance_error','injected_balance_error','teleports','collision_vehicle_events','route_changes'])
    a = next(x for x in audit['scenarios'] if x['scenario'] == c)
    assert a['vehicle_seconds_replayed'] == r['vehicle_seconds']
suite = ET.parse(evidence / 'tests.xml').getroot().find('testsuite')
assert int(suite.attrib['tests']) == 171 and int(suite.attrib['failures']) == int(suite.attrib['errors']) == 0
guard = {n: sha256((before/n).read_bytes()).hexdigest() for n in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','content.json']}
(BUILD/'input-guard.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
data = json.loads((target / 'content.json').read_text(encoding='utf-8'))
assert len(data['final']['sections']) == 48
data['updated'] = '2026-11-19'
data['status'] = '龙岗代表片区五组SUMO试验与独立审计完成；治理多完成353次访问，未观察到额外滚动改道收益。5%合成需求，容量未标定，不能外推全区。'
data['cover_subtitle'] = '龙岗不含大鹏 分区治理与代表片区SUMO试验'
cover = data['final']['sections'][0]
cover['paragraphs'] = [
    '2026年11月19日：龙岗代表片区已完成五组SUMO微观试验与独立审计。第49—53节补充3 km×3 km范围、5%合成边界访问需求、积水控制、滚动选路、结果与实际OSG三维截图。固定3,588辆计划，无雨、暴雨、治理后分别完成3,588、877、1,230次片区访问；滚动组实际改道均为0，未观察到额外改道收益。171项既有测试通过。',
    '第2—30节保留南山与小网历史，第31—41节为龙岗接收、OD及早期积水，第42—48节为分区损失与抽样点队列治理试验。早期“尚未重算交通或SUMO”是当时状态。最新SUMO仅代表片区和缩放需求，容量代理、车道信号与OD未经实测标定，未完成全龙岗动态均衡或工程收益验证。'
]
cover['slide_points'] = ['研究报告与阶段进展', '2026年11月19日', '龙岗代表片区 SUMO五组试验完成']
run = '20261118T175153_sumo_492a503a'
data['longgang_sumo'] = {'path': 'data/processed/longgang_sumo/' + run,
    'audit': 'docs/validation/longgang_sumo/independent_audit.json',
    'tests_report': 'docs/validation/longgang_sumo/tests.xml', 'tests_passed':171,
    'evidence_index': 'docs/validation/longgang_sumo/evidence_index.json',
    'calibrated':False, 'demand_fraction':0.05, 'planned':3588, 'results':results,
    'scope':'S0附近3 km×3 km工作域，含周边连接道路；非全龙岗',
    'actual_longgang_route_changes':0, 'native_osg_screenshot':True,
    'terrain_buildings_water_surface':False}

def section(title, paragraphs, left, right='', footer='', figure=None, caption='', width=14):
    s = {'title':'龙岗SUMO ' + title, 'paragraphs':paragraphs, 'slide_points':[],
        'figure':figure,'caption':caption,'rows':None,'headers':None,
        'source_label':'docs/LONGGANG_DYNAMIC_SUMO_MODEL.md；独立审计及运行 '+run,
        'ppt_left':left,'ppt_right':right,'ppt_footer':footer}
    if figure: s['figure_width_cm'] = width
    return s

data['final']['sections'] += [
section('片区、需求与实验窗口', [
    '以S0（114.131662°E、22.610792°N）附近3 km×3 km方框为工作域，选两端节点均在框内的4,969条源有向弧、2,938个节点；没有将跨越方框的长弧作精确几何裁剪。周边跨行政区道路用于连接，不能把方框当作全龙岗。每方向一条有效车道、优先权交叉口与自动生成转向，均未实测认证。',
    '从完整483×483合成OD的正常最短路径提取18,912个连续边界访问条目，包括进入、离开、穿越和区内访问。原行程再次入区另计访问，不等于新增独立全市车辆。固定正常路径入口，不反馈片区外暴雨绕行。以5%物理需求、种子42作Poisson抽样，期望3,635.62辆，实际3,588辆，五组共享同一计划；不是826对抽样OD加载，也不能乘20外推全需求。',
    '北京时间2023年9月10日10:00—14:00，空网络起步，前3小时出发、末1小时清空已有需求。窗口按无治理关闭弧数首次峰值选定，12时694条源弧关闭，76条未知弧假设正常。不继承此前106小时积压。图示为窗口内各弧各自最大估计深度，非同刻灾情。'
], 'S0附近3 km × 3 km\n4,969条弧 / 2,938节点\n\n完整483×483合成OD\n18,912个连续边界访问\n5%需求，固定3,588辆计划\n\n2023-09-10 10:00—14:00\n空网开始，末1小时无新计划\n峰值694条源弧关闭',
footer='单有效车道、优先权交叉口、固定无雨入口均为假设；76条未知弧按正常处理，结果不能乘20外推。',
figure='docs/validation/longgang_sumo/figures/road_exposure.png',caption='无治理1.3倍雨量下片区道路各自峰值水深 色标截于0.5 m，灰色未知',width=12.8),
section('积水控制与滚动选路', [
    '复用第42—48节无治理mask0和治理mask9在1.3倍雨量下的水深，没有重算水文或用SUMO重新选址。SUMO 1.28.0按1 s推进和检查安全，60 s尝试到期及外部等待车辆注入，300 s更新路线成本，900 s更新积水。采用区间起点深度，限速由km/h除3.6转为m/s；h≥0.30 m禁止passenger进入，受困车辆保守等待并在开放后恢复，不删除或传送。',
    '容量以跟驰时距tau代理：tau0=max(1,3600/C0−7.5/(v0/3.6))，tau=tau0/max(0.2,fC)。C0为veh/h，v0为km/h，7.5 m为5 m车长加2.5 m间距，tau单位s。这是未标定运动学近似。primary道路50 km/h单路段饱和检查，水深0/0.10/0.20 m的参考出流1600/1200/800，实际1338/1026/426 veh/h，偏差−16.38%/−14.50%/−46.75%，未精确实现宏观容量。',
    '当前车辆道路平均速度形成行程时间，与水深限速自由时间取较大值，以0.5平滑、最低观测速率0.5 m/s。滚动组只在一般边比较剩余路线；J旧−J新>max(60 s,0.10J旧)，或前路关闭且有开放替代路线时更新。所有组待发车辆都按当前状态选路；只用当前信息，不提前读取未来积水。',
    'TraCI使用setMaxSpeed、setDisallowed、findRoute和setRoute；同一成本状态首末边查询缓存。方法是当前成本滚动最短路，未实现Bellman时间展开规划或动态用户均衡。独立合成菱形路网10 s关闭b边，a b b2 d改为a c c2 d，1辆到达且传送0；它只验证改道功能，不能混作龙岗收益。'
], '时间与积水控制\n\n1秒：交通与安全\n60秒：待发尝试与输出\n300秒：路线成本更新\n900秒：积水状态更新\n\nh≥0.30 m禁止进入\n受困等待，开放后恢复\n\n容量采用tau时距代理\n0.20 m出流（veh/h）\n参考800 / 实际426',
 '当前成本滚动最短路\n\n道路观测时间以0.5平滑\n仅用当前状态，无未来水深\n\n一般改道门槛\nJ旧−J新>max(60 s,0.10J旧)\n闭路有开放替代时强制更新\n\n菱形合成网已成功改道\n功能验证不计入龙岗收益',
 '容量代理未经标定；当前算法不是时空Bellman规划或动态用户均衡。所有组待发需求都按当前状态选路。'),
section('五组完成量与等待', [
    '五组固定3,588辆计划。dry到达3,588、外部等待0、在网0；rain_departure与rain_rolling均到达877、外部等待2,706、在网5；governed_departure与governed_rolling均到达1,230、外部等待2,352、在网6。各组无效计划和SUMO待插入均为0。治理多完成353次片区访问，未完成从2,711降至2,358；不能解释为全龙岗净新增完成车辆。',
    '暴雨和治理后滚动组分别作519、870次在途查询，实际路径修改均为0，曲线与对应仅出发选路组重合。本设置未观察到额外滚动改道收益；这既不能作为滚动改道普遍无效的证明，也不能把功能试验的成功改道算进真实片区结果。大量计划因端点或连通阻断保留外部等待。',
    '图中上方为累计完成，下方为已释放未完成，后者包含外部等待和在网车辆。3小时后不再新增计划是人为时窗设置，不能将末小时曲线平台解释为真实暴雨交通恢复。治理沿用先前mask9，未在该SUMO片区重新优化。'
], '同一3,588辆计划\n\n无雨：完成3,588 / 未完成0\n暴雨：完成877 / 未完成2,711\n治理：完成1,230 / 未完成2,358\n治理多完成353次片区访问\n\n滚动查询519 / 870次\n实际改道均0\n未观察到额外滚动收益',
footer='仅代表5%合成需求与当前4小时时窗；两组滚动曲线分别与出发选路组重合。',
figure='docs/validation/longgang_sumo/figures/traffic_comparison.png',caption='五组累计完成及已释放未完成时序 末1小时没有新增计划出发',width=14.2),
section('耗时记账与独立核验', [
    '系统占用时间按1秒右端点累加计划出发后外部等待、SUMO待发和在网时间。按无雨、暴雨出发、暴雨滚动、治理出发、治理滚动顺序，分别为907,534 / 24,270,030 / 24,270,030 / 21,176,262 / 21,176,262 veh·s。其中外部等待含最多约60秒注入调度差，不能把所有等待均当作物理路段排队。',
    '广义成本另加未完成及无效计划每次7,200 s惩罚，依同顺序为907,534 / 43,789,230 / 43,789,230 / 38,153,862 / 38,153,862 veh·s。终端惩罚是假设，未完成仍未到达。已完成者平均行程时间为220.50 / 206.58 / 206.58 / 241.47 / 241.47 s，受到完成者选择影响，不能由暴雨完成者均时较短推断暴雨改善交通。',
    '171项既有测试通过、pip check无冲突；本轮文档同步未重跑测试或长仿真。独立审计核对12个输入SHA、4,969条源弧、3,588条计划路径、168,946个水深值，重放五组完整车辆账本及系统耗时。计划=无效+外部等待+SUMO待插入+在网+到达，五组车辆守恒误差、自动传送、碰撞车辆事件均0。',
    '这些核验支持软件和数值一致性，不能替代实测验证。当前容量代理、单车道、转向及优先权假设，空网起步、固定边界入口、单随机种子和5%需求共同限制解释。下一步应先校准容量与真实车道信号，再扩需求、种子、片区及阈值，核对片区外绕行和队列反馈。'
], '占用积分 / 广义成本，veh·s\n\n无雨\n907,534 / 907,534\n\n暴雨（两组选路相同）\n24,270,030 / 43,789,230\n\n治理（两组选路相同）\n21,176,262 / 38,153,862\n\n广义成本另计未完成×7,200 s',
 '独立核验与适用范围\n\n171项既有测试通过\n12输入SHA / 4,969源弧\n3,588计划 / 168,946水深值\n五组账本与耗时独立重放\n守恒误差、传送、碰撞均0\n\n完成者均时有选择偏差\n容量、车道信号及OD待标定\n需扩需求、种子和边界反馈',
 '计时采用1秒右端点；注入调度等待纳入积分。数值一致不等于真实交通校准，不能外推全区工程收益。'),
section('实际三维画面与复现', [
    '图为来源运行独立GUI预览中的实际SUMO原生OSG道路与车辆跟随近景，非生成式示意图。当前道路为平面z=0，车辆使用原生三维模型；未接入真实建筑、道路高程或三维水面。三维显示不参与积水求解，截图不能证明完成城市三维水动力重建。',
    '查看入口：使用项目.conda-env/python.exe运行scripts/view_longgang_sumo.py，参数为data/processed/longgang_sumo/'+run+' --scenario dry；dry可换rain_rolling或governed_rolling。查看器先核输入SHA，再加载归档控制器，输出独立preview目录。直接打开sumocfg只有路网和车型，无法复现Python注入车辆及积水控制。',
    'GUI预览与五组数值主运行分开保存。来源聊天已核验车辆跟随与真实画面；本轮核对归档截图，未重新操作SUMO窗口。OSG的缩放请求1500返回100，不能声称该倍率生效。首轮20261118T174718_sumo_d7d847ee因重复查询中断，保留但不混入本轮结果。当前接受主运行'+run+'。'
], '真实OSG车辆跟随截图\n\n道路平面z=0\n原生车辆三维模型\n无真实建筑、高程和水面\n\n用view_longgang_sumo.py查看\n先核SHA，调用归档控制器\nGUI预览单独保存\n直接sumocfg不含车辆注入控制',
footer='当前接受运行 '+run+'；三维画面支持显示功能，不代表真实城市或水流重建。',
figure='docs/validation/longgang_sumo/figures/sumo_3d_follow.jpg',caption='实际SUMO 1.28.0 OSG近景 来源运行独立GUI预览，平面道路与原生车辆',width=16)
]
(target / 'content.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sections':len(data['final']['sections']),'evidence_sha_checked':len(index['files']),'input_sha_checked':len(inputs),'tests':171}))
