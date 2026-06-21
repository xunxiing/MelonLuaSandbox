"""Check what's actually in REGISTRY vs what xj11 needs."""
from melon_lua.vpcompile.nodes import REGISTRY
from melon_lua.vpcompile.ops import op_name, NAME_TO_OP

print(f'REGISTRY size: {len(REGISTRY)}')
print(f'REGISTRY keys (first 20): {sorted(REGISTRY.keys())[:20]}')

# Check specific ops
test_ops = [512, 1283, 2318, 2308, 2058, 2306, 1280, 2305, 256, 2052, 2307, 257, 1282, 2304, 2315, 1281, 1559, 4100, 1538, 260, 2567, 2816, 2312, 2330, 2819, 2324, 2311, 2325, 1, 4098, 1557, 2309, 2560, 768, 2059, 1539, 1540, 2329, 2564, 2561, 2817, 2818, 2820, 2821, 1545, 4097, 2566, 2327]
print(f'\nChecking {len(test_ops)} ops:')
missing = []
for op in test_ops:
    if op in REGISTRY:
        print(f'  {op} ({op_name(op, "")}): FOUND')
    else:
        print(f'  {op} ({op_name(op, "")}): MISSING')
        missing.append(op)
print(f'\nTotal missing: {len(missing)}')
