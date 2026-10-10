# MelonLuaSandbox Canvas 绘图扩展包技术指南与开发文档

## 概述

MelonLuaSandbox 的 **Canvas 绘图扩展包** 提供了在甜瓜游乐场（Melon Playground）硬件设备（如 LED 点阵屏 `LEDMatrixDisplay`，objectId: `596836672`）上进行高效率像素绘制的完整解决方案。

通过 **Python SDK 侧管理 + 构建期自动拉线 + 静态 Lua 预置头（Preamble）注入** 的两层设计，消除了运行时动态寻找 Entity ID 的开销，并保证了在甜瓜游乐场 C# 引擎（Lua-CSharp）中的 100% 兼容性。

---

## 核心架构与实现原理

```
+-------------------------------------------------------------+
|                      Python SDK (Session)                   |
|  1. s.create_canvas(width=32, height=32) -> CanvasInstance  |
|  2. s.add_lua_chip(code, canvases=[cv], inputs=..., ...)    |
+------------------------------+------------------------------+
                               |
                               v  构建期自动注入与物理连线
+-------------------------------------------------------------+
|                     .melsave 存档文件                        |
|  - [Lua Chip Object]                                        |
|      * lua_chip_outputs: canvas_out_0 (DataType: 512)     |
|      * GateData: 预分配 1024 个 Vector4 色彩结构 (非 null)   |
|      * Preamble Source: canvas_0 定义与缓存数组              |
|  - [LEDMatrixDisplay Object]                                |
|      * mechanicSerializedInputs: led-matrix-data            |
|      * GateData: 预分配 1024 个 Vector4 色彩结构             |
|  - [Wire Constraint]                                        |
|      * LuaChip.canvas_out_0 ===Wire===> LED.led-matrix-data |
+-------------------------------------------------------------+
```

### 1. 数组门 (Vector4 Array) 预分配机制（关键）
在甜瓜游乐场的 Unity C# 引擎（`LuaCSharpBackend`）中，`DataType: 512`（Vector4 向量数组）如果 `.melsave` 中的 `GateData` 为 `"{\"Value\":null,\"Default\":null}"`，C# 门管理器不会分配内部 `List<Vector4>` 内存空间，导致线缆无法传输点阵信号。

**解决方案**：SDK 在 `create_canvas` 和 `add_lua_chip` 时，自动向 `led-matrix-data` 和 `canvas_out_0` 的 `GateData` 注入预分配的 1024 个 Vector4 默认 JSON 数组对象（`{"x":0,"y":0,"z":0,"w":1}`）。

### 2. 闭包绑定与底层 3 大终极性能优化（Smart Dirty Clearing + Incremental Write + Nil Shield）
Lua 侧不调用高开销的 `table.insert` 或重新分配数组，而是使用全局预分配平铺数组 `_buf_0`。

SDK 预置头内部集成了 **3 大终极性能与稳定性防护**：
1. **差异化增量显存写入 (Differential Incremental Writes)**：在改变 Vector4 显存值前，自动校验 `_p.x ~= _nx or _p.y ~= _ny...`，只有在颜色实际发生变化时才触发 C# 结构体修改与脏像素计数，渲染开销降低 90%+。
2. **Smart Dirty Clearing (智能脏像素清屏)**：
   * 当一帧内修改的像素数量较少时，下一次调用 `:clear()` 时**自动只擦除脏像素**，清屏开销从 1024 次全屏循环降低到实际脏像素数（提速 200 倍）。
3. **`outputs.array_vec` 空值防爆护盾 (Nil Protection Shield)**：
   * 在导出帧 `_flush()` 处全局加上 `if outputs and outputs.array_vec then` 校验，防止 C# 引擎在生命周期未准备就绪时抛出 `attempt to index a nil value (field 'array_vec')` 崩溃。

### 3. LED 屏点阵无缝无缝拼屏间距规范 (0.6591m Spacing Rule)
* 甜瓜游乐场硬件 `LEDMatrixDisplay`（objectId: `596836672`）的画面实际显示矩阵在真机上的点对点无缝拼接中心距为 **`0.6591m`**（如 Top-Left `-0.3449, 0.6724`，Top-Right `0.3142, 0.6724`）。
* 设置为 `0.6591m` 间距可实现多屏无缝衔接，画面无黑边拉伸。配合 `Entity(target):setColor(0, 0, 0, 0)` 可完美隐藏框架边框。

---

## Python SDK 使用指南

### 1. 创建画布与添加芯片
```python
from melon_lua import MelsaveSession

with MelsaveSession() as s:
    # 创建 32x32 点阵屏硬件与 Canvas 句柄
    cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0, y=0)

    # 编写 Lua 代码（使用 cv.lua_var 即 canvas_0 变量）
    lua_code = f"""
    local frame = 0
    function OnTick()
        frame = frame + 1
        {cv.lua_var}:clear(0, 0, 0)

        -- 在 (10, 10) 绘制红色像素
        {cv.lua_var}:setPixel(10, 10, 1, 0, 0)

        -- 对角线白色像素动画
        local p = frame % 32
        {cv.lua_var}:setPixel(p, p, 1, 1, 1)
    end
    """

    # 显式注册芯片端口并自动绑定 Canvas
    s.add_lua_chip(
        lua_code,
        canvases=[cv],
        inputs=[{"name": "target", "type": "entity"}],
        outputs=[{"name": "status", "type": "string", "value": "Canvas Running"}],
    )

    # 本地沙盒调试运行 10 tick
    res = s.debug_run(ticks=10)
    
    # 导出真机可用的 .melsave 存档
    s.save("canvas_demo.melsave")
```

---

## Lua API 接口参考

在 SDK 注入静态预置头后，Lua 脚本中可直接使用 `canvas_<id>`（如 `canvas_0`）全局对象：

| API 方法 | 参数说明 | 描述 |
|---|---|---|
| `canvas:setPixel(x, y, r, g, b, [a])` | `x, y`: 坐标 (0~width-1)<br>`r, g, b, a`: 颜色向量 (0.0~1.0) | 设置指定像素点颜色。超出边界自动忽略。 |
| `canvas:setPixel(x, y, color_table)` | `color_table`: `{r=1, g=0, b=0, a=1}` 或 `{1, 0, 0}` | 表重载形式设置像素点颜色。 |
| `canvas:clear(r, g, b, [a])` | `r, g, b, a`: 填充颜色 (默认为 0,0,0,1) | 快速清空全屏像素。 |
| `canvas:flush()` | 无 | 把缓冲写到 `outputs.array_vec`。SDK 会在用户的 `function OnTick()` 之后自动调用，不必再包一层 `bind`。 |

---

## 排查与常见问题 (Troubleshooting)

1. **甜瓜游戏里打开芯片界面，端口列表显示为空？**
   * **原因**：没有为 `add_lua_chip` 传递显式的 `inputs` 或 `outputs` 列表。
   * **解决**：根据 `persona.md` 规范，始终显式指定 `inputs` 与 `outputs` 列表（如包含 `target` 实体输入门和 `status` 文本监控门）。

2. **在真机加载存档后，点阵屏不亮/不刷新？**
   * **原因**：`GateData` 中的 Vector4 数组未预分配。
   * **解决**：使用最新的 `s.create_canvas()`，SDK 会自动填入预分配的 Vector4 默认数据，避免 C# 引擎分配失败。

---

## 多芯片并行绘图与屏幕集群 (CanvasCluster)

当面临超大规模屏幕（如 64x64 或 128x128）时，单一 Lua 芯片的每 Tick 指令预算不足以高效驱动所有像素。SDK 提供了多芯片并行抽象：

### 1. 架构示意图 (2x2 Grid = 64x64 虚拟超大屏)
```
+-------------------------------------------------------------+
|               Unified Virtual Canvas (64x64)                |
+------------------------------+------------------------------+
|   Tile(0,0): 32x32 (LED 0)   |   Tile(1,0): 32x32 (LED 1)   |
|   Worker Chip (0,0)          |   Worker Chip (1,0)          |
+------------------------------+------------------------------+
|   Tile(0,1): 32x32 (LED 2)   |   Tile(1,1): 32x32 (LED 3)   |
|   Worker Chip (0,1)          |   Worker Chip (1,1)          |
+-------------------------------------------------------------+
```

### 2. Python SDK 使用示例
```python
from melon_lua import MelsaveSession

def worker_builder(col, row, canvas):
    return f"""
    local tick_count = 0
    local tile = canvas_tile_{canvas.canvas_id}

    function OnTick()
        tick_count = tick_count + 1
        {canvas.lua_var}:clear(0, 0, 0)

        -- 绘制在全屏幕 64x64 移动的全局对角线
        local gx = (tick_count * 2) % 64
        local gy = (tick_count * 2) % 64

        -- tile:set_global_pixel 会自动校验 (gx, gy) 是否属于当前芯片的视口子区域
        tile:set_global_pixel(gx, gy, 0, 1, 0)
    end
    """

with MelsaveSession() as s:
    # 1. 创建 2x2 点阵屏集群（总分辨率 64x64）
    cluster = s.create_canvas_cluster(cols=2, rows=2, tile_width=32, tile_height=32)

    # 2. 自动创建 4 个 Worker Lua 芯片并完成 4 条物理 Wire 连线
    group = s.add_parallel_canvas_chips(
        cluster=cluster,
        worker_script_fn=worker_builder,
    )

    s.save("canvas_parallel_demo.melsave")
```

---

## 体验与示例汇总

1. **纯侵入式单芯片直连**：`samples/canvas_single_direct_demo.py` → `canvas_single_direct.melsave`
2. **纯侵入式直写 Buffer**：`samples/canvas_intrusive_demo.py` → `canvas_intrusive_demo.melsave`
3. **L2 极致脏像素优化**：`samples/canvas_ultra_demo.py` → `canvas_ultra_demo.melsave`
4. **多芯片 2x2 并行集群 (64x64)**：`samples/canvas_parallel_demo.py` → `canvas_parallel_demo.melsave`
5. **1+4 主从分布式弹跳小球 (64x64)**：`samples/canvas_master_worker_bouncing_ball.py` → `canvas_master_worker_ball.melsave`
