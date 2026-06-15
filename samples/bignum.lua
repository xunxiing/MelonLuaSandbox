-- ============ Local state (not saved to disk) ============
local tick = 0
local bigNum = {0}

function OnInit()
    tick = 0
    bigNum = {0}
    if env and env.time then
        math.randomseed(math.floor(env.time() * 1000))
    end
    print("BigNumber calculator chip initialized.")
end

function OnDestroy()
    print("BigNumber calculator chip destroyed.")
end

function OnTick()
    tick = tick + 1
    local carry = math.random(1, 1000)
    local i = 1
    while carry > 0 do
        if i > #bigNum then
            table.insert(bigNum, 0)
        end
        local currentSum = bigNum[i] + carry
        bigNum[i] = currentSum % 10
        carry = math.floor(currentSum / 10)
        i = i + 1
    end
    local totalDigits = #bigNum
    local displayStr = ""
    local MAX_DISPLAY_LIMIT = 60
    if totalDigits <= MAX_DISPLAY_LIMIT then
        local digitsTable = {}
        for j = totalDigits, 1, -1 do
            table.insert(digitsTable, bigNum[j])
        end
        displayStr = table.concat(digitsTable)
    else
        local headTable = {}
        for j = totalDigits, totalDigits - 15, -1 do
            table.insert(headTable, bigNum[j])
        end
        local tailTable = {}
        for j = 15, 1, -1 do
            table.insert(tailTable, bigNum[j])
        end
        displayStr = table.concat(headTable) .. "..." .. table.concat(tailTable)
    end
    outputs.num.tick = tick
    outputs.num.digit_count = totalDigits
    outputs.string.status = "Calculating..."
    outputs.string.value = displayStr
end
