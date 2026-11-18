# 龙岗三维交通演示交付与核验

日期：2026-11-19。交互式 Three.js 页面已在本机浏览器运行，端口 8766 仅监听 127.0.0.1。双击根目录 `启动三维仿真.cmd` 或使用 scripts/serve_digital_twin.py。操作说明见 dashboard/digital-twin/README.md。

## 交付内容

- 立体城市沙盘：程序化建筑立面与屋顶设备、植被、路灯、道路标线、软阴影、日景和夜景窗灯、带轮胎/车窗/前灯的车辆。
- 无雨、暴雨滚动、治理滚动三组情景；完整4小时轨迹、暂停/播放、1/5/15/60倍速、拖动/键盘时间轴。
- 街区、全域鸟瞰、车辆跟随、自动运镜；点击车辆检查；建筑与积水开关；全屏按钮与空格播放。
- 所有依赖保存在本地；gzip数据降低传输量；重复启动可打开已有同一演示服务。

## 数据可追溯性

来源为 data/processed/longgang_sumo/20261118T175153_sumo_492a503a。完整每秒重放输出保存在 data/processed/digital_twin_replay_20261118T183542，之前5秒试导出保存在 data/processed/digital_twin_replay，两个目录均保留。本轮不修改历史输入、控制器或manifest。导出前核对原始输入SHA，使用冻结控制器；导出器同时校验控制器快照SHA。

每秒读取TraCI订阅，并直接查询新出发车辆，避免订阅前漏车。各情景14,401帧，采样列为车辆索引、x/y米坐标、航向角度、速度m/s；网页连续帧间插值。初始空网络帧t=0保留。核验原summary的time=t-1与simulationStep后的t对应，所有逐秒在途车辆数一致。车辆/到达统计使用原60秒账本，当前车速取可见轨迹速度均值。

|情景|独立车辆ID|每秒车辆位置记录|最终到达|
|---|---:|---:|---:|
|无雨|3,588|791,166|3,588|
|暴雨|882|236,069|877|
|治理|1,236|359,459|1,230|

4,969条道路ID/顺序/每个坐标、720行分钟统计、全部模型水深数组独立核对。每组10个最终账本字段与历史值一致，包括车辆秒、改道、传送、碰撞。精简审核见 validation/digital_twin/data_audit.json，内含本机数据SHA256。大型数据不进入Git，使用导出器重建。

## 实际验证

- `.conda-env/python.exe scripts/audit_digital_twin.py`：通过。
- `.conda-env/python.exe -m pytest -q`：171 passed，56 warnings，10.99秒。本轮没有修改交通/水文模型，测试针对当时工作区运行。
- `.conda-env/python.exe -m pip check`：No broken requirements found。
- `node --check dashboard/digital-twin/app.js`：通过。
- 浏览器实际查看1280×720页面；切换日夜、暴雨/治理情景、跟随/鸟瞰；键盘跳到终点核验无雨3588、暴雨877、治理1230辆到达；暂停/播放与返回街区已验证。最终浏览器console warning/error列表为空。
- HTTP网络JSON请求返回200、Content-Encoding:gzip；接口仅监听回环地址。
- 真实浏览器截图：validation/digital_twin/day.jpg、night.jpg、rain.jpg、follow.jpg、overview.jpg。

## 解释限制

本演示是已计算试验的离线回放，不是在线TraCI控制器。道路沿用原试验的平面推定几何，未补造真实高程。建筑、植被、路灯是视觉配景而非实测建筑；未加入未经验证的信号相位。蓝色水带只表示道路模型水深，0.30m以上用中断标识，不代表连续二维水动力。每秒插值仍包含亚秒位置近似。OD、积水、容量代理未实测标定；5%需求不能乘20外推；原实际在途改道0次，三维演示不改变该结论。本轮未重算水文、需求、治理或交通模型，也未改动Word/PPT。
