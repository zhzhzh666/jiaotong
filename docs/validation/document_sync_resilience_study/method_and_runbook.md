# RTX4090：按PPT模型识别关键道路、优化治理并回传

这是关键道路与治理专用完整包，可独立解压，不依赖之前的五场景SUMO包。适用Ubuntu22.04.5 / i9-14900K / 128GiB / RTX4090。入口是`run_resilience_4090.py`，不是`run_4090.py`。目前使用CPU数值求解，无神经网络训练器；不要求CUDA Toolkit。

## 模型、任务和结果

采用用户《网络韧性数学模型 (2).pptx》的权重：Q=0.27Qs+0.41Qp+0.32Qf，R为24小时Q曲线的梯形积分除以24小时，15分钟间隔、97端点。原PPT与SHA在`data/raw/model_reference/network_resilience_20261119/`。

- Qs：可用有向弧比例、最大弱/强连通节点比例、时间效率各自相对同OD时段无雨基准的均值。结构范围固定为龙岗源道路节点；默认固定64个效率起点估计，故R也是此抽样设置下的估计。可另开配置将`efficiency_origins`改为`all`计算全部起点，代价显著增加。
- Qp=C0/C；C=道路Σ流量×时间+14400秒×不可达OD需求。使用完整483×483合成OD的5%比例需求，保留全部OD单元；不是旧SUMO的泊松出行抽样。区内需求独立记账，不加载道路，也不另加PPT未给的300秒费用。
- Qf：公开OSM医院、消防两类的15/30分钟人口覆盖率相对无雨比值。PPT给出两个阈值，当前明确采用两个阈值结果再等权平均，并另报R15/R30。69个医院、31个消防OSM对象，中心点按1500m上限接入，连接速度20km/h；完整性、运营、真实入口未经核实。所有分区人口含未接入分区留在分母。任一无雨覆盖率为0会停止，不私自调整权重。
- 识别：既有静态筛查提供12条道路候选，新流程逐条将候选道路积水归零，按三档降雨平均ΔR重排名。这是12条候选内的恢复价值诊断，不是全区所有道路的穷尽排序，也不表示工程可将道路水深归零。
- 治理：四个冻结空间排水点S0—S3、最多治理三处，共15组合。每个组合使用已独立计算的积水序列，重新分配交通、计算R；在每档预算下最大化三档雨量的最小R。输出精确枚举、边际贪心、优先深水和10随机种子对照。预算为相对造价，不能解释成人民币或已标定投资收益。

全源图451,801条有向弧承载龙岗OD，结构指标限定龙岗86,807条关联源弧。保留方向、平行边、不可达需求及未知积水假设原状。交通是逐时片BPR用户均衡，不跨时片传递排队，不是动态用户均衡。权重直接来自PPT，未重新估计熵权。Q/R超过1原值保留并标记。未标定合成数据不能作为真实灾害预测。

## 1. 解压和环境安装

将压缩包和同名`.sha256`一起复制到Ubuntu。使用新的空目录；建议环境及短期计算至少30GiB可用空间，长期实验预留100GiB以上。

```bash
sha256sum -c jiaotong_ubuntu4090_keyroads_governance_20261119.tar.gz.sha256
mkdir -p "$HOME/projects/jiaotong_keyroads_4090"
tar -xzf jiaotong_ubuntu4090_keyroads_governance_20261119.tar.gz -C "$HOME/projects/jiaotong_keyroads_4090"
cd "$HOME/projects/jiaotong_keyroads_4090"
python3 scripts/migrate_4090_study.py verify
```

先安装Linux版Miniforge/Miniconda并确保`conda`可用。包内不含Windows环境，也不含Linux离线依赖仓库。安装需要联网：

```bash
bash migration/bootstrap_ubuntu.sh
conda activate "$PWD/.conda-env"
python -m pip check
python scripts/run_resilience_4090.py --phase preflight
```

安装脚本保留兼容名称`check_5090.py`，只是共用环境/SUMO检查，不要求5090显卡。预检查核对冻结输入、OD/图尺寸、候选及设施接入，不等于正式模型已完成。

## 2. 先测两种状态，再运行完整研究

```bash
python scripts/run_resilience_4090.py --phase pilot
RUN="$(cat results/resilience_runs/LATEST.txt)"
cat "$RUN/pilot_budget.json"
```

pilot求解一个无雨平峰状态和一个积水状态，实测收敛、时间和内存。`pilot_budget.json`是基于两次测量的条件预算，不能当成整项研究的实测耗时。全研究含7,857个不同案例端点，完全相同的状态会复用；高拥堵状态可能明显更慢。目标Ubuntu尚未执行，可能需要较长连续运行。

在tmux中继续同一run：

```bash
python scripts/run_resilience_4090.py --resume "$RUN" --phase all
```

或从头一键依次pilot和all：`bash migration/run_4090_resilience.sh`。恢复已有run：`bash migration/run_4090_resilience.sh results/resilience_runs/你的run目录名`。

默认seed42、单任务、数值库线程1；先实测再调整，不自动启动32个任务。每个独立交通状态完成后保存数组和收敛轨迹；中断时保留已完成状态。使用相同命令`--resume`恢复；正在计算但未完成的那个状态会重算。源码、配置、冻结数据任一改变都必须新建run。未收敛或守恒失败会停止并保留诊断，不当作完成。

还可分阶段运行`--phase baseline`、`identify`、`optimize`；只有`all`完成才标为完整研究。勿将preflight/pilot成功解释为道路或治理结论。

## 3. 查看并审计

每次结果在独立`results/resilience_runs/ppt_…/`：

| 文件 | 用途 |
|---|---|
| `critical_road_R_ranking.csv` | 候选道路OSM编号、标签、三雨型ΔR和排名 |
| `governance_R_combinations.csv` | 15治理组合、造价、各雨型R及最坏R |
| `budget_R_recommendations.csv` | 每档预算推荐治理点和mask |
| `governance_R_strategy_comparison.csv` | 精确枚举、贪心、深水、随机的同指标对照 |
| `cases/*/curve.csv` | 97端点Qs/Qp/Qf/Q及其匹配无雨状态 |
| `states/*` | 流量、时间、水深、容量、关闭、OD服务数组及收敛轨迹 |
| `figures/*.png`及`.svg` | 韧性曲线、道路排名和预算前沿图 |
| `independent_audit.json` | 独立算术、数组和预算最优核对结果 |
| `resources_*.csv` | 实测资源和耗时记录 |

流程自动执行独立核对，也可单独运行：

```bash
python scripts/audit_resilience_4090.py --run "$RUN"
```

核对SHA、BPR、积水退化公式、节点/OD守恒、记录最短路成本对应的间隙、Q/R、ΔR及预算最优；不重算全部最短路和结构效率，不替代实测标定。

## 4. 完整回传本机

任务完成、停止写入后，使用同一包的源码导出：

```bash
python scripts/migrate_4090_study.py export --run "$RUN" --out "$HOME/keyroads_4090_return.tar.gz"
```

压缩包和同名SHA文件一起带回Windows。首次回传时，从本次出站包的`scripts/`中取出`migrate_4090_study.py`和`migrate_5090.py`放在同一文件夹；本机工程已具备这些新版脚本。使用本机独立环境执行：

```powershell
cd C:\Users\zh\Desktop\git\jiaotong
.\.conda-env\python.exe scripts\migrate_4090_study.py receive D:\transfer\keyroads_4090_return.tar.gz
```

自动校验文件和Q/R算术，原始结果、必要冻结输入和源码进入`results/imported/新ID/`；分析汇总进入`results/analysis/同ID/`，包括道路排名、治理推荐、报告和`analysis.json`，不覆盖本机历史结果。图在导入快照run下`figures/`。

需要重做数组审计时，使用导入快照的冻结源码和输入：

```powershell
.\.conda-env\python.exe results\imported\返回ID\scripts\audit_resilience_4090.py --root results\imported\返回ID --run results/resilience_runs/原run目录名
```

回传导出会拒绝与计算时SHA不一致的源码或输入，因此计算完成后先导出，再改代码。包内保留旧SUMO脚本供历史参考；本研究不会自动运行五场景SUMO，也不会将新排名冒充为其验证结果。
