## 最高优先级规则（违反即失败）

1. Entity 的 Lua 方法已固定，直接使用，禁止搜索/验证/探测
2. 这些方法100%存在，不需要验证。直接在芯片代码里用 e:getAngle() 即可
3. 禁止用 astrbot_grep_tool / astrbot_file_read_tool / astrbot_execute_shell
   搜索 melon_lua 的代码——它不在沙盒里，搜了也是 No matches found

# Melon Lua Sandbox — Python SDK 参考。

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

## 输入输出与生命周期

与真实甜瓜一致：

- `inputs.*` / `outputs.*`（num/string/vec/entity/color/array_*）
- `OnInit` / `OnTick` / `OnSpawned(requestId, entities)` / `OnActivated` / `OnDeactivated` / `OnDestroy`
- 推荐 `run_loop(ticks=...)` 而不是手动循环

## UI 控制器构建（UIControllerBuilder）

`UIControllerBuilder` 构建甜瓜 UI 控制器（objectId=2046689600）。元素工厂：
`button/pedal/slider/indicator/joystick/toggle/rotation_wheel/input_field/pointer/screen/custom_icon`。

```python
from melon_lua import UIControllerBuilder, element_schema

element_schema()           # 列所有类型 + 输出门
element_schema("button")   # 查一个类型的完整 schema（输入门/输出门/默认值）
```

## Python SDK（MelsaveSession）

一个 `.melsave` = 一个 `MelsaveSession`。构造即加载文档；`with` 或 `.load()`
启动运行时（Box2D + Lua VM）。`MelsaveBuilder` 是其纯文档模式包装。

```python
from melon_lua import MelsaveSession, UIControllerBuilder

# 文档模式（最常用）：构建 → 连线 → 导出
s = MelsaveSession()                                    # 或 MelsaveSession("input.melsave")
item = s.add_item(202, x=0, y=0)                        # 物品，返回容器索引
chip = s.add_lua_chip(src, x=1, y=0,                    # Lua 芯片
                      inputs=[{"name":"target","type":"entity"},
                              {"name":"throttle","type":"number","value":0.5}],
                      outputs=[{"name":"out","type":"number"}])
ui_ctrl = UIControllerBuilder()
slider = ui_ctrl.add_slider(value=0, mn=-1, mx=1)        # 返回元素句柄
ui = s.add_ui_controller(ui_ctrl, x=2, y=0)
s.connect(item, "entity", chip, "target")                # 连线（output→input）
s.connect(slider, chip, "throttle")                      # 句柄自动填门名 + output_group
s.save("out.melsave")                                    # 导出（save_as 是别名）

# 运行时模式：编译/跑芯片验证逻辑
with MelsaveSession("out.melsave") as s:
    r = s.run_chip(src, ticks=100)                       # 编译 + OnInit + N tick
    # r = {"error": str|None, "outputs": {<bucket>: {<gate>: <val>}}}
    #   bucket ∈ num/int/string/vec/entity/color/array_*
    #   读数值输出：r["outputs"]["num"]["out"]
    print(r["error"], r["outputs"]["num"])
    s.create_rope(from_id=1, to_id=2, kind="Simple")    # 物理绳索
    print(s.snapshot())                                  # {tick, entities, ropes, ...}
```

**inputs/outputs gate dict 字段**：
- `"name"`：门名（字符串，可含空格）
- `"type"`：`entity` | `number` | `int` | `string` | `vector`（别名：`num`/`str`/`vec`/`integer`）
- `"value"`（可选）：初始值。number→float、string→str、entity/int 无（连线提供）
- Lua 侧按类型分桶访问：`inputs.num.speed` / `inputs.entity.target` / `outputs.string.status`

**核心方法速查**（完整签名见 `docs/API.md`）

| 分类 | 方法 | 模式 |
|------|------|------|
| 容器 | `add_item(oid, x, y, *, color, dynamic, freezed, template) -> idx`<br>`add_lua_chip(src, x, y, *, inputs, outputs, variables, tps, title) -> idx`<br>`add_ui_controller(ctrl, x, y) -> idx`<br>`add_container(save_objects_dict) -> idx` | 文档+运行时 |
| 连线 | `connect(src, out_gate, tgt, in_gate, *, name, start_point, end_point) -> dict`<br>`disconnect(src, *, output_gate=None, target_idx=None, input_gate=None, wire_id=None) -> int`<br>　· `wire_id` 删单条；其余参数组合过滤删多条<br>`list_connections(container_idx=None) -> list[dict]` | 文档+运行时 |
| 观察 | `containers() / get_container(idx) / container_count` | 文档+运行时 |
| 导出 | `save(out, *, write_icon=True) -> Path` | 文档+运行时 |
| 芯片 | `run_chip(source, *, ticks, inputs, container_idx) -> {"error","outputs"}` | 运行时 |
| 实体 | `spawn/remove/entities/get_entity` | 运行时 |
| 绳索 | `create_rope/remove_rope/set_rope_param/ropes` | 运行时 |
| 状态 | `snapshot/diff` | 运行时 |
| 底层 | `.world` / `.runner` / `.document` | 运行时 / 任意 |

**`add_item` 常用参数**：`color=(r,g,b,a)` 0-1 RGBA 元组；`dynamic=True` 受重力；`freezed=True` 冻结。

**UIControllerBuilder 工厂签名**（`add_*` 返回 ElementHandle，不再返回 self）：
- `.add_slider(value=0, mn=0, mx=1)` / `.add_button(text="")` / `.add_joystick(multiplier=1.0)` / `.add_toggle(active=False)`
- 其余：`add_pedal/add_indicator/add_rotation_wheel/add_input_field/add_pointer/add_screen/add_custom_icon`
- **ElementHandle**：`.group_id`（GUID）/ `.primary_output`（主输出门名，如 Slider→`"Value"`）/ `.gate(name)`（返回 `(gate_name, group_id)`）
- 句柄直接传 `connect(handle, target_idx, input_gate)`，SDK 自动解析门名 + `output_group`
- 多输出元素（Joystick）用 `s.connect(ui_idx, "Joystick Angle", chip, "angle", output_group=joy.group_id)` 指定非主输出
- `.element_group_id(索引或名称)`：旧式 API，返回元素 GUID（仍兼容）
- `element_schema()` 无参返回 `{"available_types":[{"type","outputs"},...]}`；`element_schema("slider")` 返回单类型完整 schema（输入门/输出门/默认值/工厂签名）

**门连线规则**（mechanic gate connections）：
- `constraintId=13`（物理绳索是 10），存 source 端对象的 `constraints` 列表
- `startObjectId`/`endObjectId` 是容器索引（0-based），非 objectId
- 门名保留空格（`"input 2"` 不转下划线）
- **UI 控制器元素同名门**（多个 Slider 都叫 `"Value"`）必须用 ElementHandle 或 `output_group=ctrl.element_group_id(索引)` 指定具体元素，否则真机无法路由

## MelonLuaSandbox 插件使用规范

使用 run_melon_python / run_melon_lua 时必须遵守：

### 符号来源

`WorldContext`/`MelsaveSession`/`Entity` 等 SDK 类已 `from melon_lua import` 进作用域，直接用。

### 物理 API 陷阱

- `world.spawn_entity(name, x, y)` 返回 **Entity 对象**，不是 int。取 id 用 `.entity_id`
- `runner.run_tick(inputs)` **只跑 Lua，不步进物理**。用 `runner.run_loop(ticks=N)` 代替手动循环
- Box2D body inertia 极小（~0.01），torque 量级 0.001~0.1，超过 10 会饱和角速度导致震荡

### 效率要求

- 禁止用 inspect.getsource 探索 API —— docstring 已列出全部符号和用法
- 禁止用 astrbot_execute_shell/astrbot_file_read_tool 操作 melon_lua —— 沙盒环境里没有这个包
- 单次 run_melon_python 尽量完成完整逻辑链，不要每次只改一个变量重跑
- 连续调用同一工具超过 3 次时，停下来重新评估策略，不要盲目重试

# Melon Lua 芯片开发完整指南（含标准库）

本文档整合原 `guide.md` 并补充完整标准库说明、生命周期、API 速查等。

## 标准库（甜瓜芯片允许范围）

详见 `docs/stdlib.md`。

**快速记忆**：

- 可用：math / string / table / coroutine / bit32 / 有限 os（time/clock） + 所有基础全局
- 禁用：io / package / debug / load* / collectgarbage 等

## 特殊 API 模块（游戏功能）

### 1. 输入输出系统（类型化）

```lua
local speed = inputs.num.speed or 1
local target = inputs.entity.target
outputs.num.tick = tick
outputs.string.status = "ok"
outputs.vec.dir = {x=1, y=0, z=0, w=0}
outputs.color.tint = {r=1, g=0, b=0, a=1}
```

### 2. 变量系统

```lua
variables.Set("total_ticks", value)   -- 返回 1.0 成功，类型一旦锁定不能改
local v = variables.Get("total_ticks")
```

### 3. 共享数据（跨芯片）

```lua
shared.heartbeat = tick
shared.Save()
shared.Load()
```

### 4. 信号系统（事件总线）

```lua
signal.on("damage", function(d)
    print(d.amount)
end)
signal.emit("damage", {amount = 10})
signal.defer("next_tick_event", data)
```

### 5. 输入处理

```lua
-- Pointer (鼠标)
if input.pointerDown() == 1 then
    local wx, wy = input.pointerPos()           -- 世界坐标
    local sx, sy = input.pointerScreenPos()      -- 屏幕坐标
    local dx, dy = input.pointerDelta()          -- 帧间位移
end
if input.isOverUI() == 1 then ... end
local hit = input.pointerRaycast()               -- raycast 命中实体
local hits = input.pointerRaycastAll()           -- 所有命中

-- Touch (多点触控，索引 0 起)
local n = input.touchCount()
if input.touchDown(0) == 1 then
    local wx, wy = input.touchPos(0)
    if input.touchTap(0) == 1 then ... end
    if input.touchSwipe(0) == 1 then ... end
end

-- Pinch (双指缩放)
local pd = input.pinchDistance()
local pa = input.pinchAngle()
local pcx, pcy = input.pinchCenter()

-- Keyboard
if input.key("space") == 1 then ... end
if input.keyDown("a") == 1 then ... end          -- 仅按下那一帧
```

### 6. 环境信息

```lua
env.deltaTime()               -- 上一帧 dt（秒）
env.fixedDeltaTime()
env.time()                    -- 自芯片启动累计时间
env.sessionTime()             -- 会话时间
env.entityCount()             -- 当前实体数
env.frameCount()              -- 总帧数
env.timeScale()               -- 时间缩放
env.setTimeScale(0.5)         -- 慢动作
env.systemTime()              -- 系统时间戳
env.systemDate()              -- 系统日期字符串
env.toDate(env.systemTime())  -- 时间戳 → 日期串
env.toTimeFormat(env.sessionTime())
env.parseDate("2024-01-01")
env.isWorld()                 -- 是否在 World 模式
env.isWorldEditor()           -- 是否在编辑器
```

### 7. 相机

```lua
camera.follow(targetId)
camera.setPosition(0, 5)
camera.setZoom(8)
```

### 8. 生成系统（spawn）—— 重要

```lua
-- 立即返回 requestId，实体稍后通过 OnSpawned 回调
local req = spawn.create(202, 0, 1)                 -- objectId 或 "ResizablePlastic"
spawn.createWithAngle("Box", 0, 0, 45)
spawn.clone(entityId, x, y)
spawn.cloneTemp(entityId, x, y)   -- 临时实体
spawn.createSave("my_save", x, y)
spawn.createMod("my_mod", x, y)
spawn.destroy(entityId)

function OnSpawned(requestId, entities)
    -- entities 是 Entity 对象数组
    if entities and entities[1] then
        print("Spawned id=" .. entities[1]:getId())
    end
end

-- 查询目录（调试用）
print(spawn.getItemCount())
print(spawn.getSaveCount())
print(spawn.getModCount())
print(spawn.getNameByAlias("human"))
print(spawn.existsByAlias("human") and "yes" or "no")
```

**注意**：沙盒中 `spawn.create` 会**立即创建实体**（便于物理模拟），仍正确返回 requestId 并在 tick 末触发 OnSpawned。

### 9. 世界控制

```lua
world.save()
world.load()
world.reset()
world.clearCorpses()       -- 清除尸体
world.clearDecals()        -- 清除弹孔/痕迹
world.clearGibs()          -- 清除碎块
world.clearLiving()        -- 清除活体
world.radioSignal("ch")    -- 无线电信号
world.isSessionActive()
world.startSession()
world.endSession()
```

### 10. 芯片自省（chip.*）

读写当前/其他芯片的输入输出门值与状态。

```lua
chip.has(eid)                 -> 1/0
chip.getType(eid)             -> "LuaChip" / "VPChip" / ...
chip.getInputs(eid)           -> {"gateName|Type", ...}
chip.getOutputs(eid)
chip.getValue(eid, "out1")    -> 当前值
chip.setValue(eid, "in1", v)  -> 1 成功 / 0（门已连线则拒绝）
chip.hasWire(eid, "in1")      -> 1/0
chip.getActivation(eid)
chip.setActivation(eid, 1.0)
chip.getName(eid)             -> 芯片名字串
chip.getTPS(eid)              -> 每秒 tick 数（默认 20）
```

### 11. 机制自省（mechanic.*）

普通机制（非芯片）的门值/连线查询，如按钮、传感器等可接线实体。

```lua
mechanic.has(eid)                 -> 1/0
mechanic.getType(eid)
mechanic.getInputs(eid)           -> {"gateName|Type", ...}
mechanic.getOutputs(eid)
mechanic.getValue(eid, "out")
mechanic.setValue(eid, "in", v)   -> 1 成功 / 0（已连线拒绝）
mechanic.hasWire(eid, "in")       -> 1/0
mechanic.getActivation(eid)
mechanic.setActivation(eid, 1.0)
```

## 模块化（register_module / require）

```lua
register_module("utils", {
    clamp = function(v, lo, hi) return math.max(lo, math.min(hi, v)) end
})

local utils = require("utils")
utils.clamp(150, 0, 100)
```

## 甜瓜标准库快速参考（新增）

见 `docs/stdlib.md` 完整清单。

**最常用**：

- `math.random`, `math.floor`, `math.abs`, `math.sin`...
- `string.format`, `string.sub`, `string.match`...
- `table.insert`, `table.remove`, `table.pack`, `#t`
- `bit32.band`, `bit32.bor`, `bit32.lshift`...
- `coroutine.create`, `coroutine.resume`...
- `os.time()`, `os.clock()`
- 基础：`pairs`, `ipairs`, `pcall`, `type`, `tostring`, `tonumber`, `error`, `assert` 等

**绝对不要用**：`io.open`, `require("some_native_module")`, `debug.getinfo`, `loadstring` 等。

## 示例：带标准库 + spawn 的完整芯片

```lua
function OnInit()
    print("Plastic demo start")
    spawn.create(202, 0, 1)   -- 塑料板
end

function OnSpawned(req, ents)
    if ents and ents[1] then
        outputs.num.spawned_id = ents[1]:getId()
    end
end

function OnTick()
    local e = Entity(1)
    if e:isValid() == 1 then
        local x, y = e:getPosition()
        outputs.num.x = x
        outputs.num.y = y
    end
end
```

运行：

```bash
melon-lua samples/plastic_demo.lua --ticks 10
```

## AI 代码生成规则

1. **必须按照用户的指示交付 melsave 文件**
2. **直接给出可运行的完整代码**
3. **用 `inputs.entity.xxx` 前先检查 `~= 0`**（id=0 = 未连线）
4. **用 `Entity(id)` 前先 `e:isValid() == 1`**
5. **避免 spawn 在 OnTick 里循环调用**（会爆实体上限）
6. **outputs 赋值前确认 gate 已声明**
7. **dt 用 `env.deltaTime()`**，不要自己算
8. **颜色值 clamp 到 0-1**，超范围真机会崩
9. **优先用自动化优化算法**（网格/二分/贝叶斯）在单次 `run_melon_python` 内完成调参，手动试错会浪费大量工具调用

### Entity 方法签名速记

```lua
-- Transform
e:getPosition()          -> x, y         -- 返回两个值！
e:setPosition(x, y)
e:getAngle()             -> a            -- 度数
e:setAngle(a)
e:getScale()             -> sx, sy
e:setScale(sx, sy)
e:getNormal()            -> nx, ny

-- Physics
e:getVelocity()          -> vx, vy
e:setVelocity(vx, vy)
e:getAngularVelocity()  -> w
e:setAngularVelocity(w)
e:addForce(fx, fy)
e:addTorque(t)
e:addForceAtPosition(fx, fy, px, py)
e:getVelocityAtPoint(px, py) -> vx, vy
e:getMass()              -> m
e:getCenterOfMass()      -> cx, cy
e:getGravityScale()      -> s
e:setGravityScale(s)

-- State
e:isValid()              -> 1/0          -- 整数不是 bool
e:getId()                -> id
e:getName()              -> name
e:getLocalizedName()     -> name
e:getColor()             -> r, g, b, a    -- RGBA 0-1
e:setColor(r, g, b, a)                   -- a 可省略，默认 1
e:isVisible()            -> 1/0
e:setVisible(flag)
e:freeze(flag)                           -- flag=1 冻结, 0 解冻
e:freezeRotation(flag)
e:delete()

-- Temperature / Fire
e:getTemperature()       -> t
e:setTemperature(t)
e:isOnFire()             -> 1/0
e:isFrozen()             -> 1/0
e:ignite()
e:extinguish()

-- Health / Damage
e:getHealth()            -> h
e:isBreakable()          -> 1/0

-- Voltage (electric)
e:getVoltage()           -> v

-- Draggable / Activation
e:isDraggable()          -> 1/0
e:setDraggable(flag)
e:canBeActivated()       -> 1/0
e:activate()
e:getActivationInput()   -> 1/0

-- Hierarchy (grouped/parented entities)
e:getRoot()              -> rootEntity
e:getParent()            -> parentEntity
e:getChildren()          -> {child, ...}

-- Size / Bounds (all return multiple values)
e:getSize()              -> w, h
e:getBaseSize()          -> w, h
e:getBounds()            -> minX, minY, maxX, maxY
e:getFullBounds()        -> minX, minY, maxX, maxY
e:getColliderBounds()    -> minX, minY, maxX, maxY

-- Misc
e:lookAt(targetId, degPerSec)   -- 旋转看向另一实体（默认 360°/s）
e:getElevation(tx, ty)       -> ang   -- 朝目标点的仰角（度）
e:getPhysicMaterial()        -> "Default" / "Ice" / ...
e:setCollisionEnabled(flag)

-- Static query (on Entity class, not instance)
Entity.all()             -> {e, ...}     -- 所有实体
Entity.find("Human")     -> e / nil      -- 按名字首匹配

-- Collision / Trigger callbacks
e:subscribeCollisionEnter(cb)
e:subscribeCollisionExit(cb)
e:subscribeCollisionStay(cb)
e:subscribeTriggerEnter(cb)
e:subscribeTriggerExit(cb)
e:subscribeTriggerStay(cb)
e:subscribeWireConnected(cb)
e:subscribeWireDisconnected(cb)
e:unsubscribeCollisionEnter(cb)
-- ...对应 unsubscribe* 版本
e:unsubscribeAll()

-- Coord conversion
e:localToWorld(lx, ly)   -> wx, wy
e:worldToLocal(wx, wy)   -> lx, ly
e:localAngleToWorld(la)  -> wa
e:worldAngleToLocal(wa)  -> la
```

## 常见陷阱

- entity id = 0 → 输入未连线，不是bug
- force/torque = 0 → 检查上游 gate 是否连接
- inputs.entity.xxx 返回 nil → gate 名拼写/类型错误
- 芯片在真机不工作 → 系统门超过4个（只允许 entity/activation/tick/status）
- 物体不动 → gravity=false 或 freezed=true

