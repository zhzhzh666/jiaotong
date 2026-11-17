# 运行与图片归档接口

Phase 00 CLI：`python -m uftr.cli run --phase 00 --config configs/phase00.yaml`。当前只实现环境检查，不提供尚未完成阶段的占位仿真。

`RunArchive(project_root, config, inputs)` 创建独立run_id目录，记录配置SHA256、输入SHA256和Git commit/dirty。上下文正常结束为success，异常结束为failed并保存traceback。add_artifact要求图片在本次目录内、有明确data_kind且至少一个可校验源文件；同一路径不能重复注册。

每个artifact记录title、kind、data_kind、simulation_time_s、units、source paths/hashes、image hash、created_at；阶段、区域、情景、策略、seed、config继承运行manifest。来源标签区分observed-environment、real、synthetic、mixed、reference-page。

以manifest为权威记录，reindex扫描全部运行重建CSV与本地HTML索引；文件链接使用相对路径，目录整体备份/迁移后仍可浏览。HTML查询为本地关键词筛选，CLI支持结构化筛选。尚未开始的Streamlit页面不在本阶段实现。

Phase 00参考页核查图片位于`.cache/literature/pages`，属于文献核查材料，不是实验地图，也不是交通模型结果。未来正式运行的图片放在results/runs，截图不能使用生成式图片代替真实界面证据。

当前默认单进程写索引；并行运行应由主进程在全部子任务结束后统一reindex。持续运行被强制终止时manifest可能留为running，不能推断为success；保留后人工诊断。不自动清理历史数据。
