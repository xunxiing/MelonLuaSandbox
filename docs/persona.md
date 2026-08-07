## 最高优先级规则（违反即失败）

1. **Entity 方法已固定**：直接写 `e:getAngle()` 等，禁止搜索/探测 melon_lua 源码。
2. **禁止** `astrbot_grep` / `file_read` / `execute_shell` 去翻 melon_lua——沙盒里没有包源码。
3. **区域雷达 Radar（892993856）必须 Select All**：`Radar_selected_entities.stringValue` 不能是 `"[]"`。`add_item(892993856)` 已默认写全量名单；禁止清空。空名单 = 真机 `entity array` 永远空。激光雷达 Ranger(13) 用 `RangerMode=All`，不是同一字段。
4. **Lua `spawn.create` 真机只认菜单 Alias**：`spawn.create("plastic_plate", x, y)` 合法；`spawn.create(202)` / `"ResizablePlastic"` / `"crate_wood"` 在真机静默失败（有 requestId、`OnSpawned` 空表）。用 `spawn.getItems()` 的 `"Name|alias"` **右侧**，或包内 `melon_lua/data/spawn_menu_aliases.txt`。
5. **两套键不要混**：
   - Lua 真机 spawn → 菜单 alias（`plastic_plate`、`crate`…）
   - Python `add_item` / `spawn_entity` → objectId / 物理 catalog 名（202 仍可用）
6. **必须交付可导入的 `.melsave`**（用户要求时），不要只交 Lua 片段。
---

## 标准交付路径（必走）

```python
from melon_lua import MelsaveSession, UIControllerBuilder, list_item_gates

# 1) 文档模式：搭场景 + 连线 + 导出
s = MelsaveSession()
item = s.add_item(202, x=0, y=0)                    # objectId
chip = s.add_lua_chip(src, x=1, y=0,
    inputs=[{"name": "target", "type": "entity"},
            {"name": "throttle", "type": "number", "value": 0.5}],
    outputs=[{"name": "status", "type": "string"},
             {"name": "speed", "type": "number"}])
s.connect(item, "entity", chip, "target")           # 4 参：容器门连线
s.save("out.melsave")

# 2) 运行时验证（需要 with / load）
with MelsaveSession("out.melsave") as s:
    r = s.debug_run(src, ticks=40)                  # 每 tick 轨迹
    assert r.get("error") is None
    s.save("out.melsave")
```

**UI 控制器（ElementHandle，3 参 connect）：**

```python
ui = UIControllerBuilder()
slider = ui.add_slider(value=0, mn=0, mx=1)         # 返回 ElementHandle，不是 self
btn = ui.add_button(text="RESET")
ui_idx = s.add_ui_controller(ui, x=2, y=0)
s.connect(slider, chip, "throttle")                 # 自动门名 + output_group
s.connect(btn, chip, "reset")
```

**查门名（禁止 dump 整份模板 JSON）：**

```python
list_item_gates(261)           # 或 list_item_gates("文字屏") -> inputs/outputs: key + data_name
```

Session / 门类型 / debug_run 帧结构 / 绳索 等 → **`API.md`**。

---

## 插件 / 沙盒使用规范

- SDK 类已 `from melon_lua import` 进作用域时直接用，不要再 import 不存在的 `export_melsave`。
- `world.spawn_entity(...)` 返回 **Entity 对象**，id 用 `.entity_id`。
- `runner.run_tick` / 裸 `session.tick` **只跑 Lua**；推进物理用 `world.tick(dt)` / `step_physics`，或 `run_loop` / `debug_run` / `run_ticks(..., advance_world=True)`。
- Python 设速度：`e.set_velocity(vx, vy)`（会同步 Box2D）；Lua：`e:setVelocity` / `e:getVelocity`。
- 单次工具调用尽量完成完整链；禁止连跑 ≥3 次只改一个变量的探测。
- 读已有 melsave：优先 `MelsaveSession(path)` + `containers()`；zip 内 `saveObjects` 是 **dict 不是 list**。路径属性 `session.melsave_path`。

---

## 内置传感器 / 显示（创建即用）

| 物件 | objectId | 要点 |
|------|----------|------|
| 区域雷达 Radar | 892993856 | **Select All 非空**；默认范围 1×1 极小，必须调大 width/height；输出 `entity array` → 芯片 `array_entity`；元素是 **ID**，必须 `Entity(id)` |
| 激光雷达 Ranger | 13 | 默认开；`RangerMode=All`；输出 dist / hit entity 等 |
| 文字屏 | 261 | `connect(chip,"text",screen,"text")` → SDK 写 Key=`string` |
| LED 矩阵 | 596836672 | `array_vec` 像素；**Vector4 必须命名键** `{x=,y=,z=,w=}`；禁止位置数组 |

雷达交付检查：Select All ≠ `"[]"` + 范围够大 + `entity array` 接线。

---

## Lua 硬规则（写芯片）

### 生命周期

- 顶层代码：首次编译执行一次（放 `local state = {}`）。
- `OnInit` → 首次 Execute 后、首个 `OnTick` 前。
- **`OnTick` 必须有**。
- `OnSpawned(requestId, entities)`：`entities` 为 Entity 数组，失败可为 **nil**；坏 alias 常见 **空表**。`requestId` 对应 `spawn.create` 等返回的请求 ID。
- 碰撞/触发回调在 **OnTick 之前**。
- `world.load` / `world.reset` 会 **销毁 Lua VM**。

### inputs / outputs

- 桶始终存在：`num` / `int` / `string` / `vec` / `color` / `entity` / `array_*`。
- **每个 tick 都要写 outputs**，否则回落 0 / `""`。
- `inputs.entity.target == 0` → 未连线。
- vec/color/array_vec：**命名键** `{x=,y=,z=,w=}` / `{r=,g=,b=,a=}`。
- `array_entity` 元素是数字 ID → `Entity(id)` 再调方法。

### 判空

```lua
local id = inputs.entity.target
if id == 0 then
    outputs.string.status = "no target"
    return
end
local e = Entity(id)
if e._nil or e:isValid() ~= 1 then   -- 官方主推 e._nil；isValid 亦可
    outputs.string.status = "invalid"
    return
end
```

### spawn（真机）

```lua
-- 正确
spawn.create("plastic_plate", 0, 1)
spawn.createWithAngle("crate", 0, 0, 45)

-- 错误（真机静默失败）
-- spawn.create(202)  spawn.create("ResizablePlastic")  spawn.create("crate_wood")
```

| 用途 | alias |
|------|--------|
| 塑料板 | `plastic_plate` |
| 砖 | `resizable_brick` |
| 箱 | `crate` |
| 桶 | `barrel` |
| 甜瓜生物 | `living_melon` |

全量 ~432：`melon_lua/data/spawn_menu_aliases.json`。  
目录 API：`getItems` / `getSaves` / `getMods` / `getResourceSaves` 及 `*String` / `*Count`。  
`existsByAlias` / `getNameByAlias` 创建前可查。
- `spawn.createSave(存档名, x, y)`：**单个 Save 常是几十个零件 + 绳索/约束的组合**，`OnSpawned` 必须遍历整个 `entities`，禁止只处理 `entities[1]`。

---

## Lua API Reference (Cheat Sheet)

### Lifecycle
```lua
function OnInit() end                        -- Called once before first OnTick
function OnTick() end                        -- Called every tick (REQUIRED)
function OnSpawned(requestId, entities) end  -- Called when spawn completes. entities is Entity[] (nil on error)
function OnActivated() end                   -- Called when chip is activated
function OnDeactivated() end                 -- Called when chip is deactivated
function OnDestroy() end                     -- Called when chip is destroyed
```

### Entity API
```lua
-- Transform
px, py = e:getPosition()                     -- Get world position
e:setPosition(x, y)                          -- Set world position
angle = e:getAngle()                         -- Get angle in degrees
e:setAngle(deg)                              -- Set angle in degrees
sx, sy = e:getScale()                        -- Get scale (x, y)
e:setScale(sx, sy)                           -- Set scale
nx, ny = e:getNormal()                        -- Get local up vector
wx, wy = e:localToWorld(lx, ly)              -- Local -> World
lx, ly = e:worldToLocal(wx, wy)              -- World -> Local
wa = e:localAngleToWorld(la)                 -- Local angle -> World angle
la = e:worldAngleToLocal(wa)                 -- World angle -> Local angle

-- Physics
vx, vy = e:getVelocity()                     -- Get linear velocity (world)
e:setVelocity(vx, vy)                        -- Set linear velocity (world)
omega = e:getAngularVelocity()                -- Get angular velocity (deg/s)
e:setAngularVelocity(omega)                  -- Set angular velocity (deg/s)
e:addForce(fx, fy)                           -- Apply force at center of mass (world)
e:addTorque(torque)                          -- Apply torque
e:addForceAtPosition(fx, fy, px, py)         -- Apply force at world position
vpx, vpy = e:getVelocityAtPoint(px, py)      -- Get velocity of a world point
mass = e:getMass()                           -- Get mass
cmx, cmy = e:getCenterOfMass()               -- Get center of mass (world)
gs = e:getGravityScale()                     -- Get gravity scale
e:setGravityScale(scale)                     -- Set gravity scale
e:freeze(1) / e:freeze(0)                    -- Freeze (static body) / unfreeze (dynamic)
e:freezeRotation(1) / e:freezeRotation(0)    -- Block / allow rotation
e:setCollisionEnabled(1) / e:setCollisionEnabled(0) -- Enable / disable collisions (layer)

-- Health & Temperature
temp = e:getTemperature()                    -- Get temperature
e:setTemperature(t)                          -- Set temperature
onFire = e:isOnFire()                        -- Returns 1/0
frozen = e:isFrozen()                        -- Returns 1/0
e:ignite()                                   -- Set on fire
e:extinguish()                               -- Extinguish fire
hp = e:getHealth()                           -- Get health
breakable = e:isBreakable()                  -- Returns 1/0

-- Visuals
r, g, b, a = e:getColor()                    -- Get color (0..1)
e:setColor(r, g, b, [a])                     -- Set color (0..1)
name = e:getName()                           -- Get internal ObjectName
localName = e:getLocalizedName()             -- Get localized name
visible = e:isVisible()                      -- Returns 1/0
e:setVisible(1) / e:setVisible(0)            -- Show / hide entity

-- Electricity
voltage = e:getVoltage()                     -- Get voltage

-- Interaction
drag = e:isDraggable()                       -- Returns 1/0
e:setDraggable(1) / e:setDraggable(0)        -- Enable / disable dragging
e:activate(1) / e:activate(0)                -- Activate / deactivate mechanic
actVal = e:getActivationInput()              -- Get activation value
e:delete()                                   -- Destroy object

-- Identity & Hierarchy
id = e:getId()                               -- Get instanceID
valid = e:isValid()                          -- Returns 1/0 (alive check)
rootId = e:getRoot()                         -- Get root entity ID
parentId = e:getParent()                     -- Get parent entity ID or nil
children = e:getChildren()                   -- Get children entity IDs (array)
-- Static methods
entityCount = entity.all()                   -- Total entities in scene
foundId = entity.find(name)                  -- Find first entity by name (nil if none)

-- Bounds
w, h = e:getSize()                           -- Size (baseSize * scale)
bw, bh = e:getBaseSize()                     -- Base size (scale = 1)
cx, cy, bx, by = e:getBounds()               -- World AABB (first renderer)
fx, fy, fw, fh = e:getFullBounds()           -- World AABB (all renderers)
ccx, ccy, cw, ch = e:getColliderBounds()     -- World AABB (collider)

-- Extended
e:lookAt(targetId, deg_per_sec)              -- Aim towards targetId
elev = e:getElevation(tx, ty)                -- Get angle to target point (deg)
canAct = e:canBeActivated()                  -- Returns 1/0
mat = e:getPhysicMaterial()                  -- Get physic material name (string)
```

### Collisions & Subscriptions
```lua
-- Callback functions fire BEFORE OnTick. unsubscribe using the returned subId.
subId = e:subscribeCollisionEnter(function(other, self, nx, ny) ... end)
subId = e:subscribeCollisionExit(function(other, self) ... end)
subId = e:subscribeCollisionStay(function(other, self) ... end)
subId = e:subscribeTriggerEnter(function(other, self) ... end)
subId = e:subscribeTriggerExit(function(other, self) ... end)
subId = e:subscribeTriggerStay(function(other, self) ... end)
e:unsubscribeCollisionEnter(subId)
e:unsubscribeCollisionExit(subId)
e:unsubscribeCollisionStay(subId)
e:unsubscribeTriggerEnter(subId)
e:unsubscribeTriggerExit(subId)
e:unsubscribeTriggerStay(subId)
e:unsubscribeAll()                           -- Remove all subscriptions on this entity

-- Wire subscriptions (for chips)
subId = e:subscribeWireConnected(function(selfId, inputKey, outputEntityId, outputKey) ... end)
subId = e:subscribeWireDisconnected(function(selfId, inputKey) ... end)
e:unsubscribeWireConnected(subId)
e:unsubscribeWireDisconnected(subId)
```

### Environment & Camera
```lua
t = env.time()                               -- Time in seconds
dt = env.deltaTime()                         -- Time delta
fdt = env.fixedDeltaTime()                   -- Fixed time delta
ts = env.timeScale()                         -- Current time scale
env.setTimeScale(scale)                      -- Set time scale (0..2)
fc = env.frameCount()                        -- Current frame number
st = env.sessionTime()                       -- Seconds since session start
ec = env.entityCount()                       -- Number of entities in scene
isW = env.isWorld()                          -- Returns 1/0
isWE = env.isWorldEditor()                   -- Returns 1/0
utc = env.systemTime()                       -- UTC seconds since epoch
days = env.systemDate()                      -- UTC days since epoch
dateStr = env.toDate(days)                   -- -> "dd.MM.yyyy"
timeStr = env.toTimeFormat(utc)              -- -> "HH:MM:SS"
days = env.parseDate("31.12.2024")           -- Parse date to days since epoch

cx, cy = camera.getPosition()                -- Get camera pos
camera.setPosition(x, y)                     -- Set camera pos (ignored if following)
zoom = camera.getZoom()                      -- Get zoom
camera.setZoom(zoom)                         -- Set zoom
camera.follow(entityId)                      -- Follow entity
camera.unfollow()                            -- Stop following
isFollowing = camera.isFollowing()           -- Returns 1/0
```

### Inputs (Mouse, Touch, Keyboard)
```lua
-- Single Pointer (Unified Touch / Mouse)
down = input.pointerDown()                   -- Returns 1/0
up = input.pointerUp()                       -- Returns 1/0 (released this frame)
wx, wy = input.pointerPos()                  -- World coordinates
sx, sy = input.pointerScreenPos()            -- Screen pixels
dx, dy = input.pointerDelta()                -- Pointer delta
hitId = input.pointerRaycast()               -- Entity ID under pointer (0 if none)
allHits = input.pointerRaycastAll()          -- Array of entity IDs under pointer
overUI = input.isOverUI()                    -- Returns 1/0
downF = input.pointerDownFiltered()          -- Pointer down (not over UI)
upF = input.pointerUpFiltered()              -- Pointer up (not over UI)

-- Multi-touch (1-based index)
count = input.touchCount()                   -- Active touch count
set = input.touchSet(idx)                    -- Returns 1/0
tdown = input.touchDown(idx)                 -- Touch down this frame (1/0)
tup = input.touchUp(idx)                     -- Touch up this frame (1/0)
age = input.touchAge(idx)                    -- Touch age in seconds
id = input.touchId(idx)                      -- Stable hardware touch ID
tx, ty = input.touchPos(idx)                 -- World coordinates
sx, sy = input.touchScreenPos(idx)           -- Screen pixels
stx, sty = input.touchStartScreenPos(idx)    -- Start screen pixels
dx, dy = input.touchDelta(idx)               -- Touch delta
sdx, sdy = input.touchSwipeDelta(idx)        -- Total delta since touch start
tap = input.touchTap(idx)                    -- Tap event frame (1/0)
tapN = input.touchTapCount(idx)              -- Tap count (double tap = 2)
swipe = input.touchSwipe(idx)                -- Swipe event frame (1/0)
overUI = input.touchIsOverUI(idx)            -- Pointer currently over UI (1/0)
startedUI = input.touchStartedOverUI(idx)    -- Touch started over UI (1/0)

-- Gestures (midpoint of touch 1 and 2, or specify indices)
dist = input.pinchDistance()                 -- Distance in screen pixels
angle = input.pinchAngle()                   -- Angle in degrees
cx, cy = input.pinchCenter()                 -- Midpoint screen coordinates

-- Keyboard
held = input.key("name")                     -- Returns 1/0
pressed = input.keyDown("name")              -- Returns 1/0 (pressed this frame)
-- Key names: "space", "left", "right", "up", "down", "return", "escape", "tab", "backspace", 
--            "left shift", "right shift", "left ctrl", "a"-"z", "0"-"9"
```

### Spawning API
```lua
-- Catalog (returns array of "name|alias" or "name|id")
items = spawn.getItems()                     -- Items catalog
itemStr = spawn.getItemsString(sep)          -- Joined items catalog string
itemCount = spawn.getItemCount()             -- Item count
saves = spawn.getSaves()                     -- Saved items catalog
savesStr = spawn.getSavesString(sep)         -- Joined saves catalog string
saveCount = spawn.getSaveCount()             -- Save count
rSaves = spawn.getResourceSaves()            -- Resource saves catalog
rSavesStr = spawn.getResourceSavesString(sep)   -- Joined resource saves catalog string
rSaveCount = spawn.getResourceSaveCount()    -- Resource save count
mods = spawn.getMods()                       -- Mods catalog
modsStr = spawn.getModsString(sep)           -- Joined mods catalog string
modCount = spawn.getModCount()               -- Mod count

-- Object Creation (deferred, triggers OnSpawned)
reqId = spawn.create(alias, x, y)            -- Spawn item (must use spawn-menu alias)
reqId = spawn.createWithAngle(alias, x, y, angle)
reqId = spawn.clone(entityId, x, y)          -- Clone entity (persistent)
reqId = spawn.cloneTemp(entityId, x, y)      -- Clone entity (temporary)
reqId = spawn.createSave(name, x, y)         -- Spawn saved item
reqId = spawn.createMod(name, x, y)          -- Spawn modded item
spawn.destroy(entityId)                      -- Destroy entity
locName = spawn.getNameByAlias(alias)        -- Get localized name of alias
exists = spawn.existsByAlias(alias)          -- Returns 1/0
```

### Chip, Mechanic & UIControl Introspection
```lua
-- Chip (VPChip / LuaChip)
has = chip.has(id)                           -- Returns 1/0
kind = chip.getType(id)                      -- Returns "VPChip", "LuaChip", or nil
inputs = chip.getInputs(id)                  -- Array of "key|type"
outputs = chip.getOutputs(id)                -- Array of "key|type"
val = chip.getValue(id, gateName)            -- Read gate value
ok = chip.setValue(id, gateName, val)        -- Write gate value (1/0, fails if wired)
wired = chip.hasWire(id, gateName)           -- Returns 1/0 (is input wired?)
act = chip.getActivation(id)                 -- Get activation value
chip.setActivation(id, active)                  -- Set activation (1 or 0)
name = chip.getName(id)                      -- Get chip visual name
tps = chip.getTPS(id)                        -- Get ticks per second

-- Mechanic (engines, buttons, doors, etc.)
has = mechanic.has(id)                       -- Returns 1/0
kind = mechanic.getType(id)                  -- Returns mechanic class name or nil
inputs = mechanic.getInputs(id)              -- Array of "key|type"
outputs = mechanic.getOutputs(id)            -- Array of "key|type"
val = mechanic.getValue(id, gateName)        -- Read gate value
ok = mechanic.setValue(id, gateName, val)    -- Write gate value (1/0)
wired = mechanic.hasWire(id, gateName)       -- Returns 1/0
act = mechanic.getActivation(id)             -- Get activation value
mechanic.setActivation(id, active)              -- Set activation (1 or 0)

-- UIControl
has = uicontrol.hasUIControl(id)             -- Returns 1/0
elements = uicontrol.getElements(id)         -- Array of "name|type|elementId"
elemId = uicontrol.findElement(id, name)      -- Find element ID by name
elems = uicontrol.getElementsByType(id, type) -- Array of element IDs by type
inputs = uicontrol.getInputGates(id, elemId)  -- Array of "name|type"
outputs = uicontrol.getOutputGates(id, elemId)-- Array of "name|type"
val = uicontrol.getValue(id, elemId, gateName) -- Get element gate value
uicontrol.setValue(id, elemId, gateName, val)  -- Set element gate value
wired = uicontrol.hasWire(id, elemId, gate)  -- Returns 1/0
minX, minY, maxX, maxY = uicontrol.getAnchors(id, elemId)
ax, ay = uicontrol.getAnchoredPosition(id, elemId)
uicontrol.setAnchoredPosition(id, elemId, ax, ay)
```

### World Control
```lua
active = world.isSessionActive()             -- Returns 1/0
world.startSession()                         -- Start simulation session
world.endSession()                           -- End simulation session
world.save()                                 -- Save current state
world.load()                                 -- Reload latest save (destroys VM)
world.reset()                                -- Reset to initial state (destroys VM)
world.clearCorpses()                         -- Remove corpses
world.clearDecals()                          -- Remove decals (blood, footprints)
world.clearGibs()                            -- Remove gibs
world.clearLiving()                          -- Remove living things
sig = world.radioSignal(channel)             -- Get radio channel signal value
```

### State Storage & Communication
```lua
-- Local variables in script body persist across ticks (not saved to disk)
local counter = 0

-- Variables (persistent chip-level variables)
variables.Set("key", val)                    -- Write variable value
val = variables.Get("key")                   -- Read variable value (nil if none)

-- Shared (cross-chip table storage)
shared.key = val                             -- Write shared key
val = shared.key                             -- Read shared key

-- Signal (inter-chip event bus)
subId = signal.on("event", function(data) ... end)
signal.emit("event", data)                   -- Synchronous event emit
signal.defer("event", data)                  -- Defer to next tick
signal.off("event", subId)                   -- Unsubscribe

-- Modules (share code across chips)
register_module("module_name", table)        -- Register a module (table of functions/values)
local mod = require("module_name")           -- Import a registered module
```

### Diagnostic & Environment API
```lua
print(...)                                   -- Log info severity (white)
warn(...)                                    -- Log warning severity (yellow)
error_log(...)                               -- Log error severity (red)

-- Allowed Lua standard libraries: math, string, table, coroutine, and standard globals.
-- Blocked modules (do NOT use): os, io, debug, screen, time (use env), go, physics, sprite, event.
```

## 常见陷阱

| 现象 | 原因 |
|------|------|
| spawn 有 requestId 无实体 | 用了 objectId/类名/`crate_wood`，不是菜单 alias |
| createSave 出的 Save 缺件/散架 | 只取 `entities[1]`；Save 是多零件 + 约束组合，须遍历 `entities` |
| entity id = 0 | 输入未连线 |
| LED 黑屏 | array_vec 用了 `{r,g,b,a}` 位置数组，必须 `{x=,y=,z=,w=}` |
| 雷达永远空 | Select All 空 或 范围仍是 1×1 |
| 文字屏连不上 | 应用 `connect(...,"text")`（SDK→Key string），不要手写错 Key |
| UI 多滑块串线 | 同名 `"Value"` 必须 ElementHandle / `output_group` |
| touch 全无 | 索引写成了 0，应为 1 |
| env.time 比较/计算失效 | env.time 是函数，真机及沙盒运行必须写成 `env.time()`，不可当作数值使用 |
| `getChildren()[1]:getName()` 崩 | 返回的是 id，先 `Entity(...)` |
| 输出闪 0 | 某分支没写 outputs |
| 物体不动 | freezed / 无重力 / 只 run_tick 没步进物理 |

---

## AI 自检清单（导出前）

- [ ] `.melsave` 已 `save`
- [ ] Lua spawn 全是菜单 alias
- [ ] 雷达：Select All + 范围 + array_entity 接线 + `Entity(id)`
- [ ] 门名：`list_item_gates` 查过或用 SDK 自动解析
- [ ] UI：ElementHandle 连线
- [ ] `debug_run` / `run_chip` 无 error（能跑沙盒时）
- [ ] outputs 每路径都有赋值
- [ ] 未使用 REMOVED 模块 / 错误 Entity 静态 API
