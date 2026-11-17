"""Small TNTP fixtures, independent of downloaded files or online services."""
from pathlib import Path
import pytest
from uftr.sioux import parse_sioux

@pytest.fixture
def tntp(tmp_path):
    (tmp_path/'SiouxFalls_net.tntp').write_text('<NUMBER OF ZONES> 2\n<NUMBER OF NODES> 2\n<NUMBER OF LINKS> 2\n<END OF METADATA>\n1 2 10 1 2 .15 4 0 0 1 ;\n2 1 10 1 2 .15 4 0 0 1 ;\n')
    (tmp_path/'SiouxFalls_trips.tntp').write_text('<TOTAL OD FLOW> 5\n<END OF METADATA>\nOrigin 1\n1:0; 2:2;\nOrigin 2\n1:3; 2:0;\n')
    (tmp_path/'SiouxFalls_node.tntp').write_text('Node X Y\n1 0 0 ;\n2 1 1 ;\n')
    (tmp_path/'SiouxFalls_flow.tntp').write_text('From To Volume Cost\n1 2 2 2\n2 1 3 2\n')
    return tmp_path

def test_tntp_counts_mass_balance_and_external_reference(tntp):
    result=parse_sioux(tntp,tntp/'processed')
    assert result['nodes']==2 and result['directed_edges']==2
    assert result['total_demand_original']==5 and result['nonzero_od_pairs']==2
    assert result['all_pairs_reachable'] and result['reference_flow_records']==2
    assert 'Not run' in result['assignment_status']

@pytest.mark.parametrize('filename,before,after,reason',[
    ('SiouxFalls_trips.tntp','2:2;','2:-2;','OD'),
    ('SiouxFalls_trips.tntp','FLOW> 5','FLOW> 7','total'),
    ('SiouxFalls_net.tntp','LINKS> 2','LINKS> 3','count'),
    ('SiouxFalls_node.tntp','2 1 1','3 1 1','coordinate'),
    ('SiouxFalls_flow.tntp','1 2 2 2','1 3 2 2','flow'),
])
def test_corrupt_tntp_is_rejected(tntp,filename,before,after,reason):
    p=tntp/filename; p.write_text(p.read_text().replace(before,after))
    with pytest.raises(ValueError,match=reason): parse_sioux(tntp,tntp/'processed')
