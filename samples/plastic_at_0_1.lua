function OnInit()
    spawn.create("202", 0, 1)
end

function OnSpawned(requestId, entities)
    if entities[1] then
        outputs.num.id = entities[1]:getId()
        outputs.num.x, outputs.num.y = entities[1]:getPosition()
        outputs.string.name = entities[1]:getName() or ""
    end
end

function OnTick()
end