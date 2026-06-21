"""Parse xj11 VPchip chip_graph and compile to Lua."""
import json
from melon_lua import read_melsave

doc = read_melsave('temp/xj11/xj 11(1).melsave')

vp_indices = [i for i, o in enumerate(doc.objects) if o.object_id == 248]
print(f'Found {len(vp_indices)} VPchips at indices: {vp_indices}')

for vi in vp_indices:
    vp = doc.objects[vi]
    print(f'\n=== VPchip idx={vi} inst={vp.instance_id} ===')
    sm = vp.raw.get('saveMetaDatas')
    if not isinstance(sm, list):
        continue
    for m in sm:
        if not isinstance(m, dict):
            continue
        if m.get('key') == 'chip_graph':
            sv = m.get('stringValue')
            if not sv:
                continue
            try:
                graph = json.loads(sv)
            except Exception as e:
                print(f'  parse error: {e}')
                continue
            nodes = graph.get('Nodes') or []
            conns = graph.get('Connections') or graph.get('connections') or []
            print(f'  graph keys: {list(graph.keys())}')
            print(f'  nodes: {len(nodes)}')
            print(f'  connections: {len(conns)}')
            if nodes:
                print(f'  first node keys: {list(nodes[0].keys())[:15]}')
                # count operation types
                op_counts = {}
                for n in nodes:
                    op = n.get('OperationType') or n.get('operationType') or n.get('Op') or n.get('Type')
                    op_counts[op] = op_counts.get(op, 0) + 1
                print(f'  operation types: {op_counts}')
            break
