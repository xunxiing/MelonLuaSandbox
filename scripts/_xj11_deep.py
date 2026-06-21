"""Deep inspect a single VPchip raw structure to find where chip_graph lives."""
import json
from melon_lua import read_melsave

doc = read_melsave('temp/xj11/xj 11(1).melsave')
vp = doc.objects[4]  # first VPchip
raw = vp.raw
print('=== VPchip raw keys ===')
for k in sorted(raw.keys()):
    v = raw[k]
    t = type(v).__name__
    if isinstance(v, list):
        print(f'  {k}: list[{len(v)}]')
    elif isinstance(v, str):
        print(f'  {k}: str[{len(v)}] preview={v[:80]!r}')
    elif isinstance(v, dict):
        print(f'  {k}: dict keys={list(v.keys())[:10]}')
    else:
        print(f'  {k}: {t}={v!r}'[:200])

print()
print('=== saveMetaDatas[0] full ===')
sm = raw.get('saveMetaDatas')
if isinstance(sm, list) and sm:
    print(json.dumps(sm[0], indent=2, ensure_ascii=False)[:2000])

print()
print('=== search for chip_graph / chipGraph / graph in entire raw ===')
def find_key(obj, target_keys, path=''):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f'{path}.{k}' if path else k
            if k.lower() in target_keys:
                found.append((p, type(v).__name__, len(v) if isinstance(v, (list, str, dict)) else v))
            found.extend(find_key(v, target_keys, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f'{path}[{i}]'
            found.extend(find_key(v, target_keys, p))
    return found

results = find_key(raw, {'chip_graph', 'chipgraph', 'graph', 'nodes', 'connections', 'wires', 'links'})
for p, t, n in results:
    print(f'  {p}: {t} len={n}')

print()
print('=== stringValue fields in saveMetaDatas ===')
if isinstance(sm, list):
    for i, m in enumerate(sm):
        if isinstance(m, dict):
            sv = m.get('stringValue')
            if sv and isinstance(sv, str) and len(sv) > 5:
                print(f'  meta[{i}] key={m.get("key")!r} stringValue len={len(sv)} preview={sv[:120]!r}')
