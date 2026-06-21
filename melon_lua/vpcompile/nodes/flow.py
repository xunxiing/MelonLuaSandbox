"""Shard G: flow / IO / time nodes (Root, Exit, constants, state)."""
from __future__ import annotations

import json
import math

from ..save_data import constant_value
from ..ir import VPNode
from ._base import NodeEmitter


# Module-level chip_variables map (Key -> Value), set by codegen before emission.
# Variable nodes look up their initial value here via MechanicConnectionId.
_chip_variables: dict[str, float] = {}


def set_chip_variables(variables: dict[str, float]) -> None:
  """Inject chip_variables (Key -> Value) for emit_variable lookups."""
  global _chip_variables
  _chip_variables = dict(variables) if variables else {}


def _variable_init_value(n: VPNode) -> float:
  """Get a Variable node's initial value.

  Variable nodes store user-set values in chip_variables (keyed by the node's
  MechanicConnectionId, e.g. 'variable 7'), NOT in SaveData. If the variable
  is found in chip_variables, use that value. Otherwise fall back to
  SaveData.DataValue (constant_value), then 0.0.
  """
  mci = n.raw.get("MechanicConnectionId")
  if mci and mci in _chip_variables:
    return _chip_variables[mci]
  return constant_value(n)


def _assign(uid: str, expr: str) -> list[str]:
  return [f'    G["{uid}"] = {expr}']


def _g(i: int, ins: list[str], default: str = "0") -> str:
  return ins[i] if i < len(ins) else default


def _save_data_obj(node: VPNode) -> dict:
  sd = node.save_data
  if not sd:
      return {}
  try:
      obj = json.loads(sd)
      return obj if isinstance(obj, dict) else {}
  except (json.JSONDecodeError, TypeError):
      return {}


def _gate_name_from_save(node: VPNode, fallback: str) -> str:
  """Return the raw gate name (NOT lua-identifier-converted) from SaveData.
  Gate names may contain spaces ("input 1"); callers must use bracket notation
  when emitting Lua table accesses."""
  obj = _save_data_obj(node)
  for key in ("DataName", "MechanicInputId", "MechanicOutputId", "Name"):
      v = obj.get(key)
      if v is not None and str(v).strip():
          return str(v).strip()
  return fallback


def _lua_ident(name: str, fallback: str) -> str:
  s = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
  if not s or s[0].isdigit():
      return fallback
  return s


def _lua_str(s: str) -> str:
  """Quote a string for use as a Lua table key (bracket notation).
  Escapes backslash, quote, and newline so the key is safe for any gate name
  including those with spaces ("input 1") or special characters."""
  esc = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
  return '"{}"'.format(esc)


# GateDataType -> inputs/outputs subtable name (matches runner.py sub_categories)
_GATE_TO_SUBTABLE: dict[str, str] = {
    "Entity": "entity",
    "Number": "num",
    "IntegerNumber": "int",
    "String": "string",
    "Vector": "vec",
    "Color": "color",
    "ArrayNumber": "array_num",
    "ArrayString": "array_string",
    "ArrayVector": "array_vec",
    "ArrayEntity": "array_entity",
}


def _gate_subtable(node: VPNode) -> str:
  """Return the inputs/outputs subtable name for this Root/Exit node's gate type."""
  gdt = node.raw.get("GateDataType")
  if isinstance(gdt, str):
      gdt = gdt.strip()
  elif isinstance(gdt, int):
      # Some saves store GateDataType as int (enum value)
      int_map = {1: "Entity", 2: "Number", 4: "String", 8: "Vector",
                 24: "Color", 32: "IntegerNumber"}
      gdt = int_map.get(gdt, "Number")
  else:
      gdt = "Number"
  return _GATE_TO_SUBTABLE.get(gdt, "num")


def emit_constant(uid: str, _ins: list[str], n: VPNode) -> list[str]:
  v = constant_value(n)
  if v == int(v):
      return _assign(uid, str(int(v)))
  return _assign(uid, str(v))


def emit_pi(uid: str, _ins: list[str], _n: VPNode) -> list[str]:
  return _assign(uid, str(math.pi))


def emit_e(uid: str, _ins: list[str], _n: VPNode) -> list[str]:
  return _assign(uid, str(math.e))


def emit_identity(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  return _assign(uid, _g(0, ins))


def emit_root(uid: str, ins: list[str], n: VPNode) -> list[str]:
  # Root node's MechanicConnectionId (top-level field) maps to the input gate name.
  # Gate names may contain spaces ("input 1") — use bracket notation to access them.
  mec = n.raw.get("MechanicConnectionId") or ""
  if mec:
      gate_raw = mec.strip()
  else:
      gate_raw = _gate_name_from_save(n, "a")
  obj = _save_data_obj(n)
  ent = obj.get("EntityId") or obj.get("entityId")
  sub = _gate_subtable(n)  # subtable name: num/entity/string/vec/...
  gkey = '[{}]'.format(_lua_str(gate_raw))  # bracket-quoted key, safe for spaces
  lines = [f"    -- Root {uid}: {sub}/{gate_raw} input gate"]

  if ent is not None:
      # Entity-reference Root: hard-wired entity id
      lines.append(f'  G["{uid}"] = {int(ent)}')
  elif sub == "vec":
      # Vector input: store scalar primary + vector form in _vec
      lines.append(f'  local _rv = inputs.vec and inputs.vec{gkey}')
      lines.append(f'  if _rv then')
      lines.append(f'    G["{uid}_vec"] = _rv')
      lines.append(f'    G["{uid}"] = type(_rv) == "table" and (_rv.x or _rv[1] or 0) or _rv')
      lines.append(f'  else')
      lines.append(f'    local _n = (inputs.num and inputs.num{gkey}) or 0')
      lines.append(f'    G["{uid}"] = _n')
      lines.append(f'    G["{uid}_vec"] = {{x = _n, y = 0, z = 0, w = 0}}')
      lines.append(f'  end')
  elif sub == "entity":
      # Entity input: read entity id from inputs.entity["<gate>"]
      lines.append(f'  G["{uid}"] = (inputs.entity and inputs.entity{gkey}) or 0')
  elif sub == "string":
      # String input
      lines.append(f'  G["{uid}"] = (inputs.string and inputs.string{gkey}) or ""')
  elif ins:
      lines.append(f'  G["{uid}"] = {ins[0]}')
  else:
      # Number / int / color / array_* — default to num subtable
      lines.append(f'  G["{uid}"] = (inputs.{sub} and inputs.{sub}{gkey}) or 0')
  return lines


def emit_exit(uid: str, ins: list[str], n: VPNode) -> list[str]:
  if not ins:
      return [f"    -- Exit {uid}: no wired input"]
  # Exit node's MechanicConnectionId (top-level field) maps to the output gate name.
  # Gate names may contain spaces ("input 2") — use bracket notation to access them.
  mec = n.raw.get("MechanicConnectionId") or ""
  if mec:
      gate_raw = mec.strip()
  else:
      gate_raw = _gate_name_from_save(n, "out")
  sub = _gate_subtable(n)  # subtable name: num/entity/string/vec/color/array_*
  gkey = '[{}]'.format(_lua_str(gate_raw))  # bracket-quoted key, safe for spaces
  return [f"    outputs.{sub}{gkey} = {ins[0]}"]


def emit_variable(uid: str, ins: list[str], n: VPNode) -> list[str]:
  # Variable nodes with the same MechanicConnectionId share state in VP chips.
  # The shared G key is the MechanicConnectionId (e.g. "variable 10").
  # Other nodes reference this variable by uid; _input_exprs remaps those
  # references to the shared key (see codegen._build_var_uid_map).
  mci = n.raw.get("MechanicConnectionId")
  key = mci if mci else uid
  init = _variable_init_value(n)
  init_s = str(int(init)) if init == int(init) else str(init)
  has_set_input = len(ins) >= 2 and ins[0] != "0"
  lines = []
  if has_set_input:
      # Writer node: update shared state when condition is non-zero
      lines.append(
          f"    if ({ins[1]}) ~= 0 then G[\"{key}\"] = {ins[0]} end"
      )
  # Initialize shared state on first tick (only if not yet set)
  lines.append(f'  G["{key}"] = G["{key}"] or {init_s}')
  return lines


def emit_counter(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  mem = f'["_cnt_{uid}"]'
  num = _g(0, ins)
  inc = _g(1, ins, "0")
  dec = _g(2, ins, "0")
  rst = _g(3, ins, "0")
  return [
      f"    G{mem} = G{mem} or {num}",
      f"    if ({rst}) ~= 0 then G{mem} = {num} end",
      f"    G{mem} = G{mem} + ({inc}) - ({dec})",
      f'    G["{uid}"] = G{mem}',
  ]


def emit_delay(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  tmem = f'["_delay_{uid}"]'
  arm = f'["_delay_arm_{uid}"]'
  delay = _g(1, ins, "0")
  enable = _g(2, ins, "0")
  rst = _g(3, ins, "0")
  hold = _g(4, ins, "0")
  return [
      f"    G{tmem} = G{tmem} or 0",
      f"    G{arm} = G{arm} or false",
      f"    if ({rst}) ~= 0 then G{tmem} = 0 G{arm} = false end",
      f"    if ({enable}) ~= 0 and not G{arm} then G{arm} = true G{tmem} = 0 end",
      f"    if G{arm} then G{tmem} = G{tmem} + (1 / math.max(1, chip_tps or 20)) end",
      f"    local _dready = G{arm} and G{tmem} >= ({delay})",
      f'    G["{uid}"] = (_dready and ({hold}) ~= 0) and 1 or 0',
  ]


def emit_trigger(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  prev = f'["_trg_{uid}"]'
  cur = _g(0, ins)
  return [
      f"    G{prev} = G{prev} or 0",
      f'    G["{uid}"] = (({cur}) ~= 0 and G{prev} == 0) and 1 or 0',
      f"    G{prev} = ({cur}) ~= 0 and 1 or 0",
  ]


def emit_time(uid: str, _ins: list[str], n: VPNode) -> list[str]:
  outs = n.outputs or []
  lines = [f"    -- Time {uid}: sandbox tick time stub"]
  keys = ("time", "delta", "frame", "unscaled")
  for i in range(min(4, max(1, len(outs)))):
      key = f"{uid}_o{i}"
      if i == 0:
          lines.append(f'  G["{key}"] = (G._vp_tick or 0) / math.max(1, chip_tps or 20)')
      elif i == 1:
          lines.append(f'  G["{key}"] = 1 / math.max(1, chip_tps or 20)')
      else:
          lines.append(f'  G["{key}"] = G._vp_tick or 0')
      lines.append(f'  G["{uid}_{keys[i]}"] = G["{key}"]')
  # Always set primary G[uid] so downstream nodes can reference it
  lines.append(f'  G["{uid}"] = G["{uid}_o0"]')
  return lines


def emit_random(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  lo = _g(0, ins, "0")
  hi = _g(1, ins, "1")
  return [
      f"    local _rlo, _rhi = ({lo}), ({hi})",
      f"    if _rlo > _rhi then _rlo, _rhi = _rhi, _rlo end",
      f'    G["{uid}"] = _rlo + math.random() * (_rhi - _rlo)',
  ]


def emit_sticker(uid: str, _ins: list[str], _n: VPNode) -> list[str]:
  return [f"    -- Sticker {uid}: editor-only (no runtime)"]


def emit_delta_previous_current(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  cur = _g(0, ins)
  mem = f'["_dpc_prev_{uid}"]'
  return [
      f"    G{mem} = G{mem}",
      f'    G["{uid}"] = (({cur}) or 0) - (G{mem} or 0)',
      f"    G{mem} = ({cur}) or 0",
  ]


def emit_accumulate(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  val = _g(0, ins, "0")
  rst = _g(1, ins, "0")
  mem = f'["_acc_{uid}"]'
  dt = "1 / math.max(1, chip_tps or 20)"
  return [
      f"    G{mem} = G{mem} or 0",
      f"    if ({rst}) ~= 0 then G{mem} = 0 end",
      f"    G{mem} = G{mem} + ({val}) * ({dt})",
      f'    G["{uid}"] = G{mem}',
  ]


FLOW_EMITTERS: dict[str, NodeEmitter] = {
  "Root": emit_root,
  "Exit": emit_exit,
  "Constant": emit_constant,
  "Variable": emit_variable,
  "Counter": emit_counter,
  "Delay": emit_delay,
  "Trigger": emit_trigger,
  "Identity": emit_identity,
  "Sticker": emit_sticker,
  "Pi": emit_pi,
  "E": emit_e,
  "Time": emit_time,
  "Random": emit_random,
  "DeltaPreviousCurrent": emit_delta_previous_current,
  "Accumulate": emit_accumulate,
}