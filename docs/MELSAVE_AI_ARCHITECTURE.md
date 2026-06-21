# 沙盒加载存档 + AI 改芯片/连线 — 架构建议（文件 vs SDK）

## 演示存档里实际有什么（`jixiebi.melsave`）

| 类型 | objectId | 数量 | 沙盒现状 |
|------|----------|------|----------|
| 普通刚体 | 121 Wheel, 202 ResizablePlastic | 3 | ✅ 已可 `spawn` + 物理 |
| 配重/机关 | 274 WeightingAgent | 2 | ⚠️ 有 `mechanicData`，未模拟 |
| **可视编程芯片** | **248 VPchip** | 3 | ❌ 图在 `saveMetaDatas.chip_graph`（JSON，约 30 节点/片） |

**重要**：这份存档里是 **VPchip 节点图**（Add / Root / Position / …），**不是** `LuaChip` 里的 `.lua` 源码。  
连线顺序在图里：`Nodes[].Inputs[].connectedOutputIdModel` → `{ NodeId, Id }`（已可从存档抽出约 30 条边/片）。

另有：`chip_inputs` / `chip_outputs` / `chip_variables`（门控类型 DataType=1 常表示 **实体引用**，SerializedValue 常为 null，运行时由连线绑定）。

---

## 目标拆解

1. **加载世界**：物体位置、缩放、旋转、关节（后续）
2. **理解/编辑「链接顺序」**  
   - A. VPchip：**图节点 + 有向边**（执行/数据流顺序）  
   - B. Lua 芯片（若以后存档含 LuaChip）：**Lua 源码 + I/O 门**  
   - C. 物理：**hingeJoints / distJoints**（机械臂顺序）
3. **在沙盒里跑起来**：至少能 tick 芯片逻辑或导出改完再写回 `.melsave`
4. **给 AI 改**：需要稳定、可 diff、带语义的名字

---

## 文件 vs SDK — 建议：**SDK 为主，文件为 AI 边界**

不要二选一，用 **三层**：

```
.melsave (ZIP 真源)
    ↓ read_melsave / load_scenario
MelonScenario (SDK 内存模型)  ← 程序唯一真源
    ↓ export_scenario_for_ai / import_scenario_patch
workspace/scenarios/jixiebi/   ← 给 AI / Git / 人工 diff 的「投影」
```

### 为什么 SDK 必须是中心

- 加载存档、spawn 到 `WorldContext`、以后跑 tick、写回 melsave，都应是 **同一对象图**。
- 若只落文件，还要再写一套「文件 → 世界」同步，容易和 Box2D 实体 id 脱节。
- AI 改完应是 **patch 应用回 Scenario**，再可选 `save_melsave()`，而不是让沙盒直接读散落 JSON。

### 为什么仍需要「文件形态」

- AI（含 opencode）擅长读/写 **目录 + JSON/YAML + 小 lua**。
- **大图** `chip_graph`（单芯片 260KB+）不适合整段塞进 prompt；应 **拆文件**：
  - `manifest.json` — 存档元数据 + 物体列表摘要
  - `objects/*.json` — 每个 instance 一条（含 position、objectId）
  - `chips/<instanceId>/graph.json` — 节点+边（AI 可改连线）
  - `chips/<instanceId>/io.json` — inputs/outputs 人类可读名
  - `links_index.json` — **仅边列表**（最适合改「顺序/拓扑」）
  - 将来 `chips/<id>/script.lua` — LuaChip 专用

---

## 建议的 SDK 表面（Python）

```python
from melon_lua.scenario import MelonScenario

sc = MelonScenario.load_melsave("temp/jixiebi.melsave")
sc.spawn_into(WorldContext())          # 只物体
sc.list_chips()                        # VPchip / LuaChip 实例
edges = sc.chip_edges(instance_id)     # [{from_node, to_node, ...}]
sc.apply_edge_patch(instance_id, ...)  # AI 改连线
sc.export_workspace("workspace/jixiebi")  # 写出 AI 友好文件树
sc.import_workspace("workspace/jixiebi")  # 合并 patch
sc.save_melsave("temp/jixiebi_edited.melsave")  # 阶段 3+
```

**运行**：短期 VPchip **不解释全图**（工作量大）；可先 **只加载物体 + 用 Lua 芯片替代/包裹** 做 AI 实验。中期做 **子集解释器**（Root → Position → … 常用节点）。长期或接真机导出 Lua。

---

## 分阶段（可商量）

| 阶段 | 内容 | AI 能做什么 |
|------|------|-------------|
| **P0** ✅ 已有 | `read_melsave`、物体列表、`spawn_document_into_world` | 读物体清单、生成 Lua spawn 脚本 |
| **P1** 推荐下一步 | `MelonScenario` + `export_workspace` + `links_index.json` | 改 VPchip **连线表**（JSON），不跑图 |
| **P2** | `instanceId` ↔ 沙盒 `entity_id` 映射；门控实体引用解析 | 改「连到哪个物体」 |
| **P3** | 写回 `chip_graph` / 整包 melsave | 改完导入游戏验证 |
| **P4** | LuaChip 检测 + `chip_lua` 元数据 + `MelonScriptRunner` 多芯片 | 真 Lua AI 编辑 |
| **P5** | VPchip 部分节点模拟或转 Lua | 沙盒内「运行」原存档逻辑 |

---

## 针对「链接顺序」的具体表示（供 AI）

**推荐 `links_index.json`（每芯片一份）**：

```json
{
  "chipInstanceId": -522198,
  "objectId": 248,
  "name": "VPchip",
  "edges": [
    { "from": "Constant", "to": "Add", "order": 0 },
    { "from": "Add", "to": "Identity", "order": 1 },
    { "from": "Root", "to": "Position", "order": 2 }
  ],
  "executionHints": ["Root 多个实例为不同 OnTick 入口"]
}
```

AI 任务示例：「把 Magnitude 的输出改接到 Subtract 之前」→ 改 `edges` + 校验无环 → `apply_edge_patch` → 写回 `graph.json` 里对应 `connectedOutputIdModel`。

---

## 结论（直接回答你的犹豫）

| 方案 | 建议 |
|------|------|
| **只弄成文件** | 适合 AI，但沙盒运行/写回会痛苦 |
| **只 SDK** | 适合程序，AI 难直接改 260KB graph |
| **SDK + workspace 导出** | ✅ **推荐**：SDK 真源，文件是 AI 可编辑投影 |

如果你同意 **P1**，下一步实现：`MelonScenario`、`extract_chip_edges`、`export_workspace(jixiebi)`，并在 `temp/workspace/jixiebi/` 生成可打开的 `links_index.json` + 物体表，**仍不承诺 VPchip 全图执行**。

请回复倾向：  
1）先 **导出+改连线+写回**；2）先 **只加载物体+Lua 芯片旁路**；3）两条并行。