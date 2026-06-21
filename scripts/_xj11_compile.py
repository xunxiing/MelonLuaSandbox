"""Compile all xj11 VPchips and check for missing emitters."""
import json
import sys
from melon_lua import read_melsave
from melon_lua.vpcompile.compile import compile_vp_graph
from melon_lua.vpcompile.graph import parse_chip_graph
from melon_lua.vpcompile.ops import op_name, NAME_TO_OP

doc = read_melsave('temp/xj11/xj 11(1).melsave')
vp_indices = [i for i, o in enumerate(doc.objects) if o.object_id == 248]

for vi in vp_indices:
    vp = doc.objects[vi]
    sm = vp.raw['saveMetaDatas']
    graph = None
    for m in sm:
        if m.get('key') == 'chip_graph':
            graph = json.loads(m['stringValue'])
            break
    if not graph:
        print(f'idx={vi}: no graph')
        continue

    print(f'\n=== VPchip idx={vi} inst={vp.instance_id} ===')
    try:
        ir = parse_chip_graph(graph)
        print(f'  parsed: {len(ir.nodes)} nodes, {len(ir.edges)} edges')
        print(f'  topo order: {len(ir.topo_order)}')

        # Check for missing ops
        from melon_lua.vpcompile.nodes import REGISTRY
        missing_ops = set()
        for uid, node in ir.nodes.items():
            if node.operation_type not in REGISTRY:
                missing_ops.add((node.operation_type, node.name))
        if missing_ops:
            print(f'  MISSING EMITTERS: {missing_ops}')
        else:
            print(f'  all ops have emitters')

        # Try compile
        lua = compile_vp_graph(graph, tps=20)
        lines = lua.count('\n')
        todos = lua.count('TODO')
        print(f'  compiled: {lines} lines, {todos} TODOs')
        if todos:
            # Find TODO lines
            for i, line in enumerate(lua.split('\n')):
                if 'TODO' in line:
                    print(f'    line {i+1}: {line.strip()[:100]}')

        # Write to temp
        out_path = f'temp/xj11_idx{vi}.lua'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(lua)
        print(f'  wrote: {out_path}')

    except Exception as e:
        import traceback
        print(f'  ERROR: {e}')
        traceback.print_exc()
