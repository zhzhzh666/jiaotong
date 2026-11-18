"""Append audited full-district baseline and local transfer acceptance to 56 sections."""
from pathlib import Path
from hashlib import sha256
import json
import shutil
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'.cache/document-sync-20261119-full-baseline'
BEFORE=BUILD/'before'
BEFORE.mkdir(parents=True,exist_ok=True)
target=ROOT/'docs/deliverables'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):return sha256(p.read_bytes()).hexdigest()
data=read(target/'content.json')
assert len(data['final']['sections'])==56
for name in ['content.json','研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','delivery_manifest.json']:
    assert not (BEFORE/name).exists(), 'Never overwrite reviewed backup'
    shutil.copy2(target/name,BEFORE/name)
for name in ['final_visual_review.json','document_sync_state.json']:
    shutil.copy2(ROOT/'docs/validation'/name,BEFORE/name)
guard={n:digest(BEFORE/n) for n in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','content.json']}
guard['other_deliverables']={p.relative_to(ROOT).as_posix():digest(p) for p in target.glob('*.pptx') if p.name!='开题与阶段进展汇报.pptx'}
(BUILD/'input-guard.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
evidence=ROOT/'docs/validation/longgang_sumo_full'
index=read(evidence/'evidence_index.json')
for item in index['files']:assert digest(evidence/item['path'])==item['sha256'],item['path']
audit=read(evidence/'independent_audit.json')
r=read(evidence/'cases/dry/result.json')
assert audit['whole_district_arcs_checked']==86804 and audit['actual_injected_routes_checked']==r['arrived']==10634
assert r['planned']==11506 and r['invalid']==872
assert r['planned']==sum(r[k] for k in ['invalid','arrived','running','sumo_pending','external_pending'])
assert r['generalized_vehicle_seconds']==r['vehicle_seconds']+7200*(r['invalid']+r['unfinished'])
for base in [evidence,ROOT/'docs/validation/migration_5090']:
    suite=ET.parse(base/'tests.xml').getroot().find('testsuite')
    assert int(suite.attrib['tests'])==186 and int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
transfer=read(ROOT/'docs/validation/migration_5090/roundtrip_qa.json')
assert transfer['export_receive']=='passed' and len(transfer['checks'])==5
assert all(x['arrived']==3 and x['balance_error']==0 for x in transfer['checks'])

data['status']='全龙岗5%需求无雨基准已独立核验，Ubuntu迁移流程通过本机微型验收。暴雨治理全区比较及目标Ubuntu验收待完成。'
data['cover_subtitle']='龙岗不含大鹏 全区无雨基准与迁移流程进展'
cover=data['final']['sections'][0]
cover['paragraphs']=[
 '2026年11月19日：全龙岗5%合成需求无雨基准已完成并通过独立审计。全区有效源有向弧86,804条，含周边及整段路径共151,701弧。计划11,506次整段出行，其中10,634次可加载行程全部到达，872次未加载单独记账。本机准备至结束实测16.67分钟，采样Python加子进程RSS峰值2.525 GiB。第57—61节补充范围、账本、资源实测、条件预算与Ubuntu迁移流程。',
 '第2—30节保留南山与小网历史，31—48节为龙岗数据、水文及抽样治理，49—53节为3 km×3 km SUMO五组，54—56节为片区网页三维回放。旧片区访问计数与本次整段行程不可直接比较。当前只完成全区无雨一组，五组与迭代耗时为条件预算，尚无全区暴雨治理收益或已收敛DUE。迁移流程在Windows完成微型往返检查，目标Ubuntu仍待验收。以下历史页的阶段状态以当时记录理解，当前状态以本页及新增章节为准。'
]
cover['slide_points']=['研究报告与阶段进展','2026年11月19日','全龙岗无雨基准已完成核验']
data['longgang_sumo_full']={'path':index['run'],'source_commit':'7ca9b43','evidence_index':'docs/validation/longgang_sumo_full/evidence_index.json',
 'audit':'docs/validation/longgang_sumo_full/independent_audit.json','tests_report':'docs/validation/longgang_sumo_full/tests.xml',
 'tests_passed':186,'result':r,'calibrated':False,'demand_fraction':0.05,'full_district_dry_only':True,'gui_replay_completed':False}
data['migration_5090']={'report':'docs/PHASE_MIGRATION_5090_REPORT.md','readme':'migration/README_迁移与回传.md',
 'evidence':'docs/validation/migration_5090','tests_passed':186,'local_fixture_vehicles':3,'local_roundtrip_passed':True,
 'target_ubuntu_accepted':False,'gpu_solver':False,'evidence_sha256':{p.name:digest(p) for p in (ROOT/'docs/validation/migration_5090').iterdir() if p.is_file()}}

def section(title,paragraphs,left,right,footer,figure=None,caption='',width=16):
    return {'title':title,'paragraphs':paragraphs,'slide_points':[],'figure':figure,'caption':caption,'figure_width_cm':width,
      'rows':None,'headers':None,'source_label':'docs/PHASE_LONGGANG_FULL_SUMO_REPORT.md；docs/validation/longgang_sumo_full/；运行20261118T184221_full5_07cdb6f1',
      'ppt_left':left,'ppt_right':right,'ppt_footer':footer}
data['final']['sections'] += [
section('全龙岗无雨基准 路网与整段需求',[
 '本次覆盖龙岗不含大鹏。独立空间核验确认冻结源图86,804条有效相交有向弧全部保留，另3条自环或极短退化弧排除。加入3 km周边连接道路及抽中正常整段路径后，共151,701弧、101,794节点。周边道路仅提供连接，替代路径仍受保留网外边界限制，未加入外部—外部背景流。',
 '完整483×483合成OD先按5%物理需求、seed42抽整段行程：每15分钟N服从Poisson(0.05×q×0.25)，q单位veh/h。该口径不同于旧片区按出入次数拆分的边界访问。全区覆盖不等于100%需求，不可将车辆数乘20作为全需求结果。时窗固定为北京时间2023-09-10 10:00—14:00，空网起步，前3小时发车，末1小时清空。'
], '全区覆盖 不含大鹏\n\n龙岗有效源弧 86,804\n另排除3条退化弧\n\n加入3 km周边与正常路径\n151,701弧 / 101,794节点\n\n完整483×483合成OD\n5%需求 / seed42\n先抽整段行程\n旧片区访问口径另列', '',
 '全区覆盖与物理需求比例分开解释。无外部—外部背景流，新绕行受保留网络边界限制。',
 'docs/validation/longgang_sumo_full/figures/whole_district_coverage.png','冻结源图全龙岗范围 蓝色为龙岗相交源弧 灰色为周边与整段路径连接',14),
section('全龙岗无雨基准 车辆账本与数值审计',[
 '实际计划11,506次出行，10,634次可加载、872次未加载。未加载包括源图不连通457次、区内出行未建模312次、连接点缺失103次。25条有效计划为保持SUMO转向可行性，在相同首末弧之间修复路径，OD端点保持一致。未加载需求不能计作已到达或从分母删除。',
 '四小时结束到达10,634、在网0、SUMO待插入0、外部待发0。守恒关系为11,506＝10,634＋872，守恒误差、自动传送与碰撞车辆事件均0。系统占用12,473,271 veh·s，按每次未完成或未加载7200 s惩罚后的广义成本为18,751,671 veh·s。惩罚项属于分析约定，不是实际行驶时间。',
 '独立审计检查86,804条全区覆盖弧、151,701条SUMO弧、8,937种有效路径、10,634条实际注入路线、OD端点、逐秒占用积分、4小时记录及978条资源样本。来源186项测试与pip check通过。本次文档同步只核对既有证据和SHA，没有重跑仿真或测试。单有效车道、优先权路口、tau容量代理与合成OD尚未标定，内部一致性不代表实测交通有效性。'
], '计划 11,506次整段出行\n\n可加载 10,634\n全部到达 10,634\n期末在网、待插入、待发均0\n\n未加载 872\n不连通457 / 区内312 / 缺连接103\n25条同端点转向修复',
 '车辆守恒误差 0\n自动传送 0 / 碰撞事件 0\n\n系统占用 12,473,271 veh·s\n含未加载惩罚 18,751,671 veh·s\n惩罚 7,200 s/次\n\n独立路线、端点、积分审计通过\n186项既有测试通过\n参数及需求尚未实测标定',
 '已运行一次无雨基准。未加载保留账本，广义成本包含约定惩罚，不能全解读为实际行驶耗时。'),
section('全龙岗无雨基准 耗时与内存实测',[
 '本机Intel Core i7-14650HX，16核24线程、15.78 GiB内存，无GUI、未使用GPU求解。准备52.20 s、SUMO启动10.58 s、控制循环及关闭输出935.13 s，准备至结果完成合计1000.07 s，即16.67分钟。后续审计、预算探针与预览尝试不计入该数值。',
 '第1—4仿真小时实测耗时依次268.82、339.72、287.97、37.13 s，累计到达2380、5908、9514、10634。第4小时清空阶段没有新增计划出发，不能用其耗时外推发车时段。前3小时仍含按当前成本执行的在线出发路径查询，总计519.50 s。',
 '每1秒采样Python及子进程RSS，峰值合计2.525 GiB，共享页可能重复计数，短瞬时峰值可能漏采。整机可用内存最低261.8 MiB，受其他应用影响，不代表此模型独占内存。来源全区GUI回放因当时C盘已满而写入失败，本轮没有已完成的全区3D截图；第54—56节网页回放仍属于旧片区。'
], '本机实测 关闭GUI\n\ni7-14650HX / 15.78 GiB\n准备至结束 16.67分钟\n\n每仿真小时实际耗时\n1  268.82 s    2  339.72 s\n3  287.97 s    4    37.13 s\n\n合计RSS采样峰值 2.525 GiB\n共享页可能重复计数\n全区3D回放尚未完成','',
 '实测范围为本机5%需求、4小时无雨、关闭GUI。整机可用内存受其他应用影响。',
 'docs/validation/longgang_sumo_full/figures/performance.png','每仿真小时实际耗时与1秒采样资源轨迹 RSS为Python及子进程之和'),
section('全龙岗后续试验 条件预算与验收边界',[
 '一次无雨基准及控制命令、路径查询、全量路径刷新探针支持日程估算。顺序运行无雨、暴雨出发选路、暴雨滚动改道、治理后出发选路、治理后滚动改道，五组合计常规外推2.82 h，按可变计算耗时两倍安排为5.63 h，建议预留约6 h。无雨已完成，后续四组追加常规2.54 h、日程预留5.35 h。全部有效车辆在全部滚动时点始终活跃的极端压力外推为五组16.03 h，另列参考，不作为正常预期或保证上界。',
 '迭代预算先从单次运行B扣除已计时的在线出发查询Q，再加一次全量离线路径刷新R，基础公式T(N)约为P＋N×(B－Q＋R)。P为准备，Q＝519.50 s，R＝280.08 s。假设10、20、30、50轮，基础外推1.98、3.94、5.90、9.82 h，剩余交通计算加倍预留3.16、6.31、9.45、15.74 h。固定预分配路线运行未单独实测，替代路径概率更新开销未知，稀疏未观测边时段使用自由流回退。',
 '这些均为条件预算，不是五组实测或已运行、已收敛DUE，也不是置信区间。仅适用于本机、5%需求、4小时且关闭GUI，不能换算100%需求、24小时或5090加速倍数。下一步需目标机自身基准、同计划五组对比及实际道路关键性和治理组合复核。关键道路新模块正在计算及独立审计，尚未验收的排名不列为本轮结论。'
], '五组比较 条件外推\n\n常规合计 2.82 h\n日程预留 5.63 h 约6 h\n追加四组 2.54 / 5.35 h\n\n极端全车全时点压力项\n五组合计 16.03 h\n非正常预期或保证上界',
 '无雨迭代 条件外推\n\n基础 T(N) ≈ P＋N×(B－Q＋R)\n先扣在线查询 再加离线刷新\n\n20轮基础 3.94 h\n交通加倍预留 6.31 h\n\n迭代与概率更新尚未执行\n收敛轮数未知\n全区暴雨、治理收益待验证',
 '实测只有完整无雨一组及独立探针。预算不是已执行五组、动态均衡收敛或工程收益。'),
section('Ubuntu迁移流程 本机验收与目标机待办',[
 '面向Ubuntu22.04.5、Ultra9 285K、64 GiB及用户说明的RTX5090，新增冻结输入闭包与源码迁移、独立Python3.11/SUMO1.28.0环境、全区五情景headless运行、逐小时资源记录及情景边界恢复。迁移不复制Windows环境。运行器先做目标机基准，再复用同一路网计划补四组；现有求解器使用CPU，未新增CUDA训练器或Gawron/SDTA迭代求解。',
 '本机186项既有测试、pip check和真实单车SUMO/TraCI冒烟通过。两条500 m道路、3辆车、900秒微型夹具实际运行五组，各组均3辆到达、守恒误差0，导出、SHA校验、独立导入与分析通过。此验收只证明Windows上的流程和小夹具可往返，不能作为全区效果、Ubuntu运行或5090性能证据。',
 '回传导出保留原始输出、资源、必要输入及源码配置；接收端先验SHA和路径安全，再导入全新快照并分析，禁止覆盖旧结果与环境。大型迁移包及轨迹留本机，最终包的完整解压与SHA记录由来源聊天继续维护。目标Ubuntu尚未连接、安装或完成仿真验收。应执行scripts/check_5090.py、项目测试与目标机无雨基准，再核对五组账本和资源；随后读取已停止写入的返回快照。'
], '迁移与运行入口\n\nscripts/migrate_5090.py\nscripts/check_5090.py\nscripts/run_5090.py\n\n冻结源码与输入闭包\nUbuntu独立环境\n先无雨 再同计划五组\n逐小时资源 / 情景边界恢复',
 '已验收 Windows本机流程\n\n186项测试及单车冒烟\n微型五组 各3辆到达\n导出、校验、独立导入通过\n\n目标Ubuntu环境和全区运行待验收\n5090尚无加速实测\n当前为CPU求解\n没有新增GPU训练器',
 '微型五情景检验迁移流程，不代表全区研究效果。说明见migration/README_迁移与回传.md。')
]
data['final']['sections'][-1]['source_label']='docs/PHASE_MIGRATION_5090_REPORT.md；migration/README_迁移与回传.md；docs/validation/migration_5090/'
(target/'content.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
script=(ROOT/'scripts/append_digital_twin_presentation.mjs').read_text(encoding='utf-8')
script=script.replace('p.slides.items.length!==53||data.final.sections.length!==56','p.slides.items.length!==56||data.final.sections.length!==61')
script=script.replace('Expected reviewed 53-slide source and 56 sections','Expected reviewed 56-slide source and 61 sections')
script=script.replace("includes('龙岗代表片区 SUMO五组试验完成')","includes('龙岗片区 SUMO与三维回放已核验')")
script=script.replace("replace('龙岗代表片区 SUMO五组试验完成','龙岗片区 SUMO与三维回放已核验')","replace('龙岗片区 SUMO与三维回放已核验','全龙岗无雨基准已完成核验')")
script=script.replace('sections.slice(53)','sections.slice(56)').replace('explicitTotalSlideCount:56','explicitTotalSlideCount:61')
(ROOT/'scripts/append_full_baseline_presentation.mjs').write_text(script,encoding='utf-8')
(BUILD/'append.mjs').write_text(script,encoding='utf-8')
(BUILD/'evidence-check.json').write_text(json.dumps({'full_baseline_evidence_sha256_checked':len(index['files']),'migration_evidence_sha256':data['migration_5090']['evidence_sha256'],'research_tests_rerun':False},indent=2),encoding='utf-8')
print(json.dumps({'sections':len(data['final']['sections']),'evidence_sha_checked':len(index['files'])}))
