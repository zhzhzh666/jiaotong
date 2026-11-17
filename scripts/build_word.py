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
a=data['phase01']
b=data['phase02']
c=data['phase03']
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
p('本报告面向课题讨论与后续开发，整合原始研究构想、本地五篇参考论文和项目验收记录。Phase 00—03已完成基础设施、真实路网、空间数据处理与合成OD构建，南山研究窗口有20,447节点、40,105条有向边。本阶段接入用户从深圳市政府数据开放平台抓取的45站水位记录，地址经高德地理编码；SW零点仍待核实。Phase 02的合成风险点作为历史阶段证据保留。交通分配、韧性评价与治理优化尚未实施，后续模型明确标为规划。')
h('研究问题与范围')
p('暴雨积水会使道路降速或中断，交通需求随之绕行，并可能放大拥堵与公共服务可达性损失。本研究拟回答：在有限预算和治理道路数量约束下，优先改善哪些道路，能够提高整个交通网络在灾害过程中的综合性能。')
p('研究区域从深圳市南山区的小型真实路网开始，完成方向、长度、属性和连通性校验后再扩大范围。交通分配先用 Sioux Falls 标准网络验证，再接入深圳路网；SUMO 用于后续车辆运行过程补充分析。')
table(['工作范围','截至本次更新的状态'],[
 ['环境与可复现基础设施','Phase 00 已验收'],['本地参考论文','5篇全文已核查，关键公式页已对照'],['真实路网与外部数据','已获地形、人口、区域雨量与OSM设施；新增45站水位，零点待核实'],['交通模型与治理实验','合成OD已实现；暂无韧性提升数值'],['运行图片','环境、路网、空间数据及OD处理图均已归档，可追溯查询']],[5,11.6])
p('根目录原始 PPT、Word 和 PDF 保留不变。本文件与配套汇报为持续维护版本，后续按每阶段实际验收结果同步更新。',style='Caption')

page(); h('技术路线与模型设计')
p('道路与合成需求已实施，内涝、分配及治理为拟实施方案。完整阶段门禁与参数以 PLAN.md、MODEL_ASSUMPTIONS.md 和配置文件为准。')
sub('真实道路与需求')
p('OSM 路网保留有向 MultiDiGraph、平行边和稳定 edge_id。原始坐标使用 WGS84，距离与长度计算使用 EPSG:32650。OD 已以交通分区、人口与设施估计产生吸引量，采用重力模型和 IPF 平衡；估计与合成输入明确标识，不冒充实测出行。')
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
p('归档审计确认本次2个图片与6个输入指纹一致；两次运行共4条图像格式记录和14个索引链接存在。以上为Phase 00历史环境证据；本次新增实际路网地图见后文，暂无交通韧性曲线或治理收益图。')


page(); h('Phase 01 实际路网与基准数据')
p('已完成真实OSM道路获取、拓扑处理、方向属性和长度核查，输出GraphML、GeoJSON、CSV、统计、边界及路网图。全部断连分量保留，未补造道路；南山6对平行有向边保留。')
table(['指标','小区域','南山研究窗口'],[
 ['节点',a['small']['nodes'],a['nanshan']['nodes']],['有向边',a['small']['directed_edges'],a['nanshan']['directed_edges']],['弱连通分量',3,33],['强连通分量',62,419],['类型估计速度边',2231,39081],['容量估计边',2247,40105],['20起点可达对核查',19530,362300]],[6.6,5,5])
sub('来源与空间范围')
p('Overpass多端点502或超时，改为官方OSM map API分块XML下载，再用OSMnx公开XML接口建图。Nominatim核实南山relation 5664195。完整行政范围含海域及17条港珠澳大桥相关边；主图取原边界与[113.69,22.35,114.03,22.66]的交集，不是官方陆地边界，完整图和排除清单均保留。')
sub('属性与运行验收')
p(f"{a['tests_passed']}项测试通过、1条已有弃用警告，pip check无冲突。独立核查所有道路几何、方向、米制长度及三格式一致性。离线校验重放{a['runtime_seconds']}秒，源e811519、dirty=false。限速或类型默认速度仅作自由流代理；容量均为估计，未标定。")
sub('Sioux Falls基准')
p('固定上游提交d1639b4：24节点、76有向弧、576个OD条目（528非零），原始总需求360600。自由流时间为0.01小时，长度/坐标人工示意，需求为近似小时量；保留原始单位。76条参考流量是外部解，尚未运行项目求解器。上游捐赠数据限学术研究，原件留本地。')
p('详细命令、失败重放及修复、输入指纹与审计见docs/PHASE01_REPORT.md及docs/validation/phase01/。',style='Caption')

page(); h('南山研究窗口实际路网')
d.add_picture(str(ROOT/a['figures']['nanshan']),width=Cm(16.4))
p('图2 南山研究窗口真实OSM道路及估计自由流最短时间路径。20,447节点、40,105有向边、33个弱分量全部保留。主图聚焦主体道路，插图显示含内伶仃的完整研究边界。',style='Caption')
p('run_id  '+a['run_id'],style='Caption')
p('红线是实际有向边上的最短路核查，权重含估计自由流速度；没有使用实测流量或执行均衡分配。OSM转向限制、条件通行与信号延误尚未纳入，不能作为导航合规或实际旅行时间证明。')
p('© OpenStreetMap contributors，ODbL 1.0。位置WGS84，长度EPSG:32650。来源https://www.openstreetmap.org/copyright；验收PNG副本与哈希见docs/validation/phase01/。',style='Caption')

page(); h('深大附近小区域实际路网')
d.add_picture(str(ROOT/a['figures']['small']),width=Cm(16.4))
p('图3 小区域真实OSM道路。1,140节点、2,247有向边、3个弱连通分量；红线为估计自由流最短时间路径，未补造连接道路。',style='Caption')
p('run_id  '+a['run_id'],style='Caption')
p('小区范围[113.925,22.528,113.945,22.545]。原始数据、处理结果、失败及成功运行分别归档；本图和南山图均保留PNG/SVG，后续可按Phase 01或run_id查询。')
p('© OpenStreetMap contributors，ODbL 1.0。图像来自实际运行，非论文示意图。原始数据在data/raw/phase01/，处理数据在data/processed/phase01/。',style='Caption')


page(); h('Phase 02 空间数据与缺失替代')
p('已取得公开高程、人口栅格及2023年逐日雨量，并从原始OSM提取医院与消防站。官方平台目录页公开，但元数据请求403，下载要求实名登录；未取得可核验的历史积水坐标、道路监测水深或完整避难所清单。缺失数据不按零值处理。')
table(['数据','本次实际状态'],[
 ['地形','Copernicus GLO-30 DSM，两块原始瓦片；约30 m，垂直基准EGM2008'],
 ['人口','WorldPop 2020 UN调整模型人口，约1 km，每像元人数，CC BY 4.0'],
 ['降雨',f"宝安机场NOAA GSOD 2023，{b['rain_records']}条逐日报告；不是南山区面雨量"],
 ['公共设施',f"OSM医院{b['hospitals']}处、消防站{b['fire_stations']}处；无合格避难所标签，覆盖不完整"],
 ['积水风险',f"观测积水点0条，表示未取得数据；另存{b['synthetic_points']}个合成风险点"],
 ['工程验收',f"{b['tests_passed']}项测试通过，pip check无冲突；离线重放{b['runtime_seconds']}秒，源码878e467、dirty=false"]],[3.4,13.2])
sub('坐标与匹配')
p('位置统一为WGS84，匹配距离在EPSG:32650计算。地面风险点不能仅按最近道路认定受灾：高架、隧道和非零layer候选被排除，匝道与近邻歧义降低置信度；同一物理几何的双向边保留。输出候选边、距离、排除理由及高/中/低几何置信度。选择候选不等于认定该路发生积水。')
sub('时间和精度边界')
p('Copernicus为DSM，包含建筑和植被，不能直接作为精细排水DTM。WorldPop是2020年模型人口；按原生像元中心裁剪并保留人数，边界像元有误差，未插值到30 m。OSM为2026年快照，雨量是2023年机场单站；这些资料不足以宣称重建2023深圳灾害。')
p('run_id  '+b['run_id'],style='Caption')
p('来源、许可、访问失败、数据字典、实际命令与独立审计见docs/PHASE02_REPORT.md。当前交通分配、内涝时序、韧性和治理优化仍未运行。',style='Caption')

page(); h('合成风险点与几何匹配')
d.add_picture(str(ROOT/b['figures']['risk']),width=Cm(16.4))
p('图4 合成地形风险点在真实OSM路网上的分布。全部为低DSM道路种子与高斯聚集构建的情景输入，不是历史积水实测位置或水动力预测。',style='Caption')
p(f"共{b['synthetic_points']}个合成风险点。高/中/低几何置信度为{b['confidence'].get('high',0)}/{b['confidence'].get('medium',0)}/{b['confidence'].get('low',0)}个点，未匹配{b['confidence'].get('unmatched',0)}个。颜色仅表示距离与候选歧义，不表示实际受灾证据强弱。高架、隧道等候选另列排除理由。")
p('run_id  '+b['run_id'],style='Caption')
p('© OpenStreetMap contributors，ODbL 1.0。合成点在data/synthetic/phase02/独立保存；真实积水输出保留为空，并注明未取得数据。',style='Caption')

page(); h('公共设施数据与覆盖缺口')
d.add_picture(str(ROOT/b['figures']['facilities']),width=Cm(16.4))
p('图5 原始OSM快照提取的医院和消防站。设施点保留类型、OSM ID、名称与位置生成方法；面要素采用内部点，未核验实际入口。',style='Caption')
p(f"医院{b['hospitals']}处、消防站{b['fire_stations']}处。未识别到符合应急避难所规则的OSM标签，不代表当地没有避难设施。公交候车亭不作为避难所，集合点与法定避难所也不混同；未来覆盖率必须报告设施缺口。")
p('© OpenStreetMap contributors，ODbL 1.0。run_id  '+b['run_id'],style='Caption')

page(); h('高程 人口与区域逐日雨量')
d.add_picture(str(ROOT/b['figures']['terrain']),width=Cm(16.4))
p('图6 DSM与人口原生栅格。保留像元单位，人口为模型估计人数，不能作为2023或2026年人口普查结果。',style='Caption')
p('Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. WorldPop CC BY 4.0.',style='Caption')
d.add_picture(str(ROOT/b['figures']['rainfall']),width=Cm(16.4))
p('图7 宝安机场站59493099999逐日降水。NOAA NCEI GSOD 2023；英寸×25.4转mm，GMT名义日期，累计时段可包含前一日。没有拆分或插值成15分钟降雨。',style='Caption')
p('run_id  '+b['run_id'],style='Caption')

page(); h('Phase 03 交通分区与合成需求')
p(f"本次运行 {c['run_id']}，源码 {c['source_commit']}、dirty=false，耗时{c['runtime_seconds']}秒。{c['tests_passed']}项测试通过，pip check无冲突。共有{c['zones']}个1000 m网格裁剪分区，{c['active_internal_zones']}个参与OD，其中{c['unconnected_active_zones']}个缺少区内道路节点；仍保留这些分区的全部需求。边界需求使用{c['boundary_gateways']}个真实跨边界连接的外部节点。")
p('WorldPop原生233像元的估计人数守恒，按每个像元与分区的重叠面积均匀分摊并归一化。沿海像元也保留原先中心选中时的完整人数，因此有边界重分配误差；这不是更高精度的人口观测。吸引代理由人口份额80%和应急POI加权份额20%组成，医院权重3、消防站权重1，未用就业数据标定。')
p('基础内部需求=人口×0.05次/人/小时×0.5机动车出行比例÷1.25人/车。早、晚、平峰倍率分别2、1.8、1；边界流入和流出各为内部需求的10%，外部—外部为零。重力阻抗exp(−t/1200)，不可达生成阻抗7200 s，随后分别对内部、流入和流出块进行IPF平衡。全部参数均为未标定研究假设，需要敏感性分析。')
table(['时段','总需求 veh/h','不可达 veh/h','区内未上图 veh/h'],[[label,f"{c['periods'][key]['total_veh_h']:.3f}",f"{c['periods'][key]['by_route_status_veh_h'].get('unreachable_normal_network',0):.3f}",f"{c['periods'][key]['by_route_status_veh_h'].get('intrazonal_not_graph_loaded',0):.3f}"] for key,label in [('offpeak','平峰'),('morning_peak','早高峰'),('evening_peak','晚高峰')]],[3.2,4.5,4.5,4.4])
p(f"最大IPF相对边际误差{c['max_ipf_relative_error']:.3g}，阈值1e-9。区内出行单列为300 s局部需求，不加载道路边；区内虚拟接入速度20 km/h、最长1500 m，不代表已核实的实际行车接入。不可达OD保留正需求及缺失网络时间，不添加虚构道路。三时段均为小时需求率原型，尚无24小时出发计划。")
p('证据 '+c['report']+'；'+c['evidence'],style='Caption')
for key,label,caption in [('zones','人口分摊与道路连接','图8 真实路网与合成交通分区。图中仅展示大陆主要道路范围，海域和岛屿分区仍完整保留。'),('heatmap','三个时段的合成OD','图9 重力模型与IPF合成需求热力图。颜色为对数尺度veh/h；包含不可达与区内出行，外部—外部块为零。'),('desire','合成出行期望线','图10 早高峰最大的120对跨区需求。直线仅连接分区代表点，不代表行驶路线或观测轨迹。')]:
 page(); h(label)
 d.add_picture(str(ROOT/c['figures'][key]),width=Cm(16.4))
 p(caption,style='Caption')
 p('来源 '+c['figures'][key]+'；run_id '+c['run_id'],style='Caption')
 p('全部OD为合成数据；原始OSM道路方向、平行边和断连分量保持不变。WorldPop 2020 CC BY 4.0；© OpenStreetMap contributors，ODbL 1.0。')
page(); h('新增水位观测与位置质量')
p('用户确认水位由深圳市政府数据开放平台抓取，并选取高水位日期；45站位置由平台地址经高德地理编码生成。共18,123条记录，2023年9月7日00:00:33至9月8日20:04:05，原始时区未给出。7站行政区标为南山，按提供坐标仅6站落在当前研究边界；一条包含东莞POI的匹配另行标记，原始数据不修改。')
p('用户确认蓝、黄、橙、红分级断点为0.15/0.30/0.40 m，左闭右开区间逐条校验通过。SW平时接近零，支持疑似路面相对积水深度的解释，但平台未明确零点和原始字段单位。保留这一推测，当前不把SW直接写入道路水深，也不把源标签“交通中断”当作观察到的封路。原始表与压缩包按SHA256封存。')
d.add_picture(str(ROOT/c['figures']['stations']),width=Cm(16.4))
p('图11 45站地址地理编码分布。位置未经现场测量核验；精细道路暴露需补查。run_id '+c['run_id'],style='Caption')
page(); h('研究范围内六站的原始水位时序')
d.add_picture(str(ROOT/c['figures']['water']),width=Cm(16.4))
p('图12 研究范围内6站的原始SW采样，超过10分钟的间隔断线显示，不插值、不补零。峰值表与全量数据最大SW一致；有洪涝标签的子集与全量表逐条一致。',style='Caption')
p('来源 '+c['figures']['water']+'；run_id '+c['run_id'],style='Caption')
p('达涝时长列为首次到末次超阈值记录跨度，可能包含回落和采样空缺，不能直接视为累计积水持续时长。所选日期存在事件选择偏差，不代表全年洪涝频率。后续仍需补充精确数据集/API链接、字段单位与零点说明、坐标转换脚本及测站实际位置。')

page(); h('后续实施安排与图片查询')
table(['阶段','拟实施内容','状态'],[
 ['01','真实路网与Sioux Falls接入','已验收'],['02','空间数据与缺失替代','已验收'],['03','交通分区、合成OD及水位接入','已验收'],['04—07','内涝、道路退化、分配及韧性评价','未开始'],['08—09','关键道路识别、治理策略及预算优化','未开始'],['10—11','SUMO 补充验证与对比实验','未开始'],['12—13','中文交互界面、完整审计与交付','未开始']],[2.2,11.2,3.2])
sub('下一步验收')
p('下一阶段为Phase 04：建立24小时、15分钟参数化内涝时序，区分观测支持与合成情景，核验增长、峰值、延迟和消退。未经核实的SW零点不得默认为道路水深。')
sub('当前限制')
p('已接入水位及地址地理编码，但SW零点未核实；完整避难所清单、深圳实测OD仍缺失。已获雨量仅为机场逐日报告，人口为2020模型估计。SUMO、sumo-gui、netconvert 未在 PATH 发现；sumolib/traci 导入成功不代表可执行仿真已就绪。Phase 02历史测试有35条 rasterio/affine 未来弃用警告，GIS 读写已通过。')
sub('历史图片留存')
p('每次运行生成独立 run_id，保存 raw、figures、screenshots、logs、配置快照与 manifest；保留失败记录，不覆盖历史。后续重点保存正常、首次中断、受影响边最多、最低 Q、恢复或结束时刻的图像，重复时刻合并，原始时序完整保留。')
p('本地打开 results/index.html，按阶段、日期、区域、情景、策略筛选；或使用命令行 history 按 run_id 精确查询。索引可由 manifest 重建，manifest 为运行来源权威记录。')

page(); h('参考文献与复现入口')
for i,r in enumerate(data['references'],1):
 p(f'[{i}] '+r['citation'])
 p('https://doi.org/'+r['doi'],style='Caption')
p('OSM来源 https://www.openstreetmap.org/copyright，ODbL 1.0。Sioux Falls来源 https://github.com/bstabler/TransportationNetworks，固定版本与学术研究许可见阶段报告。',style='Caption')
sub('复现与核查')
p('工作目录为 jiaotong。项目运行使用 .conda-env/python.exe；文档维护脚本使用 Codex 提供的文档运行时，避免修改项目科学计算依赖。')
for cmd in ['.conda-env\\python.exe -m pytest','.conda-env\\python.exe -m pip check','.conda-env\\python.exe -m uftr.cli run --phase 03 --user-source '+c['user_source_snapshot'],'.conda-env\\python.exe -m uftr.cli history --phase 02','.conda-env\\python.exe -m uftr.cli reindex']:
 pp=p(cmd); pp.paragraph_format.space_after=Pt(3)
 for run in pp.runs: run.font.name='Consolas'; run.font.size=Pt(9)
p('完整任务书见 docs/TASK_SPEC.md，实施验收见 docs/PHASE00_REPORT.md 、docs/PHASE01_REPORT.md 与 docs/PHASE02_REPORT.md 与 docs/PHASE03_REPORT.md。PPT 与 Word 共用 docs/deliverables/content.json 中的日期、状态、验收数值、运行ID、图片路径与书目。',style='Caption')
args.output.parent.mkdir(parents=True,exist_ok=True)
d.save(args.output)
print(args.output)
