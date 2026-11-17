# 数据来源和真实性说明

Phase 00 验收补充：已实际生成observed-environment类型的环境JSON和PNG/SVG，均有源文件与指纹。测试中的微型GeoJSON/TIFF仅为临时兼容性测试输入，不属于深圳数据。英文4篇Crossref成功；中文Crossref 404、期刊HTTP 500，保留本地全文核实结论与在线失败记录。

## Phase 00 已有材料

- 用户原始任务书：复制到 docs/TASK_SPEC.md，保留完整阶段要求。
- 5篇论文全文：用户提供，位于项目根目录；大小、页数、SHA256 见 docs/references/local_inventory.json。原件不改动，不纳入 Git。
- 用户开题汇报 PPTX 和新建 DOCX：保留原件；原稿不编辑，维护版已同步至Phase 02，不把其中未经核实的数字当实测输入。
- 本机硬件/依赖状态：由 psutil、platform、importlib 和 nvidia-smi 实际读取；原始 JSON 随运行存档，属于 observed-environment。
- 在线论文信息：Crossref 公共元数据；访问状态及时间见 docs/references/online_metadata.json。论文全文访问状态与书目信息核实状态分别记录。

## 数据获取状态

| 数据 | 拟获取来源 | 当前状态与真实性边界 |
| --- | --- | --- |
| 机动车道路、方向、几何 | OSM/OSMnx/Overpass，来源 https://www.openstreetmap.org/ | 已获取真实OSM小区及南山研究窗口；缺失速度/车道与全部容量估计逐字段标记，见下文 |
| Sioux Falls | https://github.com/bstabler/TransportationNetworks/tree/master/SiouxFalls | 已获取固定提交d1639b4的net/trips/node/flow和README；保留原单位及学术研究许可 |
| 历史积水/水深/2023-09-07至08降雨 | 深圳官方数据开放平台、气象/水务/应急等具有明确出处的公开材料 | 积水/水深未取得（平台元数据403，下载需实名）；已获NOAA宝安2023逐日雨量，仅作区域参考 |
| DEM | Copernicus DEM https://dataspace.copernicus.eu/ 或 NASA SRTM https://www.earthdata.nasa.gov/ | 已获Copernicus GLO-30 DSM两瓦片，约30m/EGM2008；不是排水DTM，许可与原件已保存 |
| 人口 | WorldPop https://www.worldpop.org/ | 已获WorldPop 2020约1km UN调整模型人数，CC BY 4.0；保留原生像元，不是当年普查 |
| 医院/消防/避难所 | 官方公开名录优先，OSM POI 可作备选 | OSM医院14/消防15；未获完整避难所，面内点不是核验入口 |
| 真实 OD | 合法公开或用户提供 | 当前没有，允许明确标注的重力/IPF 合成替代 |

## 保存约定

data/raw 保存下载原件；data/processed 保存处理结果；data/synthetic 保存模拟输入。每个数据集记录 URL、获取时间、许可、范围、坐标系、文件校验值、处理脚本和配置。论文引用的数据来源不等于本项目已获得该数据。尤其深圳论文的5 m DEM、183个历史积水点和部门雨量数据目前未取得，不能从文章结论还原或伪造。

## Phase 01 实际获取

2026-11-17从Nominatim核实南山relation 5664195。Overpass端点502/超时后，使用官方OSM map API分块XML及OSMnx公开XML解析；不是原生Overpass下载成功。© OpenStreetMap contributors，ODbL 1.0，https://www.openstreetmap.org/copyright 。原始响应、访问时间与哈希在data/raw/phase01/20261117T192004_p01_d71ec83e/，处理结果在data/processed/phase01/20261117T193651_p01_2e554d34/。来源清单及验收副本见docs/validation/phase01/。

完整OSM行政范围20,468节点/40,122边；研究窗口为原边界与[113.69,22.35,114.03,22.66]交集，排除17条港珠澳大桥相关边、21节点，主图20,447节点/40,105边。该窗口不是官方陆地边界，窗口内33个弱分量全部保留。小区[113.925,22.528,113.945,22.545]有1140节点/2247边。WGS84保存，EPSG:32650计长，OSM并非实地测绘真值。

Sioux Falls来自https://github.com/bstabler/TransportationNetworks ，固定提交d1639b4ef218c17928ba573e806ddf8ba5e7ae6d。24节点/76弧，576个OD条目，528非零，总需求360600为原单位；0.01小时自由流时间、人工长度/坐标、外部参考流量的性质见docs/PHASE01_REPORT.md。上游捐赠数据限学术研究，原件留本地，不宣称MIT或公有领域许可。尚无项目分配结果。

## Phase 02 实际获取与未取得资料

2026-11-17下载并封存至data/raw/phase02/20261117_source_acquisition/，完整URL、访问时间、字节数、许可和SHA256见source_inventory.json及docs/validation/phase02/验收副本。处理结果run_id为20261117T203637_p02_0286d999。完整来源及失败尝试见docs/PHASE02_REPORT.md，不能把HTTP200 HTML错误页当数据。

- Copernicus AWS 2021发布N22 E113/E114：原36,641,041/25,030,462字节；30m DSM，TanDEM-X 2011—2015及更早补洞，EGM2008。修改后署名：Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved。
- WorldPop 2020 CHN 1km Aggregated UNadj：49,445,858字节，https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/CHN/chn_ppp_2020_1km_Aggregated_UNadj.tif ，CC BY 4.0。方法背景100m元数据与本次1km产品分开，失败的REST元数据404仍保留。
- NOAA NCEI GSOD：https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/2023/59493099999.csv ，站点在南山外，355有效日记录，GMT名义日期，保留缺失标志，不插值细时序。
- OSM原始XML来自Phase 01未筛道路快照，ODbL 1.0；设施覆盖不完整。公交候车亭排除，集合点与指定避难所不混淆。
- 深圳官方积水/监测/避难/气象目录公开，29200_04003891/04003929/04003846/00900273；普通元数据请求403，页面提示下载需要实名。没有绕过，没有获得官方历史积水坐标/水深。论文作者5m DEM/183点也仍未取得。
- 60点synthetic保存在data/synthetic/phase02/<run_id>/，真实processed/flood_points.geojson保留为空。几何置信度不是历史积水证据，也不是风险概率。

人口233个原生像元的1540614.3657人数合计仅是模型与研究边界裁剪结果，海岸/边界像元有误差，不能称官方人口；DSM负值保留。时间和精度不一致，不能宣称重建2023暴雨。


## Phase 03 本轮实施状态

用户已授权继续。已实现1000 m TAZ、原生人口守恒分摊、重力/IPF三时段合成OD、真实边界节点和不可达需求保留；新增45站水位数据封存与质量检查。首次成功运行20261117T215014_p03_2b8fe770；98项测试通过，pip check无冲突。正在进行干净源码离线重放和Word/PPT同步，完成前不标记阶段验收。数据平台和高德地址编码由用户确认；0.15/0.30/0.40 m分级阈值已确认，SW路面零点仅为用户推测。
