"""Shard B: trig / angle math."""
from __future__ import annotations

from ..ir import VPNode
from ._base import NodeEmitter


def _g(i: int, ins: list[str]) -> str:
  return ins[i] if i < len(ins) else "0"


def _assign(uid: str, expr: str) -> list[str]:
  return [f'    G["{uid}"] = {expr}']


def emit_acos(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  # Acos returns radians (standard math.acos behavior). RadToDeg node converts
  # to degrees. Do NOT pre-convert here — that causes double conversion when
  # followed by RadToDeg in the chip graph.
  return _assign(uid, f"math.acos({_g(0, ins)})")


def emit_rad_to_deg(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  return _assign(uid, f"({ _g(0, ins) }) * (180 / math.pi)")


def emit_deg_to_rad(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  return _assign(uid, f"({ _g(0, ins) }) * (math.pi / 180)")


def emit_delta_angle(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  if len(ins) >= 2:
      return _assign(
          uid,
          f"(({ins[1]}) - ({ins[0]})) * (180 / math.pi)",
      )
  return _assign(uid, "0")


def emit_cosine_formula_angle(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  # VP: side a,b,c -> angle at A via law of cosines; inputs: a,b,c scalars
  if len(ins) >= 3:
      a, b, c = ins[0], ins[1], ins[2]
      return _assign(
          uid,
          f"(function() local aa,bb,cc=({a}),({b}),({c}); "
          f"local x=(aa*aa+bb*bb-cc*cc)/(2*aa*bb); "
          f"if x>1 then x=1 elseif x<-1 then x=-1 end; "
          f"return math.acos(x)*(180/math.pi) end)()",
      )
  return _assign(uid, "0")


def emit_cosine_formula_side(uid: str, ins: list[str], _n: VPNode) -> list[str]:
  if len(ins) >= 3:
      a, ang, b = ins[0], ins[1], ins[2]
      return _assign(
          uid,
          f"math.sqrt(({a})^2+({b})^2-2*({a})*({b})*math.cos(({ang})*math.pi/180))",
      )
  return _assign(uid, "0")


MATH_TRIG_EMITTERS: dict[str, NodeEmitter] = {
  "Acos": emit_acos,
  "RadToDeg": emit_rad_to_deg,
  "DegToRad": emit_deg_to_rad,
  "DeltaAngle": emit_delta_angle,
  "CosineFormulaAngle": emit_cosine_formula_angle,
  "CosineFormulaSide": emit_cosine_formula_side,
}