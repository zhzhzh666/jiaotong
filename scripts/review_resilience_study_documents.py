"""Render Word and compare all retained pages/slides to the reviewed edition."""
from pathlib import Path
from PIL import Image,ImageChops
import pypdfium2 as pdfium
import json
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'.cache/document-sync-20261119-resilience-study'
OLD=ROOT/'.cache/document-sync-20261119-critical-roads'
out=B/'word-pages';out.mkdir(exist_ok=True)
pdf=pdfium.PdfDocument(B/'final-word.pdf');assert len(pdf)==69
for i in range(len(pdf)):
    pdf[i].render(scale=1.4).to_pil().save(out/f'page-{i+1}.png')
report={}
for label,old,new,prefix in [('word',OLD/'word-pages',out,'page'),('ppt',OLD/'v1/slides',B/'v1/slides','slide')]:
    identical=[];changed=[]
    assert len(list(new.glob(f'{prefix}-*.png')))==69
    for i in range(1,66):
        with Image.open(old/f'{prefix}-{i}.png') as a,Image.open(new/f'{prefix}-{i}.png') as b:
            equal=a.size==b.size and ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None
        (identical if equal else changed).append(i)
    report[label]={'pixel_identical':identical,'changed':changed,'new':[66,67,68,69]}
(B/'render-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
