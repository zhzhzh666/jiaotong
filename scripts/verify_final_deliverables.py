"""Check final document provenance after actual page and slide visual review."""
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json
import csv
import math
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
pdf=PdfReader(ROOT/review.get('word_pdf','.cache/doc-sync/final-word.pdf'))
assert len(pdf.pages)==len(sections)==review['word_pages']
assert all(len(page.extract_text().strip())>100 for page in pdf.pages)
receipt=json.loads((ROOT/review.get('ppt_receipt','.cache/doc-sync/final-reviewed.pptx.validation.json')).read_text(encoding='utf-8'))
assert receipt['finalSha256']==sha256(pptpath.read_bytes()).hexdigest()
assert receipt['packageIntegrity']['status']=='pass' and receipt['presentationLayout']['exitCode']==0 and receipt['firstPartyImport']['passed']
with ZipFile(pptpath) as ppt,ZipFile(docpath) as word:
    slides=[n for n in ppt.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    assert len(slides)==len(sections)==review['ppt_slides']
    ppt_text=''.join(ppt.read(n).decode('utf-8') for n in ppt.namelist() if n.endswith('.xml') and (n.startswith('ppt/slides/') or n.startswith('ppt/notesSlides/')))
    for s in sections:assert s['title'] in doc_text and s['title'] in ppt_text,s['title']
    for ref in data['references']:assert ref['doi'] in doc_text and ref['doi'] in ppt_text
    # Notes carry complete precision and run IDs; visible slides summarize.
    for run_id in final['runs'].values():assert run_id in ppt_text
    images=[s['figure'] for s in sections if s.get('figure')]
    # New rainfall and demand figures use editable native charts in PowerPoint.
    ppt_images=[s['figure'] for s in sections if s.get('figure') and
                (not s['title'].startswith('补充情景 ') or s['title']=='补充情景 南山合成积水点')]
    for archive,prefix,expected in [(word,'word/media/',images),(ppt,'ppt/media/',ppt_images)]:
        embedded={sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n.startswith(prefix)}
        for name in expected:assert sha256((ROOT/name).read_bytes()).hexdigest() in embedded,name

    native_series_checked=0
    if data.get('synthetic_data_package'):
        assert receipt['nativeChartValidation']['passed']
        assert receipt['nativeQuantitativeCharts']['report']['passed']
        base=ROOT/data['synthetic_data_package']['path']
        def rows(name):
            with (base/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
        rain=rows('rainfall/areal_reference_rainfall_15min.csv')
        depth=rows('flood/point_depth_timeseries.csv')
        profile=rows('demand/departure_profile_15min.csv')
        ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
        scenarios=['general','severe','extreme']
        expected_charts=[
            [(list(k/4 for k in range(96)),[float(r['intensity_mm_h']) for r in rain if r['scenario']==s]) for s in scenarios],
            [(list(k/4 for k in range(97)),[max(float(r['depth_m']) for r in depth if r['scenario']==s and float(r['time_s'])==k*900) for k in range(97)]) for s in scenarios],
            [([float(r['start_hour']) for r in profile],[float(r['total_rate_veh_h']) for r in profile])]]
        for i,expected in enumerate(expected_charts,1):
            tree=ET.fromstring(ppt.read(f'ppt/slides/charts/chart{i}.xml'))
            series=tree.findall('.//c:scatterChart/c:ser',ns)
            assert len(series)==len(expected)
            for ser,(xvalues,yvalues) in zip(series,expected):
                for field,values in [('xVal',xvalues),('yVal',yvalues)]:
                    actual=[float(v.text) for v in ser.findall(f'c:{field}/c:numRef/c:numCache/c:pt/c:v',ns)]
                    assert len(actual)==len(values)
                    assert all(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10) for a,b in zip(actual,values)),(i,field)
                native_series_checked+=1

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
 'pptx_slides':len(slides),'docx_pages':len(pdf.pages),'embedded_source_images':{'word':len(images),'ppt':len(ppt_images)},'embedded_image_sha256_matches':True,
 'previous_core_tests_passed':int(suite.attrib['tests']),'core_tests_rerun_for_document_update':False,'shared_titles_and_doi_checked':True,
 'native_chart_source_series_checked':native_series_checked,
 'pptx_package_layout_fonts_and_reimport':'pass',
 'word_render':'Microsoft Word read-only COM ExportAsFixedFormat PDF then bundled pypdfium2 PNG; LibreOffice unavailable',
 'pptx_render':'Artifact Tool final file reimport, each slide exported to PNG',
 'native_powerpoint_playback_verified':False},
 'visual_review':record(ROOT/'docs/validation/final_visual_review.json')}
if data.get('synthetic_data_package'):
    manifest['synthetic_data_package']={'path':data['synthetic_data_package']['path'],
        'generation_checks_passed':data['synthetic_data_package']['report']['check_count'],
        'observed':False,'traffic_assignment_rerun':False}
(target/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
