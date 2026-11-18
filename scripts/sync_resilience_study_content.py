"""Append locally accepted PPT-model study delivery to reviewed 65-section edition."""
from pathlib import Path
from hashlib import sha256
import json, shutil, tarfile, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'.cache/document-sync-20261119-resilience-study'
BEFORE=BUILD/'before'; BEFORE.mkdir(parents=True,exist_ok=True)
target=ROOT/'docs/deliverables'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
data=read(target/'content.json'); assert len(data['final']['sections'])==65
for n in ['content.json','研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','delivery_manifest.json']:
    assert not (BEFORE/n).exists(); shutil.copy2(target/n,BEFORE/n)
for n in ['final_visual_review.json','document_sync_state.json']: shutil.copy2(ROOT/'docs/validation'/n,BEFORE/n)
guard={n:sha(BEFORE/n) for n in ['content.json','研究方案与阶段进展.docx','开题与阶段进展汇报.pptx']}
guard['other_deliverables']={p.relative_to(ROOT).as_posix():sha(p) for p in target.glob('*.pptx') if p.name!='开题与阶段进展汇报.pptx'}
save(BUILD/'input-guard.json',guard)
source=ROOT/'docs/validation/migration_4090_study'
qa=read(source/'delivery_verification.json')
archive=ROOT/'results/exports/migration_4090_study_20261119'/qa['archive']
assert archive.stat().st_size==qa['archive_bytes']==714908047
assert sha(archive)==qa['sha256']=='83cd9aee9b57109d8ab5777b90238afa83ae771c29b47698c7bb5bdd91bbc437'
assert qa['files_verified']==796 and qa['full_extraction_and_SHA']=='passed'
assert not qa['Ubuntu_target_executed'] and not qa['Longgang_full_R_study_executed']
snapshot=ROOT/'docs/validation/document_sync_resilience_study'; snapshot.mkdir(exist_ok=True)
for p in source.iterdir():
    if p.is_file(): shutil.copy2(p,snapshot/p.name)
for src,name in [('docs/PHASE_MIGRATION_4090_STUDY_REPORT.md','phase_report.md'),
 ('migration/README_4090_关键道路与治理.md','method_and_runbook.md'),
 ('configs/longgang_resilience_4090.yaml','frozen_config.yaml'),
 ('src/uftr/resilience_ppt.py','frozen_resilience_ppt.py'),
 ('scripts/run_resilience_4090.py','frozen_run_resilience_4090.py'),
 ('scripts/audit_resilience_4090.py','frozen_audit_resilience_4090.py')]: shutil.copy2(ROOT/src,snapshot/name)
# Source files may be edited concurrently after delivery; freeze the archive version.
frozen={'configs/longgang_resilience_4090.yaml':'frozen_config.yaml','src/uftr/resilience_ppt.py':'frozen_resilience_ppt.py',
 'scripts/run_resilience_4090.py':'frozen_run_resilience_4090.py','scripts/audit_resilience_4090.py':'frozen_audit_resilience_4090.py',
 'migration/README_4090_关键道路与治理.md':'method_and_runbook.md'}
with tarfile.open(archive,'r:gz') as packed:
    names=packed.getnames()
    for src,dest in frozen.items():
        matches=[n for n in names if n==src or n.endswith('/'+src)];assert len(matches)==1
        (snapshot/dest).write_bytes(packed.extractfile(matches[0]).read())
suite=ET.parse(snapshot/'frozen_package_tests.xml').getroot().find('testsuite')
assert int(suite.attrib['tests'])==199 and int(suite.attrib['failures'])==int(suite.attrib['errors'])==0
pre=read(snapshot/'Longgang_preflight_preflight.json')
assert pre['connected_facility_objects']=={'fire_station':30,'hospital':64} and pre['efficiency_origin_count']==64
save(snapshot/'snapshot_index.json',{'qa_only':True,'archive_sha256':qa['sha256'],
 'frozen_method_and_source_extracted_from_archive':list(frozen.values()),
 'files':[{'path':p.relative_to(snapshot).as_posix(),'sha256':sha(p)} for p in sorted(snapshot.iterdir()) if p.is_file() and p.name!='snapshot_index.json']})
data['resilience_study_4090']={'snapshot':snapshot.relative_to(ROOT).as_posix(),'archive':archive.relative_to(ROOT).as_posix(),
 'archive_bytes':qa['archive_bytes'],'archive_sha256':qa['sha256'],'files_verified':796,'tests_passed':199,
 'synthetic_qa_only':True,'longgang_full_study_executed':False,'ubuntu_target_executed':False,
 'snapshot_index':(snapshot/'snapshot_index.json').relative_to(ROOT).as_posix()}
data['status']='按PPT综合韧性模型的关键道路与治理4090专用包已完成本机验收；199项测试及合成24小时流程通过。真实龙岗仅预检，目标Ubuntu与正式R研究待运行。'
data['cover_subtitle']='龙岗不含大鹏 综合韧性研究方法与4090专用包进展'
cover=data['final']['sections'][0]
cover['paragraphs']=[
 '2026年11月19日：按用户PPT综合韧性模型的关键道路识别与治理专用4090包已交付并完成本机验收。新增第66—69节说明Q=0.27Qs＋0.41Qp＋0.32Qf、24小时积分R、12候选按ΔR重新排名、四排水点15组合预算优化、设施接入及验收边界。包内199项测试、合成小路网24小时流程与回传分析通过；真实龙岗仅输入预检通过，尚无正式龙岗ΔR排名、R治理收益或目标Ubuntu实测。',
 '第2—30节为南山与小网历史，31—48节为龙岗数据、水文与抽样治理，49—56节为SUMO片区及网页回放，57—61节为全区无雨基准和早期迁移。第62—64节保留静态三快照筛查和旧抽样点队列预算结果，第65节为先前五场景包，其“R扩展准备中”是当时状态，当前以66—69节为准。当前目标Ubuntu22.04.5、i9-14900K、128 GiB、RTX4090，现有求解使用CPU。全区无雨仍为10,634次有效行程全到达、872次未加载；全区暴雨治理与全区3D仍待验证。'
]
cover['slide_points']=['研究报告与阶段进展','2026年11月19日','综合韧性专用包已完成本机验收']
def section(title,paragraphs,left,right,footer):
    return {'title':title,'paragraphs':paragraphs,'slide_points':[],'figure':None,'caption':'','rows':None,'headers':None,
      'source_label':'docs/validation/document_sync_resilience_study/；原报告docs/PHASE_MIGRATION_4090_STUDY_REPORT.md',
      'ppt_left':left,'ppt_right':right,'ppt_footer':footer}
data['final']['sections'] += [
section('综合韧性模型 Q与24小时R',[
 '专用流程采用用户PPT固定权重Q(t)=0.27Qs(t)＋0.41Qp(t)＋0.32Qf(t)。每15分钟记录一个端点，24小时共97端点，R=∫Q(t)dt/24 h，使用梯形积分。各指标相对相同OD时段的无雨状态归一化；权重未重新估计熵权。超过1的Q/R保留原值并标记，不截断。',
 'Qs为可用有向弧比例、最大弱连通节点比例、最大强连通节点比例、时间效率各自相对无雨值的均值。结构范围固定为龙岗86,807条关联源弧、58,221节点，保留方向和平行边。默认固定64个效率起点分批计算，因此R是该抽样设置下估计，不是全起点精确效率；此范围与SUMO剔除3条退化弧后的86,804条不同。',
 'Qp=C0/C，C=Σ弧流量×弧时间＋14,400 s×不可达OD需求，单位veh·s/h。完整483×483合成OD按5%比例缩放，保留全部OD单元，区别于SUMO泊松整段行程抽样。区内需求单记，不加载道路、不额外添加300 s费用。逐时片BPR用户均衡α=0.15、β=4，间隙目标10⁻⁴、最多1000轮；未收敛或守恒失败即停止，不跨时片传递排队，尚非动态用户均衡。'
], 'PPT固定权重\n\nQ = 0.27Qs＋0.41Qp＋0.32Qf\nR = 24小时Q曲线平均值\n15分钟间隔 / 97个端点\n相同OD时段无雨归一化\n\nQs 四项结构指标的相对值均值\n可用弧、弱连通、强连通、效率\n固定64个效率起点估计',
 '性能韧性与交通分配\n\nQp = C0 / C\nC = Σ弧流量×时间\n     ＋14,400 s×不可达需求\n完整483×483 OD按5%缩放\n区内需求独立记账\n\n逐时片BPR用户均衡\n间隙10⁻⁴ / 最多1000轮\n无跨时片排队 / 尚非动态均衡',
 '此页为新流程定义。固定抽样效率与未标定合成需求影响解释范围，尚无正式龙岗R结果。'),
section('功能韧性 医院消防覆盖与数据边界',[
 'Qf使用医院、消防两类设施15分钟和30分钟的人口覆盖率。先对各类覆盖率分别除以无雨覆盖率，按两类等权得到Qf15、Qf30，再等权平均得到Qf；另报R15/R30。两个阈值如何汇总属于当前实现明确采用的规则。任一无雨覆盖率为0即停止，不私自改权重。',
 '公开OSM取得69个医院、31个消防对象，按中心点在1500 m内接入道路，连接速度假设20 km/h。真实输入预检接入64医院和30消防，另5医院、1消防保留未接入标记。OD分区人口估计总量3,172,796.9942包含未接入分区，固定保留在覆盖率分母；该人口和设施均不等于官方完整服务清单。',
 '设施原始响应、ODbL来源署名、用户PPT及指纹随包冻结。道路路径考虑方向与设施、分区连接时间，但设施中心点可能不是真实出入口，OSM对象可能重复，完整性与运营未现场核实。所有指标使用同一固定分母，避免移除未接入人口虚增覆盖率；这些程序约束不替代医疗消防服务能力核验。'
], 'Qf的明确汇总规则\n\n医院及消防两类等权\n分别计算15分钟、30分钟覆盖\n各项相对无雨覆盖率归一化\nQf = (Qf15＋Qf30) / 2\n另报 R15 / R30\n\n无雨覆盖率为0即停止\n所有分区人口保留在分母',
 '公开OSM设施预检\n\n医院 69对象 / 64接入\n消防 31对象 / 30接入\n未接入 5医院＋1消防\n\n中心点接入上限 1,500 m\n连接速度假设 20 km/h\n人口估计分母约317.28万\n\n完整性、运营及真实入口未核实',
 '设施连接预检通过不等于真实服务覆盖验证。OSM原始响应与ODbL署名随包保留。'),
section('关键道路与治理 按ΔR排序及预算优化',[
 '旧静态筛查只提供12个候选道路源要素。新流程在0.7、1.0、1.3倍三档雨量下逐条将候选道路积水归零，重算24小时Q/R，以三档ΔR的平均值重新排名。它是候选内恢复价值诊断，不是全区所有道路穷尽识别，也不表示工程可以将道路积水完全消除。正式龙岗排名待完整研究运行后产生。',
 '治理单元为四个冻结空间排水点S0—S3，最多选三处，含空集共15组合；各组合读取独立计算的积水序列，重新分配交通并计算R，不把单点收益相加代替组合收益。相对预算0、1.8225、3.6450、5.4675下，最大化三档雨量中的最小24小时R，并比较精确枚举、边际贪心、深水优先与10随机种子。',
 '新R目标与第62—64节三快照静态veh·h/h指标、旧120小时抽样点队列成本增量均不同，不能直接搬用旧排名或9.8871%收益。精确最优性只限四点、最多三处及冻结模型；相对成本不是人民币，治理作用和合成需求未标定。完整研究计划含7,857个案例端点，完全相同状态可复用；两状态pilot仅给条件预算，目标机耗时尚无实测。'
], '候选道路按ΔR重新排名\n\n旧静态筛查仅提供12个候选\n单候选道路积水设零\n三档雨量各重算24小时R\n平均ΔR作为候选内排序指标\n\n诊断性恢复 / 非工程排水效果\n正式龙岗新排名尚待运行',
 '四点预算治理\n\nS0—S3 / 最多治理三处\n含空集共15组合\n预算 0 / 1.8225 / 3.6450 / 5.4675\n目标 最大化三雨型中最小R\n\n精确枚举、贪心、深水优先\n另与10随机种子比较\n\n全研究7,857案例端点可复用\n两状态pilot仅作条件预算',
 '新R目标独立于旧静态筛查与点队列成本收益。四点相对成本及冻结积水不能作真实投资效果预测。'),
section('RTX4090专用研究包 本机验收与待运行事项',[
 '新包jiaotong_ubuntu4090_keyroads_governance_20261119.tar.gz为714,908,047字节，796个冻结文件完整解压并逐文件SHA通过，本轮再次计算大包SHA256为83cd9aee9b57109d8ab5777b90238afa83ae771c29b47698c7bb5bdd91bbc437。此包独立于旧五场景SUMO包，入口scripts/run_resilience_4090.py；适用Ubuntu22.04.5、i9-14900K、128 GiB、RTX4090，默认CPU单任务、数值库线程1，不直接使用4090加速。',
 '本机包内199项测试及pip check通过；三节点六有向弧、两OD区、两道路候选、四治理点的合成夹具完成51案例×97端点，验证Q/R、道路排名、精确预算、相同源码恢复、数组审计及导出接收分析。BPR篡改被检出，源码变更拒绝导出。审计核SHA、数组、守恒、记录间隙和算术，但不重算全部最短路或结构效率。首次Windows验包因深目录路径过长失败，改短目录后通过，未改包源码。',
 '真实龙岗仅预检通过，正式全区R研究与目标Ubuntu安装、耗时、性能均未执行。运行顺序为preflight、两状态pilot、all，可同配置断点恢复；源码或输入改变必须新run。停止写入后导出结果与源码输入，receive在本机新ID目录校验、导入、分析，不覆盖历史。压缩包不含Linux离线依赖仓库，安装需联网。本轮文档维护引用既有验收证据，未重跑研究模型或测试；四组SUMO串联流程仍由开发聊天验证，尚不作为已交付研究成果。'
], '独立关键道路与治理专用包\n\n714,908,047字节 / 796冻结文件\n完整解压与逐文件SHA通过\n包内199项测试与pip check通过\n合成24小时流程及回传分析通过\n\n入口 run_resilience_4090.py\nCPU单任务 / 数值库线程1\n源码变更必须新run',
 '验收范围与后续运行\n\n合成夹具51案例×97端点\n真实龙岗仅输入预检通过\n正式龙岗R排名与收益待计算\n目标Ubuntu尚未安装或执行\n\npreflight / pilot / all\n相同源码支持断点恢复\n导出校验后回传到新ID目录\n安装需联网获取Linux依赖',
 '本机合成验收不等于正式龙岗研究完成。目标Ubuntu、四组SUMO新流程与全区3D仍待独立验证。')
]
save(target/'content.json',data)
script=(ROOT/'scripts/append_critical_roads_presentation.mjs').read_text(encoding='utf-8')
script=script.replace('p.slides.items.length!==61||data.final.sections.length!==65','p.slides.items.length!==65||data.final.sections.length!==69')
script=script.replace('Expected reviewed 61-slide source and 65 sections','Expected reviewed 65-slide source and 69 sections')
script=script.replace("includes('全龙岗无雨基准已完成核验')","includes('关键道路筛查与预算治理已核验')")
script=script.replace("replace('全龙岗无雨基准已完成核验','关键道路筛查与预算治理已核验')","replace('关键道路筛查与预算治理已核验','综合韧性专用包已完成本机验收')")
script=script.replace('sections.slice(61)','sections.slice(65)').replace('explicitTotalSlideCount:65','explicitTotalSlideCount:69')
(ROOT/'scripts/append_resilience_study_presentation.mjs').write_text(script,encoding='utf-8')
(BUILD/'append.mjs').write_text(script,encoding='utf-8')
save(BUILD/'evidence-check.json',{'archive_bytes':qa['archive_bytes'],'archive_sha256':qa['sha256'],'source_tests':199,
 'snapshot_files':len(read(snapshot/'snapshot_index.json')['files']),'research_models_or_tests_rerun':False})
print('Prepared 69 shared sections; archive SHA verified; source evidence snapshotted')
