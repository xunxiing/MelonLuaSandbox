# 甜瓜 Lua 芯片标准库支持清单

本文档基于 APK 逆向（`LuaSandboxConfigBase`、`LuaBackendConfig`、`Example_ApiReference_en.lua`）与沙盒实际实现整理。

## 甜瓜芯片允许的标准库（官方范围）

根据官方 `ApiReference`：

- **基础全局**：`pairs`、`ipairs`、`type`、`tostring`、`tonumber`、`select`、`unpack`、`pcall`、`xpcall`、`error`、`assert`、`next`、`setmetatable`、`getmetatable`、`rawequal`
- **math**：完整（含 `math.atan2`、`pow`、`cosh` 等）
- **string**：完整
- **table**：完整（含 `table.pack` 兼容）
- **coroutine**：完整
- **os**：仅 `os.time`、`os.clock`（当 `OsTime` 开关开启时）
- **bit32**：Lua 5.2 的位操作库（甜瓜使用 Lua-CSharp 5.2 提供）

**明确禁止/移除**（沙盒危险全局）：
- `io`（整个表）
- `package` / `require` 的原生模块加载（游戏用自己的 `register_module`/`require`）
- `debug`
- `load` / `loadstring` / `loadfile` / `dofile`
- `collectgarbage`
- `module`

## 沙盒实际实现（lupa + LuaJIT 5.1 对齐）

沙盒使用 **LuaJIT 5.1** 作为底层 VM，通过 `stdlib_melon.py` 主动对齐甜瓜策略：

### 已开放
- `math.*`（含补齐的 `atan2`、`pow`、`cosh` 等）
- `string.*`
- `table.*`（含 `table.pack` shim）
- `coroutine.*`
- `os.time`、`os.clock`
- `bit32.*`（纯 Lua 实现 `stdlib_bit32_shim.lua`，即使底层没有 bit 库也可用）
- 所有基础全局（pairs/pcall 等）

### 已禁用（置为 nil）
- `io`
- `package`
- `debug`
- `load`、`loadstring`、`loadfile`、`dofile`
- `collectgarbage`

### 兼容性 shim（自动注入）
- `table.pack`（如果不存在）
- `unpack = table.unpack`（兼容 Lua 5.2 风格代码）

## 如何在代码中使用

```lua
-- 标准 math / string / table
local r = math.random()
local s = string.format("%.2f", r)
local t = table.pack(1, 2, 3)
print(t.n)   -- 3

-- bit32（甜瓜 5.2 风格）
local x = bit32.band(0xFF, 0x0F)
local y = bit32.lshift(1, 3)

-- os（仅 time/clock）
local now = os.time()
local t0 = os.clock()

-- 协程
local co = coroutine.create(function() ... end)
```

## 验证方式

项目自带回归脚本：
```bash
cd MelonLuaSandbox
python scripts/verify_melon_stdlib.py
```

输出示例：
```
=== Melon Lua stdlib verification ===
Allowed categories: math, string, table, coroutine, os, bit32, base_globals
Banned present: 0
Missing critical: 0
Status: OK
```

另有 `samples/stdlib_smoke.lua` 可用于手动验证。

## 与真机差异提醒

- 底层 VM 是 LuaJIT 5.1 而非 Lua-CSharp 5.2，极少数边界行为（随机数序列、字符串格式、# 操作）可能不同。
- 游戏 API（`Entity`、`spawn`、`env` 等）**不属于**标准库，由 `LuaPreamble.lua` + 11 个 ApiModule 提供。
- `require` 在甜瓜里是游戏自定义的模块系统（`register_module`），不是 Lua 原生 `package`。

## 建议

- 写芯片时只使用本清单内的标准库函数。
- 需要跨芯片复用逻辑，请使用 `register_module` + `require`（见 `preamble.lua` 实现）。
- 调试时可用 `print` / `warn` / `error_log`，它们会进入 runner.logs。
