"""Append accepted static road screening and RTX 4090 transfer to 61 sections."""
from pathlib import Path
from hashlib import sha256
import json,csv,shutil,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'.cache/document-sync-20261119-critical-roads'
BEFORE=BUILD/'before';BEFORE.mkdir(parents=True,exist_ok=True)
target=ROOT/'docs/deliverables'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
data=read(target/'content.json');assert len(data['final']['sections'])==61
for n in ['content.json','研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','delivery_manifest.json']:
    assert not (BEFORE/n).exists();shutil.copy2(target/n,BEFORE/n)
for n in ['final_visual_review.json','document_sync_state.json']:shutil.copy2(ROOT/'docs/validation'/n,BEFORE/n)
guard={n:sha(BEFORE/n) for n in ['content.json','研究方案与阶段进展.docx','开题与阶段进展汇报.pptx']}
guard['other_deliverables']={p.relative_to(ROOT).as_posix():sha(p) for p in target.glob('*.pptx') if p.name!='开题与阶段进展汇报.pptx'}
save(BUILD/'input-guard.json',guard)
source=ROOT/'docs/validation/longgang_critical_roads/20261118T191957_critical_b29cd51f'
index=read(source/'evidence_index.json')
for item in index['files']:assert sha(source/item['path'])==item['sha256'],item['path']
report=read(source/'report.json');audit=read(source/'independent_audit.json')
assert report['counterfactual_static_solves']==48 and report['total_static_solves_including_baselines']==52
assert audit['status']=='passed' and audit['all_input_and_output_sha_match']
assert sum(x['OD_cells_compared'] for x in audit['distance_checks'])==933156
snapshot=ROOT/'docs/validation/document_sync_critical_roads';snapshot.mkdir(exist_ok=True)
selected=['report.json','independent_audit.json','validation.json','status.json','tests.xml','critical_road_ranking.csv','cases/road_counterfactuals.csv',
 'budget_recommendations.csv','governance_strategy_comparison.csv','figures/critical_roads_map.png','figures/road_restoration_ranking.png','figures/budget_strategy_comparison.png']
# Filename is verified against the actual evidence inventory rather than guessed.
if not (source/'governance_strategy_comparison.csv').exists():selected.remove('governance_strategy_comparison.csv')
for n in selected:
    dest=snapshot/n;dest.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(source/n,dest)
shutil.copy2(ROOT/'docs/PHASE_LONGGANG_CRITICAL_ROADS_REPORT.md',snapshot/'phase_report.md')
shutil.copy2(source/'evidence_index.json',snapshot/'source_evidence_index.json')
save(snapshot/'snapshot_index.json',{'source_run':index['source_run'],'original_evidence_sha_checked':len(index['files']),
 'source_index_sha256':sha(source/'evidence_index.json'),'files':[{'path':p.relative_to(snapshot).as_posix(),'sha256':sha(p)} for p in sorted(snapshot.rglob('*')) if p.is_file() and p.name!='snapshot_index.json']})

package=ROOT/'results/exports/migration_4090_simulation_20261119'
qa=read(package/'验包记录.json');assert qa['full_extraction_and_SHA']=='passed' and qa['files_verified']==1078
archive=package/qa['archive'];assert archive.stat().st_size==qa['archive_bytes']==1078459168 and sha(archive)==qa['sha256']
transfer=ROOT/'docs/validation/document_sync_migration_4090';transfer.mkdir(exist_ok=True)
for n in ['验包记录.json','package_tests.xml','check_4090.log','run_4090.log','先读_4090仿真与回传.md']:
    shutil.copy2(package/n,transfer/n)
shutil.copy2(ROOT/'docs/PHASE_MIGRATION_4090_SIMULATION_REPORT.md',transfer/'phase_report.md')
facilities=ROOT/'data/raw/model_reference/network_resilience_20261119/osm_facilities_get'
shutil.copy2(facilities/'source.json',transfer/'osm_facilities_source.json')
shutil.copy2(facilities/'facilities_wgs84.csv',transfer/'osm_facilities_wgs84.csv')
shutil.copy2(ROOT/'results/resilience_runs/ppt_20261118T194918Z_b1dba226/status.json',transfer/'resilience_preflight_status.json')
for base,test in [(snapshot,'tests.xml'),(transfer,'package_tests.xml')]:
    suite=ET.parse(base/test).getroot().find('testsuite')
    assert int(suite.attrib['tests'])==192 and int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
data['longgang_critical_roads']={'path':index['source_run'],'snapshot':snapshot.relative_to(ROOT).as_posix(),
 'snapshot_index':'docs/validation/document_sync_critical_roads/snapshot_index.json','report':report,'tests_passed':192,
 'static_full_od_screening':True,'full_dynamic_validated':False,'field_calibrated':False}
data['migration_4090']={'snapshot':transfer.relative_to(ROOT).as_posix(),'archive':archive.relative_to(ROOT).as_posix(),
 'archive_bytes':qa['archive_bytes'],'archive_sha256':qa['sha256'],'files_verified':1078,'tests_passed':192,
 'ubuntu_hardware_tested':False,'ppt_resilience_extension_delivered':False,
 'evidence_sha256':{p.name:sha(p) for p in transfer.iterdir() if p.is_file()}}
data['status']='龙岗12候选道路静态筛查及四点分预算治理对照已核验，RTX4090五场景迁移包已完成本机验包。目标Ubuntu与PPT韧性扩展待验收。'
data['cover_subtitle']='龙岗不含大鹏 关键道路筛查与预算治理进展'
cover=data['final']['sections'][0]
cover['paragraphs']=[
 '2026年11月19日：龙岗12个候选道路源要素的静态全OD反事实筛查和四点分预算治理对照已独立核验。新增第62—64节说明候选、公式、排名及治理组合。前三OSM源要素为222954715、1125597098、776647546，属于三快照等权恢复收益排序。相对预算1.8225、3.6450、5.4675下，既有抽样动态试验最优组合依次为S3、S0＋S3、S0＋S1＋S3，成本增量降低5.4498%、9.8871%、11.2577%，尚未实测标定，不能作为工程收益预测。',
 '第2—30节保留南山与小网历史，31—48节为龙岗数据、水文与抽样治理，49—56节为SUMO片区试验及网页回放，57—61节为全区无雨基准和早期迁移流程。全区5%需求无雨基准仍为10,634次有效行程全部到达、872次未加载，实测16.67分钟。本轮第65节记录用户将目标机改为Ubuntu、i9-14900K、128 GiB、RTX4090及独立五场景包验收。目标机实测、全区暴雨治理、全区3D和按PPT综合韧性R扩展仍待完成。以下历史页的状态和5090配置以当时记录理解，当前配置以第65节为准。'
]
cover['slide_points']=['研究报告与阶段进展','2026年11月19日','关键道路筛查与预算治理已核验']
base='docs/validation/document_sync_critical_roads/'
def section(title,paragraphs,left,right,footer,figure=None,caption='',width=16):
    return {'title':title,'paragraphs':paragraphs,'slide_points':[],'figure':figure,'caption':caption,'figure_width_cm':width,
      'rows':None,'headers':None,'source_label':'docs/PHASE_LONGGANG_CRITICAL_ROADS_REPORT.md；运行20261118T191957_critical_b29cd51f；精简来源快照docs/validation/document_sync_critical_roads/',
      'ppt_left':left,'ppt_right':right,'ppt_footer':footer}
data['final']['sections'] += [
section('关键道路识别 候选与静态全OD方法',[
 '龙岗不含大鹏，沿用451,801条源有向弧、307,426源节点，收缩为97,030走廊、47,498端点，保留平行有向边与原弧身份。完整483×483合成平峰OD中413区接入，静态求解不抽目的地，也不计算拥堵反馈、排队和信号。正常流量为单最短路AON，介数为32个走廊起点抽样估计，均非实测流量或精确全节点介数。',
 '1.0倍雨量峰值至少0.05 m的1,154个地面源要素中，综合深度、正常流量、介数、暴露乘流量筛选12候选。每候选做正常中断及三档雨量单路恢复，共48反事实，加4基准为52次静态求解。三档取最大同时封闭数首次出现的模型快照：0.7倍2023-09-10 10:00、1.0倍15:30、1.3倍16:30，北京时间。每次使用同一平峰OD，不代表当时实测车流。',
 '静态损失Σq×min(max(t－t0,0),7200)/3600，单位veh·h/h，正常可达但灾后不可达按7200 s增量计，正常已不可达另记。道路恢复指诊断性地将一个源要素水深设零，三快照恢复收益等权平均排名。该指标不是24小时韧性R，不代表实际灾害概率或工程排水效果。'
], '12候选源要素\n\n1,154个积水初筛要素\n综合深度、AON流量与介数\n48个反事实＋4个基准\n\n完整483×483合成平峰OD\n静态求解不抽目的地\n无拥堵反馈、排队和信号\n\n单源要素恢复为诊断试验\n蓝圈为假设750 m治理作用区','',
 '静态三快照筛查与排水点治理分开解释。源要素不等于整条命名道路，作用圈不是认证汇水区。',
 base+'figures/critical_roads_map.png','12候选源要素及四处治理点位置 含S3附近放大图 蓝圈为假设750 m作用区'),
section('关键道路识别 恢复收益排名与独立核验',[
 '12候选中前三源要素的三快照等权平均恢复收益为：OSM222954715，源位置22569，1040.1526 veh·h/h；OSM1125597098，位置39271，379.8419；OSM776647546，位置22658，204.5803。该排名不涵盖全部道路，也不代表全区动态关键性。道路中文原名存在编码异常时不猜名称，以OSM及源要素身份追溯。',
 '第一候选正常AON流量为0，但1.0倍雨量快照恢复后的收益为3120.4579 veh·h/h，为其他道路受阻时提供替代通道。这说明本例仅按正常最短路流量筛选会漏掉有价值的备选通道，不能外推所有零流量道路。',
 '独立审计直接用451,801条未收缩源弧，不调用关键性计算函数，重算四个基准933,156个OD单元，可达性及费用一致，最大时间差0.00006909 s；另复核首末候选的正常失效与其最大收益情景。来源192项测试及pip check通过，输入输出SHA一致。仅证明程序与数值一致，尚无现场标定或新全区SUMO复核。'
], '前三源要素\n\nOSM 222954715  1,040.1526\nOSM 1125597098   379.8419\nOSM 776647546    204.5803\n单位 veh·h/h\n\n第一候选正常AON流量为0\n暴雨受阻时具有替代通道价值\n\n933,156个OD单元独立核对\n192项既有测试通过','',
 '三快照等权静态恢复收益排名，仅限12候选；未标定，尚未完成全区动态关键性验证。',
 base+'figures/road_restoration_ranking.png','12候选三快照等权静态恢复收益 单源要素水深设零的诊断结果',14),
section('预算治理比较 四点最优组合与适用范围',[
 '本轮重放45份既有动态情景账本，重构四处候选全部15组合的最坏相对无雨广义成本增量及未完成量，再比较穷举、边际收益贪心、水深、流量、介数、静态道路筛查优先和随机10种子。组合目标查询已经计算的真实组合结果，没有将各单点收益相加代替组合收益。',
 '相对预算0时不治理；1.8225时S3（mask8）降低5.4498%，3.6450时S0＋S3（mask9）降低9.8871%，5.4675时S0＋S1＋S3（mask11）降低11.2577%。贪心在四预算下与四点穷举一致，水深、流量和静态筛查优先也同序，未证明贪心优于这些方法。最优性仅限这四点、最多三处和冻结参数；预算单位不是人民币。',
 '收益来自既有120小时、每起点2层目的地抽样的比例点队列，无雨参考已过饱和。原mask9同组合4层抽样下为5.7642%，原2层为9.8871%，全组合排序未做收敛。750 m圈增加4 mm/h损失能力、相对成本及未知道路正常通行均属假设。治理点和静态单道路恢复是不同决策单元，关联不证明工程汇水区；新全区动态验证、管网和真实造价仍待补充。'
], '相对预算及最优组合\n\n1.8225  S3          5.4498%\n3.6450  S0＋S3       9.8871%\n5.4675  S0＋S1＋S3  11.2577%\n\n贪心、水深、流量、静态筛查\n本例均与四点穷举同序\n没有证明贪心优于这些方法\n\n收益沿用120 h抽样点队列\n未标定及抽样敏感','',
 '比例为最坏相对无雨广义成本增量降低，非全过程R提升。最优仅限四点冻结试验，不能直接作工程预测。',
 base+'figures/budget_strategy_comparison.png','四点既有动态试验的预算策略比较 重合曲线表示相同组合 随机带为10种子范围'),
section('RTX4090迁移 当前配置与五场景包验收',[
 '用户已将目标机改为Ubuntu22.04.5、ASUS E500 G9、Intel Core i9-14900K 32逻辑线程、128 GiB、RTX4090及2 TB。当前独立包jiaotong_ubuntu4090_simulation_20261119.tar.gz为1,078,459,168字节，约1.08 GB，包含1078文件，已完整解压并逐文件校验。SHA256为bea33658d4c8c5dfd403087d2e0551d312861f1e9f9910ef467772d45575e1c4。旧5090命名脚本保留为兼容入口，不再表示当前目标硬件。',
 '五场景包沿用冻结路网、OD、积水、治理及已验收无雨基准；默认5%需求、4小时、seed42、单任务、无GUI。入口scripts/run_4090.py与scripts/check_4090.py，先安装独立Python3.11和SUMO1.28.0，目标机先跑无雨，再同计划补暴雨出发、暴雨滚动、治理出发、治理滚动四组。已完成包内192项测试及Windows真实SUMO冒烟，未连接或验收目标Ubuntu；现有求解器CPU，无深度学习训练器或迭代DUE，不据显卡型号承诺加速。',
 '回传沿用导出、SHA校验、独立快照导入与分析，不覆盖历史。大型包留本机results/exports/migration_4090_simulation_20261119/。用户PPT要求结构、性能、功能权重0.27/0.41/0.32并对24小时曲线积分为R；相关关键道路与治理扩展正单独准备，未包含在本五场景包。公开OSM医院69、消防31个对象已取得，完整性、运营与连接尚未实地核实，不能据此称功能韧性或按R排名已经验收。'
], '当前目标机\n\nUbuntu22.04.5 / i9-14900K\n128 GiB / RTX4090 / 2 TB\n\n独立五场景包约1.08 GB\n1,078个文件完整解压与SHA通过\n包内192测试及Windows冒烟通过\n\n新入口 run_4090.py\n目标Ubuntu实测待完成',
 '仿真与回传\n\n先无雨 再同计划补四组\nCPU求解 / 无GUI\n导出 校验 独立快照分析\n\nPPT三维综合韧性R扩展另备\n权重0.27 / 0.41 / 0.32\nOSM医院69 / 消防31对象\n完整性、运营、连接未实地核实\n尚无按R的新验收排名',
 '第61节为早期5090迁移历史，当前以4090配置为准。五场景包验收不等于目标Ubuntu或PPT韧性扩展验收。')
]
data['final']['sections'][-1]['source_label']='docs/PHASE_MIGRATION_4090_SIMULATION_REPORT.md；results/exports/migration_4090_simulation_20261119/验包记录.json；docs/validation/document_sync_migration_4090/'
save(target/'content.json',data)
script=(ROOT/'scripts/append_full_baseline_presentation.mjs').read_text(encoding='utf-8')
script=script.replace('p.slides.items.length!==56||data.final.sections.length!==61','p.slides.items.length!==61||data.final.sections.length!==65')
script=script.replace('Expected reviewed 56-slide source and 61 sections','Expected reviewed 61-slide source and 65 sections')
script=script.replace("includes('龙岗片区 SUMO与三维回放已核验')","includes('全龙岗无雨基准已完成核验')")
script=script.replace("replace('龙岗片区 SUMO与三维回放已核验','全龙岗无雨基准已完成核验')","replace('全龙岗无雨基准已完成核验','关键道路筛查与预算治理已核验')")
script=script.replace('sections.slice(56)','sections.slice(61)').replace('explicitTotalSlideCount:61','explicitTotalSlideCount:65')
(ROOT/'scripts/append_critical_roads_presentation.mjs').write_text(script,encoding='utf-8')
(BUILD/'append.mjs').write_text(script,encoding='utf-8')
save(BUILD/'evidence-check.json',{'critical_original_index_files_checked':len(index['files']),'migration_archive_sha256':qa['sha256'],
 'archive_bytes':qa['archive_bytes'],'files_verified_by_source':1078,'research_models_or_tests_rerun':False})
print(json.dumps({'sections':len(data['final']['sections']),'critical_evidence_sha_checked':len(index['files']),'package_sha_verified':True}))
