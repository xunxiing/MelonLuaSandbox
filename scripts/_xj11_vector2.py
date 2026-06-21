"""Check how Root/Position/Velocity (vector producers) emit values."""
import json
from melon_lua import read_melsave
from melon_lua.vpcompile.graph import parse_chip_graph
from melon_lua.vpcompile.nodes import REGISTRY

doc = read_melsave('temp/xj11/xj 11(1).melsave')
vp = doc.objects[4]
sm = vp.raw['saveMetaDatas']
graph = None
for m in sm:
    if m.get('key') == 'chip_graph':
        graph = json.loads(m['stringValue'])
        break

ir = parse_chip_graph(graph)

# Show what Root emits
for uid, n in ir.nodes.items():
    if n.name == 'Root':
        print(f'Root node {uid}:')
        print(f'  MechanicConnectionId: {n.raw.get("MechanicConnectionId")}')
        print(f'  GateDataType: {n.raw.get("GateDataType")}')
        emitter = REGISTRY.get('Root')
        if emitter:
            lines = emitter(uid, ['0'], n)
            for l in lines:
                print(f'  emit: {l}')
        print()

# Show what Position emits
for uid, n in ir.nodes.items():
    if n.name == 'Position':
        print(f'Position node {uid}:')
        emitter = REGISTRY.get('Position')
        if emitter:
            lines = emitter(uid, ['0'], n)
            for l in lines:
                print(f'  emit: {l}')
        print()
        break

# Show what Add emits (vector add vs scalar add?)
for uid, n in ir.nodes.items():
    if n.name == 'Add':
        print(f'Add node {uid}:')
        print(f'  GateDataType: {n.raw.get("GateDataType")}')
        for i, inp in enumerate(n.inputs):
            print(f'  input[{i}] DataType={inp.get("DataType")}')
        emitter = REGISTRY.get('Add')
        if emitter:
            lines = emitter(uid, ['G["a"]', 'G["b"]'], n)
            for l in lines:
                print(f'  emit: {l}')
        print()
        break
