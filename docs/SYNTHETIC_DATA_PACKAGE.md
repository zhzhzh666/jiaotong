# 南山降雨积水与交通需求合成数据包

本包是基于真实OSM路网、WorldPop模型人口与假设参数构造的实验输入。降雨、水深和OD均为合成，不能当作2023年9月暴雨重建、实测交通或已标定水动力预测。观测水位文件保持独立。

- 时间：相对情景起点0至24小时，96个15分钟区间，水深97个端点。不赋真实事件日期。
- 降雨总量：正常0、一般100、严重200、极端300 mm。5至13小时双峰雨型，峰中心8和10小时。名称是实验强度标签，不是气象等级或重现期。
- 空间：60个既有合成低DSM道路候选点，全部在研究边界内。空间扰动1.5km相关，60点雨量算术均值等于参考雨量，不代表真实面积加权降雨。
- 简化积水模型：输入有效雨量为 R[k,i] × 0.8 × A[i]，单位mm。A为假设汇水面积与积水面积比。
  排水量 D=min(H[k]+输入, c[i]×0.25+H[k]×0.25/4)，H[k+1]=H[k]+输入-D。模型H为假设路面相对积水，不采用观测SW零点。
- A=2+2.5×(1-DSM百分位)，c=8+10×DSM百分位 mm/h。DSM含建筑植被，仅作代理，不识别真实汇水区、坡向或排水管网。
- 55点具有几何道路匹配，关联54条有向边；5点保留但不赋路段水深。路段取关联点最大值，未列路段默认0只是模型假设，不证明实际无积水。
- 完整OD矩阵为574×574，包括568内部TAZ、6外部网关。242个ID有正OD，每时段58528非零对，其余分区零需求仍保留。
- 三时段基准矩阵单位veh/h。平峰36974.7448、早峰73949.4896、晚峰66554.5406 veh/h。来自既有重力/IPF合成OD，没有新观测校准。
- 7至9小时用早峰、17至19小时用晚峰，其余平峰。每小时附加倍率见config.yaml。每15分钟期望车辆数=基准OD率×倍率×0.25。
- 全天期望出行量793108.2755车次。允许小数，这是期望值，转SUMO车辆需另做可复现抽样。
- 不可达需求和区内出行仍保留在矩阵，长表route_status记录，矩阵不等于已服务道路流量。雨天需求倍率固定1，所有情景使用相同OD。
- 本包尚未重跑既有交通分配、韧性和治理实验，旧结果不能引用为本包的效果。

## 文件使用

rainfall/areal_reference_rainfall_15min.csv保存参考雨量、雨强及累计量；point_rainfall_*.csv保存点级合成雨量。
flood/point_depth_timeseries.csv或parquet保存60点全过程。edge_depth_timeseries.parquet使用既有Phase04的scenario/time_s/edge_id/depth_m接口，可作为后续新实验输入。
flood/point_parameters.csv保存假设参数；water_balance.csv保存输入、排水和末期储量；point_peak_summary.csv保存各点峰值。
demand/od_*_veh_h.csv是三个完整带行列ID的OD率矩阵；od_all_periods_long.csv保留路由状态；od_daily_expected_vehicles.csv是全天期望车次矩阵。
demand/od_15min_expected_vehicles.npz内expected_vehicles形状为(96,574,574)，单位车次/15分钟；zone_ids给出行列顺序，start_hour/end_hour给出区间。
demand/departure_profile_15min.csv保存96个区间的基准时段、倍率和总量；zone_index.csv对应全部574分区。
gis/保存合成点、TAZ、网关、接入状态与候选道路对应，不重复复制大型路网。真实道路输入路径和SHA在manifest.json。
figures/保存PNG与SVG；provenance/保存脚本、配置和数值检查。manifest.json为输入输出指纹。

```python
import numpy as np
import pandas as pd
data = np.load('demand/od_15min_expected_vehicles.npz', allow_pickle=False)
od_08_00 = data['expected_vehicles'][32]  # [8.00,8.25)，期望车次
ids = data['zone_ids']
pd.DataFrame(od_08_00, index=ids, columns=ids).to_csv('od_0800_0815.csv')
# 若分配器需要veh/h，应使用 od_08_00 / 0.25，不能把车次直接当小时率。
```

## 验证及适用范围

16项算术、边界、情景单调性及文件回读检查通过。逐步及全事件水量平衡误差见provenance/validation_report.json。检查通过只证明生成和单位换算一致，不证明假设符合真实南山排水和交通。

真实来源：© OpenStreetMap contributors，ODbL1.0；Copernicus GLO30 DSM；WorldPop2020，CC BY4.0。详见项目DATA_SOURCES.md。合成参数见provenance/config.yaml。

当前数据包路径：`data/synthetic/scenario_packages/20261118T141443_nanshan_seed42`。

生成命令：`.conda-env/python.exe scripts/generate_synthetic_data_package.py --config configs/synthetic_data_package.yaml`（创建新包并更新报告共用内容）。只读验证：`.conda-env/python.exe scripts/verify_synthetic_data_package.py`。

完整包与ZIP留本机；GitHub保留生成脚本、配置、说明、Word/PPT和小型检查记录。10个输入与38个输出SHA及ZIP内容一致，审计见`docs/validation/synthetic_data_package/package_audit.json`。
