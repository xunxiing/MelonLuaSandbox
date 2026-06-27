# Melon Lua Sandbox — Python SDK 参考

本 SDK 完整复现甜瓜游乐场芯片运行时（基于 APK 逆向的真实 `LuaPreamble.lua` + 11 ApiModule + melon 允许的标准库）。

## 安装

```bash
cd MelonLuaSandbox
pip install -e .
```

依赖：`lupa`（LuaJIT）、`Box2D`（pybox2d）、`pillow`（预览渲染）。

## 快速开始

```python
from melon_lua import (
    MelonScriptRunner, WorldContext,
    get_profile_by_object_id, object_id_for_name, list_spawnables,
    render_world,
)

# 1. 准备世界（支持 456+ 物体，objectId 或名字）
world = WorldContext()
world.spawn_entity("202", 0, 1)                    # ResizablePlastic (塑料板)
world.spawn_entity("Box", 2, 5, dynamic=True)      # 按 gameObjectName
world.spawn_entity(23, -3, 4, scale_x=1.5)         # 直接用 objectId

# 2. 编译并运行 Lua 芯片
source = '''
function OnInit()
    print("chip init")
end

function OnTick()
    local e = Entity(1)
    local x, y = e:getPosition()
    outputs.num.x = x
    outputs.num.y = y
end
'''

runner = MelonScriptRunner(tps=20, world=world, quiet=False)
runner.compile(source, chunk_name="@my_chip.lua")
runner.call_on_init()
result = runner.run_tick()
print(result["outputs"])

# 3. 批量模拟（推荐）
runner.run_loop(ticks=1000)
print(runner.logs[-10:])   # 最近日志
```

## 核心类

### WorldContext

物理世界 + 生成目录 + 实体管理。

```python
world = WorldContext(seed=42)   # 可复现随机

# 生成（立即创建实体，支持 objectId / gameObjectName / 别名）
eid = world.spawn_entity("202", x=0, y=1, dynamic=True, scale_x=1.0, scale_y=1.0)

# 直接操作实体（绕过 Lua）
e = world.get_entity(eid)
e.set_position(10, 20)
e.add_force(0, 100)

# 目录查询（基于 495 条数据）
prof = get_profile_by_object_id(202)
print(prof["width"], prof["height"], prof["mass"])

# 物理步进（由 runner 自动调用）
world.step_physics(dt=1/20)
```

主要字段/方法：
- `entities: dict[int, Entity]`
- `spawn_entity(alias_or_id, x, y, dynamic=True, ...) -> int`
- `remove_entity(eid)`
- `step_physics(dt)`
- `spawn_catalog`, `spawn_saves`, `spawn_mods`（用于 spawn.getItems 等）

### MelonScriptRunner

芯片执行引擎。

```python
runner = MelonScriptRunner(tps=20, world=world, quiet=True, log_file="run.log")

ok = runner.compile(source, chunk_name="@chip.lua")
if not ok:
    print("compile error:", runner.last_error)
    return

runner.call_on_init()                    # 调用 OnInit（会 flush spawn）
result = runner.run_tick(inputs=...)     # 单步 + 可注入 inputs
runner.run_loop(ticks=500)               # 连续跑 N tick

print(runner.get_outputs())              # 当前 outputs 快照
print(runner.logs)                       # 全部 print/warn/error_log
```

关键方法：
- `compile(source, chunk_name)`
- `call_on_init()`
- `run_tick(inputs=None) -> {"error": ..., "outputs": ...}`
- `run_loop(ticks, inputs=None, inputs_timeline=None)`
- `get_outputs() -> dict`
- `last_error`

### Entity（Python 侧）

```python
e = world.get_entity(1)
e.position_x, e.position_y = 5, 10
e.add_force(100, 0)
print(e.real_size())           # (w, h) 考虑 scale
print(e.sprite_path)           # 贴图路径（若有）
```

### 目录 API（catalog）

```python
from melon_lua import (
    catalog_stats,
    get_profile_by_object_id,
    get_profile_by_name,
    list_spawnables,
    object_id_for_name,
    resolve_spawn_name,
)

print(catalog_stats())                    # {"total": 456, "with_physics": 245, ...}
prof = get_profile_by_object_id(202)      # 完整 profile（含 width/height/mass/sprite）
oid = object_id_for_name("ResizablePlastic")  # 202
names = list_spawnables()                 # 所有可生成的名字
```

## 预览 / 截图（Pillow）

```python
from melon_lua import render_world
from pathlib import Path

render_world(
    world,
    "preview.png",
    width=800, height=600,
    ppm=128,                    # pixels per meter
    center_x=0, center_y=1,
    show_labels=True,
    scale_text=1.0,
)
```

支持：网格、实体矩形（带 sprite 颜色提示）、ID/oid/名字标签、十字准星。

## CLI（melon-lua）

```bash
melon-lua samples/hello_chip.lua --ticks 100
melon-lua chip.lua --inputs inputs.json --ticks 200
melon-lua chip.lua --inputs-timeline timeline.json --ticks 1000 --tps 60 --log-file run.log
melon-lua --api-list
```

## 输入输出与生命周期

与真实甜瓜一致：
- `inputs.*` / `outputs.*`（num/string/vec/entity/color/array_*）
- `OnInit` / `OnTick` / `OnSpawned(requestId, entities)` / `OnActivated` / `OnDeactivated` / `OnDestroy`

## 线程安全与性能

- 所有 tick 都是确定性的（Box2D + 固定种子）
- 无真实时间 sleep，适合批量模拟
- 推荐 `run_loop(ticks=...)` 而不是手动循环

## 限制

- 渲染为 2D 简易预览（无真实 sprite 裁剪/动画）
- 部分 ApiModule（mechanic/uicontrol/inputFilter）返回 mock 值
- spawn 目录当前使用别名 + 495 条尺寸表（非完整运行时菜单）

## 版本

当前 `__version__` 见 `melon_lua/__init__.py`。

## 从零构建存档（MelsaveBuilder）

`MelsaveBuilder` 用于从零程序化构建 .melsave：生成物品 + Lua 芯片 + 连线 +
导出。所有字段结构基于真机验证的 `1132luaexample.melsave`。

### 最小示例

```python
from melon_lua import MelsaveBuilder

b = MelsaveBuilder()

# 1. 生成一个物品（oid=202 = ResizablePlastic）
item = b.add_item(202, x=0.5, y=0.03, color=(0, 1, 0.3, 1))

# 2. 生成一个 Lua 芯片
chip = b.add_lua_chip(lua_source, x=-0.5, y=-0.03,
                      inputs=[{"name": "target", "type": "entity"}],
                      outputs=[{"name": "tick", "type": "number"},
                               {"name": "status", "type": "string"}],
                      tps=30)

# 3. 连线：物品的 entity 输出 -> 芯片的 target 输入
b.connect(item, "entity", chip, "target")

# 4. 导出
b.save("output.melsave")
```

### API

**生成对象**

- `add_item(object_id, x, y, *, color, dynamic, freezed, scale_x, scale_y, ...) -> int`
  生成一个可生成物品。返回容器索引。
  - `object_id`：甜瓜 objectId（202=塑料板, 132=引擎, 14=火箭主体, ...）
  - `color`：RGBA 元组 (0-1)
  - 从模板池 `melon_lua/data/item_templates/<oid>.json` 或
    `temp/objectid_templates/<oid>.json` 克隆
- `add_lua_chip(lua_source, x, y, *, inputs, outputs, variables, tps, title) -> int`
  生成一个 Lua 芯片。返回容器索引。
  - `inputs`/`outputs`：gate dict 列表，每个含 `name`/`type`/`value`(可选)
  - type 别名：`"entity"` | `"number"` | `"string"` | `"vector"` | `"int"`
  - `variables`：`{"name": str, "value": float}` 列表（持久芯片变量）
  - `tps`：ticks per second（默认 30）
  - `instruction_cost`：每 tick 最大指令数（默认 1000）
- `add_container(save_objects) -> int` — 直接添加原始 saveObjects dict

**连线**

- `connect(source_idx, output_gate, target_idx, input_gate, *, name="") -> dict`
  从源容器的输出门连线到目标容器的输入门。
  - 每个可生成物品都有一个内置 `"entity"` 输出门，提供物品自身的 entity id
  - 约束存在**源对象**（输出端）的 constraints 列表

**查询**

- `containers() -> list[dict]` — 所有容器（idx/objectId/type/position）
- `container_count` — 容器数量
- `get_container(idx) -> dict` — 获取容器 saveObjects

**导出**

- `save(out_path, *, write_icon=True) -> Path` — 写 .melsave ZIP
- `set_meta(**kwargs)` — 覆盖 MetaData 字段
- `set_icon(bytes)` / `load_icon_from(path)` — 设置图标

### Gate 类型映射

| 别名 | GateDataType | LuaValue.Type | 说明 |
|------|-------------|---------------|------|
| `entity` | 1 | 6 | 实体引用 |
| `number`/`num` | 2 | 1 | 浮点数 |
| `int`/`integer` | 2 | 2 | 整数 |
| `string`/`str` | 4 | 3 | 字符串 |
| `vector`/`vec` | 8 | 4 | 向量 |

### 芯片系统门

每个芯片自动包含以下**系统门**（无需手动声明）：

- **系统输入**：`activation`（Number，默认值 1.0）
- **系统输出**：`entity`（Entity）、`activation`（Number）、`tick`（Number）、
  `status`（String）

这些对应 Lua 代码中的 `inputs.num.activation`、`outputs.entity.entity`、
`outputs.num.tick`、`outputs.string.status`。用户只需声明额外的自定义门。

### 与 MelsaveSession 的区别

| 特性 | MelsaveBuilder | MelsaveSession |
|------|---------------|----------------|
| 场景 | 从零构建存档（blueprint） | 修改/扩展存档（runtime + diff） |
| 物理模拟 | 无（只构建 JSON） | 有（Box2D + Lua 运行） |
| 物品生成 | `add_item()` | `spawn()` / world diff |
| 芯片持久化 | `add_lua_chip()` | `add_lua_chip()` + `run_chip()` |
| 芯片执行 | 无 | `run_chip()` / `tick()` |
| 连线 | `connect()` | `wire_gate()` / `unwire_gate()` |
| 绳索 | 无 | `create_rope()` / `remove_rope()` |
| 导出 | `save()` | `save_as()`（返回绝对路径） |

两者在芯片持久化上语义对齐：`add_lua_chip()` 都把源码写入 `lua_chip_source`
元数据。MelsaveSession 额外支持运行时 `run_chip()` 编辑源码并自动同步回容器。

## UI 控制器构建（UIControllerBuilder）

`UIControllerBuilder` 构建甜瓜 UI 控制器（objectId=2046689600）——一个带屏幕
UI 元素（按钮、滑块、摇杆等）的面板。每个元素有输入门（属性配置 + 控制信号）
和输出门（交互事件 + 布局状态）。

### 元素类型

| 工厂方法 | Type | 输出门 | 说明 |
|---------|------|--------|------|
| `.button()` | 1 | `Button is down` / `Button is up` | 按钮 |
| `.pedal()` | 2 | 同上 | 踏板（按钮变体） |
| `.slider()` | 5 | `Value` | 滑块 |
| `.indicator()` | 6 | `Value` | 指示器（滑块变体） |
| `.joystick()` | 22 | `Joystick Activation` / `Joystick Direction` / `Joystick Angle` | 摇杆 |
| `.toggle()` | 17 | `Value` | 开关 |
| `.rotation_wheel()` | 12 | `Angle Value` / `Up direction` | 转向轮 |
| `.input_field()` | 11 | `Is changed` / `Field Value` | 文本输入框 |
| `.pointer()` | 14 | `Dot viewport/screen/worlds position` | 触控点 |
| `.screen()` | 18 | — | 屏幕（相机） |
| `.custom_icon()` | 19 | — | 自定义图标 |

每个元素还有 4 个布局输出门（`Anchor min/max out`、`Anchored position out`、
`Size delta out`）。

### 查询元素 schema（`element_schema`）

不需要记住每个元素类型的门列表——用 `element_schema()` 按需查：

```python
from melon_lua import element_schema

# 列出所有类型 + 输出门（快速概览）
element_schema()
# -> {"available_types": [{"type": "button", "outputs": [...]}, ...]}

# 查一个类型的完整 schema（输入门/输出门/默认值/工厂签名）
element_schema("button")
element_schema("slider")
element_schema("joy")   # 前缀匹配也可以
```

返回的 schema 结构：

```python
{
    "type": "slider",            # 规范名
    "type_ids": [5, 6, 7],       # save-data Type 值（含变体）
    "description": "滑块，拖动改变 Value 输出...",
    "inputs": [                  # 类型特定输入门（公共布局门省略）
        {"key": "Target value", "type": "number", "default": 0.0,
         "hint": "滑块/标签的目标值（运行时可改）"},
        {"key": "Min Value", "type": "number", "default": -1.0, "hint": "滑块最小值"},
        ...
    ],
    "outputs": [                 # 类型特定输出门
        {"key": "Value", "type": "number", "default": 1.0, "hint": "当前值"},
    ],
    "factory": "UIElement.slider(name, x, y, value=0, mn=0, mx=1, integers_only=False)",
}
```

公共布局门（每个元素都有，schema 中省略）：`Element shown`、`Element Title
shown`、`Button is interactable`、`Color`、`Label Pivot`、`Anchor min/max`、
`Anchored position`、`Size delta`、`Sorting order`（输入）和对应的 `... out`
（输出）。

### 最小示例

```python
from melon_lua import MelsaveBuilder, UIControllerBuilder, UIElement

# 1. 构建 UI 控制器
ctrl = UIControllerBuilder()
ctrl.add(UIElement.button("Fire", x=-150, y=100, text="FIRE"))
ctrl.add(UIElement.slider("Speed", x=150, y=100, value=5.0, mn=0, mx=10))
ctrl.add(UIElement.joystick("Move", x=0, y=-50))

# 2. 构建 Lua 芯片
b = MelsaveBuilder()
ui_idx = b.add_ui_controller(ctrl, x=0, y=0)
chip_idx = b.add_lua_chip(lua_source, x=3, y=0,
                           inputs=[{"name": "Value", "type": "number"},
                                   {"name": "Button is down", "type": "number"}],
                           outputs=[{"name": "status", "type": "string"}])

# 3. 连线：UI 输出 -> 芯片输入
b.connect(ui_idx, "Value", chip_idx, "Value")
b.connect(ui_idx, "Button is down", chip_idx, "Button is down")

b.save("ui_demo.melsave")
```

### 坐标系

- **屏幕像素坐标**：原点在屏幕中心，+x 向右，+y 向上
- `anchor_min` / `anchor_max`（0-1）：父容器相对锚点，默认 (0.5, 0.5) 居中
- `x` / `y`：距锚点的像素偏移（AnchoredPosition）
- `width` / `height`：元素尺寸像素（SizeDelta）

### UIElement API

```python
UIElement(type, name="", x=0, y=0, width=200, height=200,
          anchor_min=(0.5, 0.5), anchor_max=(0.5, 0.5), pivot=(0.5, 0.5),
          sorting_order=-1, color=(1,1,1,1), show=True, show_title=False,
          interactible=True, values={})
```

- `values`：自定义输入门值覆盖，键为门名（如 `"Button text"`、`"Target value"`），
  值为标量/字符串/向量元组
- 工厂方法（`.button()`、`.slider()` 等）预设了 type 和常见默认值

### Lua 侧读取 UI 输出

UI 元素的输出门被展平到 `mechanicSerializedOutputs`，通过 `mechCon` 约束路由
到芯片的 `inputs`。重复门名（如多个 `Value`）通过顺序区分。

```lua
function OnTick()
    local speed = inputs.num["Value"] or 0           -- slider value
    local btn = inputs.num["Button is down"] or 0    -- button state
    local joy = inputs.vec["Joystick Direction"]      -- joystick vector
    if joy then
        local dx, dy = joy.x, joy.y
    end
end
```

### 运行时操控（uicontrol API）

Lua 芯片可通过 `uicontrol` 模块运行时读取/修改已存在的 UI 元素值和位置：

```lua
local id = inputs.entity.target
if uicontrol.hasUIControl(id) == 1 then
    local elements = uicontrol.getElements(id)  -- "name|type|id" 数组
    local elId = uicontrol.findElement(id, "Speed")
    if elId then
        local val = uicontrol.getValue(id, elId, "Target value")
        uicontrol.setValue(id, elId, "Target value", 7.5)  -- 改滑块值
        uicontrol.setAnchoredPosition(id, elId, 100, 200)  -- 移动位置
    end
end
```

**限制**：`uicontrol` API 只能改运行时值和位置，不能创建/删除元素或改元素类型。

## melsave 全周期管理（MelsaveSession）

`MelsaveSession` 把 .melsave 文件的读、改、写收拢到一个对象里。原始存档文档
在内部持有，`save_as` 时自动 diff 当前 world 状态与原始存档，只 patch 改动
字段，保留所有未触碰字段。支持物理绳索（`create_rope`）和门连线
（`wire_gate`）的热创建/删除。

### 创建会话

```python
# 从已有存档加载
with MelsaveSession("input.melsave") as session:
    ...

# 从空白世界开始（无需现成存档）
with MelsaveSession() as session:        # 或 MelsaveSession.create_empty()
    session.spawn(202, 0, 0)             # 直接造物品
    session.save_as("new_world.melsave")
```

### 最小示例（加载 + 芯片 + 连线）

```python
from melon_lua import MelsaveSession

with MelsaveSession("input.melsave") as session:
    # 加载时自动读取现有门连线到 registry
    # 跑一个 Lua 芯片 100 tick
    session.run_chip(chip_source, ticks=100)
    # 拉一条物理绳索
    session.create_rope(from_id=1, to_id=2, kind="Simple", distance=1.5)
    # 热连一条门连线：c0 的 "Dot worlds position" -> c7 的 "target"
    session.wire_gate(0, "Dot worlds position", 7, "target")
    # 看当前状态
    snap = session.snapshot()
    print(snap["entity_count"], snap["ropes"])
    # 写回新存档（门连线 + 持久化芯片 自动导出）
    session.save_as("output.melsave")
```

### 从零创建带芯片的存档（无需现有存档）

```python
with MelsaveSession() as s:
    # 添加一个 Lua 芯片容器（会在 save_as 时持久化到存档）
    s.add_lua_chip(lua_source, x=1, y=2, title="MyChip",
                   inputs=[{"name":"target","type":"entity"}],
                   outputs=[{"name":"out","type":"number"}])
    # 编译 + 运行（源码自动同步回芯片容器）
    s.run_chip(lua_source, ticks=10)
    # 导出——真机直接可用
    s.save_as("chip_only.melsave")
```

### 生命周期

```
MelsaveSession(path)        # 创建（不读文件）；无参 = 空白世界
    .load()                 # 读取 + spawn 到 world + 构建 runner + 加载现有门连线
    [add_lua_chip]          # 添加持久化 Lua 芯片容器（save_as 时写入）
    [run_chip / tick]       # 编译并运行 Lua 芯片（源码同步到芯片容器）
    [create_rope / remove]  # 管理物理绳索/关节
    [wire_gate / unwire_gate]  # 热连线/断线（mechanic gate connections）
    [spawn / remove]        # 增删实体
    [snapshot / diff]       # 观察状态
    .save_as(out_path)      # diff + 合并门连线 + 持久化芯片 + 写回 .melsave
    .close()                # 释放 Box2D world + Lua VM
```

支持 `with` 上下文管理器（自动 load + close）。

### API 一览

**会话创建**

- `MelsaveSession(path=None, *, tps=20.0, quiet=True)` — path 省略时用空白世界
- `MelsaveSession.create_empty(**kw)` — 显式创建空白会话（等价 `MelsaveSession()`）

**芯片持久化 + 执行**

- `add_lua_chip(source, *, x, y, inputs, outputs, variables, tps, priority, title) -> idx`
  创建 Lua 芯片容器，标记为活跃芯片。save_as 时自动写入存档。
- `run_chip(source, *, ticks=1, inputs=None, container_idx=None) -> {"error", "outputs"}`
  编译 + OnInit + 跑 N tick。源码自动同步回活跃芯片容器（除非显式指定 container_idx）。
- `compile_only(source) -> bool` — 只编译不跑
- `tick(inputs=None) -> dict` — 单步 OnTick（需先 compile）
- `.outputs` / `.logs` / `.last_error` — 当前输出/日志/错误

**实体**

- `entities() -> list[dict]` — 所有存活实体快照
- `get_entity(eid)` — 取实体对象
- `spawn(name_or_id, x, y, **kw)` — 新增实体
- `remove(eid) -> bool` — 删除实体

**绳子/关节**（16 种 RopeTool 类型：Simple/Spring/FixedDistance/FixedLine/
Friction/Slider/Wheel/Relative/...）

- `create_rope(from_id, to_id, kind, **params) -> int` — 建绳，返回 constraint_id
- `remove_rope(constraint_id) -> bool` — 删绳
- `set_rope_param(constraint_id, key, value) -> bool` — 改绳参数
  （breakForce/distance/frequency/damping/enableCollisions/...）
- `ropes() -> list[dict]` — 当前所有绳子

**门连线 / 信号线**（mechanic gate connections — 芯片/实体门之间的信号路由）

门连线是 mechanic 约束（`constraintId=13`，带 `mechCon` 字段），与物理绳索
（`constraintId=10`，`mechCon=null`）共存于 `constraints` 列表。沙盒内可热
连线/断线，`save_as()` 时自动导出。

- `wire_gate(source_idx, output_gate, target_idx, input_gate, *,
  name="", start_point=(0,0), end_point=(0,0)) -> int`
  热连线：source 容器的 `output_gate` → target 容器的 `input_gate`。返回
  `wire_id`。
- `unwire_gate(wire_id=None, *, source_idx=None, target_idx=None,
  output_gate=None, input_gate=None) -> int`
  热断线。传 `wire_id` 删单条；否则按过滤组合删所有匹配。返回删除数。
- `wires() -> list[dict]` — 当前所有门连线（`wire_id`/`source_idx`/
  `target_idx`/`output_gate`/`input_gate`/`name`）

```python
with MelsaveSession("input.melsave") as s:
    # 加载时自动读取现有门连线到 registry

    # 热连线：c7 的 "input 2" 门 -> c5 的 "force" 门
    wid = s.wire_gate(7, "input 2", 5, "force",
                      name="left engine force",
                      start_point=(0.1, 0.0), end_point=(0.0, 0.1))

    # 热断线：按 id 或过滤组合
    s.unwire_gate(wire_id=wid)                    # 删单条
    s.unwire_gate(source_idx=7, target_idx=5)     # 按 source+target 删
    s.unwire_gate(output_gate="input 2")          # 按输出门名删

    # 列出当前连线
    for w in s.wires():
        print(f"c{w['source_idx']}.{w['output_gate']} -> "
              f"c{w['target_idx']}.{w['input_gate']}")

    # 导出：registry 非空时它是 source of truth
    # 每个 source container 的旧 mechanic 连线被替换为 registry 当前连线
    # 物理约束（constraintId=10）保留不动
    s.save_as("output.melsave")
```

**门连线 SDK 契约**（逆向自真机 2297.melsave + xj11）：

| 字段 | 值 | 说明 |
|------|----|------|
| `constraintId` | `13` | mechanic 连线固定值（10=物理绳索） |
| `mechCon.outputID` | 源门名 | 如 `"input 2"`、`"Dot worlds position"` |
| `mechCon.inputID` | 目标门名 | 如 `"force"`、`"activation"` |
| `startObjectId`/`endObjectId` | 容器索引 | 0-based 数组下标，非 objectId/localId |
| `startPoint`/`endPoint` | 视觉偏移 | 对象局部坐标系小值（<1.25），不影响信号路由 |
| `mainGuid` | UUID | `{"Value": uuid, "IsEmpty": false}` |
| 约束存放位置 | source 端 | 只在输出端对象的 `constraints` 列表存一份 |
| 门名空格 | 保留 | `"input 2"` 不转下划线 |

**快照/写回**

- `snapshot() -> dict` — {tick, elapsed, entities, ropes, variables, entity_count}
- `diff() -> dict` — 与原始存档的差异（modified/added/removed/constraints）
- `save_as(out_path, *, write_icon=True) -> Path` — diff + 写回 .melsave

**底层访问**

- `.world` — WorldContext 对象
- `.runner` — MelonScriptRunner 对象
- `.document` — 原始 MelsaveDocument（只读）

### 低层 API（不通过 Session）

```python
from melon_lua import (
    read_melsave, write_world_to_melsave, build_diff_from_world,
    WorldContext, MelonScriptRunner,
)
from melon_lua.melsave import spawn_document_into_world

doc = read_melsave("input.melsave")
world = WorldContext()
spawn_document_into_world(doc, world)
runner = MelonScriptRunner(world=world)
runner.compile(source)
runner.run_loop(ticks=100)
write_world_to_melsave(world, doc, "output.melsave")
```

### 低层门连线 API（JSON 级，无 live world）

适用于不创建 `MelsaveSession`、直接操作 Data JSON 的脚本（如
`scripts/build_new_rocket_save.py`）：

```python
import json, zipfile
from melon_lua import connect_gates, disconnect_gates, list_gate_connections

with zipfile.ZipFile("input.melsave", "r") as zf:
    data = json.loads(zf.read("Data").decode("utf-8"))

# 连线：c0 的 "Dot worlds position" -> c7 的 "target"
connect_gates(data, 0, "Dot worlds position", 7, "target",
              name="target position")

# 断线：按过滤组合
disconnect_gates(data, source_idx=7, output_gate="input 2")

# 列出连线
for c in list_gate_connections(data):
    print(f"c{c['source_idx']}.{c['output_gate']} -> "
          f"c{c['target_idx']}.{c['input_gate']}")

# 写回
from melon_lua import write_melsave
write_melsave("output.melsave", data, meta_json=None, icon_bytes=None)
```

### GateWireRegistry（直接使用）

`WorldContext.gate_wires` 字段是 `GateWireRegistry` 实例，也可直接操作：

```python
from melon_lua import WorldContext, GateWireRegistry

world = WorldContext()
wid = world.gate_wires.connect(7, "input 2", 5, "force", name="engine")
world.gate_wires.disconnect(wid)
world.gate_wires.disconnect_matching(source_idx=7, output_gate="input 2")
wires = world.gate_wires.list_all()  # list[GateWire]
```

`GateWire` dataclass 字段：`wire_id`/`main_guid`/`source_idx`/`target_idx`/
`output_gate`/`input_gate`/`start_point`/`end_point`/`name`/`start_material`/
`end_material`。

### 写回原理

1. `read_melsave` 把整个 `saveObjects` dict 存进 `MelsaveObject.raw`，零字段丢失
2. `build_diff_from_world` 比较当前 world 和原始 doc：
   - **modified**：position/rotation/scale/gravity/freezed/color 有变化的物体
   - **added**：world 里新增的实体（从 `temp/objectid_templates/<oid>.json` 克隆模板）
   - **removed**：world 里删掉但存档里有的实体
   - **constraints**：新建的绳子（按 startObjectId/endObjectId 分配到对应对象）
3. `patch_save_data` 在原始 Data JSON 的 deep copy 上应用 diff：
   - 修改的物体：deep merge patch 字段
   - 新增物体：追加到 saveObjectContainers
   - 删除的物体：从 containers 移除
   - 物理约束：合并到对应对象的 constraints 列表（按 mainGuid 去重保留原有约束）
4. **门连线合并**（`_merge_gate_wires_into_save`）：当 `world.gate_wires` 非空时，
   它是所有 mechanic 连线的 source of truth：每个 source container 的旧 mechanic
   连线（`constraintId=13`）被清除替换为 registry 当前连线；物理约束（`constraintId=10`，
   `mechCon=null`）保留不动。
5. **紧凑 JSON**：`write_melsave` 用 `separators=(",",":")` 匹配真机格式；
   缩进 JSON 会被真机加载器拒绝。
6. **instanceId 填什么都行**——真机加载时重新分配
7. **localId** 在存档里常为 0，真机加载时重建层级；沙盒用 index+1 作为匹配键

### 限制

- 新增物体只能用模板池里已有的 objectId（72 个常见物体）；不支持 modded objectId
- 物理精度不等价于真机（Box2D vs Unity 2D Physics）
- 渲染为简易 2D 预览，非真实 sprite
- mechanicData 的三重嵌套 JSON 改动需逐层 stringify（不动 mechanic 则原样保留）
- 门连线 `startPoint`/`endPoint` 是视觉偏移，沙盒不渲染连线外观，真机用于显示
