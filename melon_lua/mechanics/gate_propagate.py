"""Resolve mechanic gate wires into MelonScriptRunner input buckets."""
from __future__ import annotations

import json
from typing import Any, Optional

# Gate DataType → runner input bucket
_DT_BUCKET = {
    1: "entity",
    2: "num",
    4: "string",
    8: "vec",
    32: "int",
    128: "array_num",
    256: "array_string",
    512: "array_vec",
    1024: "array_entity",
}

_EMPTY_BUCKETS = (
    "num", "int", "string", "vec", "color", "entity",
    "array_num", "array_string", "array_vec", "array_entity",
)


def empty_inputs() -> dict[str, dict[str, Any]]:
    return {k: {} for k in _EMPTY_BUCKETS}


def _parse_gates(raw: Any) -> list[dict]:
    if not raw:
        return []
    try:
        gates = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return [g for g in gates if isinstance(g, dict)]


def chip_input_schema_from_container(so: dict) -> dict[str, str]:
    """Map chip input gate Key/DataName → runner bucket name."""
    schema: dict[str, str] = {}
    # Prefer lua_chip_inputs meta (LuaValue.Type) when present
    for md in so.get("saveMetaDatas") or []:
        if not isinstance(md, dict) or md.get("key") != "lua_chip_inputs":
            continue
        sv = md.get("stringValue") or "[]"
        try:
            items = json.loads(sv)
        except (TypeError, json.JSONDecodeError):
            items = []
        if not isinstance(items, list):
            continue
        # LuaValue.Type: 1 num, 2 int, 3 string, 4 vec, 5 color, 6 entity, 7 array
        # Array subtype is not always stored — use name heuristics + mechanic DataType
        for it in items:
            if not isinstance(it, dict):
                continue
            name = str(it.get("Name") or it.get("name") or "")
            if not name:
                continue
            lt = int(it.get("Type") or it.get("type") or 0)
            if lt == 1:
                schema[name] = "num"
            elif lt == 2:
                schema[name] = "int"
            elif lt == 3:
                schema[name] = "string"
            elif lt == 4:
                schema[name] = "vec"
            elif lt == 5:
                schema[name] = "color"
            elif lt == 6:
                schema[name] = "entity"
            elif lt == 7:
                # default array_entity for common sensor wiring names
                nlow = name.lower()
                if "string" in nlow or "str" in nlow:
                    schema[name] = "array_string"
                elif "num" in nlow or "float" in nlow:
                    schema[name] = "array_num"
                elif "vec" in nlow or "color" in nlow or "pixel" in nlow:
                    schema[name] = "array_vec"
                else:
                    schema[name] = "array_entity"
    # mechanicSerializedInputs DataType overrides / fills gaps
    md = so.get("mechanicData")
    if isinstance(md, list) and md and isinstance(md[0], dict):
        for g in _parse_gates(md[0].get("mechanicSerializedInputs")):
            key = str(g.get("Key") or "")
            dname = str(g.get("DataName") or "")
            bucket = _DT_BUCKET.get(int(g.get("DataType") or 0))
            if not bucket:
                continue
            if key:
                schema[key] = bucket
            if dname:
                schema[dname] = bucket
    return schema


def _lookup_output(values: dict[str, Any], gate_name: str) -> Any:
    if gate_name in values:
        return values[gate_name]
    # case-insensitive / strip
    gl = gate_name.lower().strip()
    for k, v in values.items():
        if str(k).lower().strip() == gl:
            return v
    return None


def build_chip_inputs_from_wires(
    world: Any,
    doc_raw: dict | None,
    chip_container_idx: int,
    *,
    chip_so: Optional[dict] = None,
) -> dict[str, dict[str, Any]]:
    """Follow gate wires into ``chip_container_idx`` and fill input buckets."""
    inputs = empty_inputs()
    if chip_so is None and isinstance(doc_raw, dict):
        containers = doc_raw.get("saveObjectContainers") or []
        if 0 <= chip_container_idx < len(containers):
            c = containers[chip_container_idx]
            if isinstance(c, dict):
                chip_so = c.get("saveObjects") or {}
    schema = chip_input_schema_from_container(chip_so or {})
    gate_vals = getattr(world, "gate_output_values", None) or {}
    wires = []
    if hasattr(world, "gate_wires") and world.gate_wires is not None:
        wires = world.gate_wires.list_all()

    for w in wires:
        if int(w.target_idx) != int(chip_container_idx):
            continue
        src_vals = gate_vals.get(int(w.source_idx)) or {}
        val = _lookup_output(src_vals, str(w.output_gate))
        if val is None:
            continue
        in_name = str(w.input_gate)
        bucket = schema.get(in_name) or schema.get(in_name.lower())
        if bucket is None:
            # infer from value shape
            if isinstance(val, list):
                if val and isinstance(val[0], (int, float)) and not isinstance(val[0], bool):
                    bucket = "array_entity"
                else:
                    bucket = "array_entity"
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                # entity gates often 0/id
                if in_name.lower() in ("entity", "target", "detector", "hit entity"):
                    bucket = "entity"
                else:
                    bucket = "num"
            elif isinstance(val, str):
                bucket = "string"
            else:
                continue
        if bucket not in inputs:
            continue
        # entity ids as int; arrays as list of int
        if bucket == "entity":
            try:
                inputs[bucket][in_name] = int(val) if val not in (None, "", False) else 0  # type: ignore[arg-type]
            except (TypeError, ValueError):
                inputs[bucket][in_name] = 0
        elif bucket == "array_entity":
            if isinstance(val, list):
                ids: list[int] = []
                for x in val:
                    try:
                        ids.append(int(x))
                    except (TypeError, ValueError):
                        continue
                inputs[bucket][in_name] = ids
            else:
                inputs[bucket][in_name] = []
        elif bucket in ("array_num", "array_string", "array_vec"):
            inputs[bucket][in_name] = list(val) if isinstance(val, list) else []
        else:
            inputs[bucket][in_name] = val
    return inputs


def merge_inputs(
    auto: Optional[dict[str, dict[str, Any]]],
    override: Optional[dict[str, dict[str, Any]]],
) -> Optional[dict[str, dict[str, Any]]]:
    """Merge override on top of auto (override wins per gate name)."""
    if not auto and not override:
        return None
    if not auto:
        return override
    if not override:
        return auto
    out = empty_inputs()
    for k in _EMPTY_BUCKETS:
        out[k] = dict(auto.get(k) or {})
        out[k].update(override.get(k) or {})
    # also pass through any extra top-level keys from override
    for k, v in override.items():
        if k not in out and isinstance(v, dict):
            out[k] = dict(v)
    return out
