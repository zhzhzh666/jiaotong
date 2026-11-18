"""Build the current research report from shared, result-derived content."""
from pathlib import Path
import json
import argparse
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'docs/deliverables/研究方案与阶段进展.docx');args=p.parse_args()
data=json.loads((ROOT/'docs/deliverables/content.json').read_text(encoding='utf-8'));sections=data['final']['sections']
d=Document();page=d.sections[0];page.page_width=Cm(21);page.page_height=Cm(29.7);page.top_margin=Cm(1.9);page.bottom_margin=Cm(1.8);page.left_margin=Cm(2.2);page.right_margin=Cm(2.2)
for name,size in [('Normal',10.5),('Title',22),('Heading 1',17),('Caption',9)]:
    s=d.styles[name];s.font.name='Microsoft YaHei';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0);s.font.bold=name in ['Title','Heading 1'];s.font.italic=False
    s.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei');s.paragraph_format.space_after=Pt(8);s.paragraph_format.line_spacing=1.18
    for key in ['asciiTheme','eastAsiaTheme','hAnsiTheme','cstheme']:s.element.get_or_add_rPr().rFonts.attrib.pop(qn('w:'+key),None)
    for border in list(s.element.xpath('./w:pPr/w:pBdr')):border.getparent().remove(border)
footer=page.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('2026-11-18 | ');field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
for i,s in enumerate(sections):
    title=d.add_paragraph(s['title'],'Title' if i==0 else 'Heading 1')
    if i:title.paragraph_format.page_break_before=True
    if i==0:d.add_paragraph('研究报告与阶段进展 · 真实深圳路网研究原型','Caption')
    for text in s['paragraphs']:d.add_paragraph(text)
    if s.get('figure'):
        image=ROOT/s['figure'];d.add_picture(str(image),width=Cm(16.3))
        caption=d.add_paragraph(s['caption'],'Caption');caption.paragraph_format.keep_with_next=False
        source_name=('合成数据包 '+Path(s['figure']).parts[3]+' / figures/'+image.name) if s['title'].startswith('补充情景 ') else s['figure']
        source=d.add_paragraph('来源：'+source_name,'Caption');source.paragraph_format.space_after=Pt(4)
    if i==0:
        d.add_paragraph('验收范围','Heading 1')
        for text in ['南山：全路网分配、24h全过程韧性、2000计划车辆SUMO抽样。','小型真实区域：六路组治理、穷举核验、十种子与独立测试。','完整数据和图片留本机；源码、配置、维护文档及验收副本上传GitHub。']:
            d.add_paragraph(text)
d.core_properties.title=data['title'];d.core_properties.subject='深圳城市暴雨内涝交通韧性研究原型与实际实验';d.core_properties.author=''
args.output.parent.mkdir(exist_ok=True,parents=True);d.save(args.output);print(args.output)
