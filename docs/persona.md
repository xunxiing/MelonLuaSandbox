# Melon Lua 芯片 Agent Persona

**喂给 AI 的文档只有两份：**

| 文档 | 职责 |
|------|------|
| **本文 `persona.md`** | 硬规则、交付流程、真机陷阱、最短示例 |
| **`docs/API.md`** | Python SDK **完整签名**（Session / connect / UI / debug / catalog） |

禁止再喂 `guide.md` / 存档格式 / VP 文档。Lua 方法签名以本文「速记」为准；Python 以 `API.md` 为准。
官方全文对照：`docs/api reference.txt`（有过时 alias，spawn 以本文为准）。

---

## 最高优先级规则（违反即失败）

1. **Entity 方法已固定**：直接写 `e:getAngle()` 等，禁止搜索/探测 melon_lua 源码。
2. **禁止** `astrbot_grep` / `file_read` / `execute_shell` 去翻 melon_lua——沙盒里没有包源码。
3. **区域雷达 Radar（892993856）必须 Select All**：`Radar_selected_entities.stringValue` 不能是 `"[]"`。`add_item(892993856)` 已默认写全量名单；禁止清空。空名单 = 真机 `entity array` 永远空。激光雷达 Ranger(13) 用 `RangerMode=All`，不是同一字段。
4. **Lua `spawn.create` 真机只认菜单 Alias**：`spawn.create("plastic_plate", x, y)` 合法；`spawn.create(202)` / `"ResizablePlastic"` / `"crate_wood"` 在真机静默失败（有 requestId、`OnSpawned` 空表）。用 `spawn.getItems()` 的 `"Name|alias"` **右侧**，或包内 `melon_lua/data/spawn_menu_aliases.txt`。
5. **两套键不要混**：
   - Lua 真机 spawn → 菜单 alias（`plastic_plate`、`crate`…）
   - Python `add_item` / `spawn_entity` → objectId / 物理 catalog 名（202 仍可用）
6. **必须交付可导入的 `.melsave`**（用户要求时），不要只交 Lua 片段。
7. **完整 Python 签名查 `API.md`**，不要猜方法名。

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
# 门名可用 Key 或 DataName，SDK 自动解析为真机 Key（如文字屏 text→string）
s.save("out.melsave")

# 2) 运行时验证（需要 with / load）
with MelsaveSession("out.melsave") as s:
    r = s.debug_run(src, ticks=40)                  # 每 tick 轨迹
    # 或 r = s.run_chip(src, ticks=40)              # 只要最终 outputs
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
# 多输出：s.connect(ui_idx, "Joystick Angle", chip, "angle", output_group=joy.group_id)
```

**查门名（禁止 dump 整份模板 JSON）：**

```python
list_item_gates(261)           # 或 list_item_gates("文字屏")
# → inputs/outputs: key + data_name
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
- `OnSpawned(requestId, entities)`：`entities` 为 Entity 数组，失败可为 **nil**；坏 alias 常见 **空表**。
- 碰撞/触发回调在 **OnTick 之前**。
- `world.load` / `world.reset` 会 **销毁 Lua VM**。

### inputs / outputs

- 桶始终存在：`num` / `int` / `string` / `vec` / `color` / `entity` / `array_*`。
- **每个 tick 都要写 outputs**，否则回落 0 / `""`。
- `inputs.entity.x == 0` → 未连线。
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

### 禁止的幻觉模块（REMOVED）

不要写：`screen.*` / `time.*` / `go.*` / `physics.*` / `sprite.*` / `event.*`。时间用 `env.*`。

### 标准库

可用：math / string / table / coroutine / bit32 / 有限 os（time/clock）+ pairs/ipairs/pcall/type/tostring/tonumber/select/unpack 等。  
禁用：io / package / debug / load* / collectgarbage。详见 `docs/others/stdlib.md`（或包内 stdlib 文档）。

---

## Lua 模块速记（完整表见官方 api reference；此处纠正常错点）

### Entity（实例方法均 `e:method`）

- Transform：`get/setPosition` `get/setAngle` `get/setScale` `getNormal` `localToWorld` `worldToLocal` `localAngleToWorld` `worldAngleToLocal`
- Physics：`get/setVelocity` `get/setAngularVelocity` `addForce` `addTorque` `addForceAtPosition` `getVelocityAtPoint` `getMass` `getCenterOfMass` `get/setGravityScale` `freeze` `freezeRotation` `setCollisionEnabled`
- State：`isValid` `getId` `getName` `getLocalizedName` `get/setColor` `isVisible` `setVisible` `delete`
- Fire/HP：`get/setTemperature` `isOnFire` `isFrozen` `ignite` `extinguish` `getHealth` `isBreakable` `getVoltage`
- Interaction：`isDraggable` `setDraggable` `canBeActivated` **`activate(1|0)`**（必须传 flag）`getActivationInput`
- Hierarchy：返回 **entityId**，不是 Entity：`getRoot()` `getParent()` `getChildren()` → 用 `Entity(id)` 包装
- Bounds：`getSize` `getBaseSize` `getBounds` `getFullBounds` `getColliderBounds`（各返回多值）
- Misc：`lookAt(targetId, degPerSec)` `getElevation` `getPhysicMaterial`
- 订阅：`subscribeCollisionEnter(cb) → subId`，**`unsubscribeCollisionEnter(subId)`**（不是 cb）；Wire 同理；`unsubscribeAll()`
- **静态查询（小写 entity 表）**：
  - `entity.all()` → **数量 number**
  - `entity.find("Name")` → **id 或 nil** → 再 `Entity(id)`

### input

- Pointer：`pointerDown/Up/Pos/ScreenPos/Delta` `pointerRaycast` `pointerRaycastAll` `isOverUI` `pointerDownFiltered` `pointerUpFiltered`
- Touch：**索引从 1 开始** `touchDown(1)`（不是 0）
- Pinch：`pinchDistance` `pinchAngle` `pinchCenter`
- Key：`key` `keyDown`（`space` `w` `left` …）

### env / camera / world

- env：`time` `deltaTime` `fixedDeltaTime` `timeScale` `setTimeScale(0..2)` `frameCount` `sessionTime` `entityCount` `isWorld` `isWorldEditor`
  - `systemTime()` → UTC 秒；`systemDate()` → **UTC 天数**；`toDate(days)` → `"dd.MM.yyyy"`；`parseDate("31.12.2024")` → days
- camera：`get/setPosition` `get/setZoom` `follow` `unfollow` `isFollowing`（follow 时 setPosition 无效）
- world：`save` `load` `reset`（后两者毁 VM）`clearCorpses/Decals/Gibs/Living` `radioSignal(channel数字)` `isSessionActive` `startSession` `endSession`

### spawn / chip / mechanic / uicontrol

- spawn：见上 + `clone` `cloneTemp` `createSave` `createMod` `destroy`
- chip.* / mechanic.*：`has` `getType` `getInputs/Outputs` `get/setValue`（wired 时 set 返回 0）`hasWire` `get/setActivation`；chip 另有 `getName` `getTPS`
  - chip = VP/Lua 芯片；mechanic = 普通机构；UI 面板用 **uicontrol**
- uicontrol.*（运行时面板，非 Python 构建）：`hasUIControl` `getElements` `findElement` `getElementsByType` `getInputGates` `getOutputGates` `get/setValue` `hasWire` `getAnchors` `get/setAnchoredPosition`

### 其它

```lua
variables.Set("k", v)   variables.Get("k")     -- 类型锁定
shared.x = 1            shared.Save() shared.Load()
local sid = signal.on("ev", fn)
signal.emit("ev", data) signal.defer("ev", data)
signal.off("ev", sid)
register_module("utils", { clamp = function(...) end })
local u = require("utils")
print(...)  warn(...)  error_log(...)
```

---

## 最短可运行芯片示例

```lua
local last = 0

function OnInit()
    print("init")
end

function OnSpawned(req, ents)
    if not ents or #ents == 0 then
        outputs.string.status = "spawn empty (bad alias?)"
        return
    end
    outputs.num.spawned_id = ents[1]:getId()
end

function OnTick()
    local id = inputs.entity.target
    if id == 0 then
        outputs.string.status = "no wire"
        outputs.num.x = 0
        return
    end
    local e = Entity(id)
    if e._nil then
        outputs.string.status = "nil entity"
        return
    end
    local x, y = e:getPosition()
    outputs.num.x = x
    outputs.num.y = y
    outputs.string.status = "ok"
    -- 需要生成时用菜单 alias，并在 OnSpawned 配置
    -- if env.time() - last > 1 then last = env.time(); spawn.create("plastic_plate", x, y+2) end
end
```

---

## 常见陷阱

| 现象 | 原因 |
|------|------|
| spawn 有 requestId 无实体 | 用了 objectId/类名/`crate_wood`，不是菜单 alias |
| entity id = 0 | 输入未连线 |
| LED 黑屏 | array_vec 用了 `{r,g,b,a}` 位置数组，必须 `{x=,y=,z=,w=}` |
| 雷达永远空 | Select All 空 或 范围仍是 1×1 |
| 文字屏连不上 | 应用 `connect(...,"text")`（SDK→Key string），不要手写错 Key |
| UI 多滑块串线 | 同名 `"Value"` 必须 ElementHandle / `output_group` |
| touch 全无 | 索引写成了 0，应为 1 |
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
