# 龙岗仿真：Ubuntu 5090 迁移与回传

目标机：Ubuntu 22.04.5 LTS / x86_64，Intel Core Ultra 9 285K（24线程），64 GiB RAM，2 TB磁盘，用户说明配备RTX 5090。研究范围为龙岗、不含大鹏。

本包包含实际源码、冻结数据、已验收片区结果、离线网页回放数据及SHA256清单，不是下载链接集合。默认全区5%合成需求、4小时、seed42、单进程、关闭GUI。没有复制Windows环境；Ubuntu创建独立Python 3.11环境。环境安装需要联网，本包没有Linux离线wheel仓库。

当前SUMO、SciPy路径查询、水文原型和NSGA-II计算使用CPU。5090可以用于图形显示和后续另行开发的深度学习；现有仓库没有PyTorch训练循环、神经网络模型或完整Gawron/SDTA迭代分配实现。不要把五组情景比较称为模型训练或动态均衡收敛结果。

## 1. 传到Ubuntu并检查

将同名的`.tar.gz`与`.tar.gz.sha256`复制到Ubuntu同一目录。以下的`迁移包.tar.gz`替换成实际文件名；建议安装在Linux原生ext4文件系统，避免直接在NTFS移动盘上运行。

```bash
sha256sum -c 迁移包.tar.gz.sha256
mkdir -p "$HOME/projects/jiaotong_5090"
tar -xzf 迁移包.tar.gz -C "$HOME/projects/jiaotong_5090"
cd "$HOME/projects/jiaotong_5090"
python3 scripts/migrate_5090.py verify
```

使用新建空目录解压。磁盘至少留15 GiB供环境和短期结果；长时段轨迹、多个种子和训练checkpoint建议预留100 GiB以上。2 TB是总容量，仍需用`df -h .`检查剩余空间。

## 2. 安装独立环境并做真实冒烟检查

先使用Linux版[Miniforge](https://github.com/conda-forge/miniforge)或Miniconda。Windows的`.conda-env`不可迁移。若当前终端找不到conda，可执行`source "$HOME/miniforge3/etc/profile.d/conda.sh"`，路径以实际安装为准。

```bash
cd "$HOME/projects/jiaotong_5090"
bash migration/bootstrap_ubuntu.sh
conda activate "$PWD/.conda-env"
python -m pytest -q
python -m pip check
```

安装脚本锁定源机已安装的第三方包版本，SUMO / sumolib / traci均为1.28.0，并执行一辆车实际到达的headless TraCI检查。Linux wheel可用性、系统动态库及驱动状态必须在目标机验证；本机Windows验收不能代替Ubuntu验收。若pip下载失败，保留报错，不要随意混装apt旧版SUMO或解除版本锁。

如果报共享库缺失，先检查：

```bash
ldd .conda-env/lib/python3.11/site-packages/sumo/bin/sumo | grep 'not found'
nvidia-smi
```

按缺失项安装系统库。Ubuntu常见需求如下（需要目标机管理员权限）：

```bash
sudo apt-get update
sudo apt-get install -y libgl1 libglu1-mesa libgomp1 libx11-6 libxext6 libxrender1 libxrandr2 libxi6 fonts-noto-cjk tmux rsync
```

系统CUDA Toolkit不是当前CPU求解器的前提；无需为本包更换显卡驱动。`nvidia-smi`失败会记录诊断，但不表示CPU仿真不能运行。若将来开发GPU训练，在另一个环境中验证PyTorch支持5090/Blackwell、CUDA张量运算和实际训练一步，再开始长任务；训练框架版本应另存锁文件。

## 3. 先基准，再五组比较

先运行目标机自己的基准；耗时以目标机保存的`hourly_performance.csv`和`resources_*.csv`为准。不要用显卡型号换算速度。

```bash
python scripts/run_5090.py --cases dry
cat results/remote_runs/LATEST.txt
```

一次创建一个新run_id，记录配置、源码SHA、环境、CPU/RAM/GPU信息、逐小时耗时、进程树RSS、车辆账本、路线、60秒FCD轨迹和日志。RSS可能重复计算共享内存；它不是GPU显存。默认先保持1个任务，检查内存峰值后再决定多种子并发；24线程不等于单个SUMO能24倍加速。

基准完成后复用同一准备路网，补跑四组。下列命令直接读取最新run路径：

```bash
RUN="$(cat results/remote_runs/LATEST.txt)"
python scripts/run_5090.py --resume "$RUN" --cases dry rain_departure rain_rolling governed_departure governed_rolling
```

或从头一次跑五组（生成另一个独立run，不能与上面同时运行）：

```bash
tmux new -s jiaotong
bash migration/run_five_cases.sh
```

`Ctrl+B`再按`D`退出tmux界面，任务继续；`tmux attach -t jiaotong`返回。关闭3D，结果完成后再回放。`LATEST.txt`仅方便单任务操作，多任务请明确记录日志里的run路径。

恢复仅支持**情景之间**，跳过已有完整`result.json`的组，并核对源码、配置及准备输入。某组中途失败会保留现场，不能从仿真中间继续；请另开run，不删除或覆盖旧结果。改变seed、需求比例、候选治理或时窗时，先复制配置到新文件，使用`--config configs/你的实验.yaml`启动新run；提高需求前先做短规模性能试验。

配置中的`output_root`属于历史入口；`run_5090.py`统一将新结果写入`results/remote_runs/`。默认900秒水深、1秒交通、300秒滚动路径保持原实现。未知桥隧/覆盖外水深在交通中假设正常；tau为未标定容量代理。

## 4. 水文和治理参数实验（按需单独运行）

这会重新计算，可能明显久于SUMO基准。没有必要为了迁移重复生成已冻结数据。

```bash
python scripts/run_longgang_adaptive.py --landcover data/raw/longgang_worldcover/20261118T163548_worldcover_c1d3d395
```

该入口输出到`data/processed/longgang_adaptive/新run_id`，支持自身严格SHA检查点；与`run_5090.py`的五情景运行是两个不同入口。要将这类结果附带回传，先复制到一个新的`results/experiments/实验名/`目录，再在下一节的export命令加`--include-extra results/experiments/实验名`。同样可附带以后训练的权重、配置、分割清单、日志和评估文件；附带目录必须已经停止写入。

OD、地表汇流和原始GIS也随包保存，但修改上游数据不会自动改变下游配置的冻结包路径。需要明确改为新包并重新准备路网；禁止给旧包改名后当作新结果。

## 5. 生成回传包

等运行状态为`complete`后导出。回传包含运行原始文件、逐小时资源记录、路线和轨迹、必要冻结输入、源码与配置快照；无需复制环境或整个外发包。

```bash
RUN="$(cat results/remote_runs/LATEST.txt)"
python scripts/migrate_5090.py export --run "$RUN" --out "$HOME/jiaotong_return.tar.gz"
```

生成`jiaotong_return.tar.gz`、同名`.sha256`和`.manifest.json`。复制压缩包和SHA文件回本机。已有同名输出会拒绝覆盖，多次导出使用新文件名。导出期间不得继续计算或编辑该run、附带的实验/训练目录。

可用U盘、局域网共享或SSH/scp。假设Ubuntu已开启SSH且本机可以连通，在Windows PowerShell：

```powershell
scp 用户名@Ubuntu主机IP:~/jiaotong_return.tar.gz* D:\transfer\
```

无需开放本项目网页服务到公网。原始路径和地址信息随数据返回；自行选择合适的传输位置。

## 6. 本机一条命令导入并汇总

在原项目`C:\Users\zh\Desktop\git\jiaotong`的PowerShell执行，替换实际回传文件路径：

```powershell
.\.conda-env\python.exe scripts\migrate_5090.py receive D:\transfer\jiaotong_return.tar.gz
```

自动校验同目录SHA文件及内部每个文件，拒绝重复导入/覆盖，导入到`results/imported/return_时间_标识/`。独立汇总在`results/analysis/同一标识/`，包括`REPORT.md`、`comparison.csv`（Excel可读UTF-8 BOM）、`analysis.json`和带压缩包SHA的导入收据。账本检查包括计划总量、无效、未发、在途、到达及注入守恒；不冒称XML独立审计或实测标定。

分析器只用Python标准库，也可由系统Python调用。不覆盖本机原数据、环境或历史运行。Linux生成的SUMO XML中会保留当时的绝对路径，作为证据原字节保存；CSV/JSON分析不依赖这些路径。重新仿真请在导入快照中安装独立环境并用运行脚本创建新run，勿直接双击旧sumocfg。

本机现有离线网页演示：

```powershell
.\.conda-env\python.exe scripts\serve_digital_twin.py
```

此网页展示原3 km×3 km片区已验收的三组每秒轨迹，**不会自动切换成Ubuntu全区新结果**。新全区FCD默认60秒，适合稀疏轨迹检查；若要新全区每秒网页回放，必须另做转换器与规模验证，不能直接替换旧网页JSON。

## 7. 包内数据和边界

- 冻结龙岗483×483合成OD、道路图及96时段矩阵，ERA5再分析雨量、DSM、WorldCover、简化D8积水与治理输出、原始OSM来源包。
- 已验收片区SUMO结果及网页回放；全区新的运行代码、默认配置和资源监测。
- 输入依赖闭包按SHA收集，历史源代码修订由各run的provenance保存。历史manifest原字节保留；历史源文件版本与当前版本不同时不宣称可直接用当前源码恢复历史run。
- 包含已完成并有独立审计的本机全区无雨基准作为参考（若manifest metadata列出）；不复制活动run和GUI预览。Ubuntu仍重新生成路网并测量，勿直接用原机绝对路径启动旧sumocfg。不含Windows环境、凭据、Git目录、Word/PPT和南山历史大数据。docs中的历史南山入口缺其数据，不能作为本包运行入口。
- 合成OD、积水、容量和治理效果均未实测标定；未实现真实排水管网/二维水动力，未完成动态均衡迭代。迁移后仍须披露这些范围限制。

当前任务来历、接续开发顺序与验收要求见`migration/REMOTE_HANDOFF.md`。无需在另一台机器重新寻找数据或从头阅读全部聊天。
