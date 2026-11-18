"""Publish the visually reviewed 69-section PPT-model study edition."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from zipfile import ZipFile
import json,shutil
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'.cache/document-sync-20261119-resilience-study';target=ROOT/'docs/deliverables'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
guard=read(B/'input-guard.json')
for n in ['研究方案与阶段进展.docx','开题与阶段进展汇报.pptx']:assert sha(target/n)==guard[n],'Concurrent formal document change: '+n
comparison=read(B/'render-comparison.json')
assert all(comparison[k]['pixel_identical']==list(range(2,66)) and comparison[k]['changed']==[1] for k in ['word','ppt'])
assert len(list((B/'word-pages').glob('page-*.png')))==len(list((B/'v1/slides').glob('slide-*.png')))==69
with ZipFile(B/'before/开题与阶段进展汇报.pptx') as before,ZipFile(B/'output/reviewed-v1.pptx') as after:
    parts=[n for n in before.namelist() if n.startswith('ppt/slides/charts/') or n.startswith('ppt/embeddings/')]
    assert len(parts)==42 and all(before.read(n)==after.read(n) for n in parts)
shutil.copy2(B/'candidate.docx',target/'研究方案与阶段进展.docx')
shutil.copy2(B/'output/reviewed-v1.pptx',target/'开题与阶段进展汇报.pptx')
review={'all_pages_and_slides_visually_reviewed':True,'word_pages':69,'ppt_slides':69,
 'method':'All 69 pages/slides rendered. Cover and 66-69 inspected individually. Pages/slides 2-65 pixel-identical to reviewed 65-section edition. All 42 chart/relationship/workbook parts byte-preserved. Read-only Word COM PDF then bundled pypdfium2 PNG; final PPTX reimport and Artifact Tool PNG. Native PowerPoint playback not checked.',
 'preserved_chart_workbook_parts':42,'individually_reviewed_changed_pages_and_slides':[1,66,67,68,69],
 'word_pdf':'.cache/document-sync-20261119-resilience-study/final-word.pdf',
 'ppt_receipt':'.cache/document-sync-20261119-resilience-study/v1/validation.json',
 'previous_review_sha256':sha(B/'before/final_visual_review.json'),
 'render_comparison':'.cache/document-sync-20261119-resilience-study/render-comparison.json',
 'word_page_images':[{'page':i,'sha256':sha(B/f'word-pages/page-{i}.png')} for i in range(1,70)],
 'ppt_slide_images':[{'slide':i,'sha256':sha(B/f'v1/slides/slide-{i}.png')} for i in range(1,70)],
 'word_sha256':sha(target/'研究方案与阶段进展.docx'),'ppt_sha256':sha(target/'开题与阶段进展汇报.pptx')}
save(ROOT/'docs/validation/final_visual_review.json',review)
state=read(ROOT/'docs/validation/document_sync_state.json')
state.update({'updated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'current_document_pages':69,'current_presentation_slides':69,
 'last_check':'PPT综合韧性Q/R、设施覆盖、12候选ΔR及四点15组合流程和4090专用研究包本机验收已同步69页/张。封面及66—69逐一查看，2—65像素一致。',
 'pending':'真实龙岗仅preflight，正式R道路排名与治理收益、目标Ubuntu安装性能及全区3D待完成。主开发四组SUMO固定/动态/治理串联流程尚在验收；独立30页专题PPT保留，不覆盖。设施完整性、运营与真实入口未实地核实。',
 'document_sha256':review['word_sha256'],'presentation_sha256':review['ppt_sha256'],
 'qa_directory':'.cache/document-sync-20261119-resilience-study','last_source_commit':'40b4959',
 'source_latest_read_status':'Changed actual messages read: PPT-model study package accepted locally; 199 frozen-package tests and synthetic 24h roundtrip. Real Longgang preflight only. Main four-stage SUMO integration remains in progress; independent 30-slide deck preserved.',
 'verification_passed':False,'latest_method_document_read':'docs/PHASE_MIGRATION_4090_STUDY_REPORT.md',
 'source_latest_completed_turn':'01a1f039-d385-7d43-92e3-66bab5ad993c',
 'source_active_turns_pending':['01a1f045-e692-72a2-8eae-f74431215514']})
state['source_latest_read_turns']=list(dict.fromkeys(state.get('source_latest_read_turns',[])+[
 '01a1f039-d385-7d43-92e3-66bab5ad993c','01a1f047-d252-7d70-8a68-e187ac577035','01a1f045-e692-72a2-8eae-f74431215514']))
state['accepted_delivery_packages']=list(dict.fromkeys(state.get('accepted_delivery_packages',[])+[
 'results/exports/migration_4090_study_20261119/jiaotong_ubuntu4090_keyroads_governance_20261119.tar.gz']))
others={p.relative_to(ROOT).as_posix():sha(p) for p in target.glob('*.pptx') if p.name!='开题与阶段进展汇报.pptx'}
state['other_deliverable_fingerprints']=[{'path':n,'sha256':h} for n,h in others.items()]
state['other_deliverables_preserved']=list(others)
state['independent_presentation_changes_during_sync']=[n for n,h in guard['other_deliverables'].items() if others.get(n)!=h]
state['verification_summary']={'critical_snapshot_sha_files_checked':14,'migration4090_snapshot_sha_files_checked':9,
 'resilience_study_snapshot_sha_files_checked':len(read(ROOT/'docs/validation/document_sync_resilience_study/snapshot_index.json')['files']),
 'source_images_word':46,'source_images_ppt':38,'native_charts':14,'native_series':45,'preserved_parts':42,'latest_source_tests':199}
save(ROOT/'docs/validation/document_sync_state.json',state)
print(json.dumps({'pages_and_slides':69,'preserved_chart_parts':42,'independent_presentations':len(others)}))
