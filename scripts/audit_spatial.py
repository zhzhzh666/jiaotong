"""Independently audit Phase 02 scientific boundaries and saved GIS outputs."""
from pathlib import Path
import argparse,json
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import Point
from uftr.archive import file_hash,write_json

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--compare-run')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path.cwd()
    run=(root/'results/runs'/args.run_id).resolve();run.relative_to(root/'results/runs')
    report=json.loads((run/'raw/spatial_report.json').read_text(encoding='utf-8'))
    config=json.loads((run/'config.json').read_text(encoding='utf-8'))['spatial']
    output=root/report['processed_root'];synthetic=root/report['synthetic_root'];snapshot=root/report['source_snapshot']
    observed=json.loads((output/'flood_points.geojson').read_text(encoding='utf-8'))
    assert observed['features']==[] and report['flood']['observed_points']==0
    points=gpd.read_file(synthetic/'flood_points.geojson').to_crs(32650)
    assert points.source_kind.eq('synthetic').all() and points.observed_depth_m.isna().all()
    edges=gpd.read_file(root/config['network_directory']/'road_edges.geojson').to_crs(32650).set_index('edge_id')
    boundary=gpd.read_file(root/config['network_directory']/'study_boundary.geojson').to_crs(32650).geometry.iloc[0]
    assert points.geometry.map(boundary.covers).all()
    candidates=pd.read_csv(output/'flood_road_mapping.csv',keep_default_na=False)
    chosen=candidates[candidates.selected_geometry]
    assert set(points.point_id)==set(candidates.point_id)
    for _,row in chosen.iterrows():
        edge=edges.loc[row.edge_id];point=points[points.point_id.eq(row.point_id)].geometry.iloc[0]
        assert abs(point.distance(edge.geometry)-float(row.distance_m))<1e-7
        assert float(row.distance_m)<=config['matching']['max_match_distance_m']
        for tag in ['bridge','tunnel']:
            assert str(edge.get(tag,'')).lower() in {'','nan','none','false','no','0','0.0'}
        assert pd.isna(edge.get('layer')) or str(edge.get('layer',0)) in {'','0','0.0','nan'}
    # Independently compare every exported population cell against the native source.
    with rasterio.open(snapshot/'population_2020_1km.tif') as original, rasterio.open(output/'population_2020_native_1km.tif') as clipped:
        assert original.crs==clipped.crs and original.res==clipped.res
        assert abs((clipped.transform.c-original.transform.c)/original.res[0]-round((clipped.transform.c-original.transform.c)/original.res[0]))<1e-7
        valid=clipped.read(1,masked=True)
        rr,cc=np.where(~valid.mask)
        xx,yy=rasterio.transform.xy(clipped.transform,rr,cc)
        source=np.array([v[0] for v in original.sample(zip(xx,yy))])
        assert np.array_equal(source,valid.data[rr,cc])
        assert np.isclose(source.sum(dtype=np.float64),report['population']['sum_native_cells'])
    rain=pd.read_csv(output/'rainfall_timeseries.csv',dtype={'station_id':str})
    raw=pd.read_csv(snapshot/'baoan_gsod_2023.csv',dtype={'STATION':str})
    merged=rain.merge(raw,left_on='date_gmt',right_on='DATE',validate='one_to_one')
    assert np.allclose(merged[merged.valid].precipitation_mm,merged[merged.valid].PRCP*25.4)
    assert rain.is_nanshan_areal_mean.eq(False).all()
    compare=None
    if args.compare_run:
        prior=json.loads((root/'results/runs'/args.compare_run/'raw/spatial_report.json').read_text(encoding='utf-8'))
        old=root/prior['processed_root'];oldsynthetic=root/prior['synthetic_root']
        for relative in ['facilities.geojson','rainfall_timeseries.csv','flood_road_mapping.csv','population_2020_native_1km.tif','copernicus_dsm_30m.tif']:
            assert file_hash(old/relative)==file_hash(output/relative),relative
        assert file_hash(oldsynthetic/'flood_points.geojson')==file_hash(synthetic/'flood_points.geojson')
        compare={'run_id':args.compare_run,'six_data_outputs_identical':True}
    result={'run_id':args.run_id,'status':'passed','observed_flood_points':0,'synthetic_points':len(points),
            'selected_directed_edge_rows_checked':len(chosen),'native_population_cells_verified':len(source),
            'rainfall_records_verified':len(merged),'compare':compare,
            'claim_boundary':'Geometric confidence is not evidence of historical flooding; no 15-minute rainfall fabricated'}
    write_json(args.output,result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
