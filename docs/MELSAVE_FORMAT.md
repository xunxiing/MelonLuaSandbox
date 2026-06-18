# .melsave 读取与中间格式（草案）

## 文件结构（APK 逆向 + 实机存档）

`.melsave` 是 **ZIP**，通常包含：

| 条目 | 内容 |
|------|------|
| `Data` | UTF-8 JSON，`SaveObjectDataContainer` 序列化 |
| `MetaData` | UTF-8 JSON，存档名、版本、地图、分类等 |
| `Icon` | PNG 缩略图 |

游戏侧（`FilesManagement.Saves` / `SaveConverter`）在加载时把 JSON 转成二进制 `SaveObjectData`；我们沙盒**直接读 JSON `Data`** 即可列出物体。

### `Data` 顶层字段

- `saveObjectContainers`: 数组，每项 `{ "saveObjects": {...}, "saveObjectChildren": [...] }`
- `averagePosition`: 相机/缩略图用平均位置
- `autoLightData`: 光照（可为 null）

### `saveObjects` 常用字段（与 `scripts/json_to_melsave.py` 一致）

- `objectId` — 稳定预制体 ID（对应 `SaveSystemItemsConfig` / 沙盒 `catalog`）
- `instanceId`, `localId`, `parentId`
- `position` / `rotation` / `scale`（`{x,y,z}`）
- `gravity`, `freezed`, `color`, `humanData`, `mechanicData`, 各类 joint…

子物体挂在 `saveObjectChildren`（递归容器）；演示存档 `jixiebi.melsave` 均为根物体 `parentId=-1`。

## 沙盒中间格式 `MelonLuaSandbox.melsave.v1`

便于列表、导入 Box2D、和 Lua 芯片对接：

```json
{
  "format": "MelonLuaSandbox.melsave.v1",
  "save": { "name": "", "category": "daodan", "appVersion": "28.6.1", ... },
  "stats": { "objectCount": 8, "countsByObjectId": { "248": 3, "274": 2, ... } },
  "objects": [
    {
      "objectId": 202,
      "name": "ResizablePlastic",
      "position": { "x": 0.41, "y": 0.46, "z": 0 },
      "rotationZ": 0,
      "scale": { "x": 1, "y": 1 },
      "parentId": -1,
      "gravity": true,
      "freezed": false
    }
  ]
}
```

- `name` 由沙盒 `catalog.get_profile_by_object_id` 解析；未知 ID 为 `objectId_<n>`。
- 可选 `--raw` 导出完整 `saveObjects` 供深度逆向。

## 工具

```bat
cd MelonLuaSandbox
python scripts\inspect_melsave.py temp\jixiebi.melsave --table
python scripts\inspect_melsave.py temp\jixiebi.melsave -o temp\jixiebi_parsed.json
```

Python API：

```python
from melon_lua.melsave import read_melsave, document_to_dict, spawn_document_into_world
from melon_lua import WorldContext

doc = read_melsave("temp/jixiebi.melsave")
world = WorldContext()
spawn_document_into_world(doc, world)  # 按 position 生成实体（仅 parentId==-1）
```

## 演示存档 `jixiebi.melsave`（8 个物体）

| objectId | 名称（catalog） | 数量 |
|----------|-----------------|------|
| 248 | VPchip | 3 |
| 274 | WeightingAgent | 2 |
| 202 | ResizablePlastic | 2 |
| 121 | Wheel | 1 |

## 待商量

1. **子物体 / 关节**：是否递归展开 `saveObjectChildren` + `hingeJoints` 进沙盒？
2. **坐标系**：存档为 Unity 3D `position`；沙盒 2D 用 `x,y`，`z` 暂忽略。
3. **导入策略**：一次性 `spawn_document_into_world` vs 生成 Lua `spawn.create` 脚本。
4. **双向**：已有 `scripts/json_to_melsave.py` 写存档；是否要在沙盒内 `export_melsave()`？