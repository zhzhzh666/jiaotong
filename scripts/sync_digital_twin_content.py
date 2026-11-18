"""Append the verified offline 3D replay to the reviewed 53-section reports."""
from pathlib import Path
from hashlib import sha256
import json
import shutil
import csv

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'.cache/document-sync-20261119-digital-twin'
BEFORE=BUILD/'before';BEFORE.mkdir(parents=True,exist_ok=True)
target=ROOT/'docs/deliverables'
for name in ['content.json','研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','delivery_manifest.json']:
    assert not (BEFORE/name).exists(), 'Do not overwrite reviewed backup'
    shutil.copy2(target/name,BEFORE/name)
for name in ['final_visual_review.json','document_sync_state.json']:
    shutil.copy2(ROOT/'docs/validation'/name,BEFORE/name)
evidence=ROOT/'docs/validation/digital_twin'
audit=json.loads((evidence/'data_audit.json').read_text(encoding='utf-8'))
visual=json.loads((evidence/'visual_review.json').read_text(encoding='utf-8'))
folder=ROOT/'dashboard/digital-twin/data'
for name,digest in audit['sha256'].items():
    assert sha256((folder/name).read_bytes()).hexdigest()==digest,name
for item in visual['screenshots']:
    assert sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
ledger=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
assert all(all(row.values()) for row in ledger['matches_archived_accounting'].values())
assert audit['source_road_shapes_matched']==4969 and visual['final_console_warning_error_count']==0
for name,arrived in [('dry',3588),('rain_rolling',877),('governed_rolling',1230)]:
    case=json.loads((folder/(name+'.json')).read_text(encoding='utf-8'))
    assert case['sample_seconds']==1 and len(case['frames'])==14401
    assert sum(len(f['v']) for f in case['frames'])==audit['cases'][name]['vehicle_samples']
    archived=ROOT/audit['source_run']/'cases'/name
    result=json.loads((archived/'result.json').read_text(encoding='utf-8'))
    for key in ledger['matches_archived_accounting'][name]: assert case['result'][key]==result[key],(name,key)
    assert result['arrived']==arrived
    with (archived/'traffic_series.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    assert len(rows)==len(case['series'])==240
    for row,saved in zip(rows,case['series']):
        for k,v in row.items(): assert float(v)==float(saved[k]),(name,k)
    assert audit['cases'][name]['every_second_running_count_matches_archived_SUMO']
assert sum(c['vehicle_samples'] for c in audit['cases'].values())==1386694
guard={n:sha256((BEFORE/n).read_bytes()).hexdigest() for n in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','content.json']}
(BUILD/'input-guard.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
checked={'data_sha_checked':len(audit['sha256']),'screenshot_sha_checked':len(visual['screenshots']),
         'frames':43203,'vehicle_samples':1386694,'minute_rows':720,'final_fields_per_case':10}
(BUILD/'evidence-check.json').write_text(json.dumps(checked,indent=2),encoding='utf-8')
d=json.loads((target/'content.json').read_text(encoding='utf-8'))
assert len(d['final']['sections'])==53
d['status']='龙岗片区SUMO与网页三维离线回放已核验。三组每秒轨迹和账本一致，程序化建筑非实测；全区基准仍待完成核验。'
d['cover_subtitle']='龙岗不含大鹏 片区交通试验与三维轨迹回放'
cover=d['final']['sections'][0]
cover['paragraphs']=[
 '2026年11月19日：龙岗代表片区五组SUMO结果已核验，新完成Three.js网页三维离线回放。第54—56节补充实际日景、积水与夜景截图、数据追溯和操作入口。三组各14,401帧，共1,386,694条车辆位置记录，逐秒车辆数与原SUMO日志一致。建筑、植被与路灯为程序化配景，积水带表示道路模型水深，尚未接入实测城市建筑、高程或连续二维水面。',
 '第2—30节保留南山与小网历史，第31—41节为龙岗数据及早期积水，第42—48节为抽样点队列治理，第49—53节为3 km×3 km、5%需求的SUMO片区试验。无雨、暴雨、治理后分别完成3,588、877、1,230次访问，实际在途改道0次。新画面不改变这些结果。全龙岗5%基准试跑和Ubuntu迁移包正在推进，待完成核验后另行同步；当前无全区均衡或工程收益结论。'
]
cover['slide_points']=['研究报告与阶段进展','2026年11月19日','龙岗片区 SUMO与三维回放已核验']
d['digital_twin']={'source_run':audit['source_run'],'replay_path':'data/processed/digital_twin_replay_20261118T183542',
    'data_audit':'docs/validation/digital_twin/data_audit.json','visual_review':'docs/validation/digital_twin/visual_review.json',
    'report':'docs/PHASE_DIGITAL_TWIN_REPORT.md','offline_replay':True,'measured_city_model':False,
    'frame_seconds':1,'frames_per_case':14401,'vehicle_samples':1386694,'minute_rows':720,
    'tests_passed':171,'source_commit':'1f784e0','data_sha256':audit['sha256']}
def section(title,paragraphs,left,footer,figure,caption):
    return {'title':'龙岗三维回放 '+title,'paragraphs':paragraphs,'slide_points':[],
            'figure':figure,'caption':caption,'figure_width_cm':16,'rows':None,'headers':None,
            'source_label':'docs/PHASE_DIGITAL_TWIN_REPORT.md；docs/validation/digital_twin/；来源运行20261118T175153_sumo_492a503a',
            'ppt_left':left,'ppt_right':'','ppt_footer':footer}
d['final']['sections'] += [
section('网页展示与数据范围',[
 'Three.js r170新增独立三维网页，支持无雨dry、暴雨rain_rolling、治理governed_rolling三情景。道路沿用原SUMO片区推定平面几何，车辆位置来自冻结控制器每秒TraCI重放。建筑、植被、路灯、屋顶与日夜照明是程序化视觉配景，未增加实测建筑轮廓、高度、道路高程或真实信号相位。',
 '来源仍为S0附近3 km×3 km、5%合成边界访问需求的片区试验，不是全龙岗模型。相同3,588辆计划下，到达仍为3,588／877／1,230次访问，暴雨和治理后的实际在途改道均0。页面回放没有新增治理或动态选路收益，单车道与tau容量代理仍未经实测标定。',
 '图为来源聊天在1280×720浏览器实际查看时保存的日景截图。界面统计是截图时刻的局部状态，不是四小时最终到达量；例如日景画面显示10:48:01，累计到达879。该网页与第53节原生OSG预览是两个不同显示入口。'
], 'Three.js网页离线回放\n\n道路：原SUMO推定几何\n车辆：每秒TraCI位置\n\n无雨 / 暴雨 / 治理三组\n到达仍为3,588 / 877 / 1,230\n原实际在途改道仍0\n\n建筑、树木、灯光为配景\n未接入实测城市三维模型',
 '实际浏览器日景截图；截图中的879为10:48:01累计到达，最终无雨到达量为3,588。',
 'docs/validation/digital_twin/day.jpg','实际网页日景 原SUMO轨迹配合程序化城市配景 非城市实景测绘'),
section('积水显示与轨迹核对',[
 '蓝色道路水带表示相应源有向弧的模型水深，橙色横线表示达到0.30 m中断阈值，不能解释为连续二维淹没水面。道路仍为原试验平面，颜色展示没有新增水动力求解。未知道路水深仍保留未知语义，其交通正常处理假设沿用原试验。',
 '完整1秒版重放保存为data/processed/digital_twin_replay_20261118T183542，早期5秒试导出目录保留。每帧记录车辆索引、x/y米坐标、航向角和速度m/s，补查新出发车辆，连续帧间线性插值。三组各14,401帧，独立车辆ID为3,588／882／1,236；车辆位置记录为791,166／236,069／359,459条，共1,386,694条，不是车辆总数。',
 '独立审计核对4,969条道路ID、顺序、全部坐标与积水数组，三组逐秒在途数与历史summary一致，720行分钟统计一致，各组10个最终账本字段与历史值一致。来源summary的time=t−1对应simulationStep后t。到达与在途统计使用60秒账本，显示车速取当前轨迹样本均值；亚秒插值仍有近似。'
], '模型水深着色\n\n蓝色：道路弧水深\n橙线：达到0.30 m中断阈值\n不代表连续二维水面\n\n3组各14,401帧\n共1,386,694条位置记录\n逐秒车辆数匹配历史日志\n4,969条道路 / 720行统计核对\n每组10个终态账本字段一致',
 '实际暴雨页面截图；位置记录数不是车辆数。每秒采样及帧间插值用于显示，原交通结果保持不变。',
 'docs/validation/digital_twin/rain.jpg','实际网页暴雨画面 蓝色带为道路模型水深 不是连续二维水面'),
section('夜景操作与复现入口',[
 '页面提供街区、全域鸟瞰、车辆跟随、自动运镜和点击车辆检查；支持暂停播放、1／5／15／60倍速、时间轴及键盘跳转、建筑与积水开关、全屏。日夜切换改变光照与窗灯，不改变仿真时间、OD或道路积水。图为实际浏览器夜景截图。',
 '在项目根目录双击启动三维仿真.cmd，或用.conda-env/python.exe运行scripts/serve_digital_twin.py；本机地址http://127.0.0.1:8766/，只监听回环。依赖及Three.js MIT许可随代码保存。大型JSON及gzip留本机，新机器须复制原试验及输入，再用scripts/export_digital_twin.py重建，并执行scripts/audit_digital_twin.py核验；仅获取代码不足以直接显示全部轨迹。',
 '来源浏览器核验记录覆盖三情景末端到达量、日夜、暂停播放、时间轴、鸟瞰与跟随，最终console warning/error为0；来源工作区171项既有测试与pip check通过。本次文档同步核对归档数据SHA和截图，没有重新运行仿真或浏览器测试。全龙岗5%基准和Ubuntu迁移包仍在推进，待完成独立核验后更新；SDTA/Gawron尚无已验收运行结果。'
], '显示与操作\n\n日夜 / 街区 / 鸟瞰 / 跟随\n自动运镜 / 车辆检查\n暂停、倍速与时间轴\n\n双击启动三维仿真.cmd\n本机地址127.0.0.1:8766\n\n完整轨迹JSON/gzip留本机\n新机器先复制或重建数据\n全区基准及迁移包待验收',
 '实际浏览器夜景截图；日夜切换仅改变显示。当前为离线轨迹回放，不能用配景证明真实建筑或水动力重建。',
 'docs/validation/digital_twin/night.jpg','实际网页夜景 窗灯和建筑为程序化配景 日夜切换不改交通结果')
]
(target/'content.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=(ROOT/'scripts/append_longgang_sumo_presentation.mjs').read_text(encoding='utf-8')
p=p.replace('p.slides.items.length!==48||data.final.sections.length!==53','p.slides.items.length!==53||data.final.sections.length!==56')
p=p.replace('Expected reviewed 48-slide source and 53 sections','Expected reviewed 53-slide source and 56 sections')
p=p.replace('龙岗代表片区 SUMO五组试验完成','龙岗片区 SUMO与三维回放已核验')
p=p.replace('龙岗不含大鹏 分区积水与治理试验完成','龙岗代表片区 SUMO五组试验完成')
p=p.replace('sections.slice(48)','sections.slice(53)').replace('explicitTotalSlideCount:53','explicitTotalSlideCount:56')
(ROOT/'scripts/append_digital_twin_presentation.mjs').write_bytes(p.encode('utf-8'))
(BUILD/'append.mjs').write_bytes(p.encode('utf-8'))
print(json.dumps({'sections':len(d['final']['sections']),**checked}))
