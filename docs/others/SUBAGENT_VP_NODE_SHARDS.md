# Multi-subagent: VP36 node → Lua mappings

Parent: `graph.py`, `compile.py`, `ops.py` (178 ops). Each subagent owns `melon_lua/vpcompile/nodes/<shard>.py`.

## Contract

`REGISTRY: dict[str, NodeEmitter]` in `nodes/__init__.py`.  
Emitter: `(uid, input_exprs, VPNode) -> list[str]` assigning `G["uid"]`.

## Shards

| Shard | File | Nodes |
|-------|------|-------|
| A | `math_basic.py` | Add, Subtract, Multiply, … |
| B | `math_trig.py` | Acos, RadToDeg, CosineFormula*, … |
| C | `logic.py` | Branch, And, Equal, … |
| D | `entity_read.py` | Position, EntityAngle, … |
| E | `entity_write.py` | AddAngularForce, AddForce, … |
| F | `vector.py` | Magnitude, SqrMagnitude |
| G | `flow.py` | Root, Exit, Constant, Counter, … |
| H | `string_array.py` | (TODO) |
| I | `meta_world.py` | (TODO stubs) |

## Reverse engineering

- IL2CPP: `*NodeViewModel.cs` under `Ui/Windows/Chip/`
- Saves: `python scripts/vp_inventory_melsave.py` on `temp/jixiebi.melsave`, `temp/atm.melsave`
- Priority: UNION inventory ops first (40 distinct in jixiebi)

## atm.melsave

User all-the-mod sample: **objectId 249**, not VP 248 — different chip type; keep for later.