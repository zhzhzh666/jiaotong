"""Export source-based maps for browsing; no interpolation or model changes."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
network = ROOT / 'data/processed/phase01/20261117T193651_p01_2e554d34/nanshan'
rain_path = ROOT / 'data/processed/phase02/20261117T203637_p02_0286d999/rainfall_timeseries.csv'
run_id = datetime.now().strftime('%Y%m%dT%H%M%S') + '_data_maps'
out = ROOT / 'results/exports' / run_id
figures = out / 'figures'
raw = out / 'raw'
figures.mkdir(parents=True)
raw.mkdir()
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False,
                     'font.size': 11, 'svg.fonttype': 'none'})
edges = gpd.read_file(network / 'road_edges.geojson').to_crs(32650)
boundary = gpd.read_file(network / 'study_boundary.geojson').to_crs(32650)
rain = pd.read_csv(rain_path, dtype={'station_id': str})
station = gpd.GeoSeries([Point(float(rain.longitude.iloc[0]), float(rain.latitude.iloc[0]))], crs=4326).to_crs(32650).iloc[0]
valid = rain.valid.astype(str).str.lower().eq('true')
rain.loc[~valid, 'precipitation_mm'] = np.nan
stats = json.loads((network / 'network_statistics.json').read_text(encoding='utf-8'))

def map_base(ax, show_station=False):
    edges.plot(ax=ax, color='#496f88', linewidth=.35, alpha=.8, rasterized=True)
    boundary.boundary.plot(ax=ax, color='#99a9b4', linestyle='--', linewidth=.9)
    xmin, ymin, xmax, ymax = edges.total_bounds
    if show_station:
        xmin, ymin = min(xmin, station.x), min(ymin, station.y)
        xmax, ymax = max(xmax, station.x), max(ymax, station.y)
    px, py = (xmax-xmin)*.07, (ymax-ymin)*.08
    ax.set_xlim(xmin-px, xmax+px)
    ax.set_ylim(ymin-py, ymax+py)
    ax.set_aspect('equal')
    ax.set_facecolor('#f4f8fa')
    ax.set_xlabel('东向坐标（m，EPSG:32650）')
    ax.set_ylabel('北向坐标（m，EPSG:32650）')
    ax.ticklabel_format(style='plain', useOffset=False)
    ax.grid(alpha=.16)
    ax.annotate('N ↑', xy=(.94,.95), xycoords='axes fraction', ha='center', fontsize=13)

fig, ax = plt.subplots(figsize=(10,10))
map_base(ax)
ax.set_title('南山研究范围：现有 OSM 机动车道路网络\n20,447 个节点 · 40,105 条有向路段', fontsize=17, pad=18)
ax.legend(handles=[Line2D([0],[0],color='#496f88',label='现有道路'),
                   Line2D([0],[0],color='#99a9b4',ls='--',label='研究边界')], loc='lower right')
fig.text(.07,.035,'来源：© OpenStreetMap contributors，ODbL 1.0；研究窗口不等同于官方陆地边界。',fontsize=10)
fig.subplots_adjust(left=.14,right=.97,top=.88,bottom=.12)
for suffix in ['png','svg']:
    fig.savefig(figures / f'nanshan_road_network_cn.{suffix}',dpi=200)
plt.close(fig)

fig = plt.figure(figsize=(15,8))
gs = fig.add_gridspec(1,2,width_ratios=[1.05,1.25],left=.08,right=.97,top=.83,bottom=.22,wspace=.26)
ax = fig.add_subplot(gs[0])
map_base(ax, True)
ax.scatter(station.x,station.y,s=165,marker='*',color='#db5e20',edgecolor='white',linewidth=.7,zorder=6)
ax.annotate('宝安机场站 59493099999\n22.639258°N，113.810664°E',xy=(station.x,station.y),xytext=(12,-10),textcoords='offset points',fontsize=10,va='top',bbox={'facecolor':'white','edgecolor':'#ddd','alpha':.95})
ax.set_title('雨量站与现有南山路网的位置',fontsize=13,pad=12)
ax = fig.add_subplot(gs[1])
subset = rain[rain.date_gmt.between('2023-09-01','2023-09-15')].copy()
x = np.arange(len(subset))
values = subset.precipitation_mm.to_numpy()
colors = ['#db5e20' if date in ['2023-09-07','2023-09-08'] else '#5586a5' for date in subset.date_gmt]
ax.bar(x,values,color=colors,width=.72,zorder=3)
for i,v in enumerate(values):
    if np.isfinite(v) and v >= 30:
        ax.text(i,v+3,f'{v:.1f}',ha='center',fontsize=10)
    elif not np.isfinite(v):
        ax.text(i,3,'缺测',ha='center',rotation=90,fontsize=9)
ax.set_xticks(x,subset.date_gmt.str.slice(5),rotation=60)
ax.set_ylabel('逐日报告降水量（mm）')
ax.set_xlabel('2023 年 9 月：NOAA GSOD 名义报告日期（GMT）')
ax.set_ylim(0,max(np.nanmax(values)*1.18,1))
ax.set_title('宝安机场单站逐日降水量｜9月1—15日',fontsize=13,pad=12)
ax.grid(axis='y',alpha=.2,zorder=0)
fig.suptitle('现有降雨数据：单站位置与暴雨期间逐日报告',fontsize=19,y=.94)
fig.text(.08,.11,'橙色为 9月7日、8日：分别 164.3 mm、110.2 mm。单站观测不能表示南山区降水空间分布。',fontsize=12)
fig.text(.08,.065,'来源：NOAA NCEI GSOD 2023，站号59493099999；全年365条记录、355条有效。\n日期按GMT报告口径，累计时段可能包含前一日；未插值成15分钟数据。底图道路：© OpenStreetMap contributors。',fontsize=10,color='#4c5964')
for suffix in ['png','svg']:
    fig.savefig(figures / f'rainfall_station_map_cn.{suffix}',dpi=200)
plt.close(fig)

subset.to_csv(raw/'rainfall_20230901_15.csv',index=False,encoding='utf-8-sig')
shutil.copy2(__file__,raw/'export_existing_data_maps.py')
inputs = [network/'road_edges.geojson',network/'study_boundary.geojson',network/'network_statistics.json',rain_path]
manifest = {'run_id': run_id, 'purpose':'Existing road and observed station rainfall maps; no interpolation',
            'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs],
            'outputs':[str(p.relative_to(ROOT)) for p in sorted(figures.iterdir())],
            'limits':['Single airport station outside Nanshan; no areal rainfall map','GMT nominal report date; accumulation may include previous day']}
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
