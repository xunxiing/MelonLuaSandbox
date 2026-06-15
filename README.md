# Melon Lua Sandbox

甜瓜游乐场 Lua 芯片执行器模拟器。

基于 APK 逆向分析提取的真实 `LuaPreamble.lua` + 完整 `Example_ApiReference_en.lua`，使用 Python + lupa（LuaJIT）重现已有的 Lua 芯片执行环境。所有 API 名称、参数、返回值均与现实一致。

## 特性

- ✅ 真实前置脚本 `LuaPreamble.lua`（Entity OOP、`shared`/`signal`/`require` 系统）
- ✅ 甜瓜允许的标准库（`stdlib_melon` + `verify_melon_stdlib.py`）
- ✅ 11 个 ApiModule：`entity`、`spawn`、`env`、`camera`、`input`、`inputFilter`、`chip`、`mechanic`、`world`、`variables`、`uicontrol`、`print`
- ✅ SDK 目录：`object_physics_by_id.json`（495 条尺寸；`spawn.create("202")` / `spawn_entity(object_id=…)`）
- ✅ 类型化输入输出：`inputs.num.x`、`outputs.string.status`、`outputs.vec.dir`、`outputs.color.tint` 等
- ✅ 完整生命周期：`OnInit`、`OnTick`、`OnActivated`、`OnDeactivated`、`OnSpawned`、`OnDestroy`
- ✅ Box2D 真实 2D 物理：重力、碰撞、`addForce`、`setVelocity`、`freeze`、`gravityScale`
- ✅ 无真实时间等待，适合快速批量 tick 模拟

## 安装

```bash
pip install -e .
```

依赖：`lupa`（LuaJIT 绑定）、`Box2D`（pybox2d）。

## CLI 使用

```bash
# 基础运行（5 秒 × 20 TPS = 100 tick）
melon-lua samples/hello_chip.lua

# 精确跑 N tick（推荐）
melon-lua samples/bignum.lua --ticks 1000

# 静态输入
melon-lua samples/adder.lua --inputs inputs.json

# 时间线输入（按 tick 切换）
melon-lua samples/adder.lua --inputs-timeline timeline.json

# 快速 TPS
melon-lua samples/bignum.lua --ticks 100 --tps 60

# 种子实体（物理测试）
melon-lua samples/physics_demo.lua --ticks 80 \
  --seed-entity "crate,0,10" \
  --seed-static "floor,0,0"

# 列出 API
melon-lua --api-list
```

### 输入文件格式

**静态** `inputs.json`：
```json
{
  "num": {"a": 5, "b": 3},
  "string": {"mode": "attack"}
}
```

**时间线** `timeline.json`（tick 从 1 开始，设置后持续到下个变化点）：
```json
{
  "1": {"num": {"a": 1}},
  "30": {"num": {"a": 10}},
  "60": {"num": {"a": 0}}
}
```

## 文档

- `docs/API.md` — Python SDK 完整参考（WorldContext、MelonScriptRunner、catalog、preview 等）
- `docs/LUA_GUIDE.md` — 甜瓜 Lua 芯片开发完整指南（生命周期、API 速查 + 标准库）
- `docs/stdlib.md` — 甜瓜芯片允许的标准库完整清单（含禁用项与验证方法）
- `docs/guide.md` — 原始简版教程（已整合进 LUA_GUIDE.md）

建议先读 `docs/LUA_GUIDE.md` 写芯片，再用 `docs/API.md` 做 Python 侧集成/模拟。

```python
from melon_lua import (
    MelonScriptRunner, WorldContext,
    get_profile_by_object_id, object_id_for_name, list_spawnables,
)

# 495 物体：objectId + 碰撞尺寸（贴图可选）
print(object_id_for_name("ResizablePlastic"))  # 202
prof = get_profile_by_object_id(202)

world = WorldContext()
# 按 objectId 或 gameObjectName 生成（自动套 APK 尺寸）
world.spawn_entity("202", 0, 5, dynamic=True)       # Plastic plate
world.spawn_entity("Box", 2, 5, dynamic=True)
world.spawn_entity("ground", 0, 0, dynamic=False, scale_x=10.0)

runner = MelonScriptRunner(tps=20, world=world)

source = '''
function OnInit()
    print("chip started")
end

function OnTick()
    local e = Entity(1)
    local x, y = e:getPosition()
    outputs.num.x = x
    outputs.num.y = y
end
'''

runner.compile(source)
runner.run_loop(ticks=100)
print(runner.logs)
```

手动单步：
```python
runner.call_on_init()
result = runner.run_tick(inputs={"num": {"a": 5}})
print(result["outputs"])
```

## 真实 API 示例

```lua
function OnInit()
    print("init!")
end

function OnTick()
    -- 读取类型化输入
    local speed = inputs.num.speed or 0

    -- Entity OOP
    local e = Entity(1)
    e:setVelocity(speed, 0)

    -- 物理
    local x, y = e:getPosition()
    outputs.num.x = x
    outputs.num.y = y

    -- 生成请求（异步回调）
    spawn.create("human", x + 2, y)
end

function OnSpawned(requestId, entities)
    print("spawned request", requestId, "got", #entities, "entities")
end
```

## 生命周期

```lua
function OnInit() end          -- 芯片初始化，调用一次
function OnActivated() end     -- 激活时调用一次
function OnTick() end          -- 每 tick 调用（按 TPS）
function OnDeactivated() end   -- 停用时调用一次
function OnDestroy() end       -- 销毁时调用一次
function OnSpawned(requestId, entities) end  -- spawn.create 完成后回调
```

## Box2D 物理

默认重力 `(0, -9.8)`，y 轴向上为正。创建 entity 时通过 `dynamic=True/False` 决定是否为刚体。

物理方法：
- `entity:addForce(fx, fy)` / `addForceAtPosition(fx, fy, px, py)` / `addTorque(t)`
- `entity:setVelocity(vx, vy)` / `setAngularVelocity(w)`
- `entity:setPosition(x, y)` / `setAngle(deg)`
- `entity:freeze(bool)` / `freezeRotation(bool)` / `setGravityScale(s)`

注意：物理 Tick 与世界 Tick 同步，不按真实时间阻塞，因此可以快速模拟长时间演化。

## 项目结构

```
melon_lua/
├── preamble.lua              -- 真实 LuaPreamble.lua（APK 原版）
├── runner.py                 -- 芯片执行引擎
├── world.py                  -- Box2D 物理世界 + 全局状态
├── entity.py                 -- Entity 数据模型
└── backend/                  -- 11 个真实 ApiModule 的 Python 后端
    ├── entity_backend.py
    ├── env_backend.py
    ├── spawn_backend.py
    ├── chip_backend.py
    ├── mechanic_backend.py
    ├── world_backend.py
    ├── camera_backend.py
    ├── input_backend.py
    ├── inputFilter_backend.py
    ├── variables_backend.py
    └── uicontrol_backend.py
```

## 限制

- 物理使用 Box2D，但物体形状目前均为矩形 box（与 sprite 无关），碰撞材质使用默认值。
- 渲染、音效、网络、真实输入设备无法模拟。
- 某些 ApiModule（如 `mechanic`、`uicontrol`、`inputFilter`）在沙盒中返回 mock 值，适合验证逻辑而非真实 UI/输入行为。
