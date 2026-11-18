"""Publish the visually inspected 61-section edition, preserving concurrent work."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from zipfile import ZipFile
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'.cache/document-sync-20261119-full-baseline'
target=ROOT/'docs/deliverables'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
guard=read(BUILD/'input-guard.json')
for n in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx']:
    assert sha(target/n)==guard[n], 'Concurrent formal deliverable change: '+n
for n,h in guard['other_deliverables'].items():assert sha(ROOT/n)==h,'Concurrent independent presentation change: '+n
comparison=read(BUILD/'render-comparison.json')
assert all(comparison[k]['pixel_identical']==list(range(2,57)) and comparison[k]['changed']==[1] for k in ['word','ppt'])
assert len(list((BUILD/'word-pages').glob('page-*.png')))==len(list((BUILD/'v2/slides').glob('slide-*.png')))==61
with ZipFile(BUILD/'before/开题与阶段进展汇报.pptx') as before,ZipFile(BUILD/'output/reviewed-v2.pptx') as after:
    parts=[n for n in before.namelist() if n.startswith('ppt/slides/charts/') or n.startswith('ppt/embeddings/')]
    assert len(parts)==42 and all(before.read(n)==after.read(n) for n in parts)

# A small immutable acceptance snapshot avoids depending on another chat's active drafts.
snapshot=ROOT/'docs/validation/document_sync_migration_5090'
snapshot.mkdir(exist_ok=True)
for p in (ROOT/'docs/validation/migration_5090').iterdir():
    if p.is_file():shutil.copy2(p,snapshot/p.name)
shutil.copy2(ROOT/'docs/PHASE_MIGRATION_5090_REPORT.md',snapshot/'phase_report.md')
shutil.copy2(ROOT/'migration/README_迁移与回传.md',snapshot/'source_readme.md')
data=read(target/'content.json')
data['migration_5090']['evidence']=snapshot.relative_to(ROOT).as_posix()
data['migration_5090']['evidence_sha256']={p.name:sha(p) for p in snapshot.iterdir() if p.is_file()}
save(target/'content.json',data)
shutil.copy2(BUILD/'candidate.docx',target/'研究方案与阶段进展.docx')
shutil.copy2(BUILD/'output/reviewed-v2.pptx',target/'开题与阶段进展汇报.pptx')
review={'all_pages_and_slides_visually_reviewed':True,'word_pages':61,'ppt_slides':61,
 'method':'All 61 final pages and slides rendered. Cover and new 57-61 individually inspected. Pages/slides 2-56 pixel-identical to the reviewed 56-section edition. All 42 original chart/relationship/workbook parts byte-preserved. Read-only Word COM PDF and bundled pypdfium2 PNG, final PPTX reimport and Artifact Tool PNG. No native PowerPoint playback claim.',
 'preserved_chart_workbook_parts':42,'individually_reviewed_changed_pages_and_slides':[1,57,58,59,60,61],
 'word_pdf':'.cache/document-sync-20261119-full-baseline/final-word.pdf',
 'ppt_receipt':'.cache/document-sync-20261119-full-baseline/v2/validation.json',
 'previous_review_sha256':sha(BUILD/'before/final_visual_review.json'),
 'render_comparison':'.cache/document-sync-20261119-full-baseline/render-comparison.json',
 'word_page_images':[{'page':i,'sha256':sha(BUILD/f'word-pages/page-{i}.png')} for i in range(1,62)],
 'ppt_slide_images':[{'slide':i,'sha256':sha(BUILD/f'v2/slides/slide-{i}.png')} for i in range(1,62)],
 'word_sha256':sha(target/'研究方案与阶段进展.docx'),'ppt_sha256':sha(target/'开题与阶段进展汇报.pptx')}
save(ROOT/'docs/validation/final_visual_review.json',review)
state=read(ROOT/'docs/validation/document_sync_state.json')
state.update({'updated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
 'current_document_pages':61,'current_presentation_slides':61,
 'last_check':'全龙岗5%无雨基准与本机迁移流程已同步61页/张，封面及57—61逐一查看，2—56像素一致。',
 'pending':'全区四个暴雨治理案例、目标Ubuntu环境与运行验收、全区3D回放未完成；关键道路计算与迁移模型扩展正在独立核验。无已收敛DUE、GPU训练或工程收益结论。',
 'document_sha256':review['word_sha256'],'presentation_sha256':review['ppt_sha256'],
 'qa_directory':'.cache/document-sync-20261119-full-baseline','last_source_commit':'7ca9b43',
 'source_latest_read_status':'Known research source histories retained; changed main, transfer, critical-road and independent PPT chats read through available messages. Full-district dry baseline accepted. Local migration fixture accepted, target Ubuntu pending. Critical-road rankings pending final independent acceptance.',
 'verification_passed':False})
state['source_wait_cursors']['01a1ee72-b914-7ee0-8576-1221bb77f825']='d3a0d2d9-718c-488f-8203-0da3b7d4e8b0:6'
state['other_deliverable_fingerprints']=[{'path':n,'sha256':h} for n,h in guard['other_deliverables'].items()]
state['other_deliverables_preserved']=list(guard['other_deliverables'])
state.setdefault('accepted_runs',[])
if '20261118T184221_full5_07cdb6f1' not in state['accepted_runs']:state['accepted_runs'].append('20261118T184221_full5_07cdb6f1')
save(ROOT/'docs/validation/document_sync_state.json',state)
print(json.dumps({'word_pages':61,'ppt_slides':61,'native_parts_byte_preserved':42,'migration_source_snapshot':str(snapshot)}))
