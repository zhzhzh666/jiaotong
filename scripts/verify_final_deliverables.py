"""Check final document provenance after actual page and slide visual review."""
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json
import xml.etree.ElementTree as ET
from docx import Document
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'docs/deliverables'
data=json.loads((target/'content.json').read_text(encoding='utf-8'))
final=data['final'];sections=final['sections']
suite=ET.parse(ROOT/'docs/validation/current-tests.xml').getroot().find('testsuite')
assert int(suite.attrib['tests'])==final['tests_passed'] and int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
review=json.loads((ROOT/'docs/validation/final_visual_review.json').read_text(encoding='utf-8'))
assert review['all_pages_and_slides_visually_reviewed']
docpath=target/'研究方案与阶段进展.docx';pptpath=target/'开题与阶段进展汇报.pptx'
doc=Document(docpath);doc_text='\n'.join(p.text for p in doc.paragraphs)
pdf=PdfReader(ROOT/'.cache/doc-sync/final-word.pdf')
assert len(pdf.pages)==len(sections)==19
assert all(len(page.extract_text().strip())>100 for page in pdf.pages)
receipt=json.loads((ROOT/'.cache/doc-sync/final-reviewed.pptx.validation.json').read_text(encoding='utf-8'))
assert receipt['finalSha256']==sha256(pptpath.read_bytes()).hexdigest()
assert receipt['packageIntegrity']['status']=='pass' and receipt['presentationLayout']['exitCode']==0 and receipt['firstPartyImport']['passed']
with ZipFile(pptpath) as ppt,ZipFile(docpath) as word:
    slides=[n for n in ppt.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    assert len(slides)==19
    ppt_text=''.join(ppt.read(n).decode('utf-8') for n in ppt.namelist() if n.endswith('.xml') and (n.startswith('ppt/slides/') or n.startswith('ppt/notesSlides/')))
    for s in sections:assert s['title'] in doc_text and s['title'] in ppt_text,s['title']
    for ref in data['references']:assert ref['doi'] in doc_text and ref['doi'] in ppt_text
    # Notes carry complete precision and run IDs; visible slides summarize.
    for run_id in final['runs'].values():assert run_id in ppt_text
    images=[s['figure'] for s in sections if s.get('figure')]
    for archive,prefix in [(word,'word/media/'),(ppt,'ppt/media/')]:
        embedded={sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n.startswith(prefix)}
        for name in images:assert sha256((ROOT/name).read_bytes()).hexdigest() in embedded,name

def record(path):
    b=path.read_bytes()
    return {'path':path.relative_to(ROOT).as_posix(),'bytes':len(b),'sha256':sha256(b).hexdigest()}

old=json.loads((target/'delivery_manifest.json').read_text(encoding='utf-8'))
for original in old['originals_preserved']:assert record(ROOT/original['path'])==original
assert review['word_sha256']==record(docpath)['sha256'] and review['ppt_sha256']==record(pptpath)['sha256']
manifest={'updated':data['updated'],'phase_status':data['status'],'accepted_runs':final['runs'],
 'deliverables':[record(pptpath),record(docpath)],'content_source':record(target/'content.json'),
 'originals_preserved':old['originals_preserved'],
 'verification':{'final_content_checked':True,'all_pages_and_slides_visually_reviewed':True,
 'pptx_slides':19,'docx_pages':19,'embedded_source_images':len(images),'embedded_image_sha256_matches':True,
 'tests_passed':int(suite.attrib['tests']),'shared_titles_and_doi_checked':True,
 'pptx_package_layout_fonts_and_reimport':'pass',
 'word_render':'Microsoft Word read-only COM ExportAsFixedFormat PDF then bundled pypdfium2 PNG; LibreOffice unavailable',
 'pptx_render':'Artifact Tool final file reimport, each slide exported to PNG',
 'native_powerpoint_playback_verified':False},
 'visual_review':record(ROOT/'docs/validation/final_visual_review.json')}
(target/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
