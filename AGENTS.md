# AGENTS.md — MelonLuaSandbox

Compact notes for OpenCode / agents. This repo is the **git root** (public: `github.com/xunxiing/MelonLuaSandbox`). Parent folder `melonapk/` (APK, `il2cpp-dump`, `lua-triage`) is **out of tree** unless the user mounts it.

## What this is

Python sandbox for **Melon Playground Lua chips** (Unity 6 / IL2CPP game): real bundled `preamble.lua`, 11 C# ApiModule backends, melon-allowed stdlib, Box2D, spawn + `object_physics_by_id.json`. **Not** a full game client; **VPchip** (visual graph, objectId 248) is documented but not fully executed here yet (`docs/VPCHIP_TO_LUA.md`).

## Setup

```bash
cd MelonLuaSandbox
pip install -r requirements.txt
# or: pip install -e .
```

Requires Python ≥3.10. Native deps: **lupa** (LuaJIT), **Box2D** (pybox2d), **pillow** (preview only).

## Verification (no pytest suite)

Run after touching runner, stdlib, backends, spawn, or catalog:

```bash
python scripts/verify_melon_stdlib.py
python scripts/verify_sdk.py
melon-lua samples/stdlib_smoke.lua --ticks 1
melon-lua samples/bignum.lua --ticks 5
```

Physics spot-check:

```bash
melon-lua samples/physics_demo.lua --ticks 80 --seed-entity "crate,0,10" --seed-static "floor,0,0"
```

There is **no** CI workflow, ruff, or mypy config in-repo; do not invent a lint pipeline unless the user asks.

## CLI entry

- Console script: `melon-lua` → `melon_lua.__main__:main`
- Batch sim uses **`--ticks N`** (no real-time sleep; `run_loop` is back-to-back ticks).
- Spawn floor for physics demos: **`--seed-static`** (not `--seed-entity-static`).
- Input JSON: use **`utf-8-sig`** when reading user files (PowerShell BOM).

## Architecture (agent-relevant)

| Layer | Location |
|-------|----------|
| Lua VM + lifecycle | `melon_lua/runner.py` (`MelonScriptRunner`) |
| Real preamble | `melon_lua/preamble.lua` (package data) |
| Stdlib policy | `melon_lua/stdlib_melon.py`, `docs/stdlib.md` |
| Backends (11 modules) | `melon_lua/backend/*` via `register_all` |
| World + Box2D | `melon_lua/world.py`, `melon_lua/entity.py` |
| Spawn queue / OnSpawned | `melon_lua/spawn_queue.py`, `spawn_backend.py` |
| objectId + sizes | `melon_lua/catalog.py`, `melon_lua/data/object_physics_by_id.json` |
| Sprites (preview) | `melon_lua/data/sprites_pack/`, `melon_lua/preview.py` |
| `.melsave` read | `melon_lua/melsave.py`, `scripts/inspect_melsave.py` |

**Critical init order in `MelonScriptRunner`:** register **all backend tables** (including `__entity_raw`) **before** `preamble.lua` executes. Preamble bails if `__entity_raw` is nil.

**Engine mismatch:** Game uses Lua-CSharp 5.2; sandbox uses **LuaJIT 5.1** via lupa. Chip-facing API is aligned; edge cases (`string.format`, RNG) may differ.

**Spawn:** `spawn.create` returns `requestId` immediately; entities are created in the same call path; `OnSpawned` is flushed end-of-tick via `__dispatch_spawn` + `__current_env`.

## Docs map

- `docs/API.md` — Python SDK
- `docs/LUA_GUIDE.md` — chip authoring
- `docs/stdlib.md` — allowed/banned globals
- `docs/MELSAVE_FORMAT.md`, `docs/MELSAVE_AI_ARCHITECTURE.md` — saves / AI workspace
- `docs/VPCHIP_TO_LUA.md` — VP graph → Lua compiler plan

## Git / hygiene

- Do **not** commit: `temp/`, `tmp/`, `frames/`, `*.mp4`, `*.log`, demo `*.png` at repo root (see `.gitignore`).
- Avoid **local absolute paths** and APK paths in committed comments (public repo).
- `pyproject.toml` `[project.urls]` may not match this repo; fix only when user requests.

## VPchip / subagent work

Target: **Melon 36.x VPchip** subset compiler under `melon_lua/vpcompile/` (see `docs/VPCHIP_TO_LUA.md`). Use feature branch `feature/vp36-compile`; deliver IR + node registry + tests per slice, not “all NodeOperationType” in one pass.

## Optional local assets

User may keep `temp/*.melsave` locally (gitignored). Rebuild physics/sprites from parent `lua-triage/` scripts is **outside** this package; sandbox ships frozen JSON under `melon_lua/data/`.