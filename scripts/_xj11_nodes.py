"""Examine xj11 node structure and connection format."""
import json
from melon_lua import read_melsave

doc = read_melsave('temp/xj11/xj 11(1).melsave')
vp = doc.objects[4]  # 24-node chip
sm = vp.raw['saveMetaDatas']
graph = None
for m in sm:
    if m.get('key') == 'chip_graph':
        graph = json.loads(m['stringValue'])
        break

nodes = graph['Nodes']
print(f'Total nodes: {len(nodes)}')
print()

# Print first 5 nodes in detail
for i, n in enumerate(nodes[:5]):
    print(f'--- Node {i} ---')
    print(f'  Id: {n.get("Id")}')
    print(f'  OperationType: {n.get("OperationType")}')
    print(f'  GateDataType: {n.get("GateDataType")}')
    print(f'  MechanicConnectionId: {n.get("MechanicConnectionId")}')
    inputs = n.get('Inputs') or []
    outputs = n.get('Outputs') or []
    print(f'  Inputs ({len(inputs)}):')
    for j, inp in enumerate(inputs):
        print(f'    [{j}] {json.dumps(inp, ensure_ascii=False)[:200]}')
    print(f'  Outputs ({len(outputs)}):')
    for j, out in enumerate(outputs):
        print(f'    [{j}] {json.dumps(out, ensure_ascii=False)[:200]}')
    sd = n.get('SaveData')
    if sd:
        print(f'  SaveData: {json.dumps(sd, ensure_ascii=False)[:200]}')
    print()

# Find how connections work - look for "From" or "Source" or "Node" references in Inputs
print('=== Connection analysis ===')
for i, n in enumerate(nodes):
    inputs = n.get('Inputs') or []
    for j, inp in enumerate(inputs):
        if isinstance(inp, dict):
            keys = list(inp.keys())
            # Look for connection-like fields
            conn_fields = [k for k in keys if k.lower() in ('from', 'source', 'node', 'nodeid', 'output', 'outputindex', 'connection', 'link', 'wire')]
            if conn_fields:
                print(f'Node {i} ({n.get("OperationType")}) input[{j}] conn fields: {conn_fields}')
                for cf in conn_fields:
                    print(f'  {cf} = {inp[cf]!r}')
                break
