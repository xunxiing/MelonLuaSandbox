"""SpaceX Starship 3-Chip Flight Control System Generator.

Generates starship_flight_controller.melsave containing:
1. Master Mission Commander Chip (Obj 1): Mission state machine (Liftoff -> MECO -> Hot Staging -> RTLS -> Orbit).
2. 1st Stage Booster Flight Controller Chip (Obj 2): 33 Raptor engine thrust, boostback burn, entry burn, Mechazilla catch.
3. 2nd Stage Starship Flight Controller Chip (Obj 3): 6 Raptor hot staging ignition, gravity turn, orbital insertion & 64x32 telemetry screen driver.
4. Telemetry Dashboard LED Screen (Obj 0): 64x32 HUD showing real-time altitude, velocity, trajectory, engine status.
"""
import os
from melon_lua.session import MelsaveSession

def generate_starship_save():
    s = MelsaveSession()
    
    # 1. Add Telemetry Display Canvas Screen (Obj 0)
    cv = s.create_canvas(
        width=64,
        height=32,
        x=0.0, y=3.0,
        scale_x=2.0, scale_y=1.0
    )

    # -------------------------------------------------------------
    # CHIP 1: Master Mission Commander Chip (总控芯片)
    # -------------------------------------------------------------
    master_code = """-- SpaceX Starship Master Mission Commander
function OnInit()
    shared.starship_mission = {
        phase = "COUNTDOWN",
        phase_idx = 1,
        time = -10.0,
        alt = 0.0,          -- meters
        vel = 0.0,          -- m/s
        downrange = 0.0,    -- km
        pitch = 90.0,       -- deg
        status_text = "T-10s 预准备中..."
    }
end

function OnTick()
    local m = shared.starship_mission
    if not m then return end

    m.time = m.time + 0.1 -- 10Hz tick simulation

    -- State Machine Transitions
    if m.time < 0 then
        m.phase = "COUNTDOWN"
        m.status_text = string.format("发射倒计时: T%.1fs", m.time)
    elseif m.time >= 0 and m.time < 30 then
        m.phase = "LIFTOFF"
        m.alt = m.alt + (m.time * m.time * 2.5)
        m.vel = m.time * 50.0
        m.status_text = string.format("点火升空! 高度:%.1fkm 速度:%.0fm/s", m.alt/1000, m.vel)
    elseif m.time >= 30 and m.time < 60 then
        m.phase = "MAX_Q"
        m.pitch = 90.0 - (m.time - 30) * 1.2
        m.alt = 2250 + (m.time - 30) * 800
        m.vel = 1500 + (m.time - 30) * 45
        m.status_text = "最大动态压过载 (MAX-Q) 节流"
    elseif m.time >= 60 and m.time < 75 then
        m.phase = "MECO_STAGING"
        m.pitch = 54.0 - (m.time - 60) * 1.6
        m.alt = 26250 + (m.time - 60) * 1200
        m.vel = 2850 + (m.time - 60) * 60
        m.status_text = "一级主发动机关机 (MECO)"
    elseif m.time >= 75 and m.time < 90 then
        m.phase = "HOT_STAGING"
        m.alt = 44250 + (m.time - 75) * 1100
        m.vel = 3750 + (m.time - 75) * 70
        m.status_text = "二级热分离环点火成功! 级间分离"
    elseif m.time >= 90 and m.time < 150 then
        m.phase = "BOOSTBACK_BURN"
        m.alt = 60750 + (m.time - 90) * 800
        m.vel = 4800 + (m.time - 90) * 50
        m.status_text = "一级火箭 180° 调头反推点火 (RTLS)"
    elseif m.time >= 150 and m.time < 220 then
        m.phase = "ORBITAL_INSERTION"
        m.pitch = 20.0 - (m.time - 150) * 0.2
        m.alt = 108750 + (m.time - 150) * 600
        m.vel = 7800 + (m.time - 150) * 35
        m.status_text = "二级星舰全加速入轨中"
    else
        m.phase = "MISSION_COMPLETE"
        m.status_text = "星舰成功一级入轨 & 一级 Mechazilla 捕获回收!"
    end

    if outputs and outputs.string and outputs.string.status then
        outputs.string.status = m.status_text
    end
end
"""

    s.add_lua_chip(
        master_code,
        inputs=[],
        outputs=[{"name": "status", "type": "string"}],
        x=-3.0, y=-2.0
    )

    # -------------------------------------------------------------
    # CHIP 2: 1st Stage Booster Flight Controller Chip (一级飞控芯片)
    # -------------------------------------------------------------
    booster_code = """-- 1st Stage Super Heavy Booster Flight Controller
function OnInit()
    shared.booster_telemetry = {
        raptors_active = 0,
        thrust_pct = 0.0,
        fuel_pct = 100.0,
        gimbal_pitch = 0.0,
        status = "STANDBY"
    }
end

function OnTick()
    local m = shared.starship_mission
    local b = shared.booster_telemetry
    if not m or not b then return end

    if m.phase == "COUNTDOWN" then
        b.raptors_active = 0
        b.thrust_pct = 0.0
        b.status = "地上预准备"
    elseif m.phase == "LIFTOFF" or m.phase == "MAX_Q" then
        b.raptors_active = 33
        b.thrust_pct = 100.0
        b.fuel_pct = math.max(0, 100 - (m.time * 0.6))
        b.gimbal_pitch = (90.0 - m.pitch) * 0.1
        b.status = "33台猛禽全功率推力发射"
    elseif m.phase == "MECO_STAGING" then
        b.raptors_active = 3
        b.thrust_pct = 10.0
        b.status = "关机保留3台中央发动机"
    elseif m.phase == "HOT_STAGING" then
        b.raptors_active = 3
        b.thrust_pct = 15.0
        b.status = "热分离反推气流姿态稳定"
    elseif m.phase == "BOOSTBACK_BURN" then
        b.raptors_active = 13
        b.thrust_pct = 85.0
        b.fuel_pct = math.max(0, b.fuel_pct - 0.2)
        b.gimbal_pitch = 180.0
        b.status = "13台猛禽返场点火 (Boostback)"
    elseif m.phase == "ORBITAL_INSERTION" or m.phase == "MISSION_COMPLETE" then
        b.raptors_active = 3
        b.thrust_pct = 40.0
        b.status = "筷子机械臂 (Mechazilla) 完美捕获回收"
    end

    if outputs and outputs.string and outputs.string.status then
        outputs.string.status = string.format("一级: %s (猛禽:%d台 推力:%.0f%%)", b.status, b.raptors_active, b.thrust_pct)
    end
end
"""

    s.add_lua_chip(
        booster_code,
        inputs=[],
        outputs=[{"name": "status", "type": "string"}],
        x=0.0, y=-2.0
    )

    # -------------------------------------------------------------
    # CHIP 3: 2nd Stage Starship Flight Controller Chip (二级飞控芯片 + 屏幕驱动)
    # -------------------------------------------------------------
    ship_code = """-- 2nd Stage Starship Upper Stage Flight Controller & HUD Screen Driver
local border_hidden = false

function OnInit()
    shared.ship_telemetry = {
        raptors_active = 0,
        vacuum_raptors = 0,
        thrust_pct = 0.0,
        fuel_pct = 100.0,
        orbit_inserted = false,
        status = "STANDBY"
    }
end

function OnTick()
    if not border_hidden then
        if inputs and inputs.entity and inputs.entity.target then
            Entity(inputs.entity.target):setColor(0, 0, 0, 0)
            border_hidden = true
        end
    end

    local m = shared.starship_mission
    local s_ship = shared.ship_telemetry
    local cv_inst = canvas_0
    if not m or not s_ship then return end

    if m.phase == "COUNTDOWN" or m.phase == "LIFTOFF" or m.phase == "MAX_Q" or m.phase == "MECO_STAGING" then
        s_ship.raptors_active = 0
        s_ship.vacuum_raptors = 0
        s_ship.thrust_pct = 0.0
        s_ship.status = "搭乘一级上升中"
    elseif m.phase == "HOT_STAGING" then
        s_ship.raptors_active = 3
        s_ship.vacuum_raptors = 3
        s_ship.thrust_pct = 100.0
        s_ship.status = "6台猛禽 (3海平面+3真空) 热分离点火"
    elseif m.phase == "BOOSTBACK_BURN" or m.phase == "ORBITAL_INSERTION" then
        s_ship.raptors_active = 3
        s_ship.vacuum_raptors = 3
        s_ship.thrust_pct = 100.0
        s_ship.fuel_pct = math.max(0, 100 - (m.time - 90) * 0.4)
        s_ship.status = "真空猛禽加速 目标第一宇宙速度"
    elseif m.phase == "MISSION_COMPLETE" then
        s_ship.raptors_active = 0
        s_ship.vacuum_raptors = 0
        s_ship.thrust_pct = 0.0
        s_ship.orbit_inserted = true
        s_ship.status = "成功进入 150km*150km 近地轨道 (SECO)"
    end

    -- Render Telemetry Dashboard to Canvas Screen
    if cv_inst and cv_inst.buffer then
        cv_inst:clear(0, 0, 0)
        
        -- Draw HUD Border Lines
        for x = 0, 63 do
            cv_inst:setPixel(x, 0, 0, 0.4, 0.8)
            cv_inst:setPixel(x, 31, 0, 0.4, 0.8)
        end
        for y = 0, 31 do
            cv_inst:setPixel(0, y, 0, 0.4, 0.8)
            cv_inst:setPixel(63, y, 0, 0.4, 0.8)
        end

        -- Draw Mechazilla Launch Tower at x=8, y=24~28
        for ty = 24, 28 do
            cv_inst:setPixel(7, ty, 0.8, 0.8, 0.8)
        end
        cv_inst:setPixel(8, 25, 1.0, 0.85, 0.2) -- Chopstick Catch Arm!

        -- Trajectory curve & Active Rocket Position
        local prog = math.min(1.0, math.max(0.0, (m.time + 10) / 230))
        local tx = math.floor(8 + prog * 48)
        local ty = math.floor(28 - math.sin(prog * 1.57) * 20)
        
        -- Trail line
        for step = 0, 10 do
            local sprog = math.max(0.0, prog - step * 0.02)
            local sx = math.floor(8 + sprog * 48)
            local sy = math.floor(28 - math.sin(sprog * 1.57) * 20)
            cv_inst:setPixel(sx, sy, 0.0, 0.85, 1.0)
        end

        -- Active Rocket Glowing Tip
        cv_inst:setPixel(tx, ty, 1.0, 0.95, 0.2)
        cv_inst:setPixel(tx-1, ty, 1.0, 0.5, 0.1)
        cv_inst:setPixel(tx+1, ty, 1.0, 0.5, 0.1)
        cv_inst:setPixel(tx, ty-1, 1.0, 0.5, 0.1)
        cv_inst:setPixel(tx, ty+1, 1.0, 0.5, 0.1)

        -- Draw Fuel Bar (Right Side x=58~61)
        local fuel_h = math.floor((s_ship.fuel_pct / 100) * 20)
        for fy = 0, fuel_h do
            cv_inst:setPixel(60, 26 - fy, 0.0, 0.9, 0.3)
            cv_inst:setPixel(61, 26 - fy, 0.0, 0.9, 0.3)
        end

        cv_inst:flush()
    end

    if outputs and outputs.string and outputs.string.status then
        outputs.string.status = string.format("二级: %s (推力:%.0f%% 燃料:%.0f%%)", s_ship.status, s_ship.thrust_pct, s_ship.fuel_pct)
    end
end
"""

    chip3_idx = s.add_lua_chip(
        ship_code,
        inputs=[{"name": "target", "type": "entity"}],
        outputs=[{"name": "status", "type": "string"}],
        canvases=[cv],
        x=3.0, y=-2.0
    )

    # Connect target entity wire for border hiding
    s.connect(cv.item_idx, "entity", chip3_idx, "target")

    save_path = "starship_flight_controller.melsave"
    s.save(save_path)
    print(f"Successfully generated SpaceX Starship 3-Chip GNC Save with Display Wires: {os.path.abspath(save_path)}")

if __name__ == "__main__":
    generate_starship_save()
