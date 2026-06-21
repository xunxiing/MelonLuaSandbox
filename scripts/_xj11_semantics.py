"""Analyze xj11 chip semantics: what data types flow through each node."""
import json
from melon_lua import read_melsave
from melon_lua.vpcompile.graph import parse_chip_graph

doc = read_melsave('temp/xj11/xj 11(1).melsave')

# idx=4 is the simplest (24 nodes, trig chain)
vp = doc.objects[4]
sm = vp.raw['saveMetaDatas']
graph = None
for m in sm:
    if m.get('key') == 'chip_graph':
        graph = json.loads(m['stringValue'])
        break

ir = parse_chip_graph(graph)
print(f'=== idx=4 (24 nodes) data flow ===')
print(f'topo order:')
for uid in ir.topo_order:
    n = ir.nodes[uid]
    gdt = n.raw.get('GateDataType', '?')
    in_types = [inp.get('DataType', '?') for inp in n.inputs]
    out_types = [out.get('DataType', '?') for out in n.outputs]
    mcid = n.raw.get('MechanicConnectionId', '')
    print(f'  {n.name:20s} gdt={gdt:8s} in={in_types} out={out_types} mcid={mcid}')

# Count how many nodes are vector vs scalar
vec_nodes = 0
scalar_nodes = 0
for uid in ir.nodes:
    n = ir.nodes[uid]
    gdt = n.raw.get('GateDataType', '')
    if gdt == 'Vector':
        vec_nodes += 1
    else:
        scalar_nodes += 1
print(f'\nVector nodes: {vec_nodes}, Scalar/other: {scalar_nodes}')
