"""Plot original SW observations and address geocodes without spatial interpolation."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import shutil
from zoneinfo import ZoneInfo

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WATER = ROOT / 'data/processed/phase03/20261117T215510_p03_ab17de87/user_water'
NETWORK = ROOT / 'data/processed/phase01/20261117T193651_p01_2e554d34/nanshan'
COLORS = ['#307db8', '#e3b52b', '#eb872f', '#cf3948']
LABELS = ['蓝：SW < 0.15 m（含零值）', '黄：0.15 ≤ SW < 0.30 m',
          '橙：0.30 ≤ SW < 0.40 m', '红：SW ≥ 0.40 m']


def main():
    run_id = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%dT%H%M%S') + '_observed_water_maps'
    out = ROOT / 'results/exports' / run_id
    figures, raw = out / 'figures', out / 'raw'
    figures.mkdir(parents=True, exist_ok=False)
    raw.mkdir()
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False,
                         'font.size': 11, 'svg.fonttype': 'none'})
    inputs = [WATER/'user_stations_all.geojson', WATER/'user_water_levels_all.csv',
              NETWORK/'road_edges.geojson', NETWORK/'study_boundary.geojson',
              ROOT/'DATA_SOURCES.md', Path(__file__).resolve()]
    inputs += sorted((ROOT/'data/raw/user_sources/field_dictionary_e9e5a7bd').glob('extracted.txt'))
    sites = gpd.read_file(inputs[0])
    sites['CZBM'] = sites.CZBM.astype(str)
    levels = pd.read_csv(inputs[1], dtype={'CZBM': str})
    levels['timestamp'] = pd.to_datetime(levels.timestamp_raw)
    levels = levels.sort_values(['CZBM', 'timestamp', 'ID'], kind='stable')
    peaks = levels.loc[levels.groupby('CZBM').water_level_raw.idxmax(),
                       ['CZBM', '地址', '行政区', 'water_level_raw', 'timestamp']].rename(
                           columns={'water_level_raw': 'peak_SW_m', 'timestamp': 'first_peak_time_BJT'})
    peaks['sample_count'] = peaks.CZBM.map(levels.groupby('CZBM').size())
    # Recompute from original samples; do not adopt old derived summary durations.
    sites = sites[['CZBM', 'within_study', 'geocoding_warning', 'geometry']].merge(peaks, on='CZBM', validate='one_to_one')
    sites = sites.sort_values('CZBM').reset_index(drop=True)
    sites['map_number'] = np.arange(1, len(sites)+1)
    sites['risk_index'] = np.searchsorted([.15, .30, .40], sites.peak_SW_m.to_numpy(), side='right')
    sites['risk_color'] = sites.risk_index.map(dict(enumerate(['蓝', '黄', '橙', '红'])))
    local = sites[sites.within_study].copy()
    assert len(sites) == 45 and len(levels) == 18123 and len(local) == 6
    assert len(levels[levels.CZBM.isin(local.CZBM)]) == 2393
    edges = gpd.read_file(inputs[2])
    boundary = gpd.read_file(inputs[3])
    outputs = []

    def save(fig, name, title):
        for ext in ['png', 'svg']:
            p = figures/f'{name}.{ext}'
            fig.savefig(p, dpi=190)
            outputs.append({'path': str(p.relative_to(out)), 'title': title})
        plt.close(fig)

    def risk_legend(counts=False):
        return [Line2D([], [], marker='o', linestyle='', color=COLORS[i], markersize=9,
                       label=LABELS[i] + (f'：{int((sites.risk_index == i).sum())}站' if counts else '')) for i in range(4)]

    fig, ax = plt.subplots(figsize=(14, 9))
    fig.subplots_adjust(left=.09, right=.96, top=.85, bottom=.19)
    edges.plot(ax=ax, color='#b6c7d0', linewidth=.24, alpha=.7, rasterized=True)
    boundary.boundary.plot(ax=ax, color='#7e939f', linewidth=.9, linestyle='--')
    for risk, color in enumerate(COLORS):
        part = sites[sites.risk_index == risk]
        ax.scatter(part.geometry.x, part.geometry.y, s=95, c=color, edgecolors='white', linewidths=1, zorder=5)
    # Explicitly retain, rather than remove, the suspicious address match.
    suspect = sites[sites.geocoding_warning]
    ax.scatter(suspect.geometry.x, suspect.geometry.y, s=230, marker='x', c='#292f35', linewidths=2, zorder=7)
    for rank, (_, row) in enumerate(sites.nlargest(3, 'peak_SW_m').iterrows()):
        ax.annotate(f'{row.CZBM}\n峰值 {row.peak_SW_m:.2f} m', (row.geometry.x, row.geometry.y),
                    xytext=(12, 15 + rank*8), textcoords='offset points', fontsize=9,
                    bbox={'facecolor': 'white', 'edgecolor': '#d8dfe3', 'alpha': .94},
                    arrowprops={'arrowstyle': '-', 'color': '#788996'}, zorder=8)
    for _, row in suspect.iterrows():
        ax.annotate(f'{row.CZBM}\n东莞POI匹配疑点，位置待核', (row.geometry.x,row.geometry.y),
                    xytext=(-110, -38), textcoords='offset points', fontsize=9,
                    bbox={'facecolor': 'white', 'edgecolor': '#999', 'alpha': .95}, zorder=9)
    xmin, ymin, xmax, ymax = sites.total_bounds
    ax.set_xlim(xmin-.04, xmax+.055)
    ax.set_ylim(ymin-.035, ymax+.035)
    ax.set_aspect(1/np.cos(np.deg2rad((ymin+ymax)/2)))
    ax.set_xlabel('经度（WGS84）'); ax.set_ylabel('纬度（WGS84）')
    ax.grid(alpha=.18); ax.set_facecolor('#f4f8fa')
    ax.ticklabel_format(style='plain', useOffset=False)
    ax.legend(handles=risk_legend(True), loc='lower right', framealpha=.95, fontsize=10)
    ax.annotate('N ↑', (.96,.93), xycoords='axes fraction', fontsize=14, ha='center')
    fig.suptitle('深圳积涝观测：45站事件期间最高水位', fontsize=20, y=.95)
    fig.text(.09,.88,'2023-09-07 00:00:33 — 09-08 20:04:05（北京时间）｜18,123条观测；各站峰值不一定同时发生', fontsize=11)
    fig.text(.09,.105,'颜色表示观测SW峰值的用户分级，蓝色包含零水位；不能据颜色认定道路已经封闭。',fontsize=11)
    fig.text(.09,.065,'测站来自深圳市政府数据开放平台，地址经高德编码；SW单位m，路面零点未正式确认。\n淡蓝线仅为已有南山道路，虚线为南山研究边界；未绘制全市道路或连续积水面。© OpenStreetMap contributors',fontsize=10,color='#53626c')
    save(fig,'shenzhen_45_stations_peak_SW','全市45站事件峰值水位观测图')

    projected = local.to_crs(32650)
    roads = edges.to_crs(32650)
    border = boundary.to_crs(32650)
    fig, ax = plt.subplots(figsize=(12,11))
    fig.subplots_adjust(left=.12,right=.96,top=.85,bottom=.23)
    roads.plot(ax=ax,color='#8ba6b8',linewidth=.35,alpha=.8,rasterized=True)
    border.boundary.plot(ax=ax,color='#8a989f',linewidth=.8,linestyle='--')
    mainland = roads[roads.geometry.centroid.y > 2485000]
    xmin,ymin,xmax,ymax = mainland.total_bounds
    ax.set_xlim(xmin-1300,xmax+1500); ax.set_ylim(ymin-1100,ymax+1000)
    ax.set_aspect('equal'); ax.set_facecolor('#f4f8fa'); ax.grid(alpha=.15)
    # Place labels in two columns with fixed vertical slots, retaining true point anchors.
    ordered = projected.sort_values('CZBM')
    positions = [( .02,.78),(.55,.82),(.02,.48),(.55,.39),(.02,.18),(.55,.12)]
    for (_, row), pos in zip(ordered.iterrows(), positions):
        color = COLORS[int(row.risk_index)]
        ax.scatter(row.geometry.x,row.geometry.y,s=180,c=color,edgecolors='white',linewidths=1.1,zorder=5)
        ax.annotate(f'{row.CZBM}｜{row.peak_SW_m:.2f} m\n{row["地址"]}',
                    xy=(row.geometry.x,row.geometry.y),xytext=pos,textcoords='axes fraction',
                    ha='left',va='center',fontsize=9.2,color='#223746',
                    bbox={'facecolor':'white','edgecolor':color,'alpha':.96,'boxstyle':'round,pad=.4'},
                    arrowprops={'arrowstyle':'-','color':color,'linewidth':1},zorder=8)
    ax.set_xlabel('东向坐标（m，EPSG:32650）'); ax.set_ylabel('北向坐标（m，EPSG:32650）')
    ax.ticklabel_format(style='plain',useOffset=False)
    ax.annotate('N ↑',(.95,.94),xycoords='axes fraction',fontsize=14)
    fig.suptitle('南山研究边界内：6站观测水位与现有路网',fontsize=19,y=.95)
    fig.text(.12,.88,'2023年9月7—8日｜2,393条原始观测；标签为各站事件最高SW，单位m',fontsize=11)
    fig.legend(handles=risk_legend(),loc='lower center',bbox_to_anchor=(.5,.095),ncol=2,fontsize=10)
    fig.text(.12,.045,'地址代理点不等于传感器精确位置；峰值不同时，不向道路赋值或进行空间插值。\nSW路面零点待核；地图为南山陆地区域视图，全部路网仍保留。来源：深圳开放平台；© OpenStreetMap contributors',fontsize=10,color='#53626c')
    save(fig,'nanshan_6_stations_roads_peak_SW','南山6站峰值水位与路网叠加图')

    fig, axes = plt.subplots(3,2,figsize=(14,11),sharex=True,sharey=True)
    fig.subplots_adjust(left=.08,right=.97,top=.81,bottom=.16,hspace=.45,wspace=.15)
    for ax, (_, row) in zip(axes.flat, ordered.iterrows()):
        group = levels[levels.CZBM == row.CZBM]
        xs, ys = [], []
        previous = None
        for stamp, value in zip(group.timestamp, group.water_level_raw):
            if previous is not None and (stamp-previous).total_seconds() > 600:
                xs.append(stamp); ys.append(np.nan)
            xs.append(stamp); ys.append(value); previous=stamp
        for lo,hi,c in [(0,.15,COLORS[0]),(.15,.30,COLORS[1]),(.30,.40,COLORS[2]),(.40,.46,COLORS[3])]:
            ax.axhspan(lo,hi,color=c,alpha=.08)
        ax.plot(xs,ys,color='#245879',linewidth=.9,zorder=3)
        ax.scatter(group.timestamp,group.water_level_raw,s=4,color='#245879',zorder=4)
        for threshold in [.15,.30,.40]: ax.axhline(threshold,color='#939fa6',ls='--',lw=.6)
        ax.set_title(f'{row.CZBM}｜{row["地址"]}\n峰值 {row.peak_SW_m:.2f} m · {row.sample_count} 条记录',fontsize=10)
        ax.set_ylim(-.025,.46); ax.grid(axis='x',alpha=.15)
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0,12]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M'))
        ax.set_xlim(levels.timestamp.min(),levels.timestamp.max())
    for ax in axes[:,0]: ax.set_ylabel('观测 SW（m）')
    for ax in axes[-1,:]: ax.set_xlabel('北京时间')
    fig.suptitle('南山6站原始水位过程：2023年9月7—8日',fontsize=20,y=.95)
    fig.text(.08,.89,'统一纵轴便于比较；保留每条观测，超过10分钟的采样间隔断线显示。',fontsize=12)
    fig.text(.08,.07,'背景分级阈值：0.15 / 0.30 / 0.40 m；0值仍按原记录展示，未补零、未插值。\nSW单位及北京时间由字段说明支持；路面零点未确认。来源：深圳市政府数据开放平台，用户提供。',fontsize=11,color='#53626c')
    save(fig,'nanshan_6_stations_SW_timeseries','南山6站原始水位过程曲线')

    summary = pd.DataFrame(sites.drop(columns='geometry'))
    summary['longitude_WGS84'] = sites.geometry.x
    summary['latitude_WGS84'] = sites.geometry.y
    summary.to_csv(raw/'station_peak_summary.csv',index=False,encoding='utf-8-sig')
    export = sites.copy()
    export['first_peak_time_BJT'] = export.first_peak_time_BJT.astype(str)
    export.to_file(raw/'station_peak_summary.geojson',driver='GeoJSON')
    shutil.copy2(__file__,raw/Path(__file__).name)
    metadata = {'run_id':run_id,'status':'success','inputs':[{'path':str(p.relative_to(ROOT)), 'sha256':sha256(p.read_bytes()).hexdigest()} for p in inputs],
                'artifacts':outputs,'stations':len(sites),'records':len(levels),'study_stations':len(local),
                'study_records':int(local.sample_count.sum()),'peak_risk_counts':sites.risk_color.value_counts().to_dict(),
                'timestamp_min':str(levels.timestamp.min()),'timestamp_max':str(levels.timestamp.max()),
                'risk_thresholds_m':[.15,.30,.40],'SW_unit':'m per supplied field dictionary','timezone':'Asia/Shanghai per supplied field dictionary',
                'limitations':['SW road-surface datum unconfirmed','Address proxy locations, suspicious Dongguan match retained',
                               'Per-station event maxima are asynchronous','No road-depth adoption, closure inference or spatial interpolation',
                               'Historical Phase03 unit/timezone pending flags retained unchanged; later dictionary supports m/BJT']}
    for artifact in metadata['artifacts']:
        artifact['sha256'] = sha256((out/artifact['path']).read_bytes()).hexdigest()
    (out/'manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    cards = ''.join(f'<h2>{a["title"]}</h2><a href="{Path(a["path"]).as_posix()}"><img src="{Path(a["path"]).as_posix()}"></a>' for a in outputs if a['path'].endswith('.png'))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>积涝观测图片</title><style>body{max-width:1200px;margin:32px auto;font-family:Microsoft YaHei}img{max-width:100%}</style><h1>积涝测站与水位观测</h1><p>45站18123条记录；南山边界内6站2393条。SW单位m，路面零点未核实，站址为地址代理点。</p>'+cards+'<p><a href="raw/station_peak_summary.csv">45站峰值汇总CSV</a> · <a href="raw/station_peak_summary.geojson">站点GeoJSON</a> · <a href="manifest.json">来源记录</a></p>',encoding='utf-8')
    print(json.dumps({'output':str(out),'risk_counts':metadata['peak_risk_counts'],'study_peaks':local[['CZBM','peak_SW_m']].to_dict('records')},ensure_ascii=False))


if __name__ == '__main__':
    main()
