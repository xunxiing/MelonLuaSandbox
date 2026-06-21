"""Inspect Split/Combine/Normalize node structures in xj11."""
import json
from melon_lua import read_melsave
from melon_lua.vpcompile.graph import parse_chip_graph

doc = read_melsave('temp/xj11/xj 11(1).melsave')

for vi in [4, 7, 8, 9]:
    vp = doc.objects[vi]
    sm = vp.raw['saveMetaDatas']
    graph = None
    for m in sm:
        if m.get('key') == 'chip_graph':
            graph = json.loads(m['stringValue'])
            break
    if not graph:
        continue
    ir = parse_chip_graph(graph)
    for uid, n in ir.nodes.items():
        if n.name in ('Split', 'Combine', 'Normalize'):
            print(f'=== idx={vi} {uid} (op={n.name}) ===')
            print(f'  inputs ({len(n.inputs)}):')
            for i, inp in enumerate(n.inputs):
                dt = inp.get('DataType', '?')
                co = inp.get('connectedOutputIdModel')
                co_node = co.get('NodeId', '?') if co else 'none'
                print(f'    [{i}] DataType={dt} from={co_node[:60] if isinstance(co_node,str) else co_node}')
            print(f'  outputs ({len(n.outputs)}):')
            for i, out in enumerate(n.outputs):
                dt = out.get('DataType', '?')
                ci = out.get('ConnectedInputsIds') or []
                print(f'    [{i}] DataType={dt} -> {len(ci)} consumers')
            sd = n.save_data
            if sd:
                print(f'  SaveData: {json.dumps(sd, ensure_ascii=False)[:200]}')
            print()
