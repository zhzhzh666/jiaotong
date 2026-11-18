"""Append the independently audited, uncalibrated Longgang pilot to shared content."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'docs/deliverables/content.json'
data = json.loads(target.read_text(encoding='utf-8'))
evidence = ROOT / 'docs/validation/longgang_adaptive'
report = json.loads((evidence / 'validation_report.json').read_text(encoding='utf-8'))
audit = json.loads((evidence / 'independent_audit.json').read_text(encoding='utf-8'))
assert audit['passed'] and report['run_id'] == audit['run_id']
assert report['recommended_mask'] == 9 and report['exact_pareto_masks'] == [0, 8, 9, 11]
data['updated'] = '2026-11-19'
data['status'] = '龙岗不含大鹏的分区损失、道路退化、抽样点队列与四候选NSGA-II试验完成，独立审计通过。未实测标定，收益对目的地抽样敏感，工程方案待复核。'
data['cover_subtitle'] = '龙岗不含大鹏 分区积水与抽样点队列治理试验'
sections = data['final']['sections'][:41]
sections[0]['paragraphs'] = [
    '2026年11月19日：龙岗不含大鹏已完成土地覆盖分区损失、分道路退化、跨时段抽样点队列和四候选治理试验。第42—48节记录最新方法与结果，165项既有测试及独立审计通过。等权规则选出S0、S3，主设置最坏额外广义成本降低9.8871%，加密目的地抽样后同组合为5.7642%，尚不足以形成工程选址结论。',
    '第2—30节保留南山与小网历史结果，第31—41节记录龙岗数据接收、合成OD及早期积水阶段。早期页面的“尚未重算交通”是当时状态；最新阶段已开展抽样动态加载，仍未完成全OD动态均衡、实测标定或龙岗SUMO复核。所有成本和治理效果均为研究假设。'
]
sections[0]['slide_points'] = ['研究报告与阶段进展', '2026年11月19日', '龙岗不含大鹏 分区积水与治理试验完成']
# The original B experiment remains intact as a historical baseline.
historical_note = '本节记录较早统一损失B方案的八组敏感性，最新分区损失与抽样交通试验见第42—48节。'
if not sections[40]['paragraphs'][0].startswith(historical_note):
    sections[40]['paragraphs'][0] = historical_note + sections[40]['paragraphs'][0]

run = 'data/processed/longgang_adaptive/' + report['run_id']
data['longgang_adaptive'] = {
    'path': run, 'report': report, 'audit': 'docs/validation/longgang_adaptive/independent_audit.json',
    'tests_report': 'docs/validation/longgang_adaptive/tests.xml', 'tests_passed': 165,
    'worldcover_source': 'docs/validation/longgang_adaptive/worldcover_source.json',
    'robustness_report': 'docs/validation/longgang_adaptive/robustness_report.json',
    'calibrated': False, 'full_od_dynamic_loading': False, 'sampled_dynamic_loading': True
}

def section(title, paragraphs, left, right='', footer='', figure=None, caption='', width=16.3):
    s = {'title': '龙岗治理试验 ' + title, 'paragraphs': paragraphs,
         'slide_points': [], 'figure': figure, 'caption': caption, 'rows': None, 'headers': None,
         'source_label': 'docs/PHASE_LONGGANG_ADAPTIVE_REPORT.md；docs/LONGGANG_ADAPTIVE_MODEL.md；运行 ' + report['run_id'],
         'ppt_left': left, 'ppt_right': right, 'ppt_footer': footer}
    if figure: s['figure_width_cm'] = width
    return s

new = [
section('土地覆盖分区与治理假设', [
    '新增ESA WorldCover 2021 v200的N21E111、N21E114原生分类裁剪。10 m类别最近邻采样至30 m，再以5×5聚合成150 m覆盖比例，属于近似比例。卫星分类为公开数据，综合损失能力仍是项目假设，不能当作实测排水或入渗能力。',
    '逐格损失能力c_i=2f建成+8f植被+4f裸地+0f水体，单位mm/h。计算域66,920格，沿用固定D8和DSM蓄泄，内部180 s、每900 s输出。ERA5时窗为北京时间2023年9月6日00时至9月11日00时，120小时，采用0.7、1.0、1.3倍三档雨量。新分区损失与第38—41节统一4 mm/h历史基准不同，二者数值不能直接混用。',
    '每处治理假设在750 m圆形作用区增加4 mm/h综合损失，区边按区内比例缩放，重叠部分不重复叠加。全部15种组合、每档雨量均重算积水。圆域并非真实排水汇水区，没有引入真实管网、二维水动力或实测工程效能。',
    '数据DOI 10.5281/zenodo.7254221，CC BY 4.0。署名：ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021), processed by ESA WorldCover consortium。原生类别裁剪经过无损重编码，非完整远端瓦片字节副本。'
], 'ESA WorldCover 2021 v200\n\n10 m分类采样至30 m\n5×5聚合为150 m覆盖比例\n66,920格，近似覆盖比例\n\nc = 2f建成 + 8f植被 + 4f裸地\n水体损失设为0，单位mm/h\n\n土地覆盖为公开卫星分类\n损失参数仍是假设',
'治理作用与重算\n\n每处半径750 m\n新增4 mm/h综合损失\n重叠取并集，区边按比例\n\n3档雨量 × 15种组合\n逐组合重新计算蓄泄\n\n沿用150 m DSM固定D8\n180秒计算，900秒输出',
'WorldCover DOI 10.5281/zenodo.7254221，CC BY 4.0，完整署名见备注。新分区损失与较早统一损失B方案不同。'),
section('水深与道路性能', [
    '6,848条地面源线取有效采样格最大水深。仅向冻结的86,807条区内或跨界弧ID映射，逐一核对u/v/key；同一源线区外其他弧不继承区内水深。952条桥隧等保持未知，交通计算对未知和覆盖外道路假设正常，不能理解为已观测干燥。早期区外弧映射错误的试算已终止，新运行重建路径与交通结果。',
    '采用Pregnolato等2017年公式，w=1000h为毫米水深，v_lim=0.0009w²−0.5529w+86.9448 km/h。h=0时用原速v0，0<h<0.30 m时v=min(v0,max(0,v_lim))，h≥0.30 m时速度和容量归零。DOI 10.1016/j.trd.2017.06.020，留存PDF第7页Eq.4。',
    '未封路时C=C0 max(0.20,1−a h/0.30)。motorway/trunk/primary/secondary/tertiary/其他的a分别为0.65/0.70/0.75/0.80/0.85/0.90。对应正常容量2,000/1,800/1,600/1,400/1,200 veh/h·方向，residential为800，service/living_street为500。容量按每方向一条有效车道假设；容量折减、等级系数和30 cm封路阈值均为项目假设，未实测标定。',
    '推定深圳路网451,801条有向弧收缩为97,030条走廊，保存每条走廊的完整源弧序列和方向。串联时间取和、容量取最小值，内部排队位置采用近似。长度L以米计时，自由行驶时间为3.6L/v秒。'
], '水深映射与速度\n\n6,848条地面源线取样点最大深度\n仅映射冻结的86,807条弧\n\nw=1000h，水深mm\nv限=0.0009w²−0.5529w+86.9448\nv=min(v0,max(0,v限))，km/h\n\nh=0保持原速\nh≥0.30 m时速度、容量归零',
'道路容量与走廊\n\nC=C0 max(0.20,1−a h/0.30)\na按等级为0.65至0.90\n每方向1条有效车道是假设\n\n451,801条源有向弧\n收缩为97,030条走廊\n串联时间之和、容量最小值\n\n952条桥隧等未知\n未知及覆盖外道路假设正常',
'速度曲线：Pregnolato等2017，DOI 10.1016/j.trd.2017.06.020。容量与封路阈值为项目假设。'),
section('抽样需求与跨时段点队列', [
    '完整483×483合成OD用于记账。同一24小时曲线重复5天，总量11,193,627.796车次；不是2023年实测逐日需求。每个有效起点按目的地概率作2层系统抽样，重复抽中合并，共826对。权重保持每起点每时段总量，目的地及路径分布仍近似。路径库取无雨及1.0/1.3倍各道路峰值状态最短路径，峰值图不代表同时洪水。',
    '每15分钟释放新需求及起点等待量，按当前行驶时间加队列量/容量在有限路径库内选择。交通以60 s推进，走廊行驶时延向上取整，出口点队列每步服务≤CΔt/3600，按路径商品队列比例放行。下游关闭则留在上游，无路则留起点，恢复后继续服务。没有再叠加BPR。',
    '累计释放=累计完成+行驶中+道路排队+起点等待。无雨参考亦只完成5,963,344.076车次，末未完成5,230,283.720车次，其中未接入92,906.182车次。单有效车道和目的地抽样可能造成需求过度集中，基础拥堵不能解释为真实龙岗状态。模型不保证FIFO，无物理回溢、信号冲突、途中重规划或动态均衡迭代。'
], '120小时、合成日重复5次\n826对带权抽样OD\n每15分钟出发时选择路径\n内部60秒跨时段传递\n\n每步服务≤CΔt/3600\n比例分配，未叠加BPR\n\n无雨仍有523.03万未完成\n基础容量和抽样尚待标定', footer='图中车辆量与等待是模型输出。比例服务不保证FIFO，无物理回溢或动态用户均衡。',
figure='docs/validation/longgang_adaptive/figures/adaptive_queues.png', caption='1.3倍雨量下无治理与S0、S3组合的时序对比 采用主设置抽样及容量假设', width=15.5),
section('目标函数与NSGA-II核对', [
    '四处候选最多选择三处，二进制mask编码，共15个可行组合。相对成本为治理区内面积km²×1单位/km²，不是人民币造价。三个最小化目标为三档雨量中相对无雨广义成本的最大增量、三档雨量中末端最大未完成车次（含未接入需求）、相对成本。每个湿情景采用相同抽样和步长的无雨参考。',
    '广义成本G=[∫(行驶中+道路排队+起点等待)dt+7200N末未完成,已接入+7200N未接入+300N区内]/3600，单位veh·h。积分记录有限时窗占用，2小时终端惩罚和300秒区内时间均为假设，未完成车辆不因此成为已到达。该指标不是实际平均延误或真实完整行程时间。',
    'NSGA-II采用二进制交叉、逐位变异、超限修复、非支配排序、拥挤距离和精英保留，种群12、8代，种子42、43、44。算法出处Deb等2002，DOI 10.1109/4235.996017。独立穷举全部15种组合，精确非支配mask为[0,8,9,11]，三个种子均覆盖该集合。',
    '在精确前沿上将三个目标归一化，按到理想点的等权距离和选出mask=9。等权规则是研究选择，不是官方偏好。最优性核对仅覆盖这四处候选、三档雨量和当前参数，不能推广为全区工程最优。'
], '三个目标均最小化\n\nf1=max雨量(G湿−G同设置无雨)\nf2=max雨量(N时窗末未完成)\nf3=区内治理面积×相对单位成本\n\nG为有限时窗占用积分\n加未完成车次×2小时惩罚\n另计未接入及区内需求\n单位veh·h，非真实平均延误',
'NSGA-II与穷举\n\n4处候选，最多选3处\n种群12、8代、3个种子\n二进制交叉、变异与精英保留\n\n全部15个可行组合独立核对\n精确Pareto mask：0、8、9、11\n三个种子覆盖率均100%\n\n归一化等权规则选mask=9\n仅限当前四候选试验',
'Deb等2002，DOI 10.1109/4235.996017。相对成本不是人民币，惩罚不是实际到达时间。'),
section('候选位置与作用范围', [
    '候选筛选采用1.0倍雨量无治理道路样点峰值×关联道路样点数平方根，按暴露排序并保持至少2 km间距。筛选未使用随后优化的交通收益。四个位置是150 m网格中心经投影转换的模型坐标，不是勘测排水工程位置。',
    'S0：114.131662°E、22.610792°N；S1：114.209642°E、22.648724°N；S2：114.229528°E、22.747908°N；S3：114.109797°E、22.610399°N。等权规则选S0与S3，mask=9，作用区内面积3.6450 km²，相对成本3.6450单位。',
    '治理仅通过750 m圆域增加4 mm/h综合损失表达，不能据此确定泵站、管径、工程边界或真实造价。图示积水为网格各自峰值，非同一时刻淹没。选址需要真实汇水区、管井、用地和施工约束复核。'
], '4个暴露候选，间距≥2 km\n位置取150 m网格中心\n\n等权规则：S0与S3\nmask=9\n作用区内面积3.6450 km²\n相对成本3.6450单位\n\n750 m圆域、增加4 mm/h\n均为假设，待工程复核', footer='坐标来自模型投影转换，非勘测工程点。各格峰值不同时发生，圆域不等于真实排水汇水区。',
figure='docs/validation/longgang_adaptive/figures/adaptive_sites.png', caption='四处暴露筛选候选及S0、S3组合 图示为各格各自峰值与假设治理作用范围', width=14.5),
section('主设置的治理结果', [
    '每起点2层目的地抽样、60 s交通步长下，无治理最坏额外广义成本57,517,671.793 veh·h，等权规则选中组合为51,830,857.474 veh·h，相对减少9.8871%。最坏末未完成由6,749,742.824降至6,650,193.028车次，减少99,549.796车次。该收益依赖假设容量、抽样和终端惩罚。',
    '完整非支配集为mask 0、8、9、11，包括无治理。mask=9取S0、S3，三处方案mask=11的第一目标更低但成本更高，等权规则没有选它。不能把一个选中组合当作唯一最优答案。',
    '三档雨量全部重算且相对同设置无雨参考，有限时窗中仍有大量未完成。新增土地覆盖损失与较早统一4 mm/h B方案不同。本轮结果是小候选集研究试验，未完成全OD加载、动态均衡、观测校准或工程收益验证。'
], '无治理 → S0、S3\n\n最坏额外广义成本\n5,751.77万 → 5,183.09万 veh·h\n主设置相对减少9.8871%\n\n最坏末未完成\n674.97万 → 665.02万车次\n减少99,549.796车次\n\n相对成本3.6450单位\n4层抽样收益为5.7642%', footer='图示主设置的15个组合和精确Pareto前沿。收益为模型比较，抽样敏感，尚不能用作工程预测。',
figure='docs/validation/longgang_adaptive/figures/adaptive_pareto.png', caption='全部15个可行组合及精确非支配集 主设置每起点2层抽样与60秒步长', width=15.5),
section('敏感性与结果适用范围', [
    '在1.3倍雨量下，将交通步长细化至30 s，无治理/选中组合的额外广义成本为57,714,588.741/52,024,471.642 veh·h。改为每起点4层抽样、60 s时为56,670,814.428/53,404,202.884 veh·h，收益降为5.7642%；末未完成分别6,477,776.949/6,408,825.487车次。每行均用对应抽样及步长的无雨参考。四层未重做全部15组合，不能宣称排序已收敛。',
    '保持路径库不变，对选中组合与无治理作附加配对检查：背景损失0.5/2倍、封路阈值0.20 m、容量2倍时，额外广义成本分别减少3,629,383.783/1,986,652.698/4,869,102.113/8,785,102.344 veh·h。均为正收益，但未在这些不确定情景上重新优化全部组合。',
    '165项既有测试通过，pip check无冲突。独立审计重放19,722,240个道路水深值，核对451,801条源有向弧、52份交通账本和15个组合，最大道路重放差7.36×10⁻¹⁸ m、最大水量记账差5.96×10⁻⁸ m³。主运行最大水量残差1.78721×10⁻⁶ m³、车辆残差5.96046×10⁻⁸车次。数值一致不能替代实测精度验证。',
    '后续重点为站点雨量与水深核对、裸地DTM及排水损失标定、完整上游边界、有向道路拓扑与实测车道容量、真实OD及抽样收敛，随后扩展FIFO、回溢和信号，结合真实汇水区与造价扩大候选集。来源运行20261118T165311_adaptive_4adc99a6，附加检查20261118T171634_robustness_8c0a6b68。本轮文档同步未重跑长模型或165项测试。'
], '抽样与时间步\n\n主设置：2层，60秒\n治理收益9.8871%\n\n加密抽样：4层，60秒\n同组合收益5.7642%\n未重做全组合排序\n\n30秒与4层均用各自无雨参考\n幅度明显受目的地抽样影响',
'数值核验与外部校准\n\n165项既有测试通过\n独立重放1,972万个道路值\n451,801条弧，52份交通账本\n\n损失、阈值、容量附加配对\n选中组合收益均保持正值\n未对这些情景重新优化\n\n待校准：雨量、水深、OD、容量\n待扩展：FIFO、回溢、信号',
'数值记账通过只支持模型内部一致性。选址收益尚未收敛或实测标定，不能直接成为工程方案。')
]
data['final']['sections'] = sections + new
for ref in [
    {'label': 'ESA WorldCover 2021 v200', 'citation': 'ESA WorldCover project 2021, processed by ESA WorldCover consortium. Contains modified Copernicus Sentinel data (2021).', 'doi': '10.5281/zenodo.7254221', 'note': 'CC BY 4.0，卫星土地覆盖分类，不是实测排水参数。'},
    {'label': 'Deb 等 2002', 'citation': 'Deb K, Pratap A, Agarwal S, Meyarivan T. A fast and elitist multiobjective genetic algorithm: NSGA-II. IEEE Transactions on Evolutionary Computation, 2002, 6(2): 182–197.', 'doi': '10.1109/4235.996017', 'note': '非支配排序、拥挤距离与精英保留。'}
]:
    if not any(r['doi'] == ref['doi'] for r in data['references']): data['references'].append(ref)
target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Shared sections:', len(data['final']['sections']))
