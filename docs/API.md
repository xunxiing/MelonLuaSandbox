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

## melsave 全周期管理（MelsaveSession）

`MelsaveSession` 把 .melsave 文件的读、改、写收拢到一个对象里。原始存档文档
在内部持有，`save_as` 时自动 diff 当前 world 状态与原始存档，只 patch 改动
字段，保留所有未触碰字段。

### 最小示例

```python
from melon_lua import MelsaveSession

with MelsaveSession("input.melsave") as session:
    session.load()
    # 跑一个 Lua 芯片 100 tick
    session.run_chip(chip_source, ticks=100)
    # 拉一条绳子
    session.create_rope(from_id=1, to_id=2, kind="Simple", distance=1.5)
    # 看当前状态
    snap = session.snapshot()
    print(snap["entity_count"], snap["ropes"])
    # 写回新存档
    session.save_as("output.melsave")
```

### 生命周期

```
MelsaveSession(path)        # 创建（不读文件）
    .load()                 # 读取 + spawn 到 world + 构建 runner
    [run_chip / tick]       # 编译并运行 Lua 芯片
    [create_rope / remove]  # 管理绳子/关节
    [spawn / remove]        # 增删实体
    [snapshot / diff]       # 观察状态
    .save_as(out_path)      # diff + 写回 .melsave
    .close()                # 释放 Box2D world + Lua VM
```

支持 `with` 上下文管理器（自动 load + close）。

### API 一览

**芯片执行**

- `run_chip(source, *, ticks=1, inputs=None) -> {"error", "outputs"}`
  编译 + OnInit + 跑 N tick。ticks=0 只编译+OnInit。
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
   - 约束：合并到对应对象的 constraints 列表（按 mainGuid 去重保留原有约束）
4. **instanceId 填什么都行**——真机加载时重新分配
5. **localId** 在存档里常为 0，真机加载时重建层级；沙盒用 index+1 作为匹配键

### 限制

- 新增物体只能用模板池里已有的 objectId（72 个常见物体）；不支持 modded objectId
- 物理精度不等价于真机（Box2D vs Unity 2D Physics）
- 渲染为简易 2D 预览，非真实 sprite
- mechanicData 的三重嵌套 JSON 改动需逐层 stringify（不动 mechanic 则原样保留）
