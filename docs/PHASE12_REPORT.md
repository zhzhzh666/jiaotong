# Phase 12 验收

运行`20261118T004847_p12_a74097b5`。命令`.conda-env/python.exe -m uftr.cli run --phase 12`。

南山已完成全图用户均衡、24小时/97端点韧性与固定2000辆计划的SUMO抽样；关键性、治理及十种子实验使用三个TAZ的小型真实区域。尚未实施南山全尺度优化，不能宣称全区治理收益或已校准历史灾害预测。

```json
{
  "status": "passed",
  "date": "2026-11-18",
  "url": "http://127.0.0.1:8501",
  "pages_verified": [
    "城市道路网络总览",
    "暴雨内涝模拟",
    "道路状态及交通拥堵",
    "城市交通韧性分析",
    "医院及应急设施可达性",
    "关键道路排名",
    "治理策略优化",
    "算法对比实验"
  ],
  "csv_download_verified": true,
  "csv_comparison": {
    "method": "pandas assert_frame_equal, all columns and rows",
    "rows": 136,
    "source_sha256": "89324d4c104aed2723ccfbe1057662d709fc2f1ba48546efff0bb8e4054ff2dd",
    "download_sha256": "0e5e7230524e3e71212c2679d7a0b210807397e8fb0c8bd3ff5a5c7003491845"
  },
  "interactions_verified": [
    "八页导航与实际内容",
    "暴雨严重切换正常：9小时最高水深0.000m",
    "时间轴36切换0：当前0小时",
    "治理预算1与3筛选",
    "效果0.6与0.4切换",
    "K1/效果0.4显示尚未预计算提示",
    "K3/效果0.6治理前后同坐标范围",
    "实验CSV真实下载且逐值一致",
    "预计算与Phase09固定参考曲线说明"
  ],
  "app_sha256": "524eb0312d286a36399c0ce8f6e1a1c001a4a9ed4794eb4b663515ef1597c8b3",
  "screenshots": [
    {
      "path": "docs/validation/phase12/01-network.jpg",
      "sha256": "6e1b9ab09b7c89a49b1f8ae37a562a2a694d97043ee79646d0ec9cf1471895c6"
    },
    {
      "path": "docs/validation/phase12/02-flood-fixed.jpg",
      "sha256": "6cecca76732d7d563d2b910824289e999b4d7615d0a344a72aefc5563c16f203"
    },
    {
      "path": "docs/validation/phase12/03-road-states.jpg",
      "sha256": "06a1ddf6e6c3137f3e6f351da16cc4540d55963550fd15d72132f5038713ecdc"
    },
    {
      "path": "docs/validation/phase12/04-resilience.jpg",
      "sha256": "dadea653514455bd2ccb58df0ed691417dd53d6721761c5c8973eebb6fbaddde"
    },
    {
      "path": "docs/validation/phase12/05-accessibility.jpg",
      "sha256": "9b469f8fa22c76142c29868b87282845393f508f6a60137b07ff358b99d90e84"
    },
    {
      "path": "docs/validation/phase12/06-ranking.jpg",
      "sha256": "f9a41f3e3ebe4141fb76dd855147c1b9abeaaa1bba5e1b6c970908d745d0f7b6"
    },
    {
      "path": "docs/validation/phase12/07-optimization.jpg",
      "sha256": "605e574647960f85d12eb872e6a17b3e218efc429513c6371629ed6e423f4436"
    },
    {
      "path": "docs/validation/phase12/08-experiments.jpg",
      "sha256": "b30418c08e67860f7ce9c95f1249eb2a5b2ce6418f307814d47e50453bad4f33"
    },
    {
      "path": "docs/validation/phase12/09-uncomputed-warning.jpg",
      "sha256": "39f638f1fb1b062e57ed13461ecc512bb7b16f34d8cc7a7097376e5a67998044"
    }
  ]
}
```
