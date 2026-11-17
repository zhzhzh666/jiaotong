"""Archive actual 97-endpoint scenarios, key maps, animation and provenance."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from PIL import Image
from .archive import RunArchive,write_json
from .config import load_config,time_grid
from .flood import generate_depths,road_response


def run_phase04(root,config_path):
    config=load_config(config_path); s=config['flood']; root=root.resolve()
    inputs=[config_path,*sorted((root/'src/uftr').glob('*.py'))]
    for name in ['points','mapping','edges','dictionary']:
        p=(root/s[name]).resolve();p.relative_to(root); inputs.append(p)
    with RunArchive(root,config,inputs) as run:
        points=gpd.read_file(root/s['points']); mapping=pd.read_csv(root/s['mapping'])
        edges=gpd.read_file(root/s['edges'])
        data,params=generate_depths(points,mapping,np.array(time_grid(config)),config['seed'],s)
        output=root/'data/synthetic/phase04'/run.run_id;output.mkdir(parents=True)
        depth_path=output/'edge_depth_timeseries.parquet';data.to_parquet(depth_path,index=False)
        params.to_csv(output/'risk_parameters.csv',index=False)
        summary=data.groupby(['scenario','time_s']).agg(max_depth_m=('depth_m','max'),mean_depth_m=('depth_m','mean'),
            wet_edges=('depth_m',lambda x:int((x>0).sum())),closed_edges=('depth_m',lambda x:int((x>=config['models']['closure_depth_m']).sum()))).reset_index()
        summary.to_csv(run.path/'raw/flood_summary.csv',index=False)
        report={'endpoints':len(time_grid(config)),'intervals':len(time_grid(config))-1,'affected_directed_edges':int(data.edge_id.nunique()),
            'rows':len(data),'source_kind':'synthetic_parameterized','not_historical_reconstruction':True,
            'unit_m_and_timezone_supported_by_user_dictionary':True,'observed_zero_datum_verified':False,
            'scenario_peak_m':data.groupby('scenario').depth_m.max().to_dict(),'output_directory':output.relative_to(root).as_posix()}
        write_json(run.path/'raw/flood_report.json',report)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
        for name,q in summary.groupby('scenario'):ax.plot(q.time_s/3600,q.max_depth_m,label=name)
        ax.set(xlabel='Hours from scenario start',ylabel='Maximum synthetic depth (m)',title='Parameterized flood scenarios | 97 endpoints, 15 min')
        ax.legend();ax.grid(alpha=.2)
        for ext in ['png','svg']:
            p=run.path/'figures'/('depth_curves.'+ext);fig.savefig(p,dpi=config['outputs']['dpi'])
            run.add_artifact(p,title='四种参数化积水情景',kind='figure',data_kind='synthetic',source_paths=[depth_path,run.path/'raw/flood_summary.csv'])
        plt.close(fig)
        roads=edges.to_crs(32650); base=roads[roads.edge_id.isin(data.edge_id)].copy()
        times=[0,6*3600,9*3600,12*3600,18*3600,24*3600]
        selected=data[data.scenario.eq('extreme')];maximum=float(selected.depth_m.max())
        def draw(t,path):
            fig,ax=plt.subplots(figsize=(8,7),layout='constrained')
            roads.plot(ax=ax,color='#c6cdd1',linewidth=.25)
            q=base.merge(selected[selected.time_s.eq(t)][['edge_id','depth_m']],on='edge_id')
            q.plot(ax=ax,column='depth_m',cmap='YlOrRd',vmin=0,vmax=maximum,linewidth=2.5,legend=True,legend_kwds={'label':'Synthetic road depth (m)','shrink':.65})
            x0,y0,x1,y1=roads.total_bounds;ax.set_xlim(max(x0,x1-40000)-300,x1+300);ax.set_ylim(y0-300,y1+300)
            ax.set(title=f'Extreme scenario | t={t/3600:g} h\nSynthetic risk points; not observed road inundation',xlabel='EPSG:32650 easting (m)',ylabel='Northing (m)')
            ax.ticklabel_format(style='plain',useOffset=False);fig.savefig(path,dpi=110);plt.close(fig)
        for t in times:
            p=run.path/'figures'/f'flood_{int(t):05d}.png';draw(t,p)
            run.add_artifact(p,title=f'极端情景积水 {t/3600:g}小时',kind='figure',data_kind='synthetic',source_paths=[depth_path],simulation_time_s=t)
        images=[]
        frames=run.path/'raw/animation_frames';frames.mkdir()
        for t in range(0,86401,3600):
            p=frames/f'{t}.png';draw(t,p)
            with Image.open(p) as im:images.append(im.convert('P',palette=Image.Palette.ADAPTIVE))
        p=run.path/'figures/flood_animation.gif';images[0].save(p,save_all=True,append_images=images[1:],duration=250,loop=0)
        run.add_artifact(p,title='极端内涝24小时演化动画（每小时帧）',kind='animation',data_kind='synthetic',source_paths=[depth_path])
        print(json.dumps({'run_id':run.run_id,**report},ensure_ascii=False),flush=True)
    return run.path


def run_phase05(root,config_path):
    config=load_config(config_path);s=config['impact'];depth_path=root/s['depths'];edge_path=root/s['edges']
    with RunArchive(root,config,[config_path,depth_path,edge_path,*sorted((root/'src/uftr').glob('*.py'))]) as run:
        depth=pd.read_parquet(depth_path);edges=gpd.read_file(edge_path)
        table=depth.merge(edges[['edge_id','free_flow_speed_kph','capacity_veh_h','length_m']],on='edge_id',validate='many_to_one')
        response=road_response(table.depth_m,table.free_flow_speed_kph,table.capacity_veh_h,{**s,'closure_depth_m':config['models']['closure_depth_m']})
        response['travel_time_s']=np.divide(table.length_m.to_numpy()*3.6,response.speed_kph.to_numpy(),out=np.full(len(table),np.inf),where=response.speed_kph.to_numpy()>0)
        result=pd.concat([table[['scenario','time_s','edge_id','depth_m']].reset_index(drop=True),response],axis=1)
        output=root/'data/synthetic/phase05'/run.run_id;output.mkdir(parents=True)
        path=output/'road_state_timeseries.parquet';result.to_parquet(path,index=False)
        report={'rows':len(result),'closed_rows':int(result.closed.sum()),'state_counts':result.state.value_counts().to_dict(),
            'output_directory':output.relative_to(root).as_posix(),'closure_threshold_m':config['models']['closure_depth_m'],
            'formula':'Pregnolato 2017 DOI 10.1016/j.trd.2017.06.020 PDF p7 Eq4; capacity is separate project assumption',
            'unaffected_edges':'all edges absent from state table remain at original normal attributes','closure':'removed from traversable network; infinite time in export only'}
        write_json(run.path/'raw/impact_report.json',report)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        h=np.linspace(0,.4,401);fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
        for model in ['pregnolato','linear']:
            q=road_response(h,50,1800,{**s,'closure_depth_m':config['models']['closure_depth_m']},model)
            axes[0].plot(h,q.speed_kph,label=model);axes[1].plot(h,q.capacity_veh_h/1800,label=model)
        for ax in axes:ax.axvline(.3,color='red',ls='--',label='0.30 m research closure');ax.set_xlabel('Depth (m)');ax.legend(fontsize=8);ax.grid(alpha=.2)
        axes[0].set_ylabel('Speed (km/h), normal=50');axes[1].set_ylabel('Capacity / normal capacity')
        fig.suptitle('Depth response: literature speed function + separate capacity assumption')
        for ext in ['png','svg']:
            p=run.path/'figures'/('road_response.'+ext);fig.savefig(p,dpi=160)
            run.add_artifact(p,title='水深—速度与容量退化对照',kind='figure',data_kind='synthetic',source_paths=[path])
        plt.close(fig)
        q=result[result.scenario.eq('extreme')];t=q.groupby('time_s').closed.sum().idxmax(); q=q[q.time_s.eq(t)]
        fig,ax=plt.subplots(figsize=(9,7),layout='constrained');roads=edges.to_crs(32650);roads.plot(ax=ax,color='#d2d8db',linewidth=.25)
        roads.merge(q[['edge_id','state']],on='edge_id').plot(ax=ax,column='state',categorical=True,legend=True,linewidth=3)
        x0,y0,x1,y1=roads.total_bounds;ax.set_xlim(max(x0,x1-40000)-300,x1+300);ax.set_ylim(y0-300,y1+300)
        ax.set(title=f'Extreme road states | t={t/3600:g} h | model assumption',xlabel='EPSG:32650 easting (m)',ylabel='Northing (m)');ax.ticklabel_format(style='plain',useOffset=False)
        p=run.path/'figures/road_states.png';fig.savefig(p,dpi=140);plt.close(fig)
        run.add_artifact(p,title='极端情景峰期道路通行状态',kind='figure',data_kind='synthetic',source_paths=[path],simulation_time_s=float(t))
        print(json.dumps({'run_id':run.run_id,**report},ensure_ascii=False),flush=True)
    return run.path
