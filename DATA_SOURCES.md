# 数据来源和真实性说明

## Phase 00 已有材料

- 用户原始任务书：复制到 docs/TASK_SPEC.md，明确本轮只实施 Phase 00。
- 5篇论文全文：用户提供，位于项目根目录；大小、页数、SHA256 见 docs/references/local_inventory.json。原件不改动，不纳入 Git。
- 用户开题汇报 PPTX 和新建 DOCX：保留原件；本阶段不编辑，不把其中未经核实的数字当实测输入。
- 本机硬件/依赖状态：由 psutil、platform、importlib 和 nvidia-smi 实际读取；原始 JSON 随运行存档，属于 observed-environment。
- 在线论文信息：Crossref 公共元数据；访问状态及时间见 docs/references/online_metadata.json。论文全文访问状态与书目信息核实状态分别记录。

## 尚未取得的数据

| 数据 | 拟获取来源 | 当前状态与真实性边界 |
| --- | --- | --- |
| 机动车道路、方向、几何 | OSM/OSMnx/Overpass，来源 https://www.openstreetmap.org/ | Phase 01 未开始；OSM 缺失属性估计需逐字段标记 |
| Sioux Falls | https://github.com/bstabler/TransportationNetworks/tree/master/SiouxFalls | Phase 01 未开始；保留原文件、版本和许可 |
| 历史积水/水深/2023-09-07至08降雨 | 深圳官方数据开放平台、气象/水务/应急等具有明确出处的公开材料 | Phase 02 未开始；可获得程度未知，不虚构官方接口或数据 |
| DEM | Copernicus DEM https://dataspace.copernicus.eu/ 或 NASA SRTM https://www.earthdata.nasa.gov/ | 待确认下载条件、分辨率和许可 |
| 人口 | WorldPop https://www.worldpop.org/ | 待确认年份、分辨率与单位；无真实人口时不称真实人口覆盖率 |
| 医院/消防/避难所 | 官方公开名录优先，OSM POI 可作备选 | 待质量验证；设施类别缺失不得伪装齐全 |
| 真实 OD | 合法公开或用户提供 | 当前没有，允许明确标注的重力/IPF 合成替代 |

## 保存约定

data/raw 保存下载原件；data/processed 保存处理结果；data/synthetic 保存模拟输入。每个数据集记录 URL、获取时间、许可、范围、坐标系、文件校验值、处理脚本和配置。论文引用的数据来源不等于本项目已获得该数据。尤其深圳论文的5 m DEM、183个历史积水点和部门雨量数据目前未取得，不能从文章结论还原或伪造。
