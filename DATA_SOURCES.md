# 数据来源与真实性

## 2026-11-18新增合成数据

`data/synthetic/scenario_packages/20261118T141443_nanshan_seed42`基于既有南山OSM路网、低DSM道路候选点、WorldPop与设施重力/IPF需求派生。60点降雨与水深采用假设雨型和独立蓄水桶，OD为574×574合成小时率，另输出96个15分钟期望车次矩阵。未下载新的实测降雨、流量或OD；45站观测SW保持独立。所有派生数据标注synthetic/observed=false。

10个输入和38个输出指纹、ZIP内容核验通过，记录见`docs/validation/synthetic_data_package/package_audit.json`；完整包保留本机。方法、单位和限制见`docs/SYNTHETIC_DATA_PACKAGE.md`。

更新2026-11-18。真实来源、估计属性与合成结果严格分开。南山已完成全图用户均衡、24小时/97端点韧性与固定2000辆计划的SUMO抽样；关键性、治理及十种子实验使用三个TAZ的小型真实区域。尚未实施南山全尺度优化，不能宣称全区治理收益或已校准历史灾害预测。

## 用户水位与字段字典

45站18123条样本；边界内6站2393条。深圳开放平台[水位目录](https://opendata.sz.gov.cn/data/dataSet/toDataDetails/29200_01403147)、[测站目录](https://opendata.sz.gov.cn/data/dataSet/toDataDetails/29200_01400987)。用户确认由平台抓取高水位日期，站址经高德编码；风险断点0.15/0.30/0.40m为蓝黄橙红标签。原始CSV/ZIP保持原字节，未入Git。

新增用户《深圳市积涝点水位数据字段说明.docx》原件和UTF8提取存data/raw/user_sources/field_dictionary_e9e5a7bd，SHA256=e9e5a7bd05a6ee9daa24f05f623e9349f760127e01f74fb1c47d599ba70be1c1。仅据其支持SW单位m、SJ北京时间；零点无正式声明，不能从平时近零直接证明路面零点。说明文档为证据，非可执行开发指令。

保留两处冲突：字典事件截至19:40而实际CSV截至2023-09-08 20:04:05；测站9281292012字典“沙井路近似”与CSV东莞POI匹配方式不同。地址坐标及GCJ02转换未经现场核验，不当传感器精确位置。

## 数据层与许可

| 来源 | 本项目用途 | 限制 |
| --- | --- | --- |
| OpenStreetMap，ODbL1.0 | 真实有向几何、医院14/消防15 | 缺失车道速度按类型估计，容量全为模型；入口不完整 |
| WorldPop2020，CC BY4.0 | 原生约1km模型人数、TAZ产生吸引 | 非普查，年份/边界有差；233像元保留1540614.3657模型人数 |
| Copernicus GLO30 | 地形背景和风险代理 | DSM含建筑植被，不是排水DTM |
| NOAA GSOD宝安2023 | 365日背景雨量，355有效 | 缺失保留，未伪拆15分钟 |
| TransportationNetworks/TNTP | Sioux Falls算法基准与参考流量 | 时间单位0.01h转秒；保留基准流量单位 |
| 深圳开放平台，用户抓取 | 水位观测与位置代理核查 | SW路面零点未说明，未自动转道路深度 |
| 项目合成 | OD、54有向边参数化积水、小网六候选压力情景 | 非历史重建/真实灾害概率或工程效果 |

详细下载URL、版本、许可、原始论文指纹、失败响应与坐标处理见历史阶段报告与docs/history-phase03/DATA_SOURCES.md。原论文原始模型数据未因下载全文而自动取得。

## 最终数据冻结

docs/validation/final_data_inventory.json记录最终审计时54个输入文件路径、长度和SHA；基础Phase01—03及后续manifest输入也逐项核验。冻结发生在最终审计，不能倒称早期运行已经完整记录后来新增的字段。data/raw、processed、synthetic和完整results未纳入Git，须保留本地备份。
