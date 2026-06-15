-- Demo chip that reads inputs every tick
local sum = 0

function OnInit()
    print("[adder] init")
end

function OnTick()
    local a = inputs.num.a or 0
    local b = inputs.num.b or 0
    sum = sum + a + b
    outputs.num.sum = sum
    outputs.num.a_now = a
    outputs.num.b_now = b
    outputs.string.last = "a=" .. tostring(a) .. " b=" .. tostring(b) .. " sum=" .. tostring(sum)
end
