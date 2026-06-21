"""Inspect xj11 melsave: find VP chips and their graphs."""
import json
import zipfile
from melon_lua import read_melsave

doc = read_melsave('temp/xj11/xj 11(1).melsave')
print('=== melsave overview ===')
print('objects:', len(doc.objects))
for i, o in enumerate(doc.objects):
    raw = o.raw
    print(f'  idx={i} oid={o.object_id} name={o.name} inst={o.instance_id}')
    if o.object_id in (248, 249):
        sm = raw.get('saveMetaDatas') or raw.get('saveMetadata')
        print(f'    saveMetaDatas type: {type(sm).__name__}')
        if isinstance(sm, list):
            for j, m in enumerate(sm):
                if isinstance(m, dict):
                    chips = m.get('chips') or []
                    cg = m.get('chip_graph') or m.get('chipGraph')
                    cg_len = len(cg) if isinstance(cg, list) else type(cg).__name__
                    chips_len = len(chips) if isinstance(chips, list) else type(chips).__name__
                    print(f'    saveMeta[{j}] chips={chips_len} chip_graph={cg_len}')
                    # dump keys
                    print(f'      keys: {list(m.keys())}')
        elif isinstance(sm, str):
            print(f'    saveMetaDatas is string len={len(sm)}')
            try:
                parsed = json.loads(sm)
                if isinstance(parsed, list):
                    print(f'    parsed list len={len(parsed)}')
                    for j, m in enumerate(parsed):
                        if isinstance(m, dict):
                            chips = m.get('chips') or []
                            cg = m.get('chip_graph') or m.get('chipGraph')
                            cg_len = len(cg) if isinstance(cg, list) else type(cg).__name__
                            chips_len = len(chips) if isinstance(chips, list) else type(chips).__name__
                            print(f'      meta[{j}] chips={chips_len} chip_graph={cg_len} keys={list(m.keys())}')
            except Exception as e:
                print(f'    parse error: {e}')
