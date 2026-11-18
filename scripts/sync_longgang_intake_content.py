"""Record approved Longgang scope and intake facts without relabelling old runs."""
from pathlib import Path
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'data/processed/longgang_intake/20261118T193729_longgang_intake_fe318c5f'
build=ROOT/'.cache/longgang-doc-sync'
backup=build/'before';backup.mkdir(parents=True,exist_ok=True)
for name in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx','content.json','delivery_manifest.json']:
    source=ROOT/'docs/deliverables'/name
    if not (backup/name).exists():shutil.copy2(source,backup/name)
source=ROOT/'docs/validation/final_visual_review.json'
if not (backup/source.name).exists():shutil.copy2(source,backup/source.name)
report=json.loads((RUN/'intake_report.json').read_text(encoding='utf-8'))
assert report['road_features_selected']==9624 and report['label_consistent_stations']==14
validation=ROOT/'docs/validation/longgang_intake';validation.mkdir(parents=True,exist_ok=True)
for name in ['intake_report.json','intake_checks.json','manifest.json','road_class_summary.csv','longgang_roads_water_candidates.png']:
    shutil.copy2(RUN/name,validation/name)
section={'title':'龙岗研究区 数据接收与迁移范围','paragraphs':[
    '研究区已按用户选择调整为随包440307龙岗区边界，包含大鹏范围。五份原件已保存并核对SHA；实际GPKG只有机动车与全部道路两层，缺少说明书声称的motor_all_bbox。',
    '筛选9,624条候选道路线，尚非有向图边；其中6,603条缺车道、9,341条缺限速。需重建交叉口、方向与立交拓扑，边界坐标基准尚待独立核验。',
    '已有水位筛得15个候选站、6,125条记录；其中14个龙岗标签站有5,731条，另1站标签冲突待核。SW路面零点及测站—道路关联仍未确认。',
    '本批未提供实测雨量、官方OD或实测车流。人口与DSM外包范围覆盖新区域，但须重新裁剪，重建TAZ/设施/网关与需求。前述南山实验属于历史结果，龙岗交通与韧性尚未重算。'],
    'slide_points':['龙岗440307含大鹏；9,624条候选道路线，未建图。',
        '14个龙岗标签站＋1个标签冲突站，SW零点待核。',
        '缺官方OD与实测车流，需重建需求并重算。'],
    'figure':'docs/validation/longgang_intake/longgang_roads_water_candidates.png',
    'caption':'龙岗含大鹏的候选路网与测站；紫叉为行政区标签冲突站，尚未验证拓扑。',
    'source_label':'用户OSM包与既有水位资料 / '+RUN.name+'；© OpenStreetMap contributors，ODbL 1.0',
    'ppt_native':False}
target=ROOT/'docs/deliverables/content.json';data=json.loads(target.read_text(encoding='utf-8'))
data['active_research']={'region':'longgang','scope':'随包440307龙岗边界，包含大鹏范围',
    'status':'数据接收完成；拓扑、需求及龙岗模型重算待实施','intake_path':RUN.relative_to(ROOT).as_posix(),
    'report':report,'assignment_ready':False}
data['status']='当前目标：龙岗（随包440307，含大鹏）；数据接收已完成，拓扑与模型待重算。南山实验作为历史保留。'
data['cover_subtitle']='研究区调整为龙岗含大鹏 南山结果作为历史保留'
data['final']['sections']=[s for s in data['final']['sections'] if not s['title'].startswith('龙岗研究区 ')]+[section]
data['final']['sections'][0]['paragraphs'][0]='2026年11月18日：研究区调整为龙岗（随包440307，含大鹏），已完成数据接收。前述南山成果作为历史实验保留，龙岗模型尚未重算。'
data['final']['sections'][0]['slide_points']=['研究报告与阶段进展','2026年11月18日','研究区调整：龙岗含大鹏；南山结果作为历史保留']
target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
common='研究目标已改为龙岗，采用用户确认的随包440307边界，包含大鹏范围。已接收五份OSM原件并逐份校验，完成9,624条候选道路线及15站6,125条水位记录筛选；其中14个龙岗标签站有5,731条记录，另1站行政区标签冲突。此数量是候选几何与观测子集，不是已建成有向路网或已验证积水。'
limits='本批没有官方OD、实测车流或新降雨/水深。路网缺节点拓扑、车道和限速存在缺失，缺少说明书所称motor_all_bbox；边界基准、测站位置与SW零点待核。人口/DSM范围覆盖可复用但尚未完成新裁剪。南山OD、60点积水和R/SUMO结果保留历史，不移名到龙岗；当前phase配置仍属历史南山，不能作为龙岗运行入口。'
for name in ['AGENTS.md','README.md','DATA_SOURCES.md','MODEL_ASSUMPTIONS.md','PLAN.md','PROGRESS.md','EXPERIMENT_LOG.md','docs/USER_GUIDE.md','docs/deliverables/README.md']:
    p=ROOT/name;text=p.read_text(encoding='utf-8');first,rest=text.split('\n',1)
    marker='## 2026-11-18 龙岗研究区数据接收'
    if marker in rest:continue
    extra='\n\n'+marker+'\n\n'+common+'\n\n'+limits+'\n\n当前目标见configs/active_research.yaml；接收说明docs/LONGGANG_DATA_INTAKE.md，接收目录`'+RUN.relative_to(ROOT).as_posix()+'`。七项复制/格式/筛选一致性检查通过，不能替代拓扑或实测标定。Word/PPT同步增加范围说明，南山原始运行证据不改写。\n\n以下保留南山历史验收记录。\n'
    p.write_text(first+extra+rest,encoding='utf-8')
p=ROOT/'docs/FINAL_REPORT.md';text=p.read_text(encoding='utf-8')
if '## 研究区调整 龙岗含大鹏' not in text:
    first,rest=text.split('\n',1);p.write_text(first+'\n\n## 研究区调整 龙岗含大鹏\n\n'+common+'\n\n'+limits+'\n\n详见LONGGANG_DATA_INTAKE.md。以下南山数值为历史成果。\n'+rest,encoding='utf-8')
print('Recorded Longgang intake; shared document content now has',len(data['final']['sections']),'sections')
