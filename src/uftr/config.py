"""Validated configuration shared by future phase entry points."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import math
import yaml


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


def validate_config(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("configuration must be a mapping")
    result = deepcopy(data)
    for key in ("project", "phase", "region", "scenario", "strategy"):
        if not isinstance(result.get(key), str) or not result[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    if result["phase"] not in {f"{n:02d}" for n in range(14)}:
        raise ValueError("phase must be a string between 00 and 13")
    seed = result.get("seed")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer in [0, 2**32)")
    if type(result.get("workers")) is not int or result["workers"] < 1:
        raise ValueError("workers must be a positive integer")
    for section in ("outputs", "simulation", "units", "crs", "models"):
        if not isinstance(result.get(section), dict):
            raise ValueError(f"{section} must be a mapping")
    output = result["outputs"]
    if not isinstance(output.get("root"), str) or not output["root"]:
        raise ValueError("outputs.root must be a path string")
    _positive(output.get("dpi"), "outputs.dpi")
    if output.get("retention") != "key-figures-and-screenshots":
        raise ValueError("unsupported retention policy")
    sim = result["simulation"]
    _positive(sim.get("duration_hours"), "duration_hours")
    _positive(sim.get("interval_minutes"), "interval_minutes")
    steps = sim["duration_hours"] * 60 / sim["interval_minutes"]
    if not math.isclose(steps, round(steps), abs_tol=1e-9):
        raise ValueError("simulation window must contain whole intervals")
    expected = {"distance": "m", "time": "s", "flow": "veh/h", "capacity": "veh/h", "flood_depth": "m"}
    if result["units"] != expected:
        raise ValueError(f"units must be {expected}")
    if result["crs"] != {"source": "EPSG:4326", "projected": "EPSG:32650"}:
        raise ValueError("initial Shenzhen CRS convention is EPSG:4326 / EPSG:32650")
    model = result["models"]
    for key in ("closure_depth_m", "bpr_alpha", "bpr_beta", "relative_gap_target"):
        _positive(model.get(key), key)
    weights = model.get("resilience_weights", {})
    if set(weights) != {"structure", "performance", "functionality"}:
        raise ValueError("three resilience weights are required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError("weights must be finite and nonnegative")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("resilience weights must sum to 1")
    if result['phase']=='01':
        network=result.get('network',{})
        bounds=network.get('small_bbox',[])
        if len(bounds)!=4 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in bounds) or not (113<bounds[0]<bounds[2]<115 and 22<bounds[1]<bounds[3]<24):
            raise ValueError('small_bbox must be WGS84 Shenzhen west,south,east,north')
        for key in ['tile_degrees','minimum_tile_degrees','buffer_m','max_requests','timeout_s','routing_sample_origins']:
            _positive(network.get(key),'network.'+key)
        if network['tile_degrees']>.1 or network['minimum_tile_degrees']>network['tile_degrees']:
            raise ValueError('invalid bounded OSM tile size')
        if not isinstance(network.get('request_pause_s'),(float,int)) or network['request_pause_s']<1:
            raise ValueError('official OSM API requires at least 1 second request spacing')
        attributes=network.get('attributes',{})
        if attributes.get('projected_crs')!='EPSG:32650' or network.get('projected_crs')!='EPSG:32650':
            raise ValueError('road distance CRS must be EPSG:32650')
        _positive(attributes.get('free_flow_factor'),'free_flow_factor')
        if attributes['free_flow_factor']>1: raise ValueError('free-flow factor must not exceed speed limit')
        window=network.get('study_window_bbox',[])
        if len(window)!=4 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in window) or not (window[0]<window[2] and window[1]<window[3]): raise ValueError('study_window_bbox must be ordered WGS84 bounds')
        if 'fallback' not in attributes.get('defaults',{}): raise ValueError('fallback road attributes required')
        for road,values in attributes['defaults'].items():
            for key in ['speed_kph','lanes_per_direction','capacity_per_lane_veh_h']: _positive(values.get(key),road+'.'+key)
            if type(values['lanes_per_direction']) is not int: raise ValueError('lanes must be integer')
    if result['phase']=='02':
        spatial=result.get('spatial',{})
        for field in ['network_directory','osm_snapshot']:
            p=spatial.get(field)
            if not isinstance(p,str) or not p or Path(p).is_absolute() or '..' in Path(p).parts:
                raise ValueError('spatial input paths must be relative and inside project')
        matching=spatial.get('matching',{})
        for field in ['search_radius_m','max_match_distance_m','high_distance_m','medium_distance_m','high_gap_m','medium_gap_m']:
            _positive(matching.get(field),field)
        if not (matching['high_distance_m']<=matching['medium_distance_m']<=matching['max_match_distance_m']<=matching['search_radius_m']):
            raise ValueError('invalid match distance ordering')
        if matching['high_gap_m']<matching['medium_gap_m']:raise ValueError('high confidence requires larger ambiguity gap')
        risk=spatial.get('synthetic_risk',{})
        for field in ['count','clusters']:
            if type(risk.get(field)) is not int or risk[field]<1:raise ValueError('risk counts must be positive integers')
        if risk['clusters']>risk['count']:raise ValueError('clusters exceed risk count')
        for field in ['cluster_sd_m','elevation_scale_m','max_dsm_m']:_positive(risk.get(field),field)
        sources=spatial.get('sources',{})
        if not sources:raise ValueError('source list required')
        for filename,spec in sources.items():
            if Path(filename).name!=filename or not spec.get('url','').startswith('https://') or not spec.get('license'):
                raise ValueError('source must have safe filename, HTTPS URL and explicit license')
        if not isinstance(spatial.get('rain_station'),str):raise ValueError('rain station ID must be a string')
    if result['phase']=='03':
        demand=result.get('demand',{})
        for field in ['network_directory','spatial_directory']:
            value=demand.get(field)
            if not isinstance(value,str) or not value or Path(value).is_absolute() or '..' in Path(value).parts:
                raise ValueError('demand input paths must be relative inside project')
        for field in ['zone_size_m','max_connector_distance_m','access_speed_kph','intrazonal_time_s',
                      'minimum_impedance_s','unreachable_impedance_s','gravity_beta_per_s',
                      'person_trip_rate_per_hour','motorized_person_trip_share','vehicle_occupancy','ipf_tolerance']:
            _positive(demand.get(field),'demand.'+field)
        if demand['motorized_person_trip_share']>1:raise ValueError('trip share exceeds one')
        for field in ['boundary_inbound_fraction','boundary_outbound_fraction','attraction_population_share']:
            value=demand.get(field)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
                raise ValueError('invalid demand fraction '+field)
        for field in ['boundary_gateways','ipf_max_iterations']:
            if type(demand.get(field)) is not int or demand[field]<1:raise ValueError('invalid demand integer '+field)
        if set(demand.get('periods',{}))!={'offpeak','morning_peak','evening_peak'}:raise ValueError('three demand periods required')
        for period,spec in demand['periods'].items():_positive(spec.get('factor'),period+'.factor')
        if not demand.get('facility_weights'):raise ValueError('facility weights required')
        for field,value in demand['facility_weights'].items():_positive(value,'facility weight '+field)
    if result['phase']=='04':
        s=result.get('flood',{})
        for k in ['correlation_length_m','base_peak_m','rise_hours','recession_hours']:_positive(s.get(k),'flood.'+k)
        for k in ['log_depth_sd','delay_sd_hours','peak_hour']:
            if not isinstance(s.get(k),(float,int)) or not math.isfinite(s[k]) or s[k]<0:raise ValueError('invalid '+k)
        if set(s.get('scenario_multipliers',{}))!={'normal','general','severe','extreme'} or s['scenario_multipliers']['normal']!=0:raise ValueError('four scenarios with dry normal required')
        values=[s['scenario_multipliers'][k] for k in ['normal','general','severe','extreme']]
        if any(not math.isfinite(x) for x in values) or not all(a<b for a,b in zip(values,values[1:])):raise ValueError('scenario intensities must increase')
    if result['phase'] in {'04','05','06','07','08','09','10','11','12','13'}:
        for section in ['flood','impact','assignment','research','sumo']:
            for key,value in result.get(section,{}).items():
                if key in {'points','mapping','edges','dictionary','depths','sioux_directory','network_root','od','demand_directory','facilities','full_depths','selection'}:
                    if not isinstance(value,str) or Path(value).is_absolute() or '..' in Path(value).parts:raise ValueError('input path must stay within project: '+key)
    if result['phase'] in {'07','08','09','10','11'}:
        s=result.get('research',{})
        for k in ['rho_s','gap_target','max_iterations','interval_s','candidate_limit','access_speed_kph']:_positive(s.get(k),'research.'+k)
        if 86400%s['interval_s']:raise ValueError('research interval must divide 24 hours')
        if not 0<=s.get('effect',-1)<=1:raise ValueError('effect must be in [0,1]')
        if s.get('budget',-1)<0 or s.get('K',-1)<0:raise ValueError('nonnegative budget and K required')
        if result['phase']=='11' and len(set(s.get('seeds',[])))<10:raise ValueError('at least ten distinct seeds required')
    return result


def load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as stream:
        return validate_config(yaml.safe_load(stream))


def time_grid(config: dict) -> list[float]:
    """Return seconds at endpoints; demand belongs to the intervening intervals."""
    sim = config["simulation"]
    count = round(sim["duration_hours"] * 60 / sim["interval_minutes"])
    return [i * sim["interval_minutes"] * 60 for i in range(count + 1)]
