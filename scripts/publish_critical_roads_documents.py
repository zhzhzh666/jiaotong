"""Publish the visually reviewed 65-section road-screening edition."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from zipfile import ZipFile
import json,shutil
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'.cache/document-sync-20261119-critical-roads';target=ROOT/'docs/deliverables'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
guard=read(BUILD/'input-guard.json')
for n in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx']:assert sha(target/n)==guard[n],'Concurrent formal document change: '+n
comparison=read(BUILD/'render-comparison.json')
assert all(comparison[k]['pixel_identical']==list(range(2,62)) and comparison[k]['changed']==[1] for k in ['word','ppt'])
assert len(list((BUILD/'word-pages').glob('page-*.png')))==len(list((BUILD/'v1/slides').glob('slide-*.png')))==65
with ZipFile(BUILD/'before/开题与阶段进展汇报.pptx') as before,ZipFile(BUILD/'output/reviewed-v1.pptx') as after:
    parts=[n for n in before.namelist() if n.startswith('ppt/slides/charts/') or n.startswith('ppt/embeddings/')]
    assert len(parts)==42 and all(before.read(n)==after.read(n) for n in parts)
shutil.copy2(BUILD/'candidate.docx',target/'研究方案与阶段进展.docx')
shutil.copy2(BUILD/'output/reviewed-v1.pptx',target/'开题与阶段进展汇报.pptx')
review={'all_pages_and_slides_visually_reviewed':True,'word_pages':65,'ppt_slides':65,
 'method':'All 65 pages and slides rendered. Cover and 62-65 inspected individually. Pages/slides 2-61 pixel-identical to reviewed 61-section edition. All 42 native chart/relationship/workbook parts byte-preserved. Read-only Word COM PDF and bundled pypdfium2 PNG; final PPTX reimport and Artifact Tool PNG. Native PowerPoint playback not checked.',
 'preserved_chart_workbook_parts':42,'individually_reviewed_changed_pages_and_slides':[1,62,63,64,65],
 'word_pdf':'.cache/document-sync-20261119-critical-roads/final-word.pdf','ppt_receipt':'.cache/document-sync-20261119-critical-roads/v1/validation.json',
 'previous_review_sha256':sha(BUILD/'before/final_visual_review.json'),'render_comparison':'.cache/document-sync-20261119-critical-roads/render-comparison.json',
 'word_page_images':[{'page':i,'sha256':sha(BUILD/f'word-pages/page-{i}.png')} for i in range(1,66)],
 'ppt_slide_images':[{'slide':i,'sha256':sha(BUILD/f'v1/slides/slide-{i}.png')} for i in range(1,66)],
 'word_sha256':sha(target/'研究方案与阶段进展.docx'),'ppt_sha256':sha(target/'开题与阶段进展汇报.pptx')}
save(ROOT/'docs/validation/final_visual_review.json',review)
state=read(ROOT/'docs/validation/document_sync_state.json')
state.update({'updated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'current_document_pages':65,'current_presentation_slides':65,
 'last_check':'12候选静态全OD关键道路、四点预算策略和RTX4090五场景迁移包验收已同步65页/张；封面及62—65逐一查看，2—61像素一致。',
 'pending':'按用户PPT结构/性能/功能权重与24小时R的扩展包仍准备中；OSM设施69医院31消防完整性、运营与连接未实地核实。目标Ubuntu实测、全区四个暴雨治理案例与全区3D回放待完成，无已收敛DUE。独立专题PPT正在套用交通模板。',
 'document_sha256':review['word_sha256'],'presentation_sha256':review['ppt_sha256'],
 'qa_directory':'.cache/document-sync-20261119-critical-roads','last_source_commit':'b3761b7 (critical-road source snapshot not yet committed by its owner)',
 'source_latest_read_status':'All known research history retained; actual changed messages from road-criticality, migration, independent PPT and main source read. Static road screening accepted; RTX4090 five-case archive accepted locally. PPT-R extension in progress; Ubuntu performance untested.',
 'verification_passed':False})
state.setdefault('accepted_runs',[])
if '20261118T191957_critical_b29cd51f' not in state['accepted_runs']:state['accepted_runs'].append('20261118T191957_critical_b29cd51f')
others={p.relative_to(ROOT).as_posix():sha(p) for p in target.glob('*.pptx') if p.name!='开题与阶段进展汇报.pptx'}
state['other_deliverable_fingerprints']=[{'path':n,'sha256':h} for n,h in others.items()]
state['other_deliverables_preserved']=list(others)
state['independent_presentation_changes_during_sync']=[n for n,h in guard['other_deliverables'].items() if others.get(n)!=h]
save(ROOT/'docs/validation/document_sync_state.json',state)
print(json.dumps({'pages_and_slides':65,'preserved_chart_parts':42,'other_presentations':len(others)}))
