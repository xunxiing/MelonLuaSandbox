-- Sample: 甜瓜游乐场 Lua 芯片脚本
-- 用法: python -m melon_lua samples/hello_chip.lua --duration 3

function onInit()
    print("芯片初始化!")
    env.set("counter", 0)
    spawn.create("测试方块", 10, 10)
end

function onTick()
    local count = env.get("counter") or 0
    count = count + 1
    env.set("counter", count)

    if count % 5 == 0 then
        print("Tick #" .. count .. " - 芯片工作中...")
    end

    O.status = "running"
    O.tick_count = count
end
