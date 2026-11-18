"""Check final document provenance after actual page and slide visual review."""
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json
import csv
import math
import xml.etree.ElementTree as ET
from docx import Document
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'docs/deliverables'
data=json.loads((target/'content.json').read_text(encoding='utf-8'))
final=data['final'];sections=final['sections']
suite=ET.parse(ROOT/'docs/validation/current-tests.xml').getroot().find('testsuite')
assert int(suite.attrib['tests'])==final['tests_passed'] and int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
review=json.loads((ROOT/'docs/validation/final_visual_review.json').read_text(encoding='utf-8'))
assert review['all_pages_and_slides_visually_reviewed']
docpath=target/'研究方案与阶段进展.docx';pptpath=target/'开题与阶段进展汇报.pptx'
doc=Document(docpath);doc_text='\n'.join(p.text for p in doc.paragraphs)
pdf=PdfReader(ROOT/review.get('word_pdf','.cache/doc-sync/final-word.pdf'))
assert len(pdf.pages)==len(sections)==review['word_pages']
assert all(len(page.extract_text().strip())>100 for page in pdf.pages)
receipt=json.loads((ROOT/review.get('ppt_receipt','.cache/doc-sync/final-reviewed.pptx.validation.json')).read_text(encoding='utf-8'))
assert receipt['finalSha256']==sha256(pptpath.read_bytes()).hexdigest()
assert receipt['packageIntegrity']['status']=='pass' and receipt['presentationLayout']['exitCode']==0 and receipt['firstPartyImport']['passed']
with ZipFile(pptpath) as ppt,ZipFile(docpath) as word:
    slides=[n for n in ppt.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    assert len(slides)==len(sections)==review['ppt_slides']
    ppt_text=''.join(ppt.read(n).decode('utf-8') for n in ppt.namelist() if n.endswith('.xml') and (n.startswith('ppt/slides/') or n.startswith('ppt/notesSlides/')))
    for s in sections:assert s['title'] in doc_text and s['title'] in ppt_text,s['title']
    for ref in data['references']:assert ref['doi'] in doc_text and ref['doi'] in ppt_text
    # Notes carry complete precision and run IDs; visible slides summarize.
    for run_id in final['runs'].values():assert run_id in ppt_text
    images=[s['figure'] for s in sections if s.get('figure')]
    # New rainfall and demand figures use editable native charts in PowerPoint.
    ppt_images=[s['figure'] for s in sections if s.get('figure') and not s.get('ppt_native',False) and
                (not s['title'].startswith('补充情景 ') or s['title']=='补充情景 南山合成积水点')]
    for archive,prefix,expected in [(word,'word/media/',images),(ppt,'ppt/media/',ppt_images)]:
        embedded={sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n.startswith(prefix)}
        for name in expected:assert sha256((ROOT/name).read_bytes()).hexdigest() in embedded,name

    native_series_checked=0
    if data.get('synthetic_data_package'):
        assert receipt['nativeChartValidation']['passed']
        assert receipt['nativeQuantitativeCharts']['report']['passed']
        base=ROOT/data['synthetic_data_package']['path']
        def rows(name):
            with (base/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
        rain=rows('rainfall/areal_reference_rainfall_15min.csv')
        depth=rows('flood/point_depth_timeseries.csv')
        profile=rows('demand/departure_profile_15min.csv')
        ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
        scenarios=['general','severe','extreme']
        expected_charts=[
            [(list(k/4 for k in range(96)),[float(r['intensity_mm_h']) for r in rain if r['scenario']==s]) for s in scenarios],
            [(list(k/4 for k in range(97)),[max(float(r['depth_m']) for r in depth if r['scenario']==s and float(r['time_s'])==k*900) for k in range(97)]) for s in scenarios],
            [([float(r['start_hour']) for r in profile],[float(r['total_rate_veh_h']) for r in profile])]]
        for i,expected in enumerate(expected_charts,1):
            tree=ET.fromstring(ppt.read(f'ppt/slides/charts/chart{i}.xml'))
            series=tree.findall('.//c:scatterChart/c:ser',ns)
            assert len(series)==len(expected)
            for ser,(xvalues,yvalues) in zip(series,expected):
                for field,values in [('xVal',xvalues),('yVal',yvalues)]:
                    actual=[float(v.text) for v in ser.findall(f'c:{field}/c:numRef/c:numCache/c:pt/c:v',ns)]
                    assert len(actual)==len(values)
                    assert all(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10) for a,b in zip(actual,values)),(i,field)
                native_series_checked+=1
        for component in ['storm_process','road_performance','traffic_process']:
            if not data.get(component):continue
            process=ROOT/data[component]['path']
            charts=json.loads((process/'raw/native_chart_data.json').read_text(encoding='utf-8'))
            ns['a']='http://schemas.openxmlformats.org/drawingml/2006/main'
            trees=[ET.fromstring(ppt.read(n)) for n in ppt.namelist() if n.startswith('ppt/slides/charts/chart') and n.endswith('.xml')]
            by_title={''.join(t.text or '' for t in tree.findall('c:chart/c:title//a:t',ns)):tree for tree in trees}
            for expected in charts:
                tree=by_title[expected['title']];series=tree.findall('.//c:scatterChart/c:ser',ns)
                assert len(series)==len(expected['series'])
                for ser,values in zip(series,expected['series']):
                    for field,key in [('xVal','x'),('yVal','y')]:
                        actual=[float(v.text) for v in ser.findall(f'c:{field}/c:numRef/c:numCache/c:pt/c:v',ns)]
                        assert len(actual)==len(values[key])
                        assert all(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10) for a,b in zip(actual,values[key]))
                    native_series_checked+=1

def record(path):
    b=path.read_bytes()
    return {'path':path.relative_to(ROOT).as_posix(),'bytes':len(b),'sha256':sha256(b).hexdigest()}

old=json.loads((target/'delivery_manifest.json').read_text(encoding='utf-8'))
for original in old['originals_preserved']:assert record(ROOT/original['path'])==original
assert review['word_sha256']==record(docpath)['sha256'] and review['ppt_sha256']==record(pptpath)['sha256']
manifest={'updated':data['updated'],'phase_status':data['status'],'accepted_runs':final['runs'],
 'deliverables':[record(pptpath),record(docpath)],'content_source':record(target/'content.json'),
 'originals_preserved':old['originals_preserved'],
 'verification':{'final_content_checked':True,'all_pages_and_slides_visually_reviewed':True,
 'pptx_slides':len(slides),'docx_pages':len(pdf.pages),'embedded_source_images':{'word':len(images),'ppt':len(ppt_images)},'embedded_image_sha256_matches':True,
 'previous_core_tests_passed':int(suite.attrib['tests']),'core_tests_rerun_for_document_update':bool(data.get('storm_process')) and not bool(data.get('active_research')),'shared_titles_and_doi_checked':True,
 'native_chart_source_series_checked':native_series_checked,
 'pptx_package_layout_fonts_and_reimport':'pass',
 'word_render':'Microsoft Word read-only COM ExportAsFixedFormat PDF then bundled pypdfium2 PNG; LibreOffice unavailable',
 'pptx_render':'Artifact Tool final file reimport, each slide exported to PNG',
 'native_powerpoint_playback_verified':False},
 'visual_review':record(ROOT/'docs/validation/final_visual_review.json')}
if data.get('synthetic_data_package'):
    manifest['synthetic_data_package']={'path':data['synthetic_data_package']['path'],
        'generation_checks_passed':data['synthetic_data_package']['report']['check_count'],
        'observed':False,'traffic_assignment_rerun':False}
if data.get('storm_process'):
    latest=ET.parse(ROOT/data['storm_process']['tests_report']).getroot().find('testsuite')
    assert int(latest.attrib['failures'])==int(latest.attrib['errors'])==0
    assert int(latest.attrib['tests'])==data['storm_process']['tests_passed']
    manifest['verification']['latest_tests_passed']=int(latest.attrib['tests'])
    manifest['storm_process']={'path':data['storm_process']['path'],'process_consistency_checks':11,
        'observed':False,'traffic_assignment_rerun':False,'tests_report':record(ROOT/data['storm_process']['tests_report'])}
if data.get('road_performance'):
    latest=ET.parse(ROOT/data['road_performance']['tests_report']).getroot().find('testsuite')
    assert int(latest.attrib['failures'])==int(latest.attrib['errors'])==0
    assert int(latest.attrib['tests'])==data['road_performance']['tests_passed']
    manifest['verification']['latest_tests_passed']=int(latest.attrib['tests'])
    manifest['road_performance']={'path':data['road_performance']['path'],'consistency_checks':len(data['road_performance']['report']['checks']),
        'observed':False,'traffic_assignment_rerun':False,'tests_report':record(ROOT/data['road_performance']['tests_report'])}
if data.get('traffic_process'):
    latest=ET.parse(ROOT/data['traffic_process']['tests_report']).getroot().find('testsuite')
    assert int(latest.attrib['failures'])==int(latest.attrib['errors'])==0
    assert int(latest.attrib['tests'])==data['traffic_process']['tests_passed']
    audit=json.loads((ROOT/'docs/validation/traffic_process/numerical_audit.json').read_text(encoding='utf-8'))
    assert audit['all_checks_passed'] and audit['intervals_audited']==384
    manifest['verification']['latest_tests_passed']=int(latest.attrib['tests'])
    manifest['traffic_process']={'path':data['traffic_process']['path'],'consistency_checks':len(data['traffic_process']['report']['checks']),
        'observed':False,'traffic_assignment_rerun':True,'tests_report':record(ROOT/data['traffic_process']['tests_report']),
        'independent_numerical_audit':record(ROOT/'docs/validation/traffic_process/numerical_audit.json')}
if data.get('active_research'):
    active=data['active_research']
    intake=ROOT/active['intake_path']
    checks=json.loads((intake/'intake_checks.json').read_text(encoding='utf-8'))
    report=json.loads((intake/'intake_report.json').read_text(encoding='utf-8'))
    assert checks['all_checks_passed'] and report==active['report']
    assert active['region']=='longgang' and report['include_dapeng']==active['include_dapeng'] and not active['assignment_ready']
    if not active['include_dapeng']:
        assert report['selected_roads_intersect_excluded_component']==report['selected_stations_in_excluded_component']==0
        assert '不含大鹏' in doc_text and '不含大鹏' in ppt_text
    assert '龙岗' in doc_text and '龙岗' in ppt_text
    manifest['active_research']={'region':active['region'],'scope':active['scope'],'include_dapeng':active['include_dapeng'],
        'intake_path':active['intake_path'],'assignment_ready':False,'traffic_assignment_rerun_for_longgang':False,
        'intake_checks':record(ROOT/'docs/validation/longgang_intake/intake_checks.json'),
        'intake_report':record(ROOT/'docs/validation/longgang_intake/intake_report.json')}
if data.get('longgang_od'):
    od=data['longgang_od'];run=ROOT/od['path']
    report=json.loads((run/'demand_report.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/od['audit']).read_text(encoding='utf-8'))
    latest=ET.parse(ROOT/od['tests_report']).getroot().find('testsuite')
    assert report==od['report'] and audit['run_id']==report['run_id'] and audit['all_checks_passed']
    assert not report['observed_od'] and not report['include_dapeng']
    assert all(report['checks'].values()) and audit['all_96_intervals_read_back']
    assert int(latest.attrib['tests'])==od['tests_passed'] and int(latest.attrib['errors'])==int(latest.attrib['failures'])==0
    assert report['run_id'] in doc_text and report['run_id'] in ppt_text
    manifest['verification']['latest_tests_passed']=od['tests_passed']
    manifest['longgang_od']={'path':od['path'],'observed':False,'topology_certified':False,
        'traffic_assignment_rerun':False,'tests_report':record(ROOT/od['tests_report']),
        'independent_numerical_audit':record(ROOT/od['audit']),
        'matrix_shape':report['matrix_shape'],'consistency_checks':len(report['checks'])}
if data.get('longgang_storm'):
    storm=data['longgang_storm'];run=ROOT/storm['path']
    report=json.loads((ROOT/'docs/validation/longgang_storm/validation_report.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/storm['audit']).read_text(encoding='utf-8'))
    latest=ET.parse(ROOT/storm['tests_report']).getroot().find('testsuite')
    assert report==storm['report'] and report['run_id']==audit['run_id']==run.name
    assert report['all_checks_passed'] and all(report['checks'].values()) and audit['all_checks_passed']
    assert not report['observed'] and not report['include_dapeng'] and not storm['hydrodynamic']
    assert int(latest.attrib['tests'])==storm['tests_passed'] and int(latest.attrib['errors'])==int(latest.attrib['failures'])==0
    assert report['run_id'] in doc_text and report['run_id'] in ppt_text
    assert report['site_count']==4139 and report['modelled_source_features']==6848
    assert report['source_feature_status_counts']['elevated_tunnel_or_nonzero_layer_not_modelled']==952
    assert audit['case_scenario_combinations_audited']==20
    assert 'C方案尚未实施' in ppt_text and '未运行SWMM或二维模型' in doc_text
    manifest['verification']['latest_tests_passed']=storm['tests_passed']
    manifest['longgang_storm']={'path':storm['path'],'observed':False,'hydrodynamic':False,
        'traffic_assignment_rerun':False,'consistency_checks':len(report['checks']),
        'tests_report':record(ROOT/storm['tests_report']),'independent_numerical_audit':record(ROOT/storm['audit'])}
if data.get('longgang_drainage'):
    drainage=data['longgang_drainage']
    assert not drainage['real_network_obtained'] and not drainage['coupled_model_run']
    manifest['longgang_drainage']={'source':record(ROOT/drainage['source']),
        'real_network_obtained':False,'coupled_model_run':False}
if data.get('longgang_era5_surface'):
    era5=data['longgang_era5_surface']
    evidence=ROOT/'docs/validation/longgang_era5_surface'
    report=json.loads((evidence/'validation_report.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/era5['audit']).read_text(encoding='utf-8'))
    attribution=json.loads((evidence/'era5_attribution.json').read_text(encoding='utf-8'))
    latest=ET.parse(ROOT/era5['tests_report']).getroot().find('testsuite')
    assert report==era5['report'] and report['run_id']==audit['run_id']==Path(era5['path']).name
    assert report['all_checks_passed'] and all(report['checks'].values()) and audit['passed']
    assert int(latest.attrib['tests'])==era5['tests_passed']==151
    assert int(latest.attrib['errors'])==int(latest.attrib['failures'])==0
    assert not report['include_dapeng'] and not report['calibrated'] and not report['observed_rain_gauges'] and not report['observed_flood_depths']
    assert report['rain_hours']==120 and report['rain_grid_count']==9 and report['domain_cells']==66920
    assert report['output_endpoints']==481 and report['case_count']==8
    assert audit['rain_values_rechecked_from_HTTP_response']==1080
    assert audit['independent_baseline_grid_endpoints_replayed']==32188520
    assert audit['known_road_values_checked']==26351104
    assert attribution==era5['attribution'] and attribution['classification']=='reanalysis_not_gauge_observation'
    assert attribution['license']=='CC BY 4.0' and attribution['attribution'] in doc_text and attribution['attribution'] in ppt_text
    assert report['run_id'] in doc_text and report['run_id'] in ppt_text
    assert not era5['traffic_assignment_rerun'] and not era5['two_dimensional_hydrodynamics']
    manifest['verification']['latest_tests_passed']=era5['tests_passed']
    manifest['longgang_era5_surface']={'path':era5['path'],'calibrated':False,
        'rain_source':'ERA5_reanalysis_via_Open_Meteo','observed_gauges':False,
        'two_dimensional_hydrodynamics':False,'traffic_assignment_rerun':False,
        'consistency_checks':len(report['checks']),
        'tests_report':record(ROOT/era5['tests_report']),
        'independent_numerical_audit':record(ROOT/era5['audit']),
        'rainfall_attribution':record(evidence/'era5_attribution.json')}
if data.get('longgang_adaptive'):
    adaptive=data['longgang_adaptive']; evidence=ROOT/'docs/validation/longgang_adaptive'
    report=json.loads((evidence/'validation_report.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/adaptive['audit']).read_text(encoding='utf-8'))
    worldcover=json.loads((ROOT/adaptive['worldcover_source']).read_text(encoding='utf-8'))
    robust=json.loads((ROOT/adaptive['robustness_report']).read_text(encoding='utf-8'))
    index=json.loads((evidence/'evidence_index.json').read_text(encoding='utf-8'))
    latest=ET.parse(ROOT/adaptive['tests_report']).getroot().find('testsuite')
    assert int(latest.attrib['tests'])==adaptive['tests_passed']==165
    assert int(latest.attrib['errors'])==int(latest.attrib['failures'])==0
    assert report==adaptive['report'] and report['run_id']==audit['run_id']==Path(adaptive['path']).name
    assert audit['passed'] and not report['calibrated'] and not report['include_dapeng']
    assert audit['independent_scatter_add_road_depth_values']==19722240
    assert audit['source_arcs_partitioned_once']==451801 and audit['frozen_depth_mapped_arcs_checked']==86807
    assert audit['traffic_ledgers_checked']==52 and audit['exact_feasible_combinations']==15
    assert audit['independent_pareto_masks']==report['exact_pareto_masks']==[0,8,9,11]
    assert report['recommended_mask']==robust['recommended_mask']==9
    assert report['recommended_sites']==[0,3] and report['nsga2_front_recall_by_seed']=={'42':1.0,'43':1.0,'44':1.0}
    for item in index['files']:
        actual=record(evidence/item['path'])
        assert actual['sha256']==item['sha256'] and actual['bytes']==item['bytes'],item['path']
    for item in ['9.8871%','5.7642%','FIFO','未实测标定',report['run_id'],robust['run_id']]:
        assert item in doc_text and item in ppt_text,item
    assert worldcover['license']=='CC BY 4.0' and worldcover['attribution'] in doc_text and worldcover['attribution'] in ppt_text
    base,recommended=report['worst_case_base_objectives'],report['worst_case_recommended_objectives']
    assert math.isclose((base[0]-recommended[0])/base[0]*100,9.8871,abs_tol=0.00005)
    sensitivities={x['mask']:x for x in report['traffic_sensitivities'] if x['destinations_per_origin']==4}
    assert math.isclose((1-sensitivities[9]['extra_generalized_vehicle_hours']/sensitivities[0]['extra_generalized_vehicle_hours'])*100,5.7642,abs_tol=0.00005)
    assert all(x['extra_cost_reduction_vehicle_hours']>0 for x in robust['comparison'])
    before=ROOT/'.cache/document-sync-20261119-adaptive/before/开题与阶段进展汇报.pptx'
    with ZipFile(before) as source,ZipFile(pptpath) as final_ppt:
        parts=[n for n in source.namelist() if n.startswith('ppt/slides/charts/') or n.startswith('ppt/embeddings/')]
        assert len(parts)==42
        assert all(source.read(n)==final_ppt.read(n) for n in parts)
    manifest['active_research']['traffic_assignment_rerun_for_longgang']=True
    manifest['active_research']['sampled_dynamic_loading_only']=True
    manifest['verification']['latest_tests_passed']=165
    manifest['verification']['model_tests_rerun_for_this_document_update']=False
    manifest['verification']['preserved_native_chart_workbook_parts']=42
    manifest['longgang_adaptive']={'path':adaptive['path'],'calibrated':False,
        'sampled_dynamic_loading':True,'full_od_dynamic_loading':False,'dynamic_user_equilibrium':False,
        'tests_report':record(ROOT/adaptive['tests_report']),'independent_audit':record(ROOT/adaptive['audit']),
        'evidence_index':record(evidence/'evidence_index.json'),'evidence_files_sha256_checked':len(index['files']),
        'worldcover_source':record(ROOT/adaptive['worldcover_source']),
        'robustness_report':record(ROOT/adaptive['robustness_report']),
        'main_extra_generalized_cost_reduction_percent':(base[0]-recommended[0])/base[0]*100,
        'four_strata_same_subset_reduction_percent':(1-sensitivities[9]['extra_generalized_vehicle_hours']/sensitivities[0]['extra_generalized_vehicle_hours'])*100,
        'engineering_recommendation_validated':False}
if data.get('longgang_sumo'):
    sumo=data['longgang_sumo']; evidence=ROOT/'docs/validation/longgang_sumo'
    index=json.loads((ROOT/sumo['evidence_index']).read_text(encoding='utf-8'))
    audit=json.loads((ROOT/sumo['audit']).read_text(encoding='utf-8'))
    latest=ET.parse(ROOT/sumo['tests_report']).getroot().find('testsuite')
    assert int(latest.attrib['tests'])==sumo['tests_passed']==171
    assert int(latest.attrib['failures'])==int(latest.attrib['errors'])==0
    assert json.loads((evidence/'status.json').read_text(encoding='utf-8'))['status']=='complete'
    assert audit['source_sha_verified']==12 and audit['source_sumo_arcs']==4969
    assert audit['planned_routes_checked']==3588 and audit['road_depth_values_checked']==168946
    for item in index['files']:
        assert record(evidence/item['path'])['sha256']==item['sha256'],item['path']
    for scenario,arrived in zip(['dry','rain_departure','rain_rolling','governed_departure','governed_rolling'],[3588,877,877,1230,1230]):
        r=json.loads((evidence/f'cases/{scenario}/result.json').read_text(encoding='utf-8'))
        a=next(x for x in audit['scenarios'] if x['scenario']==scenario)
        assert r==sumo['results'][scenario] and r['planned']==3588 and r['arrived']==arrived
        assert r['planned']==sum(r[k] for k in ['invalid','external_pending','sumo_pending','running','arrived'])
        assert r['vehicle_seconds']==a['vehicle_seconds_replayed']
        assert r['generalized_vehicle_seconds']==r['vehicle_seconds']+7200*(r['unfinished']+r['invalid'])
        assert all(r[k]==0 for k in ['route_changes','teleports','collision_vehicle_events','balance_error'])
    assert audit['routing_probe']['passed'] and audit['routing_probe']['arrived']==1
    assert audit['capacity_probe'][2]['observed_discharge_veh_h_600_to_1200']==426
    for value in [Path(sumo['path']).name,'168,946','353','426','5%','0.30 m']:
        assert value in doc_text and value in ppt_text,value
    assert not sumo['calibrated'] and sumo['demand_fraction']==0.05
    manifest['verification']['latest_tests_passed']=171
    manifest['longgang_sumo']={'path':sumo['path'],'scope':sumo['scope'],
        'demand_fraction':0.05,'planned_visits':3588,'calibrated':False,'full_longgang':False,
        'arrived_by_scenario':{k:r['arrived'] for k,r in sumo['results'].items()},
        'actual_route_changes':0,'additional_rolling_benefit_observed':False,
        'capacity_proxy_exactly_matches_reference':False,'actual_osg_screenshot':True,
        'real_terrain_buildings_water_surface':False,
        'tests_report':record(ROOT/sumo['tests_report']),'independent_audit':record(ROOT/sumo['audit']),
        'evidence_index':record(ROOT/sumo['evidence_index']),'evidence_files_sha256_checked':len(index['files'])}
if data.get('digital_twin'):
    twin=data['digital_twin']
    audit=json.loads((ROOT/twin['data_audit']).read_text(encoding='utf-8'))
    visual=json.loads((ROOT/twin['visual_review']).read_text(encoding='utf-8'))
    assert audit['source_run']==twin['source_run'] and audit['source_road_shapes_matched']==4969
    assert all(c['frames']==14401 and c['every_second_running_count_matches_archived_SUMO'] and c['all_minute_statistics_match'] for c in audit['cases'].values())
    assert sum(c['vehicle_samples'] for c in audit['cases'].values())==twin['vehicle_samples']==1386694
    assert [audit['cases'][c]['arrived'] for c in ['dry','rain_rolling','governed_rolling']]==[3588,877,1230]
    assert twin['offline_replay'] and not twin['measured_city_model'] and twin['minute_rows']==720
    assert visual['pytest'].startswith('171 passed') and visual['final_console_warning_error_count']==0
    for item in visual['screenshots']:assert record(ROOT/item['path'])['sha256']==item['sha256']
    for name,digest in audit['sha256'].items():
        assert record(ROOT/'dashboard/digital-twin/data'/name)['sha256']==digest
    for text in ['Three.js','14,401','1,386,694','程序化','离线','8766']:
        assert text in doc_text and text in ppt_text,text
    before=ROOT/'.cache/document-sync-20261119-digital-twin/before/开题与阶段进展汇报.pptx'
    with ZipFile(before) as source,ZipFile(pptpath) as final_ppt:
        parts=[n for n in source.namelist() if n.startswith('ppt/slides/charts/') or n.startswith('ppt/embeddings/')]
        assert len(parts)==42 and all(source.read(n)==final_ppt.read(n) for n in parts)
    manifest['digital_twin']={'source_run':twin['source_run'],'replay_path':twin['replay_path'],
        'source_commit':twin['source_commit'],'offline_replay':True,'measured_city_model':False,
        'frame_seconds':1,'frames_per_case':14401,'vehicle_samples':1386694,'minute_rows':720,
        'data_audit':record(ROOT/twin['data_audit']),'visual_review':record(ROOT/twin['visual_review']),
        'local_data_sha_files_checked':len(audit['sha256']),'screenshots_sha_checked':len(visual['screenshots']),
        'model_or_browser_tests_rerun_for_document_update':False}
if data.get('longgang_sumo_full'):
    full=data['longgang_sumo_full']; evidence=ROOT/'docs/validation/longgang_sumo_full'
    index=json.loads((ROOT/full['evidence_index']).read_text(encoding='utf-8'))
    audit=json.loads((ROOT/full['audit']).read_text(encoding='utf-8'))
    result=json.loads((evidence/'cases/dry/result.json').read_text(encoding='utf-8'))
    latest=ET.parse(ROOT/full['tests_report']).getroot().find('testsuite')
    assert int(latest.attrib['tests'])==full['tests_passed']==186
    assert int(latest.attrib['failures'])==int(latest.attrib['errors'])==0
    for item in index['files']:assert record(evidence/item['path'])['sha256']==item['sha256'],item['path']
    assert result==full['result'] and result['planned']==11506 and result['invalid']==872 and result['arrived']==10634
    assert result['planned']==sum(result[k] for k in ['arrived','invalid','running','sumo_pending','external_pending'])
    assert all(result[k]==0 for k in ['running','sumo_pending','external_pending','balance_error','teleports','collision_vehicle_events'])
    assert audit['source_sumo_arcs']==151701 and audit['whole_district_arcs_checked']==86804
    assert audit['vehicle_seconds_independent']==result['vehicle_seconds']==12473271
    assert result['generalized_vehicle_seconds']==18751671==result['vehicle_seconds']+7200*result['invalid']
    assert audit['actual_injected_routes_checked']==result['arrived'] and audit['hourly_records_checked']==4
    with (evidence/'cases/dry/hourly_performance.csv').open(encoding='utf-8-sig',newline='') as f: hourly=list(csv.DictReader(f))
    assert len(hourly)==4
    resource=json.loads((evidence/'resources_summary.json').read_text(encoding='utf-8'))
    budget=json.loads((evidence/'runtime_budget.json').read_text(encoding='utf-8'))
    assert math.isclose(resource['total_wall_seconds']/60,16.6678,abs_tol=.001)
    assert math.isclose(resource['peak_combined_rss_mib']/1024,2.5254,abs_tol=.001)
    assert math.isclose(budget['five_case_forecast']['planning_allowance_seconds']/3600,5.6269,abs_tol=.001)
    for text in ['86,804','151,701','11,506','10,634','872','16.67','2.525','条件预算','Ubuntu']:
        assert text in doc_text and text in ppt_text,text
    assert not full['calibrated'] and full['full_district_dry_only'] and not full['gui_replay_completed']
    manifest['verification']['latest_tests_passed']=186
    manifest['longgang_sumo_full']={'path':full['path'],'source_commit':full['source_commit'],'demand_fraction':.05,
      'planned':11506,'valid_arrived':10634,'invalid':872,'full_district_dry_only':True,'calibrated':False,
      'actual_total_wall_seconds':resource['total_wall_seconds'],'peak_sampled_combined_rss_mib':resource['peak_combined_rss_mib'],
      'five_cases_and_iterations_are_forecasts':True,'full_district_3d_replay_completed':False,
      'evidence_index':record(ROOT/full['evidence_index']),'independent_audit':record(ROOT/full['audit']),
      'tests_report':record(ROOT/full['tests_report']),'evidence_files_sha256_checked':len(index['files'])}
if data.get('migration_5090'):
    migration=data['migration_5090']; evidence=ROOT/migration['evidence']
    for name,digest in migration['evidence_sha256'].items():assert record(evidence/name)['sha256']==digest,name
    qa=json.loads((evidence/'roundtrip_qa.json').read_text(encoding='utf-8'))
    smoke=json.loads((evidence/'sumo_smoke_windows.json').read_text(encoding='utf-8'))
    assert qa['export_receive']=='passed' and len(qa['checks'])==5
    assert all(x['arrived']==3 and x['balance_error']==0 for x in qa['checks'])
    assert smoke['headless_sumo_traci_smoke']=='passed: one vehicle arrived' and not smoke['cuda_used_by_solver']
    latest=ET.parse(evidence/'tests.xml').getroot().find('testsuite')
    assert int(latest.attrib['tests'])==186 and int(latest.attrib['errors'])==int(latest.attrib['failures'])==0
    assert migration['local_roundtrip_passed'] and not migration['target_ubuntu_accepted'] and not migration['gpu_solver']
    manifest['migration_5090']={'local_roundtrip_passed':True,'local_fixture_vehicles':3,'target_ubuntu_accepted':False,
       'gpu_solver':False,'research_results':False,'roundtrip_qa':record(evidence/'roundtrip_qa.json'),
       'tests_report':record(evidence/'tests.xml'),'evidence_files_sha256_checked':len(migration['evidence_sha256'])}
(target/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
