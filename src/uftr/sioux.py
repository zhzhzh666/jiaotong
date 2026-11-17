"""Parse TransportationNetworks TNTP originals without changing benchmark units."""
from pathlib import Path
import re
import math
import networkx as nx
import pandas as pd

from .archive import write_json
from .osm_download import fetch


def download_sioux(directory,settings):
    directory.mkdir(parents=True,exist_ok=False)
    commit=fetch(settings['api_commit_url'],directory/'repository_commit.json').json()['sha']
    records=[]
    for name in ['SiouxFalls_net.tntp','SiouxFalls_node.tntp','SiouxFalls_trips.tntp','SiouxFalls_flow.tntp','README.md']:
        url=f'{settings["raw_base"]}/{commit}/SiouxFalls/{name}'
        fetch(url,directory/name)
        records.append(url)
    # The project README contains the repository licensing statement, not an invented license.
    fetch(f'{settings["raw_base"]}/{commit}/README.md',directory/'repository_README.md')
    write_json(directory/'source.json',{'repository':settings['repository'],'commit':commit,'urls':records,'units_policy':'Keep TNTP original units; do not assume veh/h or metres. See upstream README.','license_policy':'Originals retained locally, upstream licensing statements saved; review before redistribution.'})


def parse_sioux(directory,output):
    text=(directory/'SiouxFalls_net.tntp').read_text(encoding='utf-8-sig')
    metadata={k.strip():v.strip() for k,v in re.findall(r'<([^>]+)>\s*([^\r\n]*)',text)}
    rows=[]
    columns=['u','v','capacity_original','length_original','free_flow_time_original','bpr_b','bpr_power','speed_original','toll_original','link_type']
    for line in text.splitlines():
        if re.match(r'^\s*\d',line):
            values=line.replace(';','').split()
            if len(values)!=10: raise ValueError('invalid TNTP link row')
            row=dict(zip(columns,map(float,values)))
            if any(not math.isfinite(v) for v in row.values()) or row['u']!=int(row['u']) or row['v']!=int(row['v']): raise ValueError('invalid TNTP finite attributes or node IDs')
            row['u']=int(row['u']); row['v']=int(row['v']); rows.append(row)
    frame=pd.DataFrame(rows)
    if len(frame)!=int(metadata['NUMBER OF LINKS']): raise ValueError('TNTP link count mismatch')
    g=nx.DiGraph()
    for r in rows:
        if g.has_edge(r['u'],r['v']): raise ValueError('duplicate TNTP arc')
        if r['capacity_original']<=0 or r['free_flow_time_original']<=0: raise ValueError('invalid TNTP positive attributes')
        g.add_edge(r['u'],r['v'],**r)
    if len(g)!=int(metadata['NUMBER OF NODES']): raise ValueError('TNTP node count mismatch')
    trips=(directory/'SiouxFalls_trips.tntp').read_text(encoding='utf-8-sig')
    pairs=[]; origin=None
    for line in trips.splitlines():
        match=re.search(r'Origin\s+(\d+)',line)
        if match: origin=int(match[1]); continue
        if origin is not None:
            for dest,demand in re.findall(r'(\d+)\s*:\s*([\d.eE+-]+)\s*;',line):
                if origin not in g or int(dest) not in g or not math.isfinite(float(demand)) or float(demand)<0: raise ValueError('invalid TNTP OD')
                pairs.append({'origin':origin,'destination':int(dest),'demand_original':float(demand)})
    if len({(x['origin'],x['destination']) for x in pairs})!=len(pairs): raise ValueError('duplicate TNTP OD')
    expected=float(re.search(r'<TOTAL OD FLOW>\s*([\d.eE+-]+)',trips)[1])
    total=sum(p['demand_original'] for p in pairs)
    if not math.isfinite(expected) or abs(total-expected)>1e-6: raise ValueError('TNTP demand total mismatch')
    coords=[]
    for line in (directory/'SiouxFalls_node.tntp').read_text(encoding='utf-8-sig').splitlines():
        if re.match(r'^\s*\d',line):
            values=line.replace(';','').split()
            coords.append({'node_id':int(values[0]),'x_original':float(values[1]),'y_original':float(values[2])})
    if {x['node_id'] for x in coords}!=set(g) or len(coords)!=len(g) or any(not math.isfinite(x[k]) for x in coords for k in ['x_original','y_original']): raise ValueError('TNTP node coordinate mismatch')
    solution=[]
    for line in (directory/'SiouxFalls_flow.tntp').read_text(encoding='utf-8-sig').splitlines():
        if re.match(r'^\s*\d',line):
            u,v,volume,cost=line.split()
            solution.append({'u':int(u),'v':int(v),'volume_original':float(volume),'cost_original':float(cost)})
    if {(x['u'],x['v']) for x in solution}!=set(g.edges) or len(solution)!=len(g.edges) or any(not math.isfinite(x[k]) or x[k]<0 for x in solution for k in ['volume_original','cost_original']): raise ValueError('TNTP reference flow mismatch')
    output.mkdir(parents=True,exist_ok=False)
    frame.to_csv(output/'sioux_links.csv',index=False)
    pd.DataFrame(pairs).to_csv(output/'sioux_od.csv',index=False)
    pd.DataFrame(coords).to_csv(output/'sioux_nodes.csv',index=False)
    pd.DataFrame(solution).to_csv(output/'sioux_reference_flow.csv',index=False)
    stats={'nodes':len(g),'directed_edges':len(rows),'strongly_connected':nx.is_strongly_connected(g),'od_records':len(pairs),'nonzero_od_pairs':sum(p['demand_original']>0 for p in pairs),'total_demand_original':total,'metadata':metadata,'all_pairs_reachable':all(len(lengths)==len(g) for _,lengths in nx.all_pairs_dijkstra_path_length(g,weight='free_flow_time_original')),'units':'Original TNTP benchmark units retained. Not yet converted to Shenzhen m/s/veh/h.','assignment_status':'Not run; equilibrium benchmark validation belongs to Phase 06.'}
    stats['upstream_unit_notes']={'free_flow_time':'0.01 hour according to upstream Source/History; keep native values for benchmarking','distance':'arbitrarily set equal to native free-flow time, not physical metres','demand':'0.1 of original daily flows; upstream calls approximate hourly','coordinates':'upstream says artificial diagram coordinates; not treated as surveyed geometry','reference_solution':'Downloaded best-known solution is external reference, not our solver output'}
    stats['coordinate_records']=len(coords); stats['reference_flow_records']=len(solution)
    write_json(output/'sioux_statistics.json',stats)
    return stats
