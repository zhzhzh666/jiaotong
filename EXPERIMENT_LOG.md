# 实验配置与结果

## 2026-11-17 Phase 00 实施过程记录

目的：验证开发环境、配置、运行归档和图片可追溯；没有道路/内涝/交通实验结果。

初查：默认 Python 3.8.3（D:/anaconda/python.exe）；24逻辑CPU；总内存15.8 GiB，检查时可用约3.2 GiB；RTX4060 Laptop约8 GiB显存；C/D剩余约30.4/63.7 GiB。不同时间可用资源会变化，以每次运行原始JSON为准。

已执行主要命令（工作目录均为本项目）：

```powershell
conda create --prefix .conda-env --override-channels -c conda-forge python=3.11 pip -y
uv pip install --python .conda-env\python.exe -r requirements.in
python -X utf8 scripts/verify_references.py
```

使用Codex自带Python运行 `scripts/inspect_literature.py` 提取论文全文。临时文本位于 .cache/literature，不作为原文替代。

问题记录：

1. Get-CimInstance 无法访问 CIM 资源，改用 platform/psutil/nvidia-smi 获取实际信息。
2. uv 默认缓存访问被拒绝，经过执行权限审核后继续安装；没有修改base环境。
3. 默认Python在受限执行时HTTPS不可用，外网核实经权限审核执行；4篇英文Crossref成功，中文DOI为404，须另核期刊。
4. 原始PDF提取存在字体警告和数学符号失真；关键公式页已渲染核对。Land Eq.(18)与Table 5常数符号冲突已登记。

上述为实施过程记录，最终结果如下。

## Phase 00 验收结果

- Python 3.11.18，Conda环境位于`.conda-env`；uv实际安装63项依赖；Conda底层和pip层分别锁定在conda-win-64.lock.txt、requirements-win-64.lock.txt。
- 本地项目安装命令增加`--no-index --disable-pip-version-check`避免无必要的联网检查；初次普通editable安装长时间无输出后中止，离线安装成功。
- 首轮35项pytest通过；增加投影/GeoJSON/Parquet/GeoTIFF实际读写兼容检查后37项通过；最终兼容修正后复核仍为37通过、1条rasterio/affine未来弃用警告，无测试失败。原始输出见docs/validation/pytest-final.txt与XML。
- `python -m pip check`：No broken requirements found。
- `python -m uftr.cli check-config`：valid=true，97端点。
- 第一次真实运行：20261117T172555_p00_0dcd60c4；20/20导入，5.2153秒，正常结束；源实现提交772b8f6，git dirty=false。
- 生成environment_check.png和.svg，PNG已实际查看，无裁切重叠；源JSON、输入、图片SHA256校验通过；索引7个本地链接均存在。
- `python -m uftr.cli history --phase 00 --date 2026-11-17 --kind figure`返回PNG/SVG两条记录；`reindex`成功。
- 执行账号变化导致Git所有权保护报错，改为只在本项目单次命令中传safe.directory；未修改全局Git配置。CLI输出统一UTF-8。
- 5篇本地全文和10张关键页用于方法核查；4篇Crossref成功，中文Crossref404、期刊HTTP500，保留失败记录，未重复下载论文。

最终复核运行和交付文件清单见docs/PHASE00_REPORT.md；没有运行后续阶段交通实验。
