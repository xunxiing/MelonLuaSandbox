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
