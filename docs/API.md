# Melon Lua Sandbox — Python SDK 参考


## 快速开始

```python
from melon_lua import (
    MelonScriptRunner, WorldContext,
    get_profile_by_object_id, object_id_for_name, list_spawnables,
    list_item_gates, render_world,
)

# 1. 准备世界（支持 456+ 物体，objectId 或名字）
world = WorldContext()
world.spawn_entity("202", 0, 1)                    # ResizablePlastic (塑料板)
world.spawn_entity("Box", 2, 5, dynamic=True)      # 按 gameObjectName
world.spawn_entity(23, -3, 4, scale_x=1.5)         # 直接用 objectId

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

# 直接操作实体（绕过 Lua）— 字段写入会同步 Box2D body
e = world.get_entity(eid) if not hasattr(eid, "entity_id") else eid
# spawn_entity 实际返回 Entity 对象：
e = world.spawn_entity("Box", 0, 2, dynamic=True)
e.set_velocity(3.0, 4.0)          # 或 e.velocity_x=3; e.velocity_y=4
e.position_x, e.position_y = 10, 20

# 门名查询（读模板，不必建场景）
from melon_lua import list_item_gates
print(list_item_gates("文字屏"))  # inputs/outputs: key + data_name

# 物理步进（run_tick 不会调这个）
world.tick(1/20)                  # 或 world.step_physics(1/20)
```

主要字段/方法：
- `entities: dict[int, Entity]`
- `spawn_entity(alias_or_id, x, y, dynamic=True, ...) -> Entity`（不是 int；id 用 `.entity_id`）
- `remove_entity(eid)`
- `tick(dt)` / `step_physics(dt)` / `step(dt)` — 推进 Box2D
- `set_entity_velocity(eid, vx, vy)`
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
e.position_x, e.position_y = 5, 10   # 写入会同步 Box2D body
e.set_velocity(3.0, 4.0)             # 或 set_linear_velocity；Lua 用 e:setVelocity
print(e.get_velocity())              # 优先读 body
print(e.real_size())                 # (w, h) 考虑 scale
print(e.sprite_path)                 # 贴图路径（若有）
# 力/扭矩请走 Lua Entity:addForce 或 world.get_body(id) 直接操作 body
```

### 目录 API（catalog）

```python
from melon_lua import (
    catalog_stats,
    get_profile_by_object_id,
    get_profile_by_name,
    list_spawnables, list_item_gates,
    object_id_for_name,
    resolve_spawn_name,
)

print(catalog_stats())                    # {"total": 456, "with_physics": 245, ...}
prof = get_profile_by_object_id(202)      # 完整 profile（含 width/height/mass/sprite）
oid = object_id_for_name("ResizablePlastic")  # 202
names = list_spawnables()                 # 所有可生成的名字
gates = list_item_gates("文字屏")         # 或 261 / "激光雷达"
# gates["inputs"]/["outputs"]: key, data_name, name, data_type, ...
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
- `inputs.*` / `outputs.*`（num/string/vec/entity/color/array_num/array_string/array_vec/array_entity）
- `OnInit` / `OnTick` / `OnSpawned(requestId, entities)` / `OnActivated` / `OnDeactivated` / `OnDestroy`
- **Vector4 格式**：array_vec / vec / color 类型的 Lua 值必须用**命名键** `{x=, y=, z=, w=}`。位置数组 `{r,g,b,a}` 会被游戏读成零向量（黑屏/无效果）。

## 线程安全与性能

- 所有 tick 都是确定性的（Box2D + 固定种子）
- 无真实时间 sleep，适合批量模拟
- 推荐 `run_loop(ticks=...)` 而不是手动循环

## 限制

- 渲染为 2D 简易预览（无真实 sprite 裁剪/动画）
- 部分 ApiModule（mechanic/uicontrol/inputFilter）返回 mock 值
- spawn 目录当前使用别名 + 495 条尺寸表（非完整运行时菜单）

## 从零构建存档（MelsaveBuilder）

`MelsaveBuilder` 是 `MelsaveSession` 的轻量包装，用于从零程序化构建 .melsave：
生成物品 + Lua 芯片 + 连线 + 导出。字段结构对齐真机存档。新代码可直接用
`MelsaveSession`（默认文档模式）；`MelsaveBuilder` 仅作「纯构造、不跑运行时」
的语义标记。

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
  - type 别名：`"entity"` | `"number"`/`"num"` | `"string"`/`"str"` | `"vector"`/`"vec"` | `"int"` | `"array_entity"` | `"array_num"` | `"array_string"` | `"array_vec"`
  - `variables`：`{"name": str, "value": float}` 列表（持久芯片变量）
  - `tps`：ticks per second（默认 30）
  - `instruction_cost`：每 tick 最大指令数（默认 1000）
- `add_container(save_objects) -> int` — 直接添加原始 saveObjects dict

**连线**

- `connect(source_idx, output_gate, target_idx, input_gate, *, name="") -> dict`
  从源容器的输出门连线到目标容器的输入门。
  - 门名可为 **Key 或 DataName**；写入 `mechCon` 前自动解析为真机 Key
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
| `array_entity` | 1024 | 7 | 实体数组（雷达 `entity array` 等） |
| `array_num`/`array_number` | 128 | 7 | 数值数组 |
| `array_string`/`array_str` | 256 | 7 | 字符串数组 |
| `array_vec`/`array_vector` | 512 | 7 | 向量数组 |

### 芯片系统门

每个芯片自动包含以下**系统门**（无需手动声明）：

- **系统输入**：`activation`（Number，默认值 1.0）
- **系统输出**：`entity`（Entity）、`activation`（Number）、`tick`（Number）、
  `status`（String）

这些对应 Lua 代码中的 `inputs.num.activation`、`outputs.entity.entity`、
`outputs.num.tick`、`outputs.string.status`。用户只需声明额外的自定义门。

### 内置传感器 / 显示物件

**区域雷达 Radar**（objectId=`892993856`，catalog `"Radar"` / `"radar"`）
**默认开启**，且 **默认 Select All**（检测名单）。

| 方向 | 门 |
|------|----|
| 输出 | `entity` / `activation` / `trigger` / `entity array` |
| 输入 | `activation` / `shift x` / `shift y` / `hide` / `width` / `height` |

**Select All（必做）**：真机过滤名单在 `saveMetaDatas` 键
`Radar_selected_entities`，`stringValue` 为 objectId **字符串** JSON 数组
（如 `["202","13",...]`）。模板/SDK 默认写入完整名单（等价 UI 点 Select All）；
`stringValue="[]"` 时范围内 **什么都侦测不到**，`entity array` 恒空。
`boolValue` 在真机存档里通常为 `false`，不要依赖它。
名单数据见 `melon_lua/data/radar_select_all_ids.json`；`add_item` 会强制写入。

**范围**：默认 sizeX/sizeY=1.0 极小——创建后必须调大（输入门 `width`/`height`
或 `mechanicData[0].floatParameters[4]`/`[5]`）。

`entity array` 接到芯片时声明 `{"name":"targets","type":"array_entity"}`，
Lua 用 `inputs.array_entity.targets` 遍历。数组元素是 **entity ID 数字**，
调用方法前必须 `Entity(id)` 包装：

```lua
local arr = inputs.array_entity.targets
if arr then
  for i = 1, #arr do
    local ent = Entity(arr[i])
    if ent:isValid() then
      ent:setVelocity(0, 0)
    end
  end
end
```

**激光雷达 Ranger**（objectId=`13`，catalog `"Ranger"` / `"激光雷达"`）
**默认开启**（`activation=1`）。输入 `activation` / `max dist` / `hide`；
输出 `entity` / `activation` / `dist` / `trigger` / `hit point` /
`hit normal` / `hit entity` / `physics-material`。默认 `RangerMode=All`。

**文字屏 ScreenTextDevice**（objectId=`261`，catalog `"ScreenTextDevice"` /
`"文字屏"`）**默认开启**。输入 `activation` + `text` + `color`；输出
`entity` / `activation` / `text` / `color`。文本输入门 UI 名是 `text`，
真机 Key 是 `string`——写 `s.connect(chip, "text", screen, "text")` 即可，
SDK 自动解析。

**LED 矩阵显示屏**（objectId=`596836672` / `LEDMatrixDisplay`）**默认开启**，
约 32×32。输入 `activation` + `led-matrix-data`(ArrayVector) + 可选
width/height/borders。
不要把芯片 width/height 接到屏上（初值 0 会被夹成 1×1）。Vector4 必须用
命名键 `{x=r,y=g,z=b,w=a}`。与库存 `LEDMatrix`(424) 不是同一物体。

### 与 MelsaveSession 的关系

`MelsaveBuilder` 内部就是一个纯文档模式的 `MelsaveSession`，方法
（`add_item`/`add_lua_chip`/`connect`/`save`）全部代理。两者在芯片持久化上
语义对齐：`add_lua_chip()` 都把源码写入 `lua_chip_source` 元数据。
`MelsaveSession` 额外支持运行时 `run_chip()` / 绳索 / 物理。

| 特性 | MelsaveBuilder | MelsaveSession |
|------|----------------|----------------|
| 场景 | 从零构建存档（blueprint） | 加载/修改/从零构建 + 可选运行时 |
| 物理模拟 | 无 | 可选（`.load()` 或 `with` 启动） |
| 物品 / 芯片 | `add_item()` / `add_lua_chip()` | 同左 + `run_chip()` / `tick()` |
| 连线 | `connect()` | `connect()` / `disconnect()` |
| 绳索 | 无 | `create_rope()` / `remove_rope()` |
| 导出 | `save()` | `save()`（`save_as` 是别名） |

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
from melon_lua import MelsaveSession, UIControllerBuilder

# 1. 构建 UI 控制器（add_* 返回 ElementHandle）
ctrl = UIControllerBuilder()
fire  = ctrl.add_button(x=-150, y=100, text="FIRE")   # ElementHandle
speed = ctrl.add_slider(x=150, y=100, value=5.0, mn=0, mx=10)
move  = ctrl.add_joystick(x=0, y=-50)

# 2. 构建 Lua 芯片
with MelsaveSession("ui_demo.melsave") as s:
    chip_idx = s.add_lua_chip(lua_source, x=3, y=0,
        inputs=[{"name": "speed", "type": "number"},
                {"name": "fire",  "type": "number"},
                {"name": "move",  "type": "vector"}],
        outputs=[{"name": "status", "type": "string"}])
    ui_idx = s.add_ui_controller(ctrl, x=0, y=0)

    # 3. 连线：ElementHandle 自动解析门名 + output_group
    s.connect(fire,  chip_idx, "fire")
    s.connect(speed, chip_idx, "speed")
    s.connect(move,  chip_idx, "move")        # 摇杆主输出 = "Joystick Direction"
```

### 坐标系

- **屏幕像素坐标**：原点在屏幕中心，+x 向右，+y 向上
- `anchor_min` / `anchor_max`（0-1）：父容器相对锚点，默认 (0.5, 0.5) 居中
- `x` / `y`：距锚点的像素偏移（AnchoredPosition）
- 元素尺寸（SizeDelta）从原型模板继承，不可通过参数覆盖

### ElementHandle（元素句柄）

`UIControllerBuilder.add_*()` 返回 `ElementHandle` 而非 `self`。句柄携带
元素 `group_id`（GUID）和主输出门名，可直接传给 `MelsaveSession.connect`：

| 属性 | 说明 |
|------|------|
| `.group_id` | 元素稳定 GUID（mechCon.outputGroup 用） |
| `.primary_output` | 该元素类型的主输出门名（Button→`"Button is down"`，Slider→`"Value"`，Joystick→`"Joystick Direction"`，...） |
| `.container_idx` | 被 `add_ui_controller` 绑定后的容器索引（绑定前为 None） |
| `.gate(name="")` | 返回 `(gate_name, group_id)`；name 为空时用主输出门 |

```python
btn = ctrl.add_button(x=0, y=0)
# 句柄传给 connect 时：
#   - output_gate 自动用 btn.primary_output（"Button is down"）
#   - output_group 自动用 btn.group_id
s.connect(btn, chip_idx, "fire")

# 多输出元素（如 Joystick）显式指定门：
joy = ctrl.add_joystick(x=0, y=0)
s.connect(joy, chip_idx, "move")              # 主输出 "Joystick Direction"
s.connect(ui_idx, "Joystick Angle", chip_idx, "angle",
          output_group=joy.group_id)          # 指定非主输出门
```

### UIElement API

```python
UIElement(type, name="", x=0, y=0,
          anchor_min=(0.5, 0.5), anchor_max=(0.5, 0.5), pivot=(0.5, 0.5),
          color=(1,1,1,1), show=True, show_title=False,
          interactible=True, values={})
```

- `values`：自定义输入门值覆盖，键为门名（如 `"Button text"`、`"Target value"`），
  值为标量/字符串/向量元组
- 工厂方法（`.button()`、`.slider()` 等）预设了 type 和常见默认值

### Lua 侧读取 UI 输出

UI 元素的输出门被展平到 `mechanicSerializedOutputs`，通过 `mechCon` 约束路由
到芯片的 `inputs`。重复门名（如多个 `Value`）通过 `output_group`（元素 GUID）区分。

### 连线与 output_group 路由

UI 元素的输出门名是**类型名**而非元素名——多个 Slider 都叫 `"Value"`，多个 Button
都叫 `"Button is down"`。真机靠 `output_group`（元素的 GroupId GUID）区分具体是
哪个元素。

**推荐**：用 ElementHandle，SDK 自动填门名 + `output_group`（见上方示例）。

**显式索引 + GUID**（拿不到句柄时）：

```python
ctrl = UIControllerBuilder()
ctrl.add_button(x=-150, y=0)        # 索引 0
ctrl.add_slider(x=150, y=0)         # 索引 1
s.connect(ui_idx, "Button is down", chip_idx, "fire",
          output_group=ctrl.element_group_id(0))
s.connect(ui_idx, "Value", chip_idx, "speed",
          output_group=ctrl.element_group_id(1))
```

- `element_group_id(index_or_name)`：返回元素稳定 GUID
- 不传 `output_group` 时连线仍能生成，但真机上多个同类型元素无法路由

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

`MelsaveSession` 是统一的存档抽象：一个 `.melsave` 文件 = 一个 session。
构造即读取文档（document 模式），`load()` 或 `with` 启动运行时（runtime 模式）。
两种模式下都能做容器增删、连线、save；运行时操作（run_chip/debug_run/tick/
run_ticks/spawn/create_rope/snapshot/inspect）需要先 load。

### 创建会话

```python
# 从已有存档加载（构造即读取文档）
session = MelsaveSession("input.melsave")
session.save("copy.melsave")             # 文档模式直接导出

# 从空白世界开始（无需现成存档）
with MelsaveSession() as session:        # 或 MelsaveSession.create_empty()
    session.add_item(202, 0, 0)          # 文档操作 + 运行时操作都可
    session.run_chip(chip_src, ticks=10)
    session.save("new_world.melsave")
```

### 最小示例（加载 + 芯片 + 连线）

```python
from melon_lua import MelsaveSession

with MelsaveSession("input.melsave") as session:
    # 构造即加载文档；with 启动运行时
    # 跑一个 Lua 芯片 100 tick
    session.run_chip(chip_source, ticks=100)
    # 拉一条物理绳索
    session.create_rope(from_id=1, to_id=2, kind="Simple", distance=1.5)
    # 连一条门连线：c0 的 "Dot worlds position" -> c7 的 "target"
    session.connect(0, "Dot worlds position", 7, "target")
    # 看当前状态
    snap = session.snapshot()
    print(snap["entity_count"], snap["ropes"])
    # 写回新存档（门连线 + 持久化芯片 自动导出）
    session.save("output.melsave")
```

### 从零创建带芯片的存档（无需现有存档）

```python
# 文档模式（不需要运行时，最轻量）
s = MelsaveSession()
s.add_lua_chip(lua_source, x=1, y=2, title="MyChip",
               inputs=[{"name":"target","type":"entity"}],
               outputs=[{"name":"out","type":"number"}])
s.save("chip_only.melsave")

# 或运行时验证模式
with MelsaveSession() as s:
    s.add_lua_chip(lua_source, x=1, y=2,
                   inputs=[{"name":"target","type":"entity"}],
                   outputs=[{"name":"out","type":"number"}])
    s.run_chip(lua_source, ticks=10)     # 编译 + 运行（源码同步到容器）
    s.save("chip_only.melsave")
```

### 生命周期

```
MelsaveSession(path=None)   # 构造即读取文档（path=None 用空白世界）
    .load()                 # 启动运行时（spawn 到 world + 构建 runner）
[文档模式操作 - 不需要 load]
    .add_item/add_lua_chip/add_ui_controller/add_container
    .connect/disconnect/list_connections
    .save()
[运行时操作 - 需要 load 或 with]
    [run_chip / debug_run]  # 最终结果 / 每 tick 轨迹
    [compile_only / tick / run_ticks]  # 单步
    [create_rope / remove]  # 管理物理绳索/关节
    [spawn / remove]        # 增删实体
    [inspect / snapshot / diff]  # 观察状态
    .close()                # 释放 Box2D world + Lua VM
```

支持 `with` 上下文管理器（自动 load + close）。`save()` 在两种模式下都工作，
`save_as` 是 `save` 的别名。

### API 一览

**会话创建**

- `MelsaveSession(path=None, *, tps=20.0, quiet=True, app_version="36.0", map_name="Default")`
  构造即读取文档；path=None 时用空白世界
- `MelsaveSession.create_empty(**kw)` — 显式创建空白会话（等价 `MelsaveSession()`）

**容器 / 文档操作**（两种模式都能用，不要求 load）

- `add_item(object_id, x, y, *, color, dynamic, freezed, template) -> int`
  新增物品容器，返回容器索引
- `add_lua_chip(source, *, x, y, inputs, outputs, variables, tps, priority, title) -> idx`
  新增 Lua 芯片容器，标记为活跃芯片；save 时自动写入存档
- `add_ui_controller(controller, x, y) -> int` — 新增 UI 控制器
- `add_container(save_objects_dict) -> int` — 新增原始容器
- `connect(src, out_gate, tgt, in_gate, *, name, start_point, end_point) -> dict`
  连线：`src.out_gate` → `tgt.in_gate`（返回 constraint dict）。
  门名可为 **Key 或 DataName**；SDK 写入前解析为真机 Key（见下节「门名适配」）
- `disconnect(src, *, output_gate, target_idx, input_gate, wire_id) -> int`
  断线，返回删除数（过滤名同样支持 Key/DataName）
- `list_connections(container_idx=None) -> list[dict]` — 列出连线
- `containers() -> list[dict]` / `get_container(idx) -> dict` / `.container_count`
- `set_meta(**kw)` / `set_icon(bytes)` / `load_icon_from(path)`

**芯片执行**（运行时操作）

- `run_chip(source, *, ticks=1, inputs=None, container_idx=None) -> {"error", "outputs"}`
  编译 + OnInit + 跑 N tick，**只返回最终** outputs。源码自动同步回活跃芯片容器。
- `debug_run(source, *, ticks=1, inputs=None, container_idx=None, stop_on_error=True, inputs_provider=None)`
  同上，但返回 **每 tick 轨迹**（适合 AI 排查中间状态）::

      {
        "error": str | None,
        "outputs": {...},          # 最终输出
        "frames": [                # 每 tick 一条
          {
            "tick": 0,
            "outputs": {...},
            "logs_delta": [("print", "...")],
            "error": None,
            "variables": {...},    # variables.Set/Get
            "entity_count": 3,
          },
          ...
        ],
        "logs": [...],             # 全量控制台
      }

- `compile_only(source) -> bool` — 只编译不跑
- `tick(inputs=None) -> dict` — 单步 OnTick（需先 compile；**不**推进 world）
- `run_ticks(n, *, inputs=None, inputs_provider=None, tick_callback=None, advance_world=True, stop_on_error=True)`
  在已编译芯片上跑 N 步（可带 `tick_callback(i, dt, result)`）。典型单步：

      s.compile_only(src)
      s.runner.call_on_init()
      s.run_ticks(10, tick_callback=lambda i, dt, r: ...)
      print(s.inspect())

- `inspect(*, log_tail=50) -> dict` — 只读汇总：`outputs` + `variables` + `entities` + `logs` + `error`（不推进模拟）
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
（`constraintId=10`，`mechCon=null`）共存于 `constraints` 列表。统一 API 用
`connect` / `disconnect` / `list_connections`。

```python
with MelsaveSession("input.melsave") as s:
    # 连线：c7 的 "input 2" 门 -> c5 的 "force" 门
    s.connect(7, "input 2", 5, "force",
              name="left engine force",
              start_point=(0.1, 0.0), end_point=(0.0, 0.1))

    # 断线：按过滤组合
    s.disconnect(7, output_gate="input 2")           # 按输出门名删
    s.disconnect(7, target_idx=5)                    # 按 source+target 删

    # 列出当前连线
    for w in s.list_connections():
        print(f"c{w['source_idx']}.{w['output_gate']} -> "
              f"c{w['target_idx']}.{w['input_gate']}")

    # 导出
    s.save("output.melsave")
```

**门连线 SDK 契约**

| 字段 | 值 | 说明 |
|------|----|------|
| `constraintId` | `13` | mechanic 连线固定值（10=物理绳索） |
| `mechCon.outputID` | 源门 **Key** | 如 `"input 2"`、`"Button is down"` |
| `mechCon.inputID` | 目标门 **Key** | 如 `"force"`、`"string"`（文字屏 text 门） |
| `startObjectId`/`endObjectId` | 容器索引 | 0-based 数组下标，非 objectId/localId |
| `startPoint`/`endPoint` | 视觉偏移 | 对象局部坐标系小值（<1.25），不影响信号路由 |
| `mainGuid` | UUID | `{"Value": uuid, "IsEmpty": false}` |
| 约束存放位置 | source 端 | 只在输出端对象的 `constraints` 列表存一份 |
| 门名空格 | 保留 | `"input 2"` 不转下划线 |

**门名适配（Key vs DataName）**

真机 `mechCon.inputID` / `outputID` 存的是 `mechanicSerialized*` 里的 **Key**，
不是 UI 显示的 **DataName**。多数门两者相同；例外：

| 物体 | 门 | Key | DataName |
|------|----|-----|----------|
| 文字屏 (261) | 文本输入 | `string` | `text` |
| UI Button | 按下 | `Button is down` | `Is down` |
| UI Button | 抬起 | `Button is up` | `Is up` |

`connect()` / `connect_gates()` 自动解析：Key 精确匹配 → DataName→Key →
大小写不敏感 → 原样回退。因此 `s.connect(chip, "text", screen, "text")`
写入 `inputID="string"`。底层：`resolve_gate_key(save_objects, "text", side="input")`。

**快照/写回**

- `inspect(*, log_tail=50) -> dict` — outputs + variables + entities + logs + error（agent 首选）
- `snapshot() -> dict` — {tick, elapsed, entities, ropes, variables, entity_count}
- `diff() -> dict` — 与原始存档的差异（modified/added/removed/constraints）
- `save(out_path, *, write_icon=True) -> Path` — 写回 .melsave
  文档模式直接序列化；运行时模式先应用 world diff 再写。
  `save_as` 是 `save` 的别名。

**底层访问**

- `.world` — WorldContext 对象（要求 load）
- `.runner` — MelonScriptRunner 对象（要求 load）
- `.document` — 原始 MelsaveDocument

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
from melon_lua import connect_gates, disconnect_gates, list_gate_connections, resolve_gate_key

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