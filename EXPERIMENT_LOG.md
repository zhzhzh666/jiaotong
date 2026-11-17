# 实验配置与结果

## 2026-11-17 Phase 00（进行中）

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

安装、测试、运行和图像验收结果待实际完成后补充，不提前填写成功。
