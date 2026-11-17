# 数据来源和真实性说明

Phase 00 验收补充：已实际生成observed-environment类型的环境JSON和PNG/SVG，均有源文件与指纹。测试中的微型GeoJSON/TIFF仅为临时兼容性测试输入，不属于深圳数据。英文4篇Crossref成功；中文Crossref 404、期刊HTTP 500，保留本地全文核实结论与在线失败记录。

## Phase 00 已有材料

- 用户原始任务书：复制到 docs/TASK_SPEC.md，保留完整阶段要求。
- 5篇论文全文：用户提供，位于项目根目录；大小、页数、SHA256 见 docs/references/local_inventory.json。原件不改动，不纳入 Git。
- 用户开题汇报 PPTX 和新建 DOCX：保留原件；原稿不编辑，维护版已同步至Phase 01，不把其中未经核实的数字当实测输入。
- 本机硬件/依赖状态：由 psutil、platform、importlib 和 nvidia-smi 实际读取；原始 JSON 随运行存档，属于 observed-environment。
- 在线论文信息：Crossref 公共元数据；访问状态及时间见 docs/references/online_metadata.json。论文全文访问状态与书目信息核实状态分别记录。

## 数据获取状态

| 数据 | 拟获取来源 | 当前状态与真实性边界 |
| --- | --- | --- |
| 机动车道路、方向、几何 | OSM/OSMnx/Overpass，来源 https://www.openstreetmap.org/ | 已获取真实OSM小区及南山研究窗口；缺失速度/车道与全部容量估计逐字段标记，见下文 |
| Sioux Falls | https://github.com/bstabler/TransportationNetworks/tree/master/SiouxFalls | 已获取固定提交d1639b4的net/trips/node/flow和README；保留原单位及学术研究许可 |
| 历史积水/水深/2023-09-07至08降雨 | 深圳官方数据开放平台、气象/水务/应急等具有明确出处的公开材料 | Phase 02 未开始；可获得程度未知，不虚构官方接口或数据 |
| DEM | Copernicus DEM https://dataspace.copernicus.eu/ 或 NASA SRTM https://www.earthdata.nasa.gov/ | 待确认下载条件、分辨率和许可 |
| 人口 | WorldPop https://www.worldpop.org/ | 待确认年份、分辨率与单位；无真实人口时不称真实人口覆盖率 |
| 医院/消防/避难所 | 官方公开名录优先，OSM POI 可作备选 | 待质量验证；设施类别缺失不得伪装齐全 |
| 真实 OD | 合法公开或用户提供 | 当前没有，允许明确标注的重力/IPF 合成替代 |

## 保存约定

data/raw 保存下载原件；data/processed 保存处理结果；data/synthetic 保存模拟输入。每个数据集记录 URL、获取时间、许可、范围、坐标系、文件校验值、处理脚本和配置。论文引用的数据来源不等于本项目已获得该数据。尤其深圳论文的5 m DEM、183个历史积水点和部门雨量数据目前未取得，不能从文章结论还原或伪造。

## Phase 01 实际获取

2026-11-17从Nominatim核实南山relation 5664195。Overpass端点502/超时后，使用官方OSM map API分块XML及OSMnx公开XML解析；不是原生Overpass下载成功。© OpenStreetMap contributors，ODbL 1.0，https://www.openstreetmap.org/copyright 。原始响应、访问时间与哈希在data/raw/phase01/20261117T192004_p01_d71ec83e/，处理结果在data/processed/phase01/20261117T193651_p01_2e554d34/。来源清单及验收副本见docs/validation/phase01/。

完整OSM行政范围20,468节点/40,122边；研究窗口为原边界与[113.69,22.35,114.03,22.66]交集，排除17条港珠澳大桥相关边、21节点，主图20,447节点/40,105边。该窗口不是官方陆地边界，窗口内33个弱分量全部保留。小区[113.925,22.528,113.945,22.545]有1140节点/2247边。WGS84保存，EPSG:32650计长，OSM并非实地测绘真值。

Sioux Falls来自https://github.com/bstabler/TransportationNetworks ，固定提交d1639b4ef218c17928ba573e806ddf8ba5e7ae6d。24节点/76弧，576个OD条目，528非零，总需求360600为原单位；0.01小时自由流时间、人工长度/坐标、外部参考流量的性质见docs/PHASE01_REPORT.md。上游捐赠数据限学术研究，原件留本地，不宣称MIT或公有领域许可。尚无项目分配结果。
