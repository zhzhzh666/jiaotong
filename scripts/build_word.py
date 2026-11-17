"""Build the maintained Word report with the Codex bundled Python runtime."""
from pathlib import Path
import json
import argparse
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'docs/deliverables/content.json').read_text(encoding='utf-8'))
m=data['metrics']
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=ROOT/'docs/deliverables/研究方案与阶段进展.docx')
args=parser.parse_args()
d=Document()
s=d.sections[0]
s.page_width=Cm(21); s.page_height=Cm(29.7)
s.top_margin=Cm(1.9); s.bottom_margin=Cm(1.9)
s.left_margin=Cm(2.2); s.right_margin=Cm(2.2)
s.header_distance=Cm(.8); s.footer_distance=Cm(.8)
for name,size in [('Normal',10.5),('Title',22),('Subtitle',12),('Heading 1',17),('Heading 2',12),('Caption',9)]:
 st=d.styles[name]; st.font.name='Microsoft YaHei'; st.font.size=Pt(size); st.font.color.rgb=RGBColor(0,0,0)
 st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei')
 for key in ['asciiTheme','eastAsiaTheme','hAnsiTheme','cstheme']:
  st.element.get_or_add_rPr().rFonts.attrib.pop(qn('w:'+key),None)
 st.font.bold=name in ['Title','Heading 1','Heading 2']
 st.font.italic=False
 st.font.underline=False
 for border in list(st.element.xpath('./w:pPr/w:pBdr')):
  border.getparent().remove(border)
 for attr in list(st.element.get_or_add_rPr().rFonts.attrib):
  if 'Theme' in attr or 'theme' in attr: del st.element.get_or_add_rPr().rFonts.attrib[attr]
 st.font.italic=False
 st.font.bold=name in ('Title','Heading 1','Heading 2')
 props=st.element.find(qn('w:pPr'))
 if props is not None:
  for border in list(props.findall(qn('w:pBdr'))): props.remove(border)
 st.paragraph_format.space_after=Pt(7)
 st.paragraph_format.line_spacing=1.15
 if name.startswith('Heading'): st.paragraph_format.space_before=Pt(10)
header=s.header.paragraphs[0]; header.text='暴雨内涝交通韧性研究  阶段进展'; header.style=d.styles['Caption']
footer=s.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('2026-11-17  |  ')
field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); footer._p.append(field)

def p(t,style=None): return d.add_paragraph(t,style)
pending_page=False
def h(t):
 global pending_page
 heading=d.add_heading(t,1)
 if pending_page: heading.paragraph_format.page_break_before=True
 pending_page=False
def sub(t): d.add_heading(t,2)
def page():
 global pending_page
 pending_page=True
def table(headers,rows,widths):
 t=d.add_table(rows=1,cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
 for c,w in zip(t.columns,widths): c.width=Cm(w)
 for row,vals in [(t.rows[0],headers)]+[(t.add_row(),r) for r in rows]:
  for cell,text,w in zip(row.cells,vals,widths):
   cell.width=Cm(w); cell.text=str(text); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   tcPr=cell._tc.get_or_add_tcPr()
   borders=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    v=OxmlElement('w:'+edge); v.set(qn('w:val'),'single'); v.set(qn('w:sz'),'4'); v.set(qn('w:color'),'D9D9D9'); borders.append(v)
   tcPr.append(borders)
   mar=OxmlElement('w:tcMar')
   for edge in ['top','left','bottom','right']:
    v=OxmlElement('w:'+edge); v.set(qn('w:w'),'95'); v.set(qn('w:type'),'dxa'); mar.append(v)
   tcPr.append(mar)
   for para in cell.paragraphs:
    para.paragraph_format.space_after=Pt(3); para.paragraph_format.line_spacing=1.1
    for r in para.runs: r.font.size=Pt(10)
 for cell in t.rows[0].cells:
  sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'E7EDF2'); cell._tc.get_or_add_tcPr().append(sh)
  for run in cell.paragraphs[0].runs: run.bold=True
 repeat=OxmlElement('w:tblHeader'); t.rows[0]._tr.get_or_add_trPr().append(repeat)
 gap=p(''); gap.paragraph_format.space_after=Pt(2); gap.paragraph_format.line_spacing=Pt(4)
 return t

d.add_paragraph('暴雨内涝情景下城市交通网络\n韧性评估与优化研究',style='Title')
p('研究方案与阶段进展  2026年11月17日',style='Subtitle')
p('本报告面向课题讨论与后续开发，整合原始研究构想、本地五篇参考论文和项目验收记录。当前结论是 Phase 00 基础设施通过验收，真实路网、交通分配、韧性评价与治理优化尚未实施。本报告中的模型和实验安排均标明为拟实施内容。')
h('研究问题与范围')
p('暴雨积水会使道路降速或中断，交通需求随之绕行，并可能放大拥堵与公共服务可达性损失。本研究拟回答：在有限预算和治理道路数量约束下，优先改善哪些道路，能够提高整个交通网络在灾害过程中的综合性能。')
p('研究区域从深圳市南山区的小型真实路网开始，完成方向、长度、属性和连通性校验后再扩大范围。交通分配先用 Sioux Falls 标准网络验证，再接入深圳路网；SUMO 用于后续车辆运行过程补充分析。')
table(['工作范围','截至本次更新的状态'],[
 ['环境与可复现基础设施','Phase 00 已验收'],['本地参考论文','5篇全文已核查，关键公式页已对照'],['真实路网与外部数据','未获取；Phase 01、02 待实施'],['交通模型与治理实验','未实施；暂无韧性提升数值'],['运行图片','已保存环境验收 PNG 和 SVG，可追溯查询']],[5,11.6])
p('根目录原始 PPT、Word 和 PDF 保留不变。本文件与配套汇报为持续维护版本，后续按每阶段实际验收结果同步更新。',style='Caption')

page(); h('技术路线与模型设计')
p('以下内容为拟实施方案，不代表已完成的仿真结果。完整阶段门禁与参数以 PLAN.md、MODEL_ASSUMPTIONS.md 和配置文件为准。')
sub('真实道路与需求')
p('OSM 路网保留有向 MultiDiGraph、平行边和稳定 edge_id。原始坐标使用 WGS84，距离与长度计算使用 EPSG:32650。OD 拟以交通分区、人口与设施估计产生吸引量，采用重力模型和 IPF 平衡；估计与合成输入明确标识，不冒充实测出行。')
sub('参数化内涝与道路退化')
p('默认24小时、15分钟步长，共97个端点和96个区间。积水模型拟刻画增长、峰值、延迟与消退，属于参数化情景。道路速度参考 Pregnolato 等[1]的已核实公式，容量退化另按项目简化模型实现。30 cm 中断阈值是可调实验假设，不构成涉水安全建议。')
p('文献原式：v = 0.0009 w² − 0.5529 w + 86.9448，其中 w 为 mm、v 为 km/h。实现时需显式换算，零积水返回道路正常速度，受灾速度受正常上限约束，达到中断阈值后从可通行图移除。',style='Caption')
sub('交通分配与韧性')
p('拟使用 BPR 与 Frank–Wolfe 求各时间片用户均衡，记录 Relative Gap 和守恒误差。该方法是时间片静态分配；SUMO 阶段才补充车辆排队、滞留及重规划过程。不可达 OD 需保留并计入未满足需求成本。')
p('拟以结构、性能、功能三个维度构成 Q(t)，默认权重0.2、0.5、0.3，并以灾害窗口平均性能面积定义 R，越大越好。正常与灾害比较使用相同 OD 和时间片；医院等设施拟考察15/30分钟可达覆盖。权重、阈值与未满足需求惩罚都需敏感性检验。')
sub('治理优化与公平比较')
p('在预算与道路数量 K 约束下，对比不治理、随机、积水深度、流量、中心性优先与单位成本韧性增益贪心。每次治理后重新分配并重算增益；先在小网用穷举核验。正式实验拟至少使用10个种子，记录均值、离散性与运行时间。')

page(); h('本地论文核查与采用边界')
p('五篇论文均已在本地读取，当前不需要重复下载。四篇英文文献的书目通过 Crossref 核实；中文论文以本地全文首页为依据，在线 Crossref 404、期刊 HTTP 500 已记录，不影响全文可读。')
for i,r in enumerate(data['references'],1):
 sub(f'{i} {r["label"]}')
 p(r['note'])
 p(r['pages']+'。DOI '+r['doi'],style='Caption')
p('需特别区分：Ma 等的 R_loss 是性能损失面积，越小越好；本项目 R 是平均性能，越大越好。He 等的 Capacity 不能作为道路 veh/h 容量。Hong 等的15 cm阈值及8分钟医疗指标与本项目默认值不同，且回归式常数符号在公式与表格间不一致，不能直接迁移到深圳。')
p('论文中使用的部门数据不自动成为本项目输入。当前没有作者的5 m DEM、183个历史积水点或完整实验代码；不能从地图图像构造数据后标为官方原始记录。完整公式、单位与采用边界见 docs/LITERATURE_REVIEW.md。')

page(); h('Phase 00 实际验收结果')
p('本阶段完成独立仓库与 Python 环境、依赖锁定、配置校验、运行归档、图片指纹、历史索引及命令行查询。环境检查不等同于交通仿真验收。')
table(['项目','已记录的实际结果'],[
 ['Python',m['python']+' 独立 Conda 环境'],['依赖导入',f'{m["imports_passed"]}/{m["imports_total"]} 成功'],['自动检查',f'{m["tests_passed"]} 项通过，0失败，{m["warnings"]}条未来弃用警告'],['依赖一致性','pip check 无冲突'],['最终复核运行',f'{m["runtime_seconds"]}秒，success'],['来源代码','0e0b562；运行时 dirty=false']],[4.2,12.4])
d.add_picture(str(ROOT/data['figure']),width=Cm(16.4))
p('图1 实际环境快照与依赖导入检查  源记录时间为2026-11-17 17:35:15 +08:00。左图为当次内存与磁盘用量，右图为20项依赖导入结果。',style='Caption')
p('run_id  '+data['run_id'],style='Caption')
p('证据：docs/validation/environment.json、pytest-final.txt、pip-check.txt、accepted-run-manifest.json 和 run_audit.json。原始图片 PNG/SVG 及源 JSON 保留在该 run_id 的运行目录；本报告引用版本化验收副本。',style='Caption')
p('归档审计确认本次2个图片与6个输入指纹一致；两次运行共4条图像格式记录和14个索引链接存在。图片均来自实际环境数据，当前尚无路网地图、交通韧性曲线或治理收益图。')

page(); h('后续实施安排与图片查询')
table(['阶段','拟实施内容','状态'],[
 ['01—03','真实路网、灾害与人口设施数据、OD 构建','未开始'],['04—07','内涝、道路退化、分配及韧性评价','未开始'],['08—09','关键道路识别、治理策略及预算优化','未开始'],['10—11','SUMO 补充验证与对比实验','未开始'],['12—13','中文交互界面、完整审计与交付','未开始']],[2.2,11.2,3.2])
sub('下一步验收')
p('下一阶段为 Phase 01：准备南山区边界和小测试区域，获取公开 OSM/Overpass 路网与 TransportationNetworks 的 Sioux Falls 标准文件。输出 GraphML、GeoJSON、CSV、统计与路网图；检查稳定边 ID、方向、长度、平行边与实际可达最短路，不补造道路。')
sub('当前限制')
p('真实路网、积水、降雨、DEM、人口、POI 和 OD 尚未获取。SUMO、sumo-gui、netconvert 未在 PATH 发现；sumolib/traci 导入成功不代表可执行仿真已就绪。测试有1条 rasterio/affine 未来弃用警告，GIS 读写已通过。')
sub('历史图片留存')
p('每次运行生成独立 run_id，保存 raw、figures、screenshots、logs、配置快照与 manifest；保留失败记录，不覆盖历史。后续重点保存正常、首次中断、受影响边最多、最低 Q、恢复或结束时刻的图像，重复时刻合并，原始时序完整保留。')
p('本地打开 results/index.html，按阶段、日期、区域、情景、策略筛选；或使用命令行 history 按 run_id 精确查询。索引可由 manifest 重建，manifest 为运行来源权威记录。')
sub('每阶段文档同步')
p('阶段验收后同时更新本 Word 和汇报 PPT 的状态、方法、实际数值、图片来源、限制与下一步；生成后检查每页和每张幻灯片，并保存 Git 提交。源论文、环境及大型运行目录留本地；小型验收图与维护文档纳入版本管理。')

page(); h('参考文献与复现入口')
for i,r in enumerate(data['references'],1):
 p(f'[{i}] '+r['citation'])
 p('https://doi.org/'+r['doi'],style='Caption')
sub('复现与核查')
p('工作目录为 jiaotong。项目运行使用 .conda-env/python.exe；文档维护脚本使用 Codex 提供的文档运行时，避免修改项目科学计算依赖。')
for cmd in ['.conda-env\\python.exe -m pytest','.conda-env\\python.exe -m pip check','.conda-env\\python.exe -m uftr.cli run --phase 00','.conda-env\\python.exe -m uftr.cli history --phase 00','.conda-env\\python.exe -m uftr.cli reindex']:
 pp=p(cmd); pp.paragraph_format.space_after=Pt(3)
 for run in pp.runs: run.font.name='Consolas'; run.font.size=Pt(9)
p('完整任务书见 docs/TASK_SPEC.md，实施验收见 docs/PHASE00_REPORT.md。PPT 与 Word 共用 docs/deliverables/content.json 中的日期、状态、验收数值、运行ID、图片路径与书目。',style='Caption')
args.output.parent.mkdir(parents=True,exist_ok=True)
d.save(args.output)
print(args.output)
