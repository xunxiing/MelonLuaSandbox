"""UI Controller builder SDK for Melon Playground.

Constructs UIController (objectId=2046689600) save objects with custom UI
element layouts. Each UI controller has a tree of UI elements (buttons,
sliders, joysticks, etc.) defined in `uicontrol_elements` metadata.

Based on reverse-engineering of `6527test.melsave` — a real-device UI
controller demo with all 13 element types.

Element types (by Type field in save data):
    1=Button, 2=Pedal, 3=Pedal, 22=Joystick, 5=SliderStyle1, 6=SliderStyle2,
    7=SliderStyle3, 11=InputField, 12=SteeringWheel, 14=Pointer, 17=Toggle,
    18=Screen, 19=CustomIcon

Note: Types 1/2/3 are all button-family (output "Button is down/up");
Types 5/6/7 are all slider-family (output "Value"); user-visible names
in saves may differ (e.g. Type=5 named "Slider 1").

Coordinate system: screen-space pixels, anchored to RectTransform anchors.
    (0,0) = screen center, +x = right, +y = up.
    AnchorMin/Max (0-1): relative position in parent.
    AnchoredPosition: pixel offset from anchor point.
    SizeDelta: element size in pixels.
"""
from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Element type constants
# ---------------------------------------------------------------------------

BUTTON = 1
PEDAL = 2
PEDAL_ALT = 3  # Same behavior as PEDAL (outputs Button is down/up)
SLIDER = 5  # SliderStyle1 (target value + Value output)
SLIDER_ALT = 6  # SliderStyle2
SLIDER_ALT2 = 7  # SliderStyle3 (adds Fill color)
INDICATOR1 = 6  # Alias (same as SLIDER_ALT)
ROTATION_WHEEL = 12  # Steering wheel
INPUT_FIELD = 11
STEERING_WHEEL = 12
POINTER = 14
TOGGLE = 17
SCREEN = 18
CUSTOM_ICON = 19
JOYSTICK = 22
LABEL = 5  # Alias (SLIDER family is commonly used as a label/indicator)

# Deprecated aliases (kept for compat but Type values were corrected)
ROTATION_WHEEL_OLD = 7  # This was SliderStyle3, not RotationWheel

_TYPE_NAMES = {
    BUTTON: "Button", PEDAL: "Pedal", PEDAL_ALT: "Pedal",
    SLIDER: "Slider", SLIDER_ALT: "Slider", SLIDER_ALT2: "Slider",
    INPUT_FIELD: "InputField", STEERING_WHEEL: "SteeringWheel",
    POINTER: "Pointer", TOGGLE: "Toggle", SCREEN: "Screen",
    CUSTOM_ICON: "CustomIcon", JOYSTICK: "Joystick",
}

# GateDataType constants (match mechanic system)
_DT_NUMBER = 2
_DT_STRING = 4
_DT_VECTOR = 8
_DT_ENTITY = 1
_DT_COLOR = 24
_DT_INT = 32

# Prototype loader
_PROTOTYPES_PATH = Path(__file__).parent / "data" / "ui_element_prototypes.json"
_CONTROLLER_TEMPLATE_PATH = Path(__file__).parent / "data" / "ui_controller_template.json"


def _load_prototypes() -> dict[int, dict]:
    with open(_PROTOTYPES_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Introspection — agent-friendly element catalog
# ---------------------------------------------------------------------------

_COMMON_INPUTS = {
    "Element shown", "Element Title shown", "Button is interactable", "Color",
    "Label Pivot", "Anchor min", "Anchor max", "Anchored position",
    "Size delta", "Sorting order",
}
_COMMON_OUTPUTS = {
    "Anchor min out", "Anchor max out", "Anchored position out",
    "Size delta out",
}

_DT_NAMES = {1: "entity", 2: "number", 4: "string", 8: "vector",
             24: "color", 32: "int"}


def element_schema(name: str = "") -> dict:
    """Return a human/agent-readable schema for a UI element type.

    Call ``element_schema()`` for a list of all available types, or
    ``element_schema("button")`` / ``element_schema("slider")`` etc. for the
    schema of one type (case-insensitive prefix match).

    Returns::

        {
            "type": "button",            # canonical name
            "type_id": 1,                # save-data Type field
            "aliases": ["button", "pedal"],
            "description": "...",
            "inputs": [                  # type-specific input gates only
                {"key": "Button text", "type": "string", "default": "", "description": "..."},
                ...
            ],
            "outputs": [                 # type-specific output gates only
                {"key": "Button is down", "type": "number", "description": "..."},
                ...
            ],
            "factory": "UIElement.button(name, x, y, text='...')",
        }

    Common layout gates (present on every element: Element shown, Color,
    Anchor min/max, Size delta, etc.) are omitted for brevity.
    """
    protos = _load_prototypes()
    groups = {
        "button": [BUTTON, PEDAL, PEDAL_ALT],
        "slider": [SLIDER, SLIDER_ALT, SLIDER_ALT2],
        "joystick": [JOYSTICK],
        "toggle": [TOGGLE],
        "steering_wheel": [STEERING_WHEEL],
        "input_field": [INPUT_FIELD],
        "pointer": [POINTER],
        "screen": [SCREEN],
        "custom_icon": [CUSTOM_ICON],
    }
    # Inverse map: type_id -> group name
    id2group = {}
    for gname, ids in groups.items():
        for tid in ids:
            id2group[tid] = gname

    if not name:
        # List all types
        result = []
        for gname, ids in groups.items():
            tid = ids[0]
            proto = protos[tid]
            outs = [_describe_gate(o, _COMMON_OUTPUTS) for o in proto["Outputs"]
                    if o["Key"] not in _COMMON_OUTPUTS]
            result.append({
                "type": gname,
                "type_ids": ids,
                "outputs": outs,
                "factory": _factory_sig(gname),
            })
        return {"available_types": result}

    key = name.lower().strip()
    # Match by group name (prefix) or alias
    matched_group = None
    for gname in groups:
        if gname == key or gname.startswith(key) or key.startswith(gname):
            matched_group = gname
            break
    if matched_group is None:
        # Try direct type name from _TYPE_NAMES
        for tid, tname in _TYPE_NAMES.items():
            if tname.lower() == key:
                matched_group = id2group.get(tid)
                break
    if matched_group is None:
        return {"error": f"Unknown element type '{name}'. Call element_schema() for available types."}

    tid = groups[matched_group][0]
    proto = protos[tid]
    ins = [_describe_gate(i, _COMMON_INPUTS) for i in proto["Inputs"]
           if i["Key"] not in _COMMON_INPUTS]
    outs = [_describe_gate(o, _COMMON_OUTPUTS) for o in proto["Outputs"]
            if o["Key"] not in _COMMON_OUTPUTS]
    return {
        "type": matched_group,
        "type_ids": groups[matched_group],
        "aliases": groups[matched_group],
        "description": _type_description(matched_group),
        "inputs": ins,
        "outputs": outs,
        "factory": _factory_sig(matched_group),
    }


def _describe_gate(gate: dict, skip: set[str]) -> dict | None:
    """Describe one gate, skipping common layout gates."""
    if gate["Key"] in skip:
        return None
    dt = gate.get("GateDataType", _DT_NUMBER)
    desc = {
        "key": gate["Key"],
        "type": _DT_NAMES.get(dt, f"dt{dt}"),
        "editable": gate.get("CanBeEdited", True),
    }
    # Parse default value
    sv = gate.get("SerializedValue", "")
    if sv:
        try:
            pv = json.loads(sv)
            if "Value" in pv:
                desc["default"] = pv["Value"]
        except (json.JSONDecodeError, TypeError):
            pass
    # Add semantic hint for well-known gates
    hint = _GATE_HINTS.get(gate["Key"])
    if hint:
        desc["hint"] = hint
    return desc


_GATE_HINTS = {
    "Button text": "按钮上显示的文字",
    "Button multiplier": "按下时输出的倍率",
    "Inverse": "反转输出（0↔1）",
    "Target value": "滑块/标签的目标值（运行时可改）",
    "Min Value": "滑块最小值",
    "Max Value": "滑块最大值",
    "Integers only": "只允许整数值",
    "Joystick Multiplier": "摇杆灵敏度倍率",
    "Offset Angle": "摇杆基准角度偏移",
    "Active": "开关初始状态（0=关 1=开）",
    "Rotation wheel limit": "转向轮旋转范围（度）",
    "Button is down": "按钮按下时=1",
    "Button is up": "按钮松开时=1",
    "Value": "当前值（滑块/开关/标签）",
    "Joystick Activation": "摇杆激活时=1",
    "Joystick Direction": "摇杆方向向量{x,y}",
    "Joystick Angle": "摇杆角度（度）",
    "Angle Value": "转向轮当前角度",
    "Up direction": "转向轮向上方向向量",
    "Is changed": "输入框内容变化时=1",
    "Field Value": "输入框当前值",
    "Dot viewport position": "触控点视口坐标",
    "Dot screen position": "触控点屏幕坐标",
    "Dot worlds position": "触控点世界坐标向量",
    "active": "屏幕是否激活",
    "camera": "绑定的相机实体",
}


_TYPE_DESC = {
    "button": "按钮，按下输出 Button is down=1，松开输出 Button is up=1",
    "slider": "滑块，拖动改变 Value 输出，支持 Min/Max 范围和整数模式",
    "joystick": "摇杆，输出 Joystick Direction 向量和 Joystick Angle 角度",
    "toggle": "开关，点击切换 Value（0/1）",
    "steering_wheel": "转向轮，旋转输出 Angle Value 角度和 Up direction 方向",
    "input_field": "文本输入框，输出 Field Value 和 Is changed 变化标志",
    "pointer": "触控点，输出屏幕/视口/世界坐标位置",
    "screen": "屏幕/相机面板，绑定相机实体显示视角",
    "custom_icon": "自定义图标，纯显示用途无交互输出",
}


def _type_description(name: str) -> str:
    return _TYPE_DESC.get(name, "")


def _factory_sig(name: str) -> str:
    sigs = {
        "button": 'UIElement.button(name, x, y, text="")',
        "slider": 'UIElement.slider(name, x, y, value=0, mn=0, mx=1, integers_only=False)',
        "joystick": 'UIElement.joystick(name, x, y, multiplier=1.0, offset_angle=0.0)',
        "toggle": 'UIElement.toggle(name, x, y, active=False)',
        "steering_wheel": 'UIElement.steering_wheel(name, x, y)',
        "input_field": 'UIElement.input_field(name, x, y)',
        "pointer": 'UIElement.pointer(name, x, y)',
        "screen": 'UIElement.screen(name, x, y, active=True)',
        "custom_icon": 'UIElement.custom_icon(name, x, y)',
    }
    return sigs.get(name, "")


# ---------------------------------------------------------------------------
# Vector2 builder (mimics Unity Vector2 JSON with magnitude/sqrMagnitude)
# ---------------------------------------------------------------------------

def _vec2(x: float, y: float) -> dict:
    """Build a Unity Vector2 JSON structure with computed magnitude fields."""
    import math
    mag = math.sqrt(x * x + y * y)
    if mag > 0:
        nx, ny = x / mag, y / mag
    else:
        nx, ny = 0.0, 0.0
    sm = x * x + y * y
    if mag > 0:
        snx, sny = nx, ny
        snorm_nx = snx / mag if mag else 0.0
        snorm_ny = sny / mag if mag else 0.0
    else:
        snorm_nx = snorm_ny = 0.0
    return {
        "x": float(x),
        "y": float(y),
        "normalized": {
            "x": nx, "y": ny,
            "normalized": {"x": snorm_nx, "y": snorm_ny,
                           "magnitude": 1.0 if mag > 0 else 0.0,
                           "sqrMagnitude": 1.0 if mag > 0 else 0.0},
            "magnitude": 1.0 if mag > 0 else 0.0,
            "sqrMagnitude": 1.0 if mag > 0 else 0.0,
        },
        "magnitude": mag,
        "sqrMagnitude": sm,
    }


def _vec4(x: float, y: float, z: float = 0.0, w: float = 0.0) -> dict:
    """Build a Unity Vector4 (used by mechanic gates as quaternion-like)."""
    import math
    mag = math.sqrt(x * x + y * y + z * z + w * w)
    nx = x / mag if mag > 0 else 0.0
    ny = y / mag if mag > 0 else 0.0
    nz = z / mag if mag > 0 else 0.0
    nw = w / mag if mag > 0 else 0.0
    sm = x * x + y * y + z * z + w * w
    return {
        "x": float(x), "y": float(y), "z": float(z), "w": float(w),
        "normalized": {
            "x": nx, "y": ny, "z": nz, "w": nw,
            "magnitude": 1.0 if mag > 0 else 0.0,
            "sqrMagnitude": 1.0 if mag > 0 else 0.0,
        },
        "magnitude": mag,
        "sqrMagnitude": sm,
    }


# ---------------------------------------------------------------------------
# SerializedValue builders (for element Inputs/Outputs)
# ---------------------------------------------------------------------------

def _num_gate_value(value: float, default: float = 0.0,
                    mn: float = -3.40282347e38, mx: float = 3.40282347e38,
                    checkbox: bool = False) -> str:
    return json.dumps({
        "Value": value, "Default": default,
        "Min": mn, "Max": mx, "IsCheckbox": checkbox,
    }, separators=(",", ":"))


def _vec_gate_value(x: float, y: float, dx: float = 0.0, dy: float = 0.0,
                    mn: float = -3.40282347e38, mx: float = 3.40282347e38) -> str:
    return json.dumps({
        "Value": _vec4(x, y),
        "Default": _vec4(dx, dy),
        "MinVector": _vec4(mn, mn, mn, mn),
        "MaxVector": _vec4(mx, mx, mx, mx),
    }, separators=(",", ":"))


def _color_gate_value(r: float, g: float, b: float, a: float = 1.0) -> str:
    """Color stored as Vector4 (r,g,b,a) in 0-1 range."""
    return _vec_gate_value(r, g, b, a)


def _string_gate_value(text: str = "", default: str = "",
                       max_len: int = 2147483647) -> str:
    return json.dumps({
        "IsMultiline": False, "Value": text,
        "Default": default, "MaxLength": max_len,
    }, separators=(",", ":"))


def _entity_gate_value() -> str:
    return json.dumps({"Value": 0}, separators=(",", ":"))


# ---------------------------------------------------------------------------
# UIElement
# ---------------------------------------------------------------------------

# Primary output gate per element type — the single "default" output an agent
# most likely wants to wire. Used by ElementHandle when no explicit gate given.
_PRIMARY_OUTPUT: dict[int, str] = {
    BUTTON: "Button is down",
    PEDAL: "Button is down",
    PEDAL_ALT: "Button is down",
    SLIDER: "Value",
    SLIDER_ALT: "Value",
    SLIDER_ALT2: "Value",
    TOGGLE: "Value",
    JOYSTICK: "Joystick Direction",
    STEERING_WHEEL: "Angle Value",
    INPUT_FIELD: "Field Value",
    POINTER: "Dot worlds position",
    SCREEN: "active",
    CUSTOM_ICON: "",  # display-only, no signal output
}

# Maps the Slider family (Type=5) used by labels/indicators back to "Value".
for _t in (SLIDER, SLIDER_ALT, SLIDER_ALT2):
    _PRIMARY_OUTPUT.setdefault(_t, "Value")


@dataclass
class UIElement:
    """A single UI element on a UI controller panel.

    Use the class methods (`.button()`, `.slider()`, `.joystick()`, etc.) to
    create elements with sensible defaults; then customize position/size/values.
    """
    type: int
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 200.0
    height: float = 200.0
    anchor_min: tuple[float, float] = (0.5, 0.5)
    anchor_max: tuple[float, float] = (0.5, 0.5)
    pivot: tuple[float, float] = (0.5, 0.5)
    sorting_order: int = -1
    color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    show: bool = True
    show_title: bool = False
    interactible: bool = True
    # Type-specific overrides for input gate values
    values: dict[str, Any] = field(default_factory=dict)
    # Stable GUID used for GroupId in mechanic gates and mechCon.outputGroup.
    # Generated once at construction so wires can reference it before build.
    group_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ---- Factory methods ----

    @classmethod
    def button(cls, name: str = "Button", x: float = 0, y: float = 0,
               text: str = "", **kw) -> "UIElement":
        el = cls(type=BUTTON, name=name, x=x, y=y, **kw)
        if text:
            el.values["Button text"] = text
        return el

    @classmethod
    def pedal(cls, name: str = "Pedal", x: float = 0, y: float = 0,
              text: str = "", **kw) -> "UIElement":
        el = cls(type=PEDAL, name=name, x=x, y=y, **kw)
        if text:
            el.values["Button text"] = text
        return el

    @classmethod
    def slider(cls, name: str = "Slider", x: float = 0, y: float = 0,
               value: float = 0.0, mn: float = 0.0, mx: float = 1.0,
               integers_only: bool = False, **kw) -> "UIElement":
        el = cls(type=SLIDER, name=name, x=x, y=y, **kw)
        el.values["Target value"] = value
        el.values["Min Value"] = mn
        el.values["Max Value"] = mx
        if integers_only:
            el.values["Integers only"] = 1.0
        return el

    @classmethod
    def joystick(cls, name: str = "Joystick", x: float = 0, y: float = 0,
                 multiplier: float = 1.0, offset_angle: float = 0.0, **kw) -> "UIElement":
        el = cls(type=JOYSTICK, name=name, x=x, y=y, **kw)
        el.values["Joystick Multiplier"] = multiplier
        el.values["Offset Angle"] = offset_angle
        return el

    @classmethod
    def toggle(cls, name: str = "Toggle", x: float = 0, y: float = 0,
               active: bool = False, **kw) -> "UIElement":
        el = cls(type=TOGGLE, name=name, x=x, y=y, **kw)
        el.values["Active"] = 1.0 if active else 0.0
        return el

    @classmethod
    def label(cls, name: str = "Label", x: float = 0, y: float = 0,
              value: float = 0.0, **kw) -> "UIElement":
        # Label uses Slider family (Type=5) which has a Value output
        el = cls(type=SLIDER, name=name, x=x, y=y, **kw)
        el.values["Target value"] = value
        return el

    @classmethod
    def rotation_wheel(cls, name: str = "SteeringWheel", x: float = 0, y: float = 0,
                       value: float = 0.0, limit: float = 360.0, **kw) -> "UIElement":
        el = cls(type=STEERING_WHEEL, name=name, x=x, y=y, **kw)
        el.values["Target value"] = value
        el.values["Rotation wheel limit"] = limit
        return el

    @classmethod
    def input_field(cls, name: str = "InputField", x: float = 0, y: float = 0,
                    **kw) -> "UIElement":
        return cls(type=INPUT_FIELD, name=name, x=x, y=y, **kw)

    @classmethod
    def steering_wheel(cls, name: str = "SteeringWheel", x: float = 0, y: float = 0,
                       **kw) -> "UIElement":
        return cls(type=STEERING_WHEEL, name=name, x=x, y=y, **kw)

    @classmethod
    def pointer(cls, name: str = "Pointer", x: float = 0, y: float = 0, **kw) -> "UIElement":
        return cls(type=POINTER, name=name, x=x, y=y, **kw)

    @classmethod
    def screen(cls, name: str = "Screen", x: float = 0, y: float = 0,
               active: bool = True, **kw) -> "UIElement":
        el = cls(type=SCREEN, name=name, x=x, y=y, **kw)
        el.values["active"] = 1.0 if active else 0.0
        return el

    @classmethod
    def custom_icon(cls, name: str = "CustomIcon", x: float = 0, y: float = 0, **kw) -> "UIElement":
        return cls(type=CUSTOM_ICON, name=name, x=x, y=y, **kw)

    @classmethod
    def indicator(cls, name: str = "Indicator1", x: float = 0, y: float = 0,
                  value: float = 0.0, mn: float = 0.0, mx: float = 1.0, **kw) -> "UIElement":
        # Indicator1 uses Slider family (Type=6)
        el = cls(type=SLIDER_ALT, name=name, x=x, y=y, **kw)
        el.values["Target value"] = value
        el.values["Min Value"] = mn
        el.values["Max Value"] = mx
        return el

    # ---- Serialization ----

    def to_dict(self, order: int, prototypes: dict[int, dict]) -> dict:
        """Build the full element dict matching uicontrol_elements schema."""
        proto = copy.deepcopy(prototypes[self.type])
        proto["Id"] = self.group_id
        default_name = proto.get("DefaultName", _TYPE_NAMES.get(self.type, ""))
        proto["Name"] = self.name or default_name
        # Real device: IsUserChangedName is False when name matches DefaultName,
        # True only when user gave a custom name different from default.
        proto["IsUserChangedName"] = bool(self.name) and (self.name != default_name)
        # Real device: Order and Key are always 0 for every element (not index).
        proto["Order"] = 0
        proto["Show"] = self.show
        proto["ShowTitle"] = self.show_title
        proto["Interactible"] = self.interactible
        proto["MainColor"] = {
            "r": int(self.color[0] * 255),
            "g": int(self.color[1] * 255),
            "b": int(self.color[2] * 255),
            "a": int(self.color[3] * 255),
        }
        proto["Key"] = 0
        # Apply user value overrides on Inputs
        for inp in proto["Inputs"]:
            gate_key = inp["Key"]
            if gate_key in self.values:
                new_val = self.values[gate_key]
                inp["SerializedValue"] = _build_serialized_value(
                    inp.get("GateDataType", _DT_NUMBER), gate_key, new_val, inp.get("SerializedValue", ""))
        # RectTransformData: keep the prototype's structure (correct SizeDelta,
        # Rotation as float, RotationQuaternion, Position, etc.) and only
        # override AnchoredPosition with the user's x/y. The prototype is
        # extracted from real-device saves so its RectTransformData is correct.
        rt = copy.deepcopy(proto.get("RectTransformData", {}))
        rt["AnchoredPosition"] = _vec2(self.x, self.y)
        proto["RectTransformData"] = rt
        return proto


def _build_serialized_value(data_type: int, gate_key: str, value: Any,
                            original_sv: str) -> str:
    """Build a SerializedValue JSON string for a gate based on its type."""
    if data_type in (_DT_NUMBER, _DT_INT):
        # Special handling for known checkbox gates
        is_checkbox = gate_key in (
            "Element shown", "Element Title shown", "Button is interactable",
            "Inverse", "Use border", "Use text", "Auto size", "Integers only",
            "Use by timescale",
        )
        mn, mx = (0.0, 1.0) if is_checkbox else (-3.40282347e38, 3.40282347e38)
        return _num_gate_value(float(value), default=float(value),
                               mn=mn, mx=mx, checkbox=is_checkbox)
    if data_type == _DT_STRING:
        return _string_gate_value(str(value))
    if data_type == _DT_VECTOR:
        if isinstance(value, dict):
            return _vec_gate_value(value.get("x", 0), value.get("y", 0))
        if isinstance(value, (list, tuple)):
            return _vec_gate_value(value[0], value[1])
        return _vec_gate_value(0.0, 0.0)
    if data_type == _DT_COLOR:
        if isinstance(value, dict):
            return _color_gate_value(value.get("r", 1), value.get("g", 1),
                                      value.get("b", 1), value.get("a", 1))
        if isinstance(value, (list, tuple)):
            return _color_gate_value(*value)
        return _color_gate_value(1.0, 1.0, 1.0, 1.0)
    return original_sv


def _build_rect_transform(x: float, y: float, w: float, h: float,
                          anchor_min: tuple, anchor_max: tuple,
                          pivot: tuple, sorting_order: int) -> dict:
    """Build a RectTransformData dict.

    Matches real-device structure (verified against 6762.melsave):
    - Rotation is a float (Euler angle), NOT a Vector2
    - RotationQuaternion is a Vector4 (x,y,z,w + eulerAngles)
    - Position is a Vector2 (absolute screen position)
    - SortingOrder is NOT in RectTransformData (lives in element-level gate)
    """
    return {
        "AnchoredPosition": _vec2(x, y),
        "AnchorMin": _vec2(anchor_min[0], anchor_min[1]),
        "AnchorMax": _vec2(anchor_max[0], anchor_max[1]),
        "Pivot": _vec2(pivot[0], pivot[1]),
        "SizeDelta": _vec2(w, h),
        "Position": _vec2(0.0, 0.0),
        "Rotation": 0.0,
        "RotationQuaternion": {
            "x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0,
            "eulerAngles": {
                "x": 0.0, "y": 0.0, "z": 0.0,
                "magnitude": 0.0, "sqrMagnitude": 0.0,
            },
        },
        "Scale": _vec2(1.0, 1.0),
    }


# ---------------------------------------------------------------------------
# UIControllerBuilder
# ---------------------------------------------------------------------------

def _float_max() -> float:
    return 3.40282347e38


def _build_mech_gate(key: str, data_type: int, gate_data: str | None,
                     can_edit: bool = True, data_name: str | None = None,
                     group_id: str | None = None, group: int = 0,
                     group_name: str | None = None) -> dict:
    """Build a mechanicSerializedInputs/Outputs gate entry.

    For element gates (not system gates), pass group_id/group/group_name so the
    game can distinguish same-name gates across elements (e.g. multiple "Value"
    outputs). The game routes wires via outputGroup = element's GroupId (GUID).
    """
    gate: dict = {
        "Key": key,
        "DataType": data_type,
        "DataName": data_name or key,
        "CanBeEdit": can_edit,
        "GateData": gate_data,
    }
    if group_id is not None:
        gate["GroupId"] = group_id
        gate["Group"] = group or 0
        gate["GroupName"] = group_name
    else:
        gate["GroupId"] = None
        gate["Group"] = 0
        gate["GroupName"] = None
    return gate


def _gate_data_default(data_type: int, value: Any = None) -> str:
    """Build a default GateData JSON for mechanicData."""
    if data_type in (_DT_NUMBER, _DT_INT):
        return json.dumps({
            "Value": float(value) if value is not None else 0.0,
            "Default": 0.0,
            "Min": -_float_max(), "Max": _float_max(),
            "IsCheckbox": False,
        }, separators=(",", ":"))
    if data_type == _DT_VECTOR:
        return json.dumps({"Value": _vec4(0, 0)}, separators=(",", ":"))
    if data_type == _DT_COLOR:
        return json.dumps({"Value": _vec4(1, 1, 1, 1)}, separators=(",", ":"))
    if data_type == _DT_ENTITY:
        return json.dumps({"Value": 0}, separators=(",", ":"))
    return "{}"


class ElementHandle:
    """Lightweight reference to a UI element added via ``add_*``.

    Returned by ``UIControllerBuilder.add_button`` / ``add_slider`` / etc.
    Carries the element's ``group_id`` (GUID) and primary output gate name,
    so callers can wire it without remembering gate names or calling
    ``element_group_id(idx)`` separately.

    ``handle.gate("Value")`` returns a tuple ``(gate_name, group_id)`` that
    can be passed to ``connect``. The bare handle is also accepted by
    ``MelsaveSession.connect`` as the source — in that case the element's
    primary output gate is used automatically.

    The handle resolves its container index lazily: it holds a back-reference
    to its ``UIControllerBuilder`` and is bound to a container index the first
    time the controller is added to a session (via
    ``MelsaveSession.add_ui_controller``).
    """

    __slots__ = ("_element", "_controller", "_container_idx")

    def __init__(self, element: "UIElement", controller: "UIControllerBuilder"):
        self._element = element
        self._controller = controller
        # Resolved by MelsaveSession.add_ui_controller via _bind_container().
        self._container_idx: int | None = None

    @property
    def group_id(self) -> str:
        """Element's stable GroupId (GUID) — pass to connect(output_group=...)."""
        return self._element.group_id

    @property
    def name(self) -> str:
        return self._element.name

    @property
    def type(self) -> int:
        return self._element.type

    @property
    def primary_output(self) -> str:
        """The default output gate name for this element type."""
        return _PRIMARY_OUTPUT.get(self._element.type, "")

    @property
    def container_idx(self) -> int | None:
        """Container index once the controller is added to a session, else None."""
        return self._container_idx

    def _bind_container(self, idx: int) -> None:
        """Called by MelsaveSession.add_ui_controller to resolve lazy binding."""
        self._container_idx = idx

    def gate(self, gate_name: str = "") -> tuple[str, str]:
        """Return ``(gate_name, group_id)`` for use with connect.

        If ``gate_name`` is empty, the element's primary output gate is used.
        """
        gn = gate_name or self.primary_output
        if not gn:
            raise ValueError(
                f"Element type {self._element.type} has no primary output gate; "
                f"specify gate_name explicitly"
            )
        return (gn, self._element.group_id)


class UIControllerBuilder:
    """Build a UI controller (objectId=2046689600) save object.

    A UI controller holds a panel of UI elements (buttons, sliders, joysticks,
    etc.). Each element has inputs (configurable properties + control signals)
    and outputs (interaction events + layout state).

    Example::

        b = UIControllerBuilder()
        b.add(UIElement.button("Fire", x=-100, y=100, text="FIRE"))
        b.add(UIElement.slider("Speed", x=100, y=100, value=0.5, mx=10))
        b.add(UIElement.joystick("Move", x=0, y=-100))
        so = b.build_save_object(x=0, y=0)
    """

    def __init__(self):
        self._elements: list[UIElement] = []
        self._handles: list[ElementHandle] = []
        self._prototypes = _load_prototypes()

    def add(self, element: UIElement) -> "ElementHandle":
        """Add a UI element. Returns an ElementHandle for the added element."""
        self._elements.append(element)
        h = ElementHandle(element, self)
        self._handles.append(h)
        return h

    @property
    def handles(self) -> list["ElementHandle"]:
        """All element handles (bound to a container idx after add_ui_controller)."""
        return list(self._handles)

    def add_button(self, name: str = "Button", x: float = 0, y: float = 0,
                   text: str = "", **kw) -> "ElementHandle":
        return self.add(UIElement.button(name, x, y, text=text, **kw))

    def add_slider(self, name: str = "Slider", x: float = 0, y: float = 0,
                   value: float = 0.0, mn: float = 0.0, mx: float = 1.0, **kw) -> "ElementHandle":
        return self.add(UIElement.slider(name, x, y, value=value, mn=mn, mx=mx, **kw))

    def add_joystick(self, name: str = "Joystick", x: float = 0, y: float = 0,
                     multiplier: float = 1.0, **kw) -> "ElementHandle":
        return self.add(UIElement.joystick(name, x, y, multiplier=multiplier, **kw))

    def add_toggle(self, name: str = "Toggle", x: float = 0, y: float = 0,
                   active: bool = False, **kw) -> "ElementHandle":
        return self.add(UIElement.toggle(name, x, y, active=active, **kw))

    def add_label(self, name: str = "Label", x: float = 0, y: float = 0,
                  value: float = 0.0, **kw) -> "ElementHandle":
        return self.add(UIElement.label(name, x, y, value=value, **kw))

    def add_pedal(self, name: str = "Pedal", x: float = 0, y: float = 0,
                  text: str = "", **kw) -> "ElementHandle":
        return self.add(UIElement.pedal(name, x, y, text=text, **kw))

    def add_rotation_wheel(self, name: str = "SteeringWheel", x: float = 0, y: float = 0,
                           value: float = 0.0, limit: float = 360.0, **kw) -> "ElementHandle":
        return self.add(UIElement.rotation_wheel(name, x, y, value=value, limit=limit, **kw))

    def add_input_field(self, name: str = "InputField", x: float = 0, y: float = 0, **kw) -> "ElementHandle":
        return self.add(UIElement.input_field(name, x, y, **kw))

    def add_pointer(self, name: str = "Pointer", x: float = 0, y: float = 0, **kw) -> "ElementHandle":
        return self.add(UIElement.pointer(name, x, y, **kw))

    def add_screen(self, name: str = "Screen", x: float = 0, y: float = 0,
                   active: bool = True, **kw) -> "ElementHandle":
        return self.add(UIElement.screen(name, x, y, active=active, **kw))

    def add_custom_icon(self, name: str = "CustomIcon", x: float = 0, y: float = 0, **kw) -> "ElementHandle":
        return self.add(UIElement.custom_icon(name, x, y, **kw))

    def add_indicator(self, name: str = "Indicator1", x: float = 0, y: float = 0,
                      value: float = 0.0, mn: float = 0.0, mx: float = 1.0, **kw) -> "ElementHandle":
        return self.add(UIElement.indicator(name, x, y, value=value, mn=mn, mx=mx, **kw))

    def add_steering_wheel(self, name: str = "SteeringWheel", x: float = 0, y: float = 0, **kw) -> "ElementHandle":
        return self.add(UIElement.steering_wheel(name, x, y, **kw))

    @property
    def element_count(self) -> int:
        return len(self._elements)

    def element_group_id(self, name_or_index: str | int) -> str:
        """Return the stable GroupId (GUID) of an element.

        Pass this as ``connect(..., output_group=...)`` when wiring UI controller
        gates that share output names across elements (e.g. multiple "Value"
        outputs). Resolves by element name (first match) or 0-based index.

        Args:
            name_or_index: Element name or 0-based element index.

        Raises:
            KeyError: If name not found. IndexError: If index out of range.
        """
        if isinstance(name_or_index, int):
            return self._elements[name_or_index].group_id
        for el in self._elements:
            if el.name == name_or_index:
                return el.group_id
        raise KeyError(f"no UI element named {name_or_index!r}")

    def build_uicontrol_elements(self) -> dict:
        """Build the uicontrol_elements metadata value."""
        elements_json = [el.to_dict(i, self._prototypes)
                         for i, el in enumerate(self._elements)]
        return {"Elements": elements_json}

    def build_mechanic_data(self) -> dict:
        """Build the mechanicData entry (mechanicSerializedInputs/Outputs).

        Each element's Inputs/Outputs are flattened into the controller's
        global gate list. Element gates carry GroupId/Group/GroupName so the
        game can distinguish same-name gates across elements (e.g. multiple
        "Value" outputs) — wires route via outputGroup = element GroupId.
        """
        mech_inputs: list[dict] = []
        mech_outputs: list[dict] = []

        # System gates (no group). Real-device mechanic gates use CanBeEdit=true
        # even for system gates (matches 12356test.melsave reference).
        mech_inputs.append(_build_mech_gate("activation", _DT_NUMBER,
            _gate_data_default(_DT_NUMBER, 1.0), can_edit=True))
        # "Override sorting" is a controller-level system input present on real
        # device UI controllers (see UIControlMechanic.OVERRIDE_SORTING const).
        mech_inputs.append(_build_mech_gate("Override sorting", _DT_NUMBER,
            json.dumps({"Value": 0.0, "Default": 0.0, "Min": 0.0, "Max": 1.0,
                        "IsCheckbox": True}, separators=(",", ":")),
            can_edit=True))
        mech_outputs.append(_build_mech_gate("entity", _DT_ENTITY, None, can_edit=True))
        mech_outputs.append(_build_mech_gate("activation", _DT_NUMBER,
            _gate_data_default(_DT_NUMBER), can_edit=True))

        # Flatten element gates with group identity
        for el_idx, el in enumerate(self._elements):
            proto = el.to_dict(el_idx, self._prototypes)
            gid = proto.get("Id") or ""
            gnum = proto.get("Group", 0)
            gname = proto.get("Name", "")
            for inp in proto["Inputs"]:
                # SerializedValue from the prototype IS the GateData payload —
                # pass through verbatim (real device keeps Default/Min/Max etc).
                gd = inp.get("SerializedValue") or None
                mech_inputs.append(_build_mech_gate(
                    inp["Key"], inp.get("GateDataType", _DT_NUMBER),
                    gd, can_edit=inp.get("CanBeEdited", True),
                    data_name=inp.get("DataName", inp["Key"]),
                    group_id=gid, group=gnum, group_name=gname))
            for out in proto["Outputs"]:
                gd = out.get("SerializedValue") or None
                mech_outputs.append(_build_mech_gate(
                    out["Key"], out.get("GateDataType", _DT_NUMBER),
                    gd, can_edit=out.get("CanBeEdited", True),
                    data_name=out.get("DataName", out["Key"]),
                    group_id=gid, group=gnum, group_name=gname))

        return {
            "activationInput": 0.0,
            "floatParameters": [0.0, 0.0],
            "mechanicSerializedInputs": json.dumps(mech_inputs, ensure_ascii=False,
                                                    separators=(",", ":")),
            "mechanicSerializedOutputs": json.dumps(mech_outputs, ensure_ascii=False,
                                                     separators=(",", ":")),
        }

    def build_save_object(self, x: float = 0.0, y: float = 0.0, *,
                          z: float = 0.0, title: str = "") -> dict:
        """Build a complete UI controller saveObjects dict.

        Deep-copies the controller template (from 6527test.melsave) and
        overwrites mechanicData + uicontrol_elements metadata + position.
        """
        with open(_CONTROLLER_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = json.load(f)
        so = copy.deepcopy(template)
        so["position"] = {"x": float(x), "y": float(y), "z": float(z)}
        so["freezed"] = True
        so["constraints"] = []

        # Replace mechanicData
        so["mechanicData"] = [self.build_mechanic_data()]

        # Replace uicontrol_elements metadata
        elements_json = self.build_uicontrol_elements()
        elements_str = json.dumps(elements_json, ensure_ascii=False,
                                  separators=(",", ":"))

        found = False
        for sm in so["saveMetaDatas"]:
            if sm["key"] == "uicontrol_elements":
                sm["stringValue"] = elements_str
                found = True
                break
        if not found:
            so["saveMetaDatas"].append({
                "key": "uicontrol_elements",
                "boolValue": False,
                "stringValue": elements_str,
                "intValue": 0,
                "floatValue": 0.0,
                "vector2Value": {"x": 0.0, "y": 0.0},
                "vector3Value": {"x": 0.0, "y": 0.0, "z": 0.0},
                "vector4Value": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0,
                                  "magnitude": 0.0, "sqrMagnitude": 0.0},
                "texture2DValue": None,
            })

        # uicontrol_inputs / uicontrol_outputs describe the controller's own
        # SYSTEM gates (activation/entity/Override sorting) — NOT the flattened
        # element gates. The template already carries them in the correct
        # format (field name "SerializedValue", not "GateData"), so we leave
        # them untouched. Element gates live only in mechanicData.

        # Strip leftover custom_icon_* entries from the template (each
        # CustomIcon element adds its own; rebuilding means old ones are stale)
        so["saveMetaDatas"] = [
            sm for sm in so["saveMetaDatas"]
            if not sm.get("key", "").startswith("custom_icon_")
        ]

        return so


__all__ = [
    "UIControllerBuilder", "UIElement", "ElementHandle", "element_schema",
    # Type constants
    "BUTTON", "PEDAL", "PEDAL_ALT", "SLIDER", "SLIDER_ALT", "SLIDER_ALT2",
    "INPUT_FIELD", "STEERING_WHEEL", "POINTER", "TOGGLE", "SCREEN",
    "CUSTOM_ICON", "JOYSTICK",
]
