-- Entity API preamble
-- Creates Entity(id) constructor with metatable delegating to __entity_raw C# module

-- ============================================================
-- Безопасные хелперы (используются всеми блоками преамбулы).
-- ============================================================

function safeLen(t)
    if t == nil then return 0 end
    if __lua_seq_len ~= nil then
        return __lua_seq_len(t) or 0
    end
    -- Fallback: ручной обход до первого nil-разрыва.
    local n = 0
    while t[n + 1] ~= nil do n = n + 1 end
    return n
end

-- Безопасный вызов user-callback'а: если он бросит, ловим pcall'ом и логируем,
-- чтобы единичная ошибка в подписке/листенере не валила весь dispatch и не
-- оставляла остальные подписки в полусломанном состоянии.
function __lua_safe_call(fn, ctx, ...)
    if type(fn) ~= "function" then return end
    local ok, err = pcall(fn, ...)
    if not ok then
        local logger = error_log or warn or print
        if logger then
            logger("[lua][" .. tostring(ctx) .. "] " .. tostring(err))
        end
    end
end

-- Стабильная итерация sequence-таблицы. Стандартное `#` в LuaCSharp на таблицах
-- с false-дырками может вернуть не-число → "for limit must be a number".
-- Останавливаемся на первой реально nil-ячейке. false-значения скипаем в callback'е.
function __lua_seq_each(t, callback)
    if type(t) ~= "table" or type(callback) ~= "function" then return end
    local i = 1
    while true do
        local v = t[i]
        if v == nil then return end
        callback(i, v)
        i = i + 1
    end
end

-- Длина sequence-таблицы по той же модели, что и __lua_seq_each.
function __lua_seq_len(t)
    if type(t) ~= "table" then return 0 end
    local i = 0
    while t[i + 1] ~= nil do i = i + 1 end
    return i
end

do
    local _e = __entity_raw
    if _e == nil then return end

    -- Noop object: delegates to __entity_raw with id=-1, returns defaults (0, "")
    local _noop_mt = {}
    _noop_mt.__index = function(t, k)
        local fn = _e[k]
        if fn then
            return function(_, ...)
                return fn(-1, ...)
            end
        end
        return function() return nil end
    end
    local _noop = setmetatable({ _id = -1, _nil = true }, _noop_mt)

    -- Callback registry для collision/trigger подписок
    local _callbacks = {}
    local _cb_counter = 0

    local function _register_callback(fn)
        _cb_counter = _cb_counter + 1
        _callbacks[_cb_counter] = fn
        return _cb_counter
    end

    local function _remove_callback(cbId)
        _callbacks[cbId] = nil
    end

    -- Таблицы имён для subscribe/unsubscribe
    local _subscribe_methods = {
        subscribeCollisionEnter = true, subscribeCollisionExit = true, subscribeCollisionStay = true,
        subscribeTriggerEnter = true, subscribeTriggerExit = true, subscribeTriggerStay = true,
        subscribeWireConnected = true, subscribeWireDisconnected = true
    }
    local _unsubscribe_methods = {
        unsubscribeCollisionEnter = true, unsubscribeCollisionExit = true, unsubscribeCollisionStay = true,
        unsubscribeTriggerEnter = true, unsubscribeTriggerExit = true, unsubscribeTriggerStay = true,
        unsubscribeWireConnected = true, unsubscribeWireDisconnected = true
    }

    -- Entity metatable
    -- ВАЖНО: LuaCSharp передаёт имя метода вместо self при вызове через __index.
    -- Поэтому используем t из замыкания __index(t, k), self игнорируем.
    local _mt = {}
    _mt.__index = function(t, k)
        local fn = _e[k]
        if fn == nil then return nil end

        local id = t._id

        -- Subscribe: оборачиваем Lua callback → регистрируем → передаём cbId в C#
        if _subscribe_methods[k] then
            return function(_, callback)
                local cbId = _register_callback(callback)
                fn(id, cbId)
                return cbId
            end
        end

        -- Unsubscribe: удаляем из Lua registry + вызываем C#
        if _unsubscribe_methods[k] then
            return function(_, cbId)
                _remove_callback(cbId)
                fn(id, cbId)
            end
        end

        -- unsubscribeAll
        if k == "unsubscribeAll" then
            return function(_)
                fn(id)
            end
        end

        -- Default: пробрасываем id
        return function(_, ...)
            return fn(id, ...)
        end
    end

    function Entity(id)
        if id == nil or id == 0 then
            return _noop
        end
        if type(id) ~= "number" then
            return _noop
        end
        return setmetatable({ _id = id }, _mt)
    end

    entity = {
        get = Entity,
        all = _e.all,
        find = _e.find
    }

    -- Collision/Trigger dispatch
    -- C# устанавливает глобалы __cb_id, __cb_other, __cb_self, __cb_nx, __cb_ny перед вызовом
    function __dispatch_collision()
        local cbId = __cb_id
        if cbId == nil then return end
        local fn = _callbacks[cbId]
        if type(fn) ~= "function" then return end

        local otherId = tonumber(__cb_other) or 0
        local selfId = tonumber(__cb_self) or 0
        local otherE = Entity(otherId)
        local selfE = Entity(selfId)
        __lua_safe_call(fn, "collision", otherE, selfE, __cb_nx, __cb_ny)
    end

    function __dispatch_trigger()
        local cbId = __cb_id
        if cbId == nil then return end
        local fn = _callbacks[cbId]
        if type(fn) ~= "function" then return end

        local otherId = tonumber(__cb_other) or 0
        local selfId = tonumber(__cb_self) or 0
        local otherE = Entity(otherId)
        local selfE = Entity(selfId)
        __lua_safe_call(fn, "trigger", otherE, selfE)
    end

    -- Wire connection/disconnection dispatch
    -- C# устанавливает: __cb_id, __cb_self, __cb_input_key, __cb_input_group,
    --   __cb_output_entity, __cb_output_key (только для connected)
    function __dispatch_wire_connected()
        local cbId = __cb_id
        if cbId == nil then return end
        local fn = _callbacks[cbId]
        if type(fn) ~= "function" then return end

        local selfId = tonumber(__cb_self) or 0
        local outputEntityId = tonumber(__cb_output_entity) or 0
        __lua_safe_call(fn, "wire_connected", selfId, __cb_input_key, outputEntityId, __cb_output_key)
    end

    function __dispatch_wire_disconnected()
        local cbId = __cb_id
        if cbId == nil then return end
        local fn = _callbacks[cbId]
        if type(fn) ~= "function" then return end

        local selfId = tonumber(__cb_self) or 0
        __lua_safe_call(fn, "wire_disconnected", selfId, __cb_input_key)
    end
end

-- Spawn callback dispatch
-- __current_env устанавливается C# перед каждым Execute/CallFunction —
-- указывает на env-таблицу текущего чипа, где определена OnSpawned.
function __dispatch_spawn(requestId, idsArray)
    local env = __current_env
    local fn = env and env.OnSpawned or OnSpawned
    if type(fn) ~= "function" then return end

    if type(idsArray) ~= "table" then
        __lua_safe_call(fn, "OnSpawned", requestId, nil)
        return
    end

    -- Стабильный обход: __lua_seq_len избегает падения "# limit must be a number"
    -- если idsArray попал с false-дырками или странной структурой.
    local count = __lua_seq_len(idsArray)
    if count <= 0 then
        __lua_safe_call(fn, "OnSpawned", requestId, nil)
        return
    end

    local entities = {}
    for i = 1, count do
        entities[i] = Entity(idsArray[i])
    end
    __lua_safe_call(fn, "OnSpawned", requestId, entities)
end

-- ============================================================
-- shared — межчиповая таблица (любые Lua типы)
-- ============================================================

shared = {}

-- shared.Save() / shared.Load() — реализованы через C# функции
-- __shared_save(table) и __shared_load(), регистрируются из C#.
-- Если C# функции не зарегистрированы — noop.

function shared.Save()
    if type(__shared_save) ~= "function" then return false end
    local ok, result = pcall(__shared_save, shared)
    return ok and result == 1
end

function shared.Load()
    if type(__shared_load) ~= "function" then return false end
    local ok, data = pcall(__shared_load)
    if not ok or type(data) ~= "table" then return false end
    -- deep merge: data → shared. pcall на pairs тоже — на случай странных таблиц от C#.
    local pcok, perr = pcall(function()
        for k, v in pairs(data) do
            if type(v) == "table" and type(shared[k]) == "table" then
                for kk, vv in pairs(v) do
                    shared[k][kk] = vv
                end
            else
                shared[k] = v
            end
        end
    end)
    if not pcok then
        local logger = error_log or warn or print
        if logger then logger("[shared.Load] merge failed: " .. tostring(perr)) end
        return false
    end
    return true
end

-- ============================================================
-- signal — event bus между чипами
-- ============================================================

signal = {}
local _sig_listeners = {}    -- channel -> { [1]=cb|false, [2]=cb|false, ..., count = N }
local _sig_deferred = {}     -- queue: { [1]={ch=, d=}, ..., count = N }
local _sig_deferred_count = 0

function signal.on(channel, callback)
    if type(channel) ~= "string" or type(callback) ~= "function" then
        return nil
    end
    local list = _sig_listeners[channel]
    if type(list) ~= "table" then
        list = { count = 0 }
        _sig_listeners[channel] = list
    end
    -- Явный счётчик, не #list — # на таблице с false-дырками в LuaCSharp может
    -- вернуть не-число и уронить "for limit must be a number".
    local id = (list.count or 0) + 1
    -- Захватываем env-name подписчика В МОМЕНТ ПОДПИСКИ. signal.on вызывается
    -- из OnInit/OnTick чипа-handler'а, тогда __current_env_name указывает на
    -- его env. Это имя нужно при emit'е, чтобы C#-API (spawn.* и т.п.) видели
    -- env handler'а, а не emitter'а — иначе spawn results'ы уходят к чужому
    -- чипу и OnSpawned никогда не дёргается у handler'а.
    list[id] = { cb = callback, env = __current_env_name }
    list.count = id
    return id
end

function signal.off(channel, subId)
    local list = _sig_listeners[channel]
    if type(list) ~= "table" or subId == nil then return end
    if list[subId] then
        list[subId] = false
    end
end

function signal.emit(channel, data)
    local list = _sig_listeners[channel]
    if type(list) ~= "table" then return end
    local n = list.count or 0
    if type(n) ~= "number" or n <= 0 then return end
    for i = 1, n do
        local entry = list[i]
        if type(entry) == "table" and type(entry.cb) == "function" then
            -- Push env handler'а на стек на время вызова → pop. Если env у
            -- entry нет (может произойти если signal.on вызван до первого
            -- SetCurrentEnv) — пропускаем push, callback всё равно отработает.
            local pushed = false
            if entry.env ~= nil and entry.env ~= ""
               and __push_current_env ~= nil then
                __push_current_env(entry.env)
                pushed = true
            end
            -- pcall: ошибка в одном подписчике не должна блокировать остальных.
            __lua_safe_call(entry.cb, "signal.emit:" .. channel, data)
            if pushed and __pop_current_env ~= nil then
                __pop_current_env()
            end
        end
    end
end

function signal.defer(channel, data)
    if type(channel) ~= "string" then return end
    _sig_deferred_count = _sig_deferred_count + 1
    _sig_deferred[_sig_deferred_count] = { ch = channel, d = data }
end

-- Вызывается из C# pre-execute hook каждый тик (перед OnTick каждого чипа)
function __flush_signals()
    if _sig_deferred_count <= 0 then return end
    -- Снимок очереди: новые defer'ы из callback'ов попадут в следующий тик.
    local batch = _sig_deferred
    local n = _sig_deferred_count
    _sig_deferred = {}
    _sig_deferred_count = 0
    for i = 1, n do
        local item = batch[i]
        if type(item) == "table" and type(item.ch) == "string" then
            signal.emit(item.ch, item.d)
        end
    end
end

-- custom modules
__modules = __modules or {}
function register_module(moduleName, module)
    if type(moduleName) ~= "string" or moduleName == "" then
        local logger = error_log or warn or print
        if logger then logger("[register_module] expected non-empty string name") end
        return false
    end
    if module == nil then
        local logger = error_log or warn or print
        if logger then logger("[register_module] module is nil for '" .. moduleName .. "'") end
        return false
    end
    __modules[moduleName] = module
    return true
end

function require(moduleName)
    if type(moduleName) ~= "string" then
        error("require: moduleName must be a string, got " .. type(moduleName))
    end
    local module = __modules[moduleName]
    if module == nil then
        error("Module not found: " .. moduleName)
    end
    return module
end
