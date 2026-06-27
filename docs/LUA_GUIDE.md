# Melon Lua 芯片开发完整指南（含标准库）

本文档整合原 `guide.md` 并补充完整标准库说明、生命周期、API 速查等。

## 生命周期函数

```lua
function OnInit()        -- 初始化时调用一次（可在这里 spawn）
function OnSpawned(requestId, entities)  -- 异步 spawn 完成时调用
function OnActivated()   -- 芯片激活时调用
function OnDeactivated() -- 芯片停用时调用
function OnDestroy()     -- 销毁时调用
function OnTick()        -- 每帧必须执行的主函数（核心逻辑）
```

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
variables.Set("total_ticks", value)
local v = variables.Get("total_ticks")
variables.SetGlobal("score", 100)
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

### 5. 实体操作（Entity OOP）

```lua
local e = Entity(targetId)
if e:isValid() == 1 then
    local x, y = e:getPosition()
    e:setColor(1, 0, 0, 1)
    e:addForce(0, 50)
    e:subscribeCollisionEnter(function(other, self, nx, ny)
        print("Hit: " .. other:getName())
    end)
end
```

完整方法见 `Example_ApiReference_en.lua` 或沙盒 `entity_backend.py`。

### 6. 输入处理

```lua
if input.pointerDown() == 1 then
    local wx, wy = input.pointerPos()
end
if input.key("space") == 1 then ... end
```

### 7. 环境信息

```lua
env.deltaTime()
env.time()
env.entityCount()
env.toTimeFormat(env.sessionTime())
```

### 8. 相机

```lua
camera.follow(targetId)
camera.setPosition(0, 5)
camera.setZoom(8)
```

### 9. 生成系统（spawn）—— 重要

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
print(spawn.getNameByAlias("human"))
```

**注意**：沙盒中 `spawn.create` 会**立即创建实体**（便于物理模拟），仍正确返回 requestId 并在 tick 末触发 OnSpawned。

### 10. 世界控制

```lua
world.save()
world.load()
world.reset()
world.clearCorpses()
world.clearDecals()
```

## 模块化（register_module / require）

```lua
register_module("utils", {
    clamp = function(v, lo, hi) return math.max(lo, math.min(hi, v)) end
})

local utils = require("utils")
utils.clamp(150, 0, 100)
```

## AI 代码生成规则

1. 代码中所有标识符使用英文
2. 字符串内容、注释不使用中文
3. 不解释基础 Lua 语法
4. 重点说明 MelonLua 自定义 API
5. 直接给出可运行的完整代码

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

---

文档位置：
- `docs/API.md` — Python SDK 完整参考
- `docs/stdlib.md` — 标准库详细清单
- `docs/guide.md` — 原始简版教程（本文件已整合增强版）
