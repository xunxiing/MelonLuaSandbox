# Subagent prompt — Melon 36.x VPchip → Lua (subset compiler)

Copy everything below the line into a **general** or **explore** subagent. Work on branch **`feature/vp36-compile`** only.

---

## Mission

Implement **C0 + C1** of `docs/VPCHIP_TO_LUA.md` for **Melon 36.x VPchip** (`objectId` 248, graph in `saveMetaDatas[key=chip_graph]`). Goal: parse graph → IR → generate Lua that runs in **`MelonScriptRunner`** (not a second VM).

**Out of scope for this task:** full `NodeOperationType` enum, melsave write-back, Frida, parent `melonapk/` tooling.

## Repo

- Root: `MelonLuaSandbox/` (this git repo)
- Install: `pip install -e .`
- Verify after changes:
  ```bash
  python scripts/verify_melon_stdlib.py
  python scripts/verify_sdk.py
  ```

## References (read first)

| Doc / path | Use |
|------------|-----|
| `docs/VPCHIP_TO_LUA.md` | Compiler pipeline, semantics |
| `docs/MELSAVE_FORMAT.md` | ZIP / `Data` JSON |
| `melon_lua/melsave.py` | Load `.melsave` |
| `scripts/inspect_melsave.py` | CLI inspect |
| IL2CPP (user machine, optional): `../il2cpp-dump/DiffableCs/Assembly-CSharp/Ui/Windows/Chip/NodeOperationType.cs` | Op codes |
| Demo save (local, gitignored): `temp/jixiebi.melsave` | 3× VPchip; prefer **instance `-522198`** (tps=240, ~28 nodes, mostly math) |

If `temp/jixiebi.melsave` missing, document how to obtain it; still implement parser against **checked-in fixture** `tests/fixtures/vp_graph_minimal.json` (you create minimal graph JSON).

## Deliverables

1. **`melon_lua/vpcompile/`** package:
   - `graph.py` — parse `chip_graph` dict: nodes, edges from `Inputs[].connectedOutputIdModel`, stable short ids
   - `ir.py` — `MelonGraph` dataclasses
   - `ops.py` — map `OperationType` int → name (at least codes used in `jixiebi` / fixture)
   - `codegen.py` — emit Lua: `OnInit`/`OnTick`, `G` cache table, **MAX_GATE_ITER** loop placeholder (default 32)
   - `compile.py` — `compile_vp_graph(graph: dict, *, tps, chip_meta) -> str`

2. **`tests/fixtures/vp_graph_minimal.json`** — tiny graph: Constant → Add → (output binding)

3. **`scripts/compile_vp_from_melsave.py`** — CLI:
   ```bash
   python scripts/compile_vp_from_melsave.py temp/jixiebi.melsave --instance -522198 -o workspace/chips/-522198/generated.lua
   ```

4. **`docs/VP36_NODE_MATRIX.md`** — table: `OperationType`, node name, implemented (yes/no), Lua mapping notes

5. **C1 nodes (minimum):** `Constant` (257), `Add` (2304), `Identity` (1), `Root` (256) as input injection stub. No entity ops required in C1 unless easy.

6. **Smoke test script** `scripts/smoke_vp_compile.py` — compile fixture → `MelonScriptRunner.compile(generated)` → `run_loop(ticks=5)` without LuaError.

## Constraints

- Generated Lua must use **melon chip lifecycle** (`OnInit`/`OnTick`) and allowed stdlib only.
- Do **not** commit `temp/`, `*.png`, `*.mp4`, logs.
- Do **not** add local Windows paths or APK secrets to committed files.
- Prefer **opencode `write`/`edit`** for file changes; run commands via bash.
- Entity writes (`AddAngularForce`, etc.) are **C2** — stub with `-- TODO` comments if referenced.

## Acceptance

- [ ] `python scripts/smoke_vp_compile.py` exits 0
- [ ] `docs/VP36_NODE_MATRIX.md` lists all op types seen in `jixiebi` three graphs (run a small inventory script)
- [ ] `compile_vp_from_melsave.py` produces `generated.lua` for instance `-522198` when save present

## Suggested steps

1. Inventory op types from `jixiebi.melsave` (reuse logic from session: count `OperationType` per node).
2. Implement graph parse + edge list.
3. Topological or iterative evaluation order for DAG subset.
4. Codegen constants and Add chain.
5. Wire smoke test + matrix doc.
6. Single commit message: `feat(vpcompile): C0/C1 graph parse and math codegen for VP36`

## Report back to parent session

- Files added/changed list
- `VP36_NODE_MATRIX.md` summary (count implemented vs needed for `jixiebi`)
- Blockers for C2 (entity nodes, Root→Entity binding)
- Sample snippet of generated Lua (first 40 lines)