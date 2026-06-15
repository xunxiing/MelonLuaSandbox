-- Full bit32 for melon (Lua 5.2); works without LuaJIT `bit` library
if bit32 ~= nil and type(bit32.band) == 'function' and type(bit32.btest) == 'function' then
    return
end

local function to_u32(n)
    n = math.floor(tonumber(n) or 0)
    if n < 0 then n = n + 4294967296 end
    return n % 4294967296
end

local function band(a, b)
    a, b = to_u32(a), to_u32(b)
    local r, p = 0, 1
    for _ = 1, 32 do
        if a % 2 == 1 and b % 2 == 1 then r = r + p end
        a, b = math.floor(a / 2), math.floor(b / 2)
        p = p * 2
    end
    return r
end

local function bor(a, b)
    a, b = to_u32(a), to_u32(b)
    local r, p = 0, 1
    for _ = 1, 32 do
        if a % 2 == 1 or b % 2 == 1 then r = r + p end
        a, b = math.floor(a / 2), math.floor(b / 2)
        p = p * 2
    end
    return r
end

local function bxor(a, b)
    a, b = to_u32(a), to_u32(b)
    local r, p = 0, 1
    for _ = 1, 32 do
        if a % 2 ~= b % 2 then r = r + p end
        a, b = math.floor(a / 2), math.floor(b / 2)
        p = p * 2
    end
    return r
end

local function bnot(a)
    return to_u32(4294967295 - to_u32(a))
end

local function lshift(a, n)
    return to_u32(to_u32(a) * (2 ^ (n % 32)))
end

local function rshift(a, n)
    return math.floor(to_u32(a) / (2 ^ (n % 32)))
end

local function arshift(a, n)
    a = to_u32(a)
    n = n % 32
    if a >= 2147483648 then
        return to_u32(math.floor(a / (2 ^ n)) + (2 ^ (32 - n) - 1) * (2 ^ n))
    end
    return rshift(a, n)
end

bit32 = {
    band = function(...) local a = select(1, ...); for i = 2, select('#', ...) do a = band(a, select(i, ...)) end; return a end,
    bor = function(...) local a = select(1, ...); for i = 2, select('#', ...) do a = bor(a, select(i, ...)) end; return a end,
    bxor = function(...) local a = select(1, ...); for i = 2, select('#', ...) do a = bxor(a, select(i, ...)) end; return a end,
    bnot = bnot,
    lshift = lshift,
    rshift = rshift,
    arshift = arshift,
    lrotate = function(x, disp)
        x, disp = to_u32(x), disp % 32
        return to_u32(bor(lshift(x, disp), rshift(x, 32 - disp)))
    end,
    rrotate = function(x, disp)
        x, disp = to_u32(x), disp % 32
        return to_u32(bor(rshift(x, disp), lshift(x, 32 - disp)))
    end,
    btest = function(...)
        local n = select('#', ...)
        if n < 1 then return false end
        local acc = to_u32(select(1, ...))
        for i = 2, n do acc = band(acc, to_u32(select(i, ...))) end
        return acc ~= 0
    end,
    extract = function(n, field, width)
        n = to_u32(n)
        field = field or 0
        width = width or 1
        local mask = lshift(1, width) - 1
        return band(rshift(n, field), mask)
    end,
    replace = function(n, v, field, width)
        n, v = to_u32(n), to_u32(v)
        field = field or 0
        width = width or 1
        local mask = lshift(1, width) - 1
        v = band(v, mask)
        local cleared = band(n, bnot(lshift(mask, field)))
        return to_u32(cleared + lshift(v, field))
    end,
}