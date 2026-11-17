"""Verify maintained artifact evidence using the Codex bundled Python runtime.

Run after visually reviewing every final slide and Word PDF page. This check
verifies provenance and embedded bytes; it does not replace visual inspection.
"""
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json
import xml.etree.ElementTree as E
from docx import Document
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'docs/deliverables'
data = json.loads((target / 'content.json').read_text(encoding='utf-8'))
a = data['phase01']
accepted = json.loads((ROOT / a['evidence']).read_text(encoding='utf-8'))
assert a['run_id'] == accepted['run_id']
suite = E.parse(ROOT / 'docs/validation/phase01/pytest-accepted.xml').getroot().find('testsuite')
assert int(suite.attrib['tests']) == a['tests_passed']
assert int(suite.attrib['failures']) == int(suite.attrib['errors']) == 0
doc = Document(target / '研究方案与阶段进展.docx')
doc_text = '\n'.join(p.text for p in doc.paragraphs) + '\n' + '\n'.join(
    c.text for t in doc.tables for r in t.rows for c in r.cells)
assert not doc.styles['Title'].element.xpath('./w:pPr/w:pBdr')
assert len(PdfReader(ROOT / '.cache/doc-sync/phase01-word.pdf').pages) == 9
expected_images = [data['figure'], *a['figures'].values()]
with ZipFile(target / '开题与阶段进展汇报.pptx') as ppt, ZipFile(target / '研究方案与阶段进展.docx') as word:
    slides = [n for n in ppt.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    assert len(slides) == 13
    ppt_text = ''.join(ppt.read(n).decode('utf-8') for n in ppt.namelist()
                       if (n.startswith('ppt/slides/') or n.startswith('ppt/notesSlides/')) and n.endswith('.xml'))
    for value in [data['run_id'], a['run_id'], str(data['metrics']['runtime_seconds']),
                  str(a['runtime_seconds']), str(a['tests_passed'])]:
        assert value in doc_text and value in ppt_text, value
    for ref in data['references']:
        assert ref['doi'] in doc_text and ref['doi'] in ppt_text
    for z, prefix in [(ppt, 'ppt/media/'), (word, 'word/media/')]:
        hashes = {sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith(prefix)}
        for name in expected_images:
            assert sha256((ROOT / name).read_bytes()).hexdigest() in hashes, name

def record(path):
    b = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(b), 'sha256': sha256(b).hexdigest()}

# Compare originals against the previously recorded immutable fingerprints.
old = json.loads((target / 'delivery_manifest.json').read_text(encoding='utf-8'))
for original in old['originals_preserved']:
    assert record(ROOT / original['path']) == original
validation = ROOT / 'docs/validation/phase01'
inventory = {
    'run_id': a['run_id'], 'source_commit': a['source_commit'],
    'visual_review': 'Both final road PNGs individually inspected; no clipping or text overlap',
    'files': [record(p) for p in sorted(validation.iterdir()) if p.is_file() and p.name != 'acceptance_inventory.json']
}
(validation / 'acceptance_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
manifest = {
    'updated': data['updated'], 'phase_status': data['status'], 'run_id': a['run_id'],
    'phase00_run_id': data['run_id'],
    'deliverables': [record(target / n) for n in ['开题与阶段进展汇报.pptx', '研究方案与阶段进展.docx']],
    'content_source': record(target / 'content.json'), 'originals_preserved': old['originals_preserved'],
    'evidence': [record(ROOT / p) for p in [*expected_images, a['evidence'],
                 'docs/validation/phase01/pytest-accepted.xml', 'docs/validation/phase01/acceptance_inventory.json']],
    'verification': {
        'pptx_slides': 13, 'docx_pages': 9, 'embedded_image_sha256_matches': True,
        'shared_metrics_and_doi_checked': True, 'pptx_package_layout_fonts_and_reimport': 'pass',
        'pptx_render': 'Artifact Tool final reimport PNG; all 13 slides individually inspected',
        'word_render': 'render_docx.py unavailable due to missing LibreOffice; Microsoft Word COM ExportAsFixedFormat PDF then bundled pypdfium2 PNG; all 9 final pages individually inspected',
        'qa_directory': '.cache/doc-sync/',
        'limitations': 'Native PowerPoint application not inspected; Word preview inspected as PDF page images.'
    },
    'github_upload_status': 'Pending authentication and remote configuration; not uploaded'
}
(target / 'delivery_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('PASS: 13 slides, 9 pages; shared evidence, original fingerprints and all 3 embedded PNG hashes agree.')
