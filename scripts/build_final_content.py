"""Build shared Word/PPT facts and versioned acceptance copies from real runs."""
from pathlib import Path
import json
import shutil
import xml.etree.ElementTree as ET
import pandas as pd
from uftr.archive import write_json,file_hash
from uftr.final_audit import latest_success,audit_archive

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'docs/deliverables';data=json.loads((target/'content.json').read_text(encoding='utf-8'))
runs={p:latest_success(ROOT,p) for p in ['04','05','06','08','09','10','11']}
runs['07']=latest_success(ROOT,'07','nanshan');runs['07_small']=latest_success(ROOT,'07','small')
reports={}
for phase,run in runs.items():
    report_name={'04':'flood_report.json','05':'impact_report.json','06':'assignment_report.json'}.get(phase,'stage_report.json')
    reports[phase]=json.loads((run/'raw'/report_name).read_text(encoding='utf-8'))
    validation=ROOT/'docs/validation'/('phase'+phase)
    validation.mkdir(exist_ok=True,parents=True)
    for source in [run/'manifest.json',run/'raw'/report_name,*run.glob('figures/*.png')]:
        shutil.copy2(source,validation/('accepted-run-manifest.json' if source.name=='manifest.json' else source.name))
    write_json(validation/'run_audit.json',audit_archive(ROOT,run))
    # Small output tables, not raw observations or large archived simulations.
    for name in ['resilience_summary.csv','penalty_sensitivity.csv','critical_road_ranking.csv','strategy_comparison.csv','optimized_road_selection.json','sumo_comparison.csv','experiment_statistics.csv','experiment_results.csv','efficiency_benchmark.csv']:
        p=run/'raw'/name
        if p.is_file():shutil.copy2(p,validation/name)
    command=f'.conda-env\\python.exe -m uftr.cli run --phase {phase[:2]}'
    if phase=='07':command+=' --config configs/phase07_nanshan.yaml'
    text=f'# Phase {phase} 实际运行报告\n\n运行 `{run.name}`，命令：`{command}`。\n\n'
    text+='本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。\n\n'
    if phase in {'08','09','11','07_small'}:text+='本阶段数值适用小型真实路网（三个TAZ、9条正OD，含3条区内未上图项），不是南山全尺度优化。研究窗口外需求在scope字段记录。\n\n'
    if phase=='10':text+='南山2000辆计划为固定资源抽样，约占原小时率积分的0.184%；不是全天全量交通。小网治理方案与南山风险集无交集，因此南山disaster/optimized相同，不作为全区治理收益证据。两个原有OSM自环只在SUMO中沿原曲线中点拆分，保留一对多映射，原交通图不变。\n\n'
    if phase=='11':text+='训练种子42—51，独立灾害种子1042—1051与OD种子5042—5051。C/D/E为种子42单因素/消融；G记录真实分配耗时。原运行十训练种子完成后绘图后端失败，恢复已有计算检查点并重跑独立测试，来源指纹见报告。\n\n'
    text+='参数见对应configs；独立审计与验收副本见docs/validation/phase'+phase+'。\n\n```json\n'+json.dumps(reports[phase],ensure_ascii=False,indent=2)+'\n```\n'
    (ROOT/'docs'/f'PHASE{phase}_REPORT.md').write_text(text,encoding='utf-8')

tests=ET.parse(ROOT/'docs/validation/current-tests.xml').getroot().find('testsuite');test_count=int(tests.attrib['tests'])
assert int(tests.attrib['failures'])==int(tests.attrib['errors'])==0
f=reports['04'];a=reports['06'];full=reports['07'];small=reports['07_small'];opt=reports['09'];suite=reports['11']
strategy=pd.read_csv(runs['09']/'raw/strategy_comparison.csv');sumo=pd.read_csv(runs['10']/'raw/sumo_comparison.csv');experiments=pd.read_csv(runs['11']/'raw/experiment_results.csv');sections=[]
def section(title,paragraphs,points=None,figure=None,caption='',rows=None,headers=None):
    sections.append({'title':title,'paragraphs':paragraphs,'slide_points':points or paragraphs,'figure':figure,'caption':caption,'rows':rows,'headers':headers})
def fig(phase,name):return f'docs/validation/phase{phase}/{name}.png'

section('暴雨内涝交通网络韧性评估与优化',[
    '研究报告与阶段进展 · 2026年11月18日。基于深圳南山真实有向道路网络，完成参数化内涝、静态用户均衡、全过程韧性、道路治理与SUMO原型。',
    '治理与十种子实验使用独立小网压力情景，南山完成全图分配、97端点韧性和抽样SUMO。全部OD、容量、灾害峰值、成本与治理效果尚未标定。'],
    ['研究报告与阶段进展','2026年11月18日','真实路网 · 参数化内涝 · 交通韧性与治理原型'])
section('研究范围与数据来源',[
    '南山研究窗口：20,447节点、40,105条有向边、33弱分量；小网1,140节点、2,247条有向边。保留方向、平行边和断连，不补造道路。范围是OSM行政边界与研究bbox交集，包含海域/岛屿，不等于官方陆地边界。',
    'WorldPop 2020原生约1km像元分配后保留1,540,614.3657模型人数。568个TAZ中236个正产生/吸引区；193个区内有接入、43个缺接入但需求保留。人口年份与2026 OSM不一致。',
    'Copernicus为DSM，非排水DTM；宝安机场逐日雨量只作区域背景，不拆成15分钟实测雨量。OSM有14医院、15消防站，入口待核验，完整避难所清单缺失。'],
    ['南山：20,447节点 / 40,105有向边；保留全部断连。','WorldPop 2020模型人口，重力/IPF生成合成OD。','DSM、机场日雨量、OSM设施均存在精度或覆盖限制。'])
section('监测水位证据与模型边界',[
    '45站18,123条水位样本，实际CSV覆盖2023-09-07 00:00:33至09-08 20:04:05。用户提供字段说明支持SW单位m、SJ北京时间；说明书截至19:40与实际记录冲突，以记录为准。来源为深圳市政府数据开放平台，水位资源29200/01403147，测站资源29200/01400987。',
    'SW零点未由平台正式说明。旱时近零支持路面积水解释，但不能直接证明；因此观测SW未自动作为道路水深输入。坐标来自地址经高德编码和GCJ02转换，非官方传感器实测点。9281292012的说明书“沙井路近似定位”与CSV东莞POI方式不一致，保留位置警告。',
    '0.15/0.30/0.40m蓝黄橙红为用户确认的源数据分级；本项目0.30m道路中断另属研究假设。说明书引用标准未提供核实条款，不作强制封路依据。'],
    ['SW：单位m；SJ：北京时间，字典支持。','路面零点与地址代理位置仍未核实；保留两处资料冲突。','分级标签不作为实测封路；模拟深度与观测分开。'])
section('交通分配模型与基准验证',[
    '使用BPR：t=t0[1+0.15(x/c)^4]，AON按起点聚合，Frank–Wolfe配合方向导数线搜索。最短路每次选择当前成本最低的平行弧，原始弧流量独立保留；关闭边移出通行网络。Sioux Falls时间0.01小时乘36转秒，流量保留原基准单位。',
    f"Sioux Falls相对间隙{a['sioux']['relative_gap']:.8g}，参考流量相对RMSE {a['sioux']['relative_flow_rmse']*100:.4f}%。南山平峰间隙{a['osm']['nanshan']['relative_gap']:.8g}，节点守恒最大误差{a['osm']['nanshan']['node_balance_max_error']:.3g} veh/h。",
    '南山平峰需求36,974.7448 veh/h：路网上服务31,971.5188、不可达3,649.7494、区内未上图1,353.4766。不可达与区内需求单列，不通过删OD提高结果。时片均衡不等于完整动态交通分配。'],
    [f"Sioux Falls gap={a['sioux']['relative_gap']:.3g}；相对RMSE={a['sioux']['relative_flow_rmse']*100:.4f}%。",'南山完整路网达到1e-4目标；不可达与区内需求保留。'],fig('06','assignment_validation'),'实际求解收敛曲线与上游参考流量对比；来源 '+runs['06'].name)
section('24小时参数化内涝情景',[
    '97端点、96个15分钟区间。地面几何匹配后的54条有向边使用h_e(t)=H_e g_e(t)，平滑增长和有限时间消退；空间相关长度1500m，基准峰值0.25m，峰时9h、增长4h、消退9h，延迟标准差0.5h。一般/严重/极端乘数0.65/1.25/2.0。',
    f"正常全零，三种灾害最大深度分别{f['scenario_peak_m']['general']:.3f}、{f['scenario_peak_m']['severe']:.3f}、{f['scenario_peak_m']['extreme']:.3f}m。完整Parquet、关键地图和每小时帧GIF均归档。本模型不是水动力预测，也未复现2023历史暴雨。"],
    ['四情景、97端点；空间相关峰值与延迟，有限时间恢复。','54条有向边采用合成积水；不解释为历史重建。'],fig('04','depth_curves'),'合成峰值水深时间曲线；来源 '+runs['04'].name)
section('道路速度与容量退化',[
    'Pregnolato等（2017）PDF第7页Eq.4：v=0.0009w²−0.5529w+86.9448，w:mm、v:km/h。工程适配：零水深返回正常速度；速度不超过原自由流值；h≥0.30m排除通行。',
    '容量独立设置为c0×max(0.2,1−0.8h/0.30)，达到中断阈值后移出网络。线性速度函数作对照，容量模型是项目假设，不能归为原论文结论。正常/轻度/重度/中断的边界为0、0.15、0.30m。'],
    ['文献速度函数：mm→km/h，零积水保持正常值。','容量另设；0.30m中断是可调整研究参数。'],fig('05','road_response'),'两种速度模型与独立容量假设的实际函数曲线；来源 '+runs['05'].name)
section('综合韧性的定义与成本口径',[
    'Qs为道路可用比例、最大弱/强连通节点比例、时间加权网络效率相对正常值的等权均值。效率不可达贡献0，南山15个固定起点到全部节点抽样；不声称是全节点对精确效率。',
    '性能成本C=Σx_e t_e+300D_intrazonal+ρD_unserved，ρ默认14,400s。Qp=C0/C，同时间片、同OD正常基准。Qf对医院和消防15/30min人口覆盖比值取均值；缺失设施类别不补造，基准覆盖0项从归一化中排除并记录。',
    'Q=0.2Qs+0.5Qp+0.3Qf；功能不可用时对有效权重重归一化。R按端点梯形积分除24h。需求率按7—10h早峰、17—20h晚峰，其余平峰；96区间计算车辆数，不将97端点视为97次发车。'],
    ['结构：可用性、弱/强连通与抽样时间效率。','性能：保留不可达惩罚与区内成本，同OD基准。','功能：15/30min覆盖；Q权重0.2/0.5/0.3，时间积分得R。'])
section('南山全过程韧性结果',[
    '四个情景使用完全相同的小时OD与正常基准。正常、一般、严重、极端R依次为 '+ ' / '.join(f"{full['scores'][k]:.9f}" for k in ['normal','general','severe','extreme'])+'。',
    f"180次实际分配，最大gap {full['scope']['max_gap']:.3g}，节点守恒误差≤{full['scope']['max_node_balance_error']:.3g} veh/h；本次计算约{full['elapsed_s']/60:.1f}分钟。",
    '影响较小是这组有限合成风险、合成OD与归一化口径的计算结果，不代表深圳真实暴雨损失很小。ρ=7200/14400/28800s时平均R约0.999523/0.999680/0.999792，既有未服务需求会影响归一化。'],
    ['南山：一般R≈0.999914，严重≈0.999665，极端≈0.999461。','全过程收敛；影响幅度受有限合成风险与惩罚口径限制。'],fig('07','resilience_curve'),'纵轴显示接近1的窄幅变化，不能将小数差异解读为城市实测结论。')
section('医院与消防设施可达性',[
    '居民起点来自TAZ人口与现有道路接入节点；无接入人口保留在分母中。设施代表点匹配至现有节点，最长1500m、虚拟接入速度20km/h，入口和实际接入路线未核验。沿有向交通时间找最近医院或消防站，未取得避难所清单。',
    '地图为归档极端情景的代表时刻，展示60分钟截断色标，不可达原值保留在数据中。深色区域包含正常断连和接入缺失，不能直接归因于积水。小网所选TAZ人口约64,440.75，不能视为小bbox内精确人口。'],
    ['人口加权15/30分钟覆盖；方向与断连保留。','虚拟接入与OSM入口不确定；缺失避难所不补零。'],fig('07','hospital_accessibility_map'),'代表时刻医院网络时间；不可达仅在色标显示中截断，原始数据不改。')
section('六组候选道路的关键性',[
    '小网使用独立压力情景：从正常有流量的现有地面物理几何组抽取六组，正反向弧共同治理。该风险设计有条件抽样偏差，与南山54弧风险集不同，不能混用。',
    '实际计算峰值水深、正常流量、32起点抽样边介数、单独关闭性能损失、医院15分钟损失、逐路治理后重新分配的ΔR。当前六候选医院损失均为0，不制造功能增益。',
    '单路治理最高ΔR约0.004171（road_05）。水深与ΔR的Spearman相关−0.20、正常流量与ΔR约0.93；仅六组样本，不据此作一般因果推断。'],
    ['六个候选物理路组；每条单独治理后重算。','水深不等于全网价值；本算例流量与治理收益相关更强。'],fig('08','critical_roads_map'),'单路治理ΔR的实际空间分布；来源 '+runs['08'].name)
section('预算约束优化与穷举核验',[
    '统一成本1，预算3、K=3、积水削减0.6；一般/严重/极端等权作为研究设定，不是灾害真实概率。贪心每轮枚举可行新增道路，重新分配并以边际R/成本选择；没有正收益时停止，不要求花完预算。',
    '种子42下，不治理R=0.991268226；韧性贪心选择road_05、road_03、road_04，R=0.997156009，提升约0.005887783。流量优先得到同一集合和数值。枚举42个可行集合，最优R相同，贪心差距0；这不是一般最优性保证。'],
    ['预算3、K=3、成本1、效果0.6；三种灾害等权。','贪心与流量优先并列；42集合穷举验证当前解。'],fig('09','strategy_comparison'),'种子42，统一成本/预算/OD/时间窗；纵轴截取邻近1的范围。')
section('十种子策略与独立鲁棒性',[
    '训练种子42—51改变空间相关水深场；随机策略同种子取样。十种子平均R：不治理0.989540、随机0.993249、水深0.992793、介数0.994357、流量与贪心均0.996364。未人为要求贪心超过所有基准。',
    f"固定种子42学得的方案，在独立灾害种子1042—1051与OD种子5042—5051上评估。配对ΔR均值{suite['heldout_paired_gain_ci95']['mean']:.6f}，95% t区间[{suite['heldout_paired_gain_ci95']['ci95_low']:.6f},{suite['heldout_paired_gain_ci95']['ci95_high']:.6f}]。",
    '区间只描述随机模型实现差异，不是深圳真实韧性参数置信区间。优化与测试保留相同评价公式；独立OD变化仅用于样本外检验。'],
    ['十训练种子；流量优先与贪心平均R均≈0.996364。','独立灾害与OD测试：固定方案平均增益≈0.007565。'],fig('11','experiment_strategy_comparison'),'十种子均值；标准差与t区间见experiment_statistics.csv。')
section('预算、效果与消融实验',[
    '预算请求K=0/1/3/5/10/20，六个候选不足时截断为0/1/3/5/6/6；效果δ=0.2/0.4/0.6/0.8。C/D为种子42的单因素敏感性，未给不存在的重复样本置信区间。',
    'E分别替换动态积水为峰值常量、取消容量退化、固定正常路线（阻断OD计未服务）、取消功能权重，以及仅按严重情景优化后用多情景评价。无重新分配消融只在小网AON正常分配已均衡的范围使用，不能推广成对任意UE路流的精确路径分解。',
    'G记录Sioux Falls、小网、南山的实际分配耗时与范围。南山全过程韧性约21.6分钟，候选优化与十种子只在小网运行，尚无南山全尺度优化耗时。'],
    ['K不足时显式截断；效果0.2—0.8为研究参数。','五类消融与A—G输出齐备；C/D/E使用种子42。'],fig('11','budget_effect_sensitivity'),'种子42的确定性敏感性；截断后的有效K与原始请求同时保留。')
section('SUMO车辆过程与完整去向',[
    '官方Eclipse SUMO 1.28.0已在项目环境运行。将真实OSM有向几何导出plain XML，保留edge_id映射；两个原有自环沿同一曲线分成两段以适配SUMO，不添加跨路连接。车道连接与路口优先规则由SUMO生成，信号、转向限制与跟驰未实测标定。',
    '小网固定计划1890辆：1267有可行路线、623区内未上图。三情景均1263完成、4辆期末在途；完成者平均行程约231.00/245.94/234.77秒。设置time-to-teleport=-1，封路时保留在途车辆，无法发车的计划留外部队列，重规划失败保留原车。',
    '南山固定抽样2000辆，约占全小时率积分0.184%；1723路由、277未路由计划，三情景均1708完成、15在途。小网治理集合与南山风险无交集，南山disaster/optimized相同，不能用来宣称全区治理收益。全部六运行车辆平衡且teleport为0。'],
    ['SUMO 1.28.0：两种规模、三种情景，计划固定。','全部车辆去向平衡、teleport=0；未路由与期末在途保留。'],fig('10','sumo_vehicle_accounting'),'全计划车辆口径；不只比较已完成车辆。')
section('实际仿真车辆状态',[
    '图中位置来自SUMO TraCI实际车辆快照，非论文示意图。速度与通行限制每15分钟更新，SUMO内部步长1秒；BPR的veh/h容量不直接赋给SUMO容量。',
    '小网治理验证具有模型条件依赖，南山采用抽样车辆只能检验转换、封路、绕行和记账链路，不能证明全量拥堵或城市级治理收益。未完成车辆与外部等待均在原始结果中保留。'],
    ['TraCI真实车辆位置与路网几何叠加。','封路、恢复、重规划与待发队列，保留全部车辆记录。'],fig('10','sumo_vehicles_small'),'实际模拟位置快照；该图不是SUMO GUI截图。')
section('中文交互系统与历史查询',[
    '八页包括路网、内涝、道路状态、韧性、应急设施、关键道路、治理和算法实验。提供情景、15分钟时间轴、K、策略和治理效果筛选，治理前后选中道路图与CSV导出；明确展示预计算历史结果。',
    '未计算的预算×策略×效果组合提示缺少结果，不伪装实时优化。8页经真实浏览器检查；CSV下载核验成功，截图保存在docs/validation/phase12。启动命令见项目说明书。'],
    ['八页中文界面，按情景、时间、预算和效果筛选。','明确历史预计算；未计算组合提示，支持CSV导出。'],'docs/validation/phase12/07-optimization.jpg','本机浏览器实际操作截图，绿色为选中治理道路。')
section('科学解释与规划使用边界',[
    '在当前小网压力设计中，选择网络替代性弱且正常承载较高的道路可改善平均韧性；最深积水优先并未取得最佳结果。这提示后续排水改造排序应同时检查交通需求和替代路线，而不能只按水深。',
    '该结论不能直接变成深圳工程投资顺序：OD、速度/容量、治理成本效果、洪水概率、SW零点和地址位置尚未标定；人口、道路和事件年份不一致，完整避难所缺失。',
    '下一轮实证工作应核实监测传感器位置与零点，取得实测路段速度流量、OD和信号数据，用独立事件校验暴露与性能，再扩大候选和优化范围。当前未完成南山全尺度优化，GA作为可选对照未实现。'],
    ['当前结果支持模型条件下的道路筛选讨论。','工程投资前需核实零点、位置、OD、容量与成本效果。','尚无南山全尺度优化结论；不作城市洪灾预测。'])
section('验收、复现与成果位置',[
    f'{test_count}项pytest通过，44条既有rasterio/affine弃用警告；pip check无冲突。检查正常/中断、平行弧、节点守恒、预算、穷举差距、独立种子、车辆去向和图片输入指纹。历史源文件按当前字节、原Git blob或SHA256完全一致的源快照核验，不改原运行。',
    '每次运行独立run_id，保留失败和检查点；results/index.html为本机图片索引。所有原始结果留results/runs，data/raw与data/synthetic分开；GitHub保留源码、配置、维护文档与小型验收图片/表格。',
    '本机启动：.conda-env\\python.exe -m streamlit run app.py。阶段运行：.conda-env\\python.exe -m uftr.cli run --phase 04（替换阶段号）；完整新实验使用configs/phase11_fresh.yaml，恢复检查点使用phase11.yaml。GitHub：https://github.com/zhzhzh666/jiaotong。'],
    [f'{test_count}项测试、依赖一致性和数值审计；保留全部失败记录。','results/index.html查询图片；配置和run_id追溯结果。','源码、配置、Word/PPT与验收副本同步GitHub。'])
section('参考文献与数据许可',[
    *[r['citation']+' DOI '+r['doi']+'；采用边界：'+r['note'] for r in data['references']],
    'OpenStreetMap contributors，ODbL 1.0；WorldPop 2020，CC BY 4.0；Copernicus DSM保留供应商署名。Sioux Falls上游学术研究单位与版本见Phase01报告。深圳公开平台目录链接见DATA_SOURCES.md，字段说明为用户提供的研究数据字典，不冒充平台官方零点声明。'],
    [r['label']+'：'+r['doi'] for r in data['references']])

# Keep separately generated experiment-input sections when refreshing run facts.
sections.extend(s for s in data.get('final',{}).get('sections',[]) if s.get('title','').startswith(('补充情景 ','情景建模 ','道路模型 ','交通评估 ')))
data.update(updated='2026-11-18',status='研究原型：南山分配与韧性评估、小网治理与十种子实验；实际验收范围及限制见报告')
data['final']={'sections':sections,'tests_passed':test_count,'runs':{p:r.name for p,r in runs.items()},'scope_limit':'small optimization/ten seeds; full Nanshan assignment/resilience and sampled SUMO only'}
write_json(target/'content.json',data)
write_json(ROOT/'docs/validation/accepted_runs.json',data['final']['runs'])
shutil.copy2(ROOT/'data/raw/user_sources/field_dictionary_e9e5a7bd/provenance.json',ROOT/'docs/validation/water_dictionary_provenance.json')
print(f'{len(sections)} shared report sections; {test_count} tests; '+json.dumps(data['final']['runs']))
