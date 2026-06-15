# MelonLua 开发指南

## 生命周期函数

```lua
function OnInit()        -- 初始化时调用一次
function OnSpawned()     -- 异步操作完成时调用
function OnActivated()   -- 芯片激活时调用
function OnDeactivated() -- 芯片停用时调用
function OnDestroy()     -- 销毁时调用
function OnTick()        -- 每帧必须执行的主函数
```

## 特殊 API 模块

### 1. 输入输出系统

```lua
-- 类型化的输入读取
local speed = inputs.num.speed or 1
local target = inputs.entity.target
local a = inputs.string.a
local data = inputs.array_num.data

-- 类型化的输出写入
outputs.num.tick = tick
outputs.string.a = "hello"
outputs.vec.pointer = {x, y, z, w}
```

### 2. 变量系统

```lua
variables.Set("total_ticks", value)
variables.Get("total_ticks")
variables.SetGlobal("score", 100)
variables.GetGlobal("score")
```

### 3. 共享数据系统

```lua
shared.heartbeat = tick
shared.Save()
shared.Load()
```

### 4. 信号系统

```lua
signal.on("damage", function(d)
    print(d.amount)
end)
signal.emit("damage", {amount = 10})
signal.defer("next_tick_event", data)
```

### 5. 实体操作

```lua
local e = Entity(targetId)
if e:isValid() == 1 then
    local x, y = e:getPosition()
    local angle = e:getAngle()
    local sx, sy = e:getScale()
    local vx, vy = e:getVelocity()
    local mass = e:getMass()
    e:setColor(r, g, b, a)
    e:addForce(0, 50)
    e:ignite()
    e:extinguish()
    e:subscribeCollisionEnter(function(other, self, nx, ny)
        print("Hit: " .. other:getName())
    end)
end
```

### 6. 输入处理

```lua
if input.pointerDown() == 1 then
    local wx, wy = input.pointerPos()
    local hitId = input.pointerRaycast()
end
if input.key("space") == 1 then
    -- space pressed
end
```

### 7. 环境信息

```lua
env.deltaTime()
env.time()
env.entityCount()
env.toTimeFormat(env.sessionTime())
env.toDate(env.systemDate())
```

### 8. 相机控制

```lua
camera.follow(targetId)
camera.unfollow()
camera.setPosition(0, 5)
camera.setZoom(8)
```

### 9. 生成系统

```lua
-- 异步生成 (deferred), 结果通过 OnSpawned 回调
local req = spawn.create(objectId, x, y)             -- 异步生成
spawn.createWithAngle(objectId, x, y, angle)         -- 带角度异步生成
spawn.clone(entityId, x, y)                          -- 异步克隆
spawn.cloneTemp(entityId, x, y)                      -- 异步临时克隆
spawn.destroy(entityId)                              -- 销毁实体

-- 异步生成结果回调: 收到 requestId 和生成的实体数组
function OnSpawned(requestId, entities)
    -- entities 永远是一个数组 (即使生成失败也是 nil)
    if entities then
        for i = 1, #entities do
            print("Spawned: " .. entities[i]:getName() .. " id=" .. entities[i]:getId())
        end
    end
end

-- 查询当前可用资源 (用于 OnInit 中调试)
local itemCount = spawn.getItemCount()   -- 物品总数 (例如 455)
local saveCount = spawn.getSaveCount()   -- 玩家存档数量
local modCount  = spawn.getModCount()    -- 已加载的 Mod 数量

-- 通常在 OnInit 中打印这些信息
function OnInit()
    print("Items: " .. spawn.getItemCount()
        .. " Saves: " .. spawn.getSaveCount()
        .. " Mods: " .. spawn.getModCount())
end
```

### 10. 世界控制

```lua
world.save()
world.load()
world.reset()
world.clearCorpses()
world.clearDecals()
```

## 模块化系统

```lua
-- 注册可重用模块
register_module("utils", {
    clamp = function(v, lo, hi)
        return math.max(lo, math.min(hi, v))
    end
})

-- 使用模块
local utils = require("utils")
utils.clamp(150, 0, 100)
```

## AI 代码生成规则

1. **代码中所有标识符使用英文**（变量名、字段名、函数名）
2. **字符串内容、注释可使用中文**
3. **不解释基础 Lua 语法**（如 if/for/function 等）
4. **重点说明 MelonLua 自定义 API 的使用方法**
5. **直接给出可运行的完整代码**
