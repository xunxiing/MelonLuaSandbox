
-- 弹簧悬挂车 v5（180tps 出厂版）
-- v4：反作用力施加在车身挂点(±ax)——消除倾斜时的虚假净扭矩（一歪就散的根因）
--     新增 klevel 自动回正扭矩：τ = -klevel·sin(车身角)，把车拉回水平
-- 弹簧逻辑不变：d = (轮心-挂心)·车身法线（点乘，角度实时跟随）
local function servo(e, tx, ty, ax, ay, bvx, bvy, ux, uy, nx, ny, kp, kd)
    local wx, wy = e:getPosition()
    local dx, dy = wx - ax, wy - ay
    local along = dx * ux + dy * uy
    local d = dx * nx + dy * ny
    local vx, vy = e:getVelocity()
    local vrel_n = (vx - bvx) * nx + (vy - bvy) * ny
    local vrel_t = (vx - bvx) * ux + (vy - bvy) * uy
    local m = e:getMass()
    local fn = m * (kp * (ty - d) - kd * vrel_n)
    local ft = m * (kp * (tx - along) - kd * vrel_t)
    return fn * nx + ft * ux, fn * ny + ft * uy
end

function OnTick()
    local rest = inputs.num.rest or 0.2
    local ax = inputs.num.ax or 1.5
    local kp = inputs.num.kp or 100
    local kd = inputs.num.kd or 20
    local lift = inputs.num.lift or 0
    local kv = inputs.num.kv or 2
    local kwa = inputs.num.kwa or 200
    local klevel = inputs.num.klevel or 0

    local bid = inputs.entity.body
    if bid == nil or bid == 0 then
        outputs.string.status = "body not wired"
        return
    end
    local body = Entity(bid)
    if (not body) or body._nil or body:isValid() ~= 1 then
        outputs.string.status = "body invalid"
        return
    end
    local bx, by = body:getPosition()
    local ra = math.rad(body:getAngle())
    local ux, uy = math.cos(ra), math.sin(ra)
    local nx, ny = -math.sin(ra), math.cos(ra)
    local bvx, bvy = body:getVelocity()

    if lift ~= 0 then
        body:addForce(0, body:getMass() * (lift - kv * bvy))
    end
    if kwa ~= 0 then
        body:addTorque(-kwa * math.rad(body:getAngularVelocity()))
    end
    if klevel ~= 0 then
        body:addTorque(-klevel * math.sin(ra))
    end

    for i = 1, 2 do
        local key = (i == 1) and "wheel1" or "wheel2"
        local tx = (i == 1) and -ax or ax
        local id = inputs.entity[key]
        if id == nil or id == 0 then
            outputs.string.status = key .. " not wired"
            return
        end
        local e = Entity(id)
        if (not e) or e._nil or e:isValid() ~= 1 then
            outputs.string.status = key .. " invalid"
            return
        end
        if lift ~= 0 then
            local _, wvy = e:getVelocity()
            e:addForce(0, e:getMass() * (lift - kv * wvy))
        end
        local atx = bx + tx * ux
        local aty = by + tx * uy
        local fx, fy = servo(e, 0, -rest, atx, aty, bvx, bvy,
                             ux, uy, nx, ny, kp, kd)
        e:addForce(fx, fy)
        body:addForceAtPosition(-fx, -fy, atx, aty)
    end
    outputs.string.status = "ok"
end
