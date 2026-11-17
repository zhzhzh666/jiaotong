"""Chinese dashboard displaying explicitly identified, archived research runs."""
from pathlib import Path
import io
import json
import zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
import plotly.graph_objects as go

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='深圳暴雨交通韧性研究',layout='wide')
PAGES=['城市道路网络总览','暴雨内涝模拟','道路状态及交通拥堵','城市交通韧性分析','医院及应急设施可达性','关键道路排名','治理策略优化','算法对比实验']


def latest(phase,region=None):
    for manifest in sorted((ROOT/'results/runs').glob(f'*_p{phase}_*/manifest.json'),reverse=True):
        m=json.loads(manifest.read_text(encoding='utf-8'))
        if m['status']!='success':continue
        config=json.loads((manifest.parent/'config.json').read_text(encoding='utf-8'))
        if region is None or config.get('research',{}).get('region')==region:return manifest.parent,m
    return None,None


@st.cache_data
def read_csv(path,mtime):return pd.read_csv(path)


def csv(path):return read_csv(str(path),path.stat().st_mtime_ns)


@st.cache_data
def roads(region):
    p=ROOT/'data/processed/phase01/20261117T193651_p01_2e554d34'/region/'road_edges.geojson'
    q=gpd.read_file(p);return pd.DataFrame({'edge_id':q.edge_id,'path':[list(g.coords) for g in q.geometry]})


def map_roads(region,states=None,selected=None,key='map'):
    q=roads(region).copy();q['color']=[[120,142,156,150] for _ in range(len(q))];q['width']=2
    if states is not None:
        dep=dict(zip(states.edge_id,states.depth_m))
        q['depth_m']=q.edge_id.map(dep).fillna(0)
        q['color']=[([190,28,52,255] if h>=.3 else [245,149,30,255]) if h>0 else [120,142,156,120] for h in q.depth_m]
        q['width']=np.where(q.depth_m>0,5,2)
    if selected:
        mask=q.edge_id.isin(selected);q.loc[mask,'color']=pd.Series([[0,155,100,255] for _ in range(mask.sum())],index=q.index[mask]);q.loc[mask,'width']=7
    q['color_key']=q.color.map(lambda a:tuple(a));figure=go.Figure()
    for color,part in q.groupby('color_key'):
        x=[];y=[];labels=[]
        for row in part.itertuples():
            for lon,lat,*_ in row.path:x.append(lon);y.append(lat);labels.append(row.edge_id)
            x.append(None);y.append(None);labels.append(None)
        figure.add_trace(go.Scattergl(x=x,y=y,text=labels,mode='lines',hovertemplate='%{text}<extra></extra>',line={'color':f'rgba({color[0]},{color[1]},{color[2]},{color[3]/255})','width':float(part.width.max())},showlegend=False))
    figure.update_layout(height=480,margin={'l':10,'r':10,'t':10,'b':25},xaxis_title='经度 WGS84',yaxis_title='纬度 WGS84',dragmode='pan')
    figure.update_yaxes(scaleanchor='x',scaleratio=1/np.cos(np.deg2rad(22.54)))
    if region=='nanshan':figure.update_xaxes(range=[113.69,114.04]);figure.update_yaxes(range=[22.34,22.67])
    else:figure.update_xaxes(range=[113.924,113.946],constrain='domain');figure.update_yaxes(range=[22.527,22.546],constrain='domain')
    st.plotly_chart(figure,width='stretch',config={'scrollZoom':True},key=key)


page=st.sidebar.radio('功能页面',PAGES)
st.sidebar.caption('结果来自已归档运行；更改控件筛选预计算结果。')
region=st.sidebar.selectbox('路网范围',['small','nanshan'],format_func=lambda s:'小型真实区域' if s=='small' else '南山研究窗口')
scenario=st.sidebar.selectbox('暴雨强度',['normal','general','severe','extreme'],index=2,format_func=lambda x:{'normal':'正常','general':'一般','severe':'严重','extreme':'极端'}[x])
step=st.sidebar.slider('灾害时刻（15分钟步长）',0,96,36);time_s=step*900
st.sidebar.write(f'当前时刻：{time_s/3600:g} 小时')
budget=st.sidebar.selectbox('治理道路数量预算 K',[0,1,3,5,10,20],index=2)
strategy=st.sidebar.selectbox('治理策略',['none','random','depth','flow','centrality','resilience_greedy'],index=5,format_func=lambda x:{'none':'不治理','random':'随机','depth':'水深优先','flow':'流量优先','centrality':'介数优先','resilience_greedy':'韧性贪心'}[x])
effect=st.sidebar.select_slider('积水削减比例',options=[.2,.4,.6,.8],value=.6)
st.title('深圳暴雨内涝交通韧性研究')
st.caption('真实 OSM 路网 + 合成 OD 与参数化积水；时间片用户均衡。当前展示历史预计算结果。')
st.header(page)
st.info('水位观测单位为米、北京时间；SW 路面零点尚未核实。地址坐标未经传感器位置测量。治理与十种子实验来自小型真实区域，不能解释为深圳全市优化结论。')

flood_run,flood_manifest=latest('04');impact_run,_=latest('05');r07,_=latest('07',region);r08,_=latest('08');r09,_=latest('09');r11,_=latest('11')
states=None
if flood_run:
    report=json.loads((flood_run/'raw/flood_report.json').read_text());depth=pd.read_parquet(ROOT/report['output_directory']/'edge_depth_timeseries.parquet')
    states=depth[depth.scenario.eq(scenario)&depth.time_s.eq(time_s)]

if page==PAGES[0]:
    a,b,c=st.columns(3);a.metric('节点',1140 if region=='small' else 20447);b.metric('有向边',2247 if region=='small' else 40105);c.metric('弱连通分量',3 if region=='small' else 33)
    map_roads(region);st.write('保留有向平行边、断连和原始几何；路网速度与容量包含按道路类型估计的属性。')
elif page==PAGES[1]:
    if states is None:st.warning('尚无成功的内涝运行。')
    else:
        st.write(f'南山情景：{scenario}，{time_s/3600:g}小时；最高水深 {states.depth_m.max():.3f} m。')
        map_roads('nanshan',states)
        q=csv(flood_run/'raw/flood_summary.csv');st.line_chart(q.pivot(index='time_s',columns='scenario',values='max_depth_m'))
        st.caption('该地图来自 Phase 04 的南山风险情景；小网治理压力试验使用独立的六组道路情景。')
elif page==PAGES[2]:
    map_roads('nanshan',states)
    if impact_run:
        report=json.loads((impact_run/'raw/impact_report.json').read_text());q=pd.read_parquet(ROOT/report['output_directory']/'road_state_timeseries.parquet');q=q[q.scenario.eq(scenario)&q.time_s.eq(time_s)]
        st.dataframe(q[['edge_id','depth_m','speed_kph','capacity_veh_h','state']],hide_index=True)
    r06,_=latest('06')
    if r06:st.write('正常分配边流量');st.dataframe(pd.read_parquet(r06/'raw'/f'{region}_flows.parquet').head(100),hide_index=True)
elif page==PAGES[3]:
    if r07:
        q=csv(r07/'raw/resilience_timeseries.csv');st.line_chart(q.pivot(index='time_s',columns='scenario',values='Q'))
        part=q[q.scenario.eq(scenario)&q.time_s.eq(time_s)];st.dataframe(part[['scenario','time_s','Qs','Qp','Qf','Q','unserved_veh_h','relative_gap']],hide_index=True)
        st.dataframe(csv(r07/'raw/resilience_summary.csv'),hide_index=True);st.caption('同一时片采用相同 OD 正常基准；不可达需求计入惩罚。结构效率为抽样起点到全部节点的时间加权效率。')
    else:st.warning('当前范围的韧性运行尚未完成。')
elif page==PAGES[4]:
    st.warning('OSM 医院/消防清单和入口不完整；未取得合格避难所清单，不能据此认定现实无避难所。')
    if r07:
        q=csv(r07/'raw/resilience_timeseries.csv');part=q[q.scenario.eq(scenario)&q.time_s.eq(time_s)]
        st.dataframe(part[[c for c in q if 'coverage' in c or c in ['scenario','time_s']]],hide_index=True)
        p=r07/'figures/hospital_accessibility_map.png'
        if p.is_file():st.image(str(p),caption='该图为归档极端情景代表时刻，非侧栏当前时刻；数值表按侧栏筛选。')
elif page==PAGES[5]:
    st.caption('候选道路排名及单独治理收益：小型真实路网的六组地面道路压力试验。')
    if r08:
        q=csv(r08/'raw/critical_road_ranking.csv');st.dataframe(q,hide_index=True);st.image(str(r08/'figures/critical_roads_map.png'))
elif page==PAGES[6]:
    st.caption('预算和效果控件筛选已计算方案。超出六个候选时 K 自动截断；尚无对应组合时会明确提示。')
    chosen=None
    if r11:
        q=csv(r11/'raw/experiment_results.csv')
        if effect!=.6:
            part=q[q.experiment.eq('D_effect')&q.effect.eq(effect)] if strategy=='resilience_greedy' and budget==3 else q.iloc[0:0]
        elif budget!=3:
            part=q[q.experiment.eq('C_budget')&q.K_requested.eq(budget)] if strategy=='resilience_greedy' else q.iloc[0:0]
        else:part=q[q.experiment.eq('B_strategies')&q.seed.eq(42)&q.strategy.eq(strategy)]
        if len(part):st.dataframe(part,hide_index=True);chosen=str(part.iloc[0].selected).split('|') if pd.notna(part.iloc[0].selected) else []
        else:st.warning('尚未预计算这个预算、策略与效果组合。可用训练方案：K=3、效果0.6下六策略；贪心的预算与效果分别做单因素敏感性。')
    elif r09 and budget==3 and effect==.6:
        q=csv(r09/'raw/strategy_comparison.csv');part=q[q.strategy.eq(strategy)];st.dataframe(part,hide_index=True);chosen=str(part.iloc[0].selected).split('|') if pd.notna(part.iloc[0].selected) else []
    if chosen is not None and r08:
        rank=csv(r08/'raw/critical_road_ranking.csv');edge_ids=[e for text in rank[rank.road_id.isin(chosen)].directed_edge_ids for e in text.split('|')]
        left,right=st.columns(2)
        with left:st.subheader('治理前');map_roads('small')
        with right:st.subheader('治理后选中道路');map_roads('small',selected=edge_ids,key='after_map')
        st.caption('绿色表示实际选中治理道路；效果与收益由表中归档模型计算，地图不把未计算水深伪装为实时结果。')
    if r09:
        st.caption('下图固定展示 Phase 09 种子42、K=3、效果0.6的六策略参考曲线，不随侧栏预算或效果变化。')
        st.line_chart(csv(r09/'raw/strategy_timeseries.csv').groupby(['time_s','strategy']).Q.mean().unstack())
elif page==PAGES[7]:
    if r11:
        q=csv(r11/'raw/experiment_results.csv');experiment=st.selectbox('实验组',sorted(q.experiment.unique()));part=q[q.experiment.eq(experiment)];st.dataframe(part,hide_index=True)
        st.dataframe(csv(r11/'raw/experiment_statistics.csv'),hide_index=True);st.caption('B/F 为十种子均值、标准差与 t 区间；C/D/E 为种子42的确定性参数对比。区间不代表深圳真实韧性估计误差。')
        st.download_button('下载实验原始结果 CSV',q.to_csv(index=False).encode('utf-8-sig'),'experiment_results.csv','text/csv')
    else:st.warning('十种子实验正在运行，结果完成后刷新页面。')

with st.expander('运行来源、导出与历史图片'):
    for phase in ['04','05','06','07','08','09','10','11']:
        folder,m=latest(phase)
        if m:
            st.write(f"Phase {phase} · {m['run_id']} · {m['status']} · {m.get('elapsed_s',0):.1f}秒")
            st.download_button(f'下载 Phase {phase} manifest',(folder/'manifest.json').read_bytes(),m['run_id']+'_manifest.json','application/json',key='manifest_'+phase)
    index=ROOT/'results/index.html'
    if index.is_file():st.download_button('下载本机图片查询索引 HTML',index.read_bytes(),'index.html','text/html')
    st.caption('本机完整图片索引：results/index.html；下载后的索引需与 results 文件夹相同层级使用。')
