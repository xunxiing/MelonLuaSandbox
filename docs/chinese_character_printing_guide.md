# 紫晶石灰《LED点阵屏_汉字打印》模块 SDK 接入与使用指南

本文档记录了由 **紫晶石灰** 开发的 `Chinese_character_printing` 8105 字 11×11 汉字打印模块在 `MelonLuaSandbox` Python SDK 中的集成方式与使用 API。

---

## 1. 模块简介

* **作者**：紫晶石灰
* **模块名称**：`Chinese_character_printing`
* **使用字体**：`Cubic_11`（标准 11×11 像素字符）
* **支持字库**：
  * 《通用规范汉字表》**8105 字完整版**
  * ASCII 32 ~ 126 常用字符与标点
* **存储方式**：通过甜瓜原生 `register_module("Chinese_character_printing", epl)` 在 `OnInit()` 中注册到全局共享内存模块表。

---

## 2. Lua 端函数接口规范

### 函数签名

### 严禁在 Chunk 顶层 (函数体外部) 直接 require 模块

由于甜瓜游乐场 C# Lua 引擎在载入地图文件时，多个 Lua 芯片的顶层 Chunk 代码是异步/并行解析执行的：
* **如果用户芯片在顶层全局位置直接调用 `local print_char = require("Chinese_character_printing")`**，可能会在 Provider 芯片的 `OnInit()` 尚未执行完成前运行，从而抛出：
  `385 module not found Chinese_character_printing` 崩溃！

### 推荐的懒加载 (Lazy Require) 安全模式

在 `OnTick()` 内部进行延迟懒加载：

```lua
local print_char = nil

function OnTick()
    -- 延迟懒加载防护：等待 Provider 芯片 OnInit 完成注册
    if not print_char then
        if shared and shared.modules and shared.modules["Chinese_character_printing"] then
            print_char = require("Chinese_character_printing")
        elseif _G.Chinese_character_printing then
            print_char = _G.Chinese_character_printing
        else
            outputs.string.status = "等待汉字模块加载..."
            return
        end
    end

    local buf = canvas_0.buffer
    if not buf then return end
    canvas_0:clear(0, 0, 0)

    -- 正常调用 print_char 即可
    print_char(buf, 32, 32, 2, 2, "原", {x=1, y=0.85, z=0.2, w=1})
    canvas_0:flush()
end
```

### 参数说明

| 参数名 | 数据类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `array_vec` | `table` | 目标的 1D Vector4 显存缓冲区表 | `canvas_0.buffer` |
| `screen_x` | `number` | 显示屏宽度 (像素) | `32` |
| `screen_y` | `number` | 显示屏高度 (像素) | `32` |
| `tx` | `number` | 字符打印左上角 X 轴坐标 | `2` |
| `ty` | `number` | 字符打印左上角 Y 轴坐标 | `2` |
| `a` | `string` | 待打印的单个字符 | `"原"` 或 `"A"` |
| `rgb` | `table` | 字符颜色 Vector4 | `{x = 1.0, y = 0.85, z = 0.2, w = 1.0}` |

* **坐标说明**：Y 轴以向下为正数，打印坐标对应字符 **11×11 占位框的左上角**。
* **擦除说明**：打印空格符时，会将当前 11×11 占位空间全部填充为输入的 `rgb` 颜色，可用于清屏或覆盖擦除。

---

## 3. Python SDK 集成指南

Python SDK 在 `melon_lua.packages.chinese_printing` 中提供了自动化模块提供者芯片注入工具。

### 示例代码

```python
from melon_lua import MelsaveSession
from melon_lua.packages import add_chinese_printing_provider

with MelsaveSession() as s:
    # 1. 创建 32x32 LED 屏幕
    cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=0.0)

    # 2. 注入紫晶石灰汉字模块 Provider 芯片 (自动包含 379KB 完整字库与 register_module)
    add_chinese_printing_provider(s, x=-3.0, y=0.0)

    # 3. 编写用户业务 Lua 芯片
    user_script = """
    local print_char = require("Chinese_character_printing")

    function OnTick()
        local buf = canvas_0.buffer
        if not buf then return end

        canvas_0:clear(0, 0, 0)

        local GOLD = {x = 1.0, y = 0.85, z = 0.2, w = 1.0}
        local CYAN = {x = 0.0, y = 0.85, z = 1.0, w = 1.0}

        -- 在屏幕上打印汉字
        Chinese_character_printing(buf, 32, 32, 2, 2, "原", GOLD)
        Chinese_character_printing(buf, 32, 32, 16, 2, "神", CYAN)

        canvas_0:flush()
    end
    """

    # 4. 添加用户芯片并保存存档
    chip_idx = s.add_lua_chip(user_script, canvases=[cv], x=3.0, y=0.0, instruction_cost=300000)
    s.connect(cv.item_idx, "entity", chip_idx, "target")
    s.save("chinese_printing_demo.melsave")
```

---

## 4. 性能与注意事项

1. **指令预算**：
   * 汉字打印点阵拆解包含 `while` 循环与字符串截取。
   * 建议单芯片单帧打印的字符数不超过 **2 ~ 4 个**。
   * 建议将用户芯片的 `instruction_cost` 设为 `200000` ~ `300000`。
2. **字符范围限制**：
   * 仅支持《通用规范汉字表》8105 字及 ASCII 32~126。请勿输入表情符号或其他生僻字，避免索引 `nil`。
