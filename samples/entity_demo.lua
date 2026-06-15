-- Sample: 实体操控示例
-- 用法: python -m melon_lua samples/entity_demo.lua --duration 3

function onInit()
    print("创建实体...")
    self_id = spawn.create("玩家芯片", 0, 0)
    target_id = spawn.create("目标方块", 50, 30)
    print("self_id=" .. self_id .. " target_id=" .. target_id)
end

function onTick()
    local target = entity.getById(target_id)
    if target then
        entity.setVelocity(target_id, 1.0, 0.5)
        local pos = entity.getPosition(target_id)
        print(string.format("目标位置: (%.1f, %.1f)", pos.x, pos.y))
    end
end
