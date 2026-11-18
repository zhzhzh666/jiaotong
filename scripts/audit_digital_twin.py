"""Independently audit viewer geometry, every frame count and minute statistics."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT/'dashboard/digital-twin/data'
    net = json.loads((folder/'network.json').read_text(encoding='utf-8'))
    archived = ROOT/net['source_run']
    source_net = ET.parse(archived/'raw/network.net.xml').getroot()
    edges = pd.read_csv(archived/'raw/source_sumo_mapping.csv')
    shapes = {e.attrib['id']: e.find('lane').attrib['shape'] for e in source_net.findall('edge') if e.attrib.get('function') != 'internal'}
    assert [r['id'] for r in net['roads']] == edges.edge_id.tolist()
    for road in net['roads']:
        expected = [[round(float(v),2) for v in p.split(',')[:2]] for p in shapes[road['id']].split()]
        assert road['points'] == expected
    states = np.load(archived/'raw/road_states.npz')
    report = {'source_run': net['source_run'], 'source_road_shapes_matched': len(net['roads']), 'cases': {}}
    for name in ['dry', 'rain_rolling', 'governed_rolling']:
        data = json.loads((folder/(name+'.json')).read_text(encoding='utf-8'))
        assert data['sample_seconds'] == 1
        assert len(data['frames']) == 14401
        assert len(set(data['ids'])) == len(data['ids'])
        summary = {int(float(row.attrib['time']))+1:int(row.attrib['running']) for row in ET.parse(archived/'cases'/name/'summary.xml').getroot().findall('step')}
        total = 0
        for t, frame in enumerate(data['frames']):
            assert frame['t'] == t
            assert len(frame['v']) == len(set(v[0] for v in frame['v']))
            if t:
                assert len(frame['v']) == summary[t], (name,t,len(frame['v']),summary[t])
            for v in frame['v']:
                assert len(v) == 5 and 0 <= v[0] < len(data['ids'])
                assert np.isfinite(v).all() and v[4] >= 0
                assert -50 < v[1] < 3050 and -50 < v[2] < 3050
            total += len(frame['v'])
        expected_series = pd.read_csv(archived/'cases'/name/'traffic_series.csv')
        pd.testing.assert_frame_equal(pd.DataFrame(data['series']), expected_series, check_dtype=False)
        if name != 'dry':
            raw = states['baseline' if name == 'rain_rolling' else 'governed']
            assert np.allclose(net['depths'][name], np.where(np.isfinite(raw), raw, -1), atol=.000051)
        report['cases'][name] = {'frames':len(data['frames']), 'unique_vehicles':len(data['ids']),
                                'vehicle_samples':total,'every_second_running_count_matches_archived_SUMO':True,
                                'all_minute_statistics_match':True, 'arrived':data['result']['arrived']}
    report['sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*.json'))}
    dest = ROOT/'docs/validation/digital_twin/data_audit.json'
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
