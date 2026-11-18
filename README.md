# 深圳暴雨内涝交通韧性研究原型

2026-11-18新增南山合成输入包：60个候选积水点，正常/一般/严重/极端参考雨量0/100/200/300 mm，24小时、15分钟步长；574×574完整OD与96个区间矩阵。16项一致性检查通过。入口为本机`data/synthetic/scenario_packages/20261118T141443_nanshan_seed42/index.html`，同目录旁有约50.5 MiB ZIP；方法和字段见[合成数据说明](docs/SYNTHETIC_DATA_PACKAGE.md)。这些数据未实测校准，新包尚未重跑分配与韧性，下面的既有实验结果不属于本包。

2026-11-18：Phase 00—13按上述实际范围完成研究原型与最终审计；106项测试通过、44条既有弃用警告，pip check无冲突。南山已完成全图用户均衡、24小时/97端点韧性与固定2000辆计划的SUMO抽样；关键性、治理及十种子实验使用三个TAZ的小型真实区域。尚未实施南山全尺度优化，不能宣称全区治理收益或已校准历史灾害预测。

## 使用与结果

界面启动后打开 http://127.0.0.1:8501 。八页中文系统展示预计算结果，侧栏筛选情景、时间、K、策略与效果；未计算组合明确提示。治理图为小网选中道路，Phase09参考曲线有固定参数标识。


```powershell
.conda-env/python.exe -m pytest -q
.conda-env/python.exe -m pip check
.conda-env/python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
.conda-env/python.exe -m uftr.cli run --phase 06
.conda-env/python.exe -m uftr.cli run --phase 07 --config configs/phase07_nanshan.yaml
.conda-env/python.exe -m uftr.cli run --phase 11 --config configs/phase11_fresh.yaml
.conda-env/python.exe -m uftr.cli run --phase 13
.conda-env/python.exe -m uftr.cli reindex
.conda-env/python.exe -m uftr.cli history --phase 10
.conda-env/python.exe experiments/run_all.py --phases 04 05 06 07 08 09 10 11 --include-full-nanshan --dry-run
```

最后一条先检查命令，删除`--dry-run`才执行；包含南山07约22分钟，完整十种子需更久。Phase11默认恢复配置依赖本机失败运行的已完成训练检查点，`phase11_fresh.yaml`才是从零重算。12需要实际浏览器验收文件，13需要数据、历史运行和已验证交付文档，不是只克隆源码即可运行。新增运行保留新run_id，不覆盖历史。


## 实际结果

Sioux Falls相对间隙9.92645e-5，参考流量相对RMSE0.05736%；南山平峰间隙1.70415e-5，未服务3649.7494 veh/h与区内1353.4766 veh/h均保留。南山正常/一般/严重/极端R为1 / 0.999913959 / 0.999664636 / 0.999460725，全部180次分配收敛，约21.6分钟。小网六路组、成本1、K=3、预算3、效果0.6，贪心选择road_05/road_03/road_04：R由0.991268226提高至0.997156009，与流量优先并列；42集合穷举差距0。独立十种子配对增益0.007565316，95% t区间[0.006974898,0.008155734]，只描述随机模型差异。

监测SW零点与测站地址代理位置未核实；OD、容量、积水、治理成本效果与情景概率未实测标定；人口与OSM年份不同，完整避难所缺失。南山时间效率为15起点抽样，介数32起点抽样。南山SUMO治理集合与风险无交集，灾害与治理结果相同；不据此证明全区治理有效。C/D/E只用种子42，B/F各十种子。GA为可选扩展未实现；G为实际分配效率表，不冒充南山优化耗时。

## 文档、图片与数据

- [Word研究报告](docs/deliverables/研究方案与阶段进展.docx)：19页；[PPT汇报](docs/deliverables/开题与阶段进展汇报.pptx)：19张，均逐页渲染查看，12张嵌入源图SHA匹配。
- [最终报告](docs/FINAL_REPORT.md)、[操作说明](docs/USER_GUIDE.md)、[最终审计](docs/validation/final_audit.json)。
- 本机完整图片索引`results/index.html`；每次`results/runs/<run_id>/`保留raw、figures、screenshots、logs、配置与manifest。Git中可查`docs/validation/phase04`至`phase12`的小型验收副本。
- 原始资料、完整`data`和`results/runs`留本机，克隆仓库不包含这些大型输入，复现需按`configs`路径恢复本机备份；`docs/validation/final_data_inventory.json`冻结54个输入文件字节。
- 根目录论文、原PPT/Word和用户六份水位CSV/ZIP保留；原稿指纹见`delivery_manifest.json`。字段字典存本机`data/raw/user_sources/field_dictionary_e9e5a7bd`。

## 环境与来源

使用本项目`.conda-env/python.exe`（Python3.11），锁定依赖见`requirements-lock.txt`，Eclipse SUMO/traci/sumolib1.28.0。新机器在独立Python3.11环境中安装`requirements-lock.txt`和`pip install -e .`；不修改系统/base环境。包锁来自Windows，不保证其他平台二进制依赖完全一致。

OSM / WorldPop / Copernicus / NOAA / TNTP来源、许可及估计字段见[DATA_SOURCES.md](DATA_SOURCES.md)。45站18123条水位来自用户抓取的深圳开放平台，SW为m、SJ北京时间；路面零点仍未正式说明，不将观测直接当道路积水深度。

[GitHub仓库](https://github.com/zhzhzh666/jiaotong)。逐阶段run_id见[PROGRESS.md](PROGRESS.md)，历史Phase03文档保存在`docs/history-phase03/`；历史“未开始”描述不代表当前状态。
