-- 左对齐。字号锁 5，<nobr> 禁止换行。
-- 每次左移一个字，不补空格，避免切字时整行右弹。

local DEFAULT_TEXT = "欢迎乘坐甜瓜铁路运输集团云水号动车组      G3611   甜瓜东→万城岛松山，本站：甜瓜东  下一站：雨林港"
local COLS = 8
local STEP = 4

local function plain(s)
    s = string.gsub(s or "", "\r", "")
    s = string.gsub(s, "\n", " ")
    return s
end

local function units_of(s)
    local n = 0
    local i = 1
    local len = #s
    while i <= len do
        local b = string.byte(s, i)
        local w = 1
        if b >= 240 then
            w = 4
        elseif b >= 224 then
            w = 3
        elseif b >= 192 then
            w = 2
        end
        if i + w - 1 > len then
            w = 1
        end
        n = n + ((b < 128) and 1 or 2)
        i = i + w
    end
    return n
end

local function take(s, from_unit, count)
    local out = {}
    local got = 0
    local seen = 0
    local i = 1
    local len = #s
    while i <= len and got < count do
        local b = string.byte(s, i)
        local w = 1
        if b >= 240 then
            w = 4
        elseif b >= 224 then
            w = 3
        elseif b >= 192 then
            w = 2
        end
        if i + w - 1 > len then
            w = 1
        end
        local cw = (b < 128) and 1 or 2
        if seen >= from_unit then
            out[#out + 1] = string.sub(s, i, i + w - 1)
            got = got + cw
        end
        seen = seen + cw
        i = i + w
    end
    return table.concat(out)
end

local phase = 0
local tick = 0

local function window_of(base, p)
    local loop = base .. "    "
    local total = units_of(loop)
    if total < 1 then
        total = 1
    end
    local cell = p % total
    return "<size=17><nobr>" .. take(loop .. loop, cell, COLS) .. "</nobr></size>"
end

local function hide_frame()
    local id = inputs.entity.screen
    if id ~= nil and id ~= 0 then
        local e = Entity(id)
        if e and e._nil ~= true and e:isValid() == 1 then
            e:setColor(0, 0, 0, 0)
        end
    end
end

function OnInit()
    phase = 0
    tick = 0
    hide_frame()
    outputs.string.text = window_of(plain(DEFAULT_TEXT), 0)
    outputs.vec.color = { x = 0.784, y = 0.086, z = 0.118, w = 0.65 }
end

function OnTick()
    local custom = inputs.string.text
    local base = plain((custom ~= nil and custom ~= "") and custom or DEFAULT_TEXT)
    hide_frame()
    tick = tick + 1
    if tick % STEP == 0 then
        phase = phase + 1
    end
    outputs.string.text = window_of(base, phase)
    outputs.vec.color = { x = 0.784, y = 0.086, z = 0.118, w = 0.65 }
end
