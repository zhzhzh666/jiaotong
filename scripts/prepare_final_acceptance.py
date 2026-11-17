"""Prepare reproducible configs and record observed browser acceptance evidence."""
from pathlib import Path
import json
import shutil
import yaml
import pandas as pd
from uftr.archive import file_hash, write_json

root = Path(__file__).resolve().parents[1]
config = yaml.safe_load((root/'configs/phase11.yaml').read_text(encoding='utf-8'))
config['research'].pop('resume_results_directory', None)
(root/'configs/phase11_fresh.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False),encoding='utf-8')
for phase in ['12','13']:
    c={k:v for k,v in config.items() if k!='research'}
    c.update(phase=phase,scenario='browser-acceptance' if phase=='12' else 'independent-final-audit')
    if phase=='13':
        c['audit_data']={'networks':config['research']['network_root'],
          'spatial':'data/processed/phase02/20261117T203637_p02_0286d999',
          'demand':config['research']['demand_directory'],'synthetic_od':config['research']['od'],
          'used_flood_depth':config['research']['full_depths'],
          'field_dictionary':'data/raw/user_sources/field_dictionary_e9e5a7bd'}
    (root/f'configs/phase{phase}.yaml').write_text(yaml.safe_dump(c,allow_unicode=True,sort_keys=False),encoding='utf-8')
ui=root/'docs/validation/phase12'
# Superseded screenshot is retained locally, excluded from accepted evidence.
old=ui/'02-flood.jpg'
if old.exists():shutil.move(str(old),str(root/'.cache/doc-sync/02-flood-superseded.jpg'))
download=Path('C:/Users/zh/Downloads/experiment_results.csv')
source=root/'docs/validation/phase11/experiment_results.csv'
pd.testing.assert_frame_equal(pd.read_csv(download),pd.read_csv(source))
pages=['城市道路网络总览','暴雨内涝模拟','道路状态及交通拥堵','城市交通韧性分析','医院及应急设施可达性','关键道路排名','治理策略优化','算法对比实验']
report={'status':'passed','date':'2026-11-18','url':'http://127.0.0.1:8501',
 'pages_verified':pages,'csv_download_verified':True,
 'csv_comparison':{'method':'pandas assert_frame_equal, all columns and rows','rows':len(pd.read_csv(source)),
 'source_sha256':file_hash(source),'download_sha256':file_hash(download)},
 'interactions_verified':['八页导航与实际内容','暴雨严重切换正常：9小时最高水深0.000m','时间轴36切换0：当前0小时',
 '治理预算1与3筛选','效果0.6与0.4切换','K1/效果0.4显示尚未预计算提示','K3/效果0.6治理前后同坐标范围',
 '实验CSV真实下载且逐值一致','预计算与Phase09固定参考曲线说明'],
 'app_sha256':file_hash(root/'app.py'),
 'screenshots':[{'path':p.relative_to(root).as_posix(),'sha256':file_hash(p)} for p in sorted(ui.glob('*.jpg'))]}
write_json(ui/'browser-verification.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
