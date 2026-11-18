"""Presentation figure derived from frozen metrics, without changing the run."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();run=args.run.resolve();out=args.output.resolve();out.mkdir(exist_ok=True,parents=True)
source=run/'raw/interval_metrics.csv';d=pd.read_csv(source)
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':11,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
labels={'normal':'正常','general':'一般100 mm','severe':'严重200 mm','extreme':'极端300 mm'}
colors={'normal':'#71808A','general':'#4B8CAA','severe':'#E39A35','extreme':'#BE4058'}
for ax,field,title in zip(axes,['Q','mean_served_network_time_s'],['综合交通性能 Q','已服务出行平均道路时间 s']):
    for scenario,color in colors.items():
        part=d[d.scenario.eq(scenario)].sort_values('interval_index')
        ax.step(np.r_[part.start_hour,24.],np.r_[part[field],part[field].iloc[-1]],where='post',label=labels[scenario],color=color)
    ax.set_ylabel(title);ax.grid(alpha=.2)
axes[1].set_xlabel('相对情景起点 小时');axes[1].set_xlim(0,24)
fig.suptitle('南山合成情景 时片用户均衡与交通评估')
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',ncol=4,bbox_to_anchor=(.54,.935))
fig.text(.07,.015,'96个15分钟出发区间；使用区间起点道路状态与同需求正常基准。合成且未标定，时片之间不传递排队。',fontsize=10)
fig.tight_layout(rect=(0,.05,1,.86))
files=[]
for ext in ['png','svg']:
    path=out/('traffic_resilience_process.'+ext);fig.savefig(path,dpi=170);files.append(path)
plt.close(fig)
def record(path):return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha256(path.read_bytes()).hexdigest()}
report={'run_id':run.name,'inputs':[record(source),record(run/'manifest.json'),record(Path(__file__).resolve())],
    'outputs':[record(path) for path in files],'change':'Legend moved outside axes only; stored numerical results and frozen package unchanged'}
(out/'figure_source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
