"""Record approved Longgang scope and intake facts without relabelling old runs."""
from pathlib import Path
import json
import shutil
import argparse
import yaml

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--run',type=Path)
p.add_argument('--build',type=Path,default=ROOT/'.cache/longgang-doc-sync')
args=p.parse_args()
active_cfg=yaml.safe_load((ROOT/'configs/active_research.yaml').read_text(encoding='utf-8'))
RUN=(args.run or ROOT/active_cfg['accepted_intake']).resolve()
RUN.relative_to(ROOT)
build=args.build.resolve()
build.relative_to(ROOT)
backup=build/'before';backup.mkdir(parents=True,exist_ok=True)
for name in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','content.json','delivery_manifest.json']:
    source=ROOT/'docs/deliverables'/name
    if not (backup/name).exists():shutil.copy2(source,backup/name)
source=ROOT/'docs/validation/final_visual_review.json'
if not (backup/source.name).exists():shutil.copy2(source,backup/source.name)
report=json.loads((RUN/'intake_report.json').read_text(encoding='utf-8'))
assert report['include_dapeng']==active_cfg['include_dapeng'] and report['region']=='longgang'
included=report['include_dapeng']
scope_short='龙岗含大鹏' if included else '龙岗不含大鹏'
scope_text='随包440307龙岗区边界，包含大鹏范围' if included else '随包440307保留龙岗主面，排除大鹏面'
n=report['road_features_selected'];ns=report['station_candidates'];nw=report['water_record_candidates']
nc=report['label_consistent_stations'];nwc=report['label_consistent_water_records']
conflict=len(report['label_conflict_station_ids'])
validation=ROOT/'docs/validation/longgang_intake';validation.mkdir(parents=True,exist_ok=True)
for name in ['intake_report.json','intake_checks.json','manifest.json','road_class_summary.csv','longgang_roads_water_candidates.png']:
    shutil.copy2(RUN/name,validation/name)
section={'title':'龙岗研究区 数据接收与迁移范围','paragraphs':[
    f'当前研究范围为{scope_text}。五份原件保持原字节；实际GPKG只有机动车与全部道路两层，缺少说明书声称的motor_all_bbox。' + ('' if included else '依所供中心点选择龙岗主面，未用经纬线粗切；旧含大鹏版本保留。'),
    f'筛选{n:,}条候选道路线，尚非有向图边；其中{report["missing_lanes"]:,}条缺车道、{report["missing_maxspeed"]:,}条缺限速。需重建交叉口、方向与立交拓扑，边界坐标基准尚待独立核验。',
    f'已有水位筛得{ns}个候选站、{nw:,}条记录；其中{nc}个龙岗标签站有{nwc:,}条，另{conflict}站标签冲突待核。SW路面零点及测站—道路关联仍未确认。',
    '本批未提供实测雨量、官方OD或实测车流。人口与DSM外包范围覆盖新区域，但须重新裁剪，重建TAZ/设施/网关与需求。前述南山实验属于历史结果，龙岗交通与韧性尚未重算。'],
    'slide_points':[f'{scope_short}；{n:,}条候选道路线，未建图。',
        f'{nc}个龙岗标签站＋{conflict}个标签冲突站，SW零点待核。',
        '缺官方OD与实测车流，需重建需求并重算。'],
    'figure':'docs/validation/longgang_intake/longgang_roads_water_candidates.png',
    'caption':scope_short+'的候选路网与测站；紫叉为行政区标签冲突站，尚未验证拓扑。',
    'source_label':'用户OSM包与既有水位资料 / '+RUN.name+'；© OpenStreetMap contributors，ODbL 1.0',
    'ppt_native':False}
target=ROOT/'docs/deliverables/content.json';data=json.loads(target.read_text(encoding='utf-8'))
data['active_research']={'region':'longgang','scope':scope_text,'include_dapeng':included,'scope_short':scope_short,
    'status':'数据接收完成；拓扑、需求及龙岗模型重算待实施','intake_path':RUN.relative_to(ROOT).as_posix(),
    'report':report,'assignment_ready':False}
data['status']=f'当前目标：{scope_short}；数据筛选完成，拓扑与模型待重算。南山实验作为历史保留。'
data['cover_subtitle']=f'研究区调整为{scope_short} 南山结果作为历史保留'
data['final']['sections']=[s for s in data['final']['sections'] if not s['title'].startswith('龙岗研究区 ')]+[section]
data['final']['sections'][0]['paragraphs'][0]=f'2026年11月18日：当前研究范围为{scope_short}，已按最新范围重新筛选道路与测站。已有南山成果作为历史实验保留，龙岗模型尚未重算。'
data['final']['sections'][0]['slide_points']=['研究报告与阶段进展','2026年11月18日',f'研究区调整：{scope_short}；南山结果作为历史保留']
target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
common=f'当前范围为{scope_text}。已按用户最新要求筛选{n:,}条候选道路线及{ns}站{nw:,}条水位记录；其中{nc}个龙岗标签站有{nwc:,}条记录，另{conflict}站行政区标签冲突。此数量是候选几何与观测子集，不是已建成有向路网或已验证积水。'
limits='本批没有官方OD、实测车流或新降雨/水深。路网缺节点拓扑、车道和限速存在缺失，缺少说明书所称motor_all_bbox；边界基准、测站位置与SW零点待核。人口/DSM范围覆盖可复用但尚未完成新裁剪。南山OD、60点积水和R/SUMO结果保留历史，不移名到龙岗；当前phase配置仍属历史南山，不能作为龙岗运行入口。'
for name in ['AGENTS.md','README.md','DATA_SOURCES.md','MODEL_ASSUMPTIONS.md','PLAN.md','PROGRESS.md','EXPERIMENT_LOG.md','docs/USER_GUIDE.md','docs/deliverables/README.md']:
    p=ROOT/name;text=p.read_text(encoding='utf-8');first,rest=text.split('\n',1)
    marker='## 2026-11-18 龙岗研究区数据接收' if included else '## 2026-11-18 龙岗研究范围剔除大鹏'
    if marker in rest:continue
    checks=json.loads((RUN/'intake_checks.json').read_text(encoding='utf-8'))
    extra='\n\n'+marker+'\n\n'+common+'\n\n'+limits+'\n\n当前目标见configs/active_research.yaml；接收说明docs/LONGGANG_DATA_INTAKE.md，接收目录`'+RUN.relative_to(ROOT).as_posix()+f'`。{len(checks["checks"])}项复制/格式/筛选一致性检查通过，不能替代拓扑或实测标定。Word/PPT同步更新范围说明。\n\n以下保留此前含大鹏版本及南山的历史记录，最新范围以本节为准。\n'
    p.write_text(first+extra+rest,encoding='utf-8')
p=ROOT/'docs/FINAL_REPORT.md';text=p.read_text(encoding='utf-8')
heading='## 研究区调整 '+scope_short
if heading not in text:
    first,rest=text.split('\n',1);p.write_text(first+'\n\n'+heading+'\n\n'+common+'\n\n'+limits+'\n\n详见LONGGANG_DATA_INTAKE.md。以下含大鹏及南山范围/数值为历史成果。\n'+rest,encoding='utf-8')
print('Recorded Longgang intake; shared document content now has',len(data['final']['sections']),'sections')
