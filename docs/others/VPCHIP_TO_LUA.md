# VPchip 可视化图 → Lua：能否「无损」？

## 结论（实话）

| 含义 | 能否做到 |
|------|----------|
| **存档可往返**（Lua ↔ 同一份 `chip_graph` JSON 字节级一致） | ❌ 不现实（图里有 UUID、编辑器坐标、ViewModel 字符串） |
| **行为等价**（同一存档、同一 TPS，在沙盒里 tick 结果与真机 VPchip 一致） | ✅ **理论可行**，但是 **工程 = 实现整套节点语义**（上百种 `NodeOperationType`） |
| **结构保真**（连线、门名、常量、变量初值不丢，嵌进生成 Lua 的注释/IR） | ✅ 推荐作为第一阶段目标 |
| **你这份 `jixiebi` 里出现的节点子集** | ✅ 可先做一个 **子集编译器**，覆盖 Constant/Root/Add/Multiply/Branch/Position/AddAngularForce… |

「奇妙的逻辑」= **不要把图当图片看**，而是当 **数据流图（DFG）+ 每 tick 的固定点迭代** 编译成 Lua。

---

## 真机里图是什么（APK / 存档）

- 类型：`VPChip`（`objectId` 248），不是 `LuaChip`。
- 图 JSON：`saveMetaDatas[key=chip_graph].stringValue`
  - `Nodes[]`：每节点 `Id`（含人类名如 `Add : uuid`）、`OperationType`（整数）、`Inputs`/`Outputs`
  - 连线：`Inputs[].connectedOutputIdModel` → `{ NodeId, Id }`（无单独 `Links` 数组）
- 门控：`chip_inputs` / `chip_outputs` / `chip_variables`（JSON 数组，含 `DataName`、`GateDataType`）
  - `GateDataType = 1` → **实体**（运行时由 Root/连线绑定）
- 调度：`chip_tps`、`chip_priority`；类上有 `maxGateIterationInGraph`（**环图需要多轮求值**，不是简单 DAG 拓扑一次）

`OperationType` 与节点名对应关系在 IL2CPP：`Ui.Windows.Chip.NodeOperationType`（例如 `Root=256`, `Constant=257`, `Add=2304`, `AddAngularForce=1545`, `Branch=2567`）。

`jixiebi.melsave` 三片 VPchip 里节点名统计（节选）：Constant×49、Root×46、AddAngularForce×28、Multiply×22、Branch×14、Add×13…

---

## 推荐编译管线（Melon VP → Lua）

```
chip_graph JSON
    → 解析为 MelonGraph IR（节点表、边表、端口类型、常量烘焙值）
    → 绑定 chip_inputs/outputs/variables（人类可读名 ↔ Root 出口）
    → 按真机语义做「拓扑 + 迭代」（对齐 maxGateIteration）
    → 代码生成 Lua：
         - shared 状态表（变量、Counter、Branch 锁存）
         - OnInit / OnTick（TPS 由 runner 控制）
         - 节点体映射到 Entity API / math / mechanic 等价调用
    → 可选：附带 graph.json 哈希 + 反编译注释（结构保真）
```

### 生成 Lua 的形状（示意）

```lua
-- @vp_source instance=-522198 tps=240 ops=28
local G = {}  -- 节点输出缓存 + 变量

function OnInit()
  G["var_link"] = 7.165  -- 来自 chip_variables SerializedValue
end

function OnTick()
  for _iter = 1, MAX_GATE_ITER do
    G["const_1"] = 14.0
    G["add_1"] = G["const_1"] + (inputs.num.x or 0)
    -- Branch / Root / Position / AddAngularForce ...
  end
  outputs.num.y = G["out_main"]
end
```

实体引用不生成魔法数字：编译为 `Entity(save_instance_map[...])` 或芯片 `inputs` 里绑定的门。

---

## 节点 → Lua 映射原则

1. **纯数学**（Add、Multiply、Sin、Branch…）→ 直接 Lua 表达式 / `math.*`。
2. **实体读**（Position、Velocity、Angle…）→ `Entity(id):getPosition()` 等（与 `EntityApiModule` 一致）。
3. **实体写**（AddForce、AddAngularForce、Activate…）→ 对应 setter，**写在 tick 末或按节点顺序**（需对照 `Process()` 副作用顺序）。
4. **Root** → 从芯片外部 inputs 或上游节点 **注入** 到该 Root 绑定的 `DataName`（如 `statblie obj`）。
5. **Variable** → `shared` 或 `G` 表 + `chip_variables` 初值；跨 tick 保持。
6. **Constant** → 编译期折叠；若图里带烘焙 GateData 则读 `SerializedValue` JSON 的 `Value`。
7. **Exit** → 映射到 `outputs.*` 或终止本 tick 子图。

每新增一种 `NodeOperationType`，在 `vp_nodes/registry.py` 加一条 `(op_type, codegen_fn)`，并对照 `*NodeViewModel.Process()` 做单测。

---

## 「无损」的真正难点

1. **节点种类多**：`NodeOperationType` 枚举 100+（实体、向量、逻辑、比较、数组…）。
2. **动态类型**：`GateDynamicTypeData`（Add 等）在运行时选 number/vector。
3. **环与迭代**：与 `maxGateIterationInGraph` 一致才能和真机一样。
4. **多芯片优先级**：`priority` + 全局 TPS；沙盒要多 `MelonScriptRunner` 或统一 scheduler。
5. **实体引用**：inputs 里 `SerializedValue: null` 的实体门，需结合 **instanceId / 存档物体表** 或游戏内连线恢复。
6. **浮点 / 角度**：Unity 角度、Vector2/3/4 字段要和 API 一致（沙盒已有 vec 表）。

所以：**不是一条公式瞬间全图转 Lua**，而是 **IR + 节点库 + 迭代语义** 滚雪球；对单存档可以 **只实现用到的 op 集合**，在该存档上达到「实用无损」。

---

## 和「直接写 Lua 芯片」的关系

- **LuaChip**（36.x 新芯片）：存档里是另一套元数据 + Lua 源码，**不用走 VP 编译器**，直接 `MelonScriptRunner`。
- **VPchip**：必须 **图编译器** 或 **图解释器**（在 Python/Lua 里跑 MelonGraph IR）。
- 你的目标「全部转 Lua」= 长期应做成 **`vpchip compile` CLI**：  
  `jixiebi.melsave` → `workspace/chips/-522198/generated.lua` → 沙盒加载运行。

---

## 建议实施顺序

| 阶段 | 交付 | 验证 |
|------|------|------|
| **C0** | `vp_graph.py`：解析 graph、抽边、按 `NodeOperationType` 命名节点 | 与手工统计一致 |
| **C1** | 仅 **无环纯数** 节点：Constant→Add→Identity→outputs | 对比真机输出（需录屏/Frida 或人工） |
| **C2** | + Branch、Variable、Root+inputs | `jixiebi` 中 tps=240 那片 |
| **C3** | + 实体读 Position/Elevation/Magnitude + AddAngularForce | 机械臂存档场景 |
| **C4** | 迭代环 + priority 调度 | 多芯片同场景 |
| **C5** | 反向：Lua → graph（仅子集，供 AI 改后再编回） | 可选 |

---

## 对你问题的直接回答

> 可视化芯片能否通过某种逻辑 **全部无损** 转为 Lua？

- **全部**：要等价于实现 **整个 VP 虚拟机**，只是 **输出介质从图变成 Lua 文本**；可行，工作量 = 游戏芯片文档级。
- **奇妙的逻辑**：**数据流图 IR + 固定点迭代 + 按 OperationType 分发表 codegen 到甜瓜已有 Entity/Lua API**——这就是正路；不是 NLP 魔法。
- **建议**：接受「**存档级结构保真 + 行为等价（节点子集逐步扩大）**」，不要追求 JSON 字节无损。

若你同意，下一步可在仓库加 `melon_lua/vpcompile/`：**从 `jixiebi` 挑 tps=240、28 节点那片做第一版 Lua 生成**，并在沙盒里用 `MelonScriptRunner` 跑起来（哪怕先只算数、不驱动物体）。