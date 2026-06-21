"""Dump full input/output structure of xj11 nodes."""
import json
from melon_lua import read_melsave

doc = read_melsave('temp/xj11/xj 11(1).melsave')
vp = doc.objects[4]
sm = vp.raw['saveMetaDatas']
graph = None
for m in sm:
    if m.get('key') == 'chip_graph':
        graph = json.loads(m['stringValue'])
        break

nodes = graph['Nodes']

# Node 4 (Split) has inputs with connectedOutputIdModel
n = nodes[4]
print('=== Split node full input[0] ===')
inp = n['Inputs'][0]
print(json.dumps(inp, indent=2, ensure_ascii=False))

print()
print('=== Split node output[1] (has ConnectedInputsIds) ===')
out = n['Outputs'][1]
print(json.dumps(out, indent=2, ensure_ascii=False))

print()
print('=== Root node 0 output[0] ===')
print(json.dumps(nodes[0]['Outputs'][0], indent=2, ensure_ascii=False)[:1500])

print()
# Find connectedOutputIdModel structure
print('=== All connectedOutputIdModel keys across nodes ===')
co_keys = set()
for n in nodes:
    for inp in (n.get('Inputs') or []):
        co = inp.get('connectedOutputIdModel')
        if co:
            co_keys.update(co.keys())
print(co_keys)

print()
print('=== Sample connectedOutputIdModel ===')
for n in nodes:
    for inp in (n.get('Inputs') or []):
        co = inp.get('connectedOutputIdModel')
        if co:
            print(json.dumps(co, indent=2, ensure_ascii=False)[:500])
            break
    else:
        continue
    break
