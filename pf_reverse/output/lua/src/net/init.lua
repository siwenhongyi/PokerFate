local pb = require "pb"
local protoc = require "protoc"

require "net.net_game"
require "net.net_table"
require "net.net_pk"
require "net.net_props"
require "net.net_role"

local protos = {
    "CSGameDef.proto",
    "CSValue.proto",
    "CSGame.proto",
    "CSHoldem.proto",
    "CSLobJackpot.proto",
    "CSProps.proto",
    "CSRole.proto",
    "CSSideGame.proto",
}

for _, v in ipairs(protos) do
    local s = ResManager:GetProtoAsset("Proto/" .. v)
    protoc:load(s, v)
end

local messages = {}
for k, v in pairs(protoc.loaded) do
    for _, m in ipairs(v.message_type) do
        messages["pb." .. m.name] = m
    end
end

local msg_meta = {}
for k, m in pairs(messages) do
    local metaTb = {}
    if m.field then
        for _, f in ipairs(m.field) do
            if f.label == 1 then
                if f.type == 3 or f.type == 5 or f.type == 13 then
                    if f.default_value then
                        metaTb[f.name] = tonumber(f.default_value)
                    else
                        metaTb[f.name] = 0
                    end
                elseif f.type == 9 then
                    if f.default_value then
                        metaTb[f.name] = f.default_value
                    else
                        metaTb[f.name] = ""
                    end
                elseif f.type == 11 then
                    local subMsg = metaTb.___subMsg
                    if not subMsg then
                        subMsg = {}
                        metaTb.___subMsg = subMsg
                    end
                    subMsg[f.name] = string.sub(f.type_name, 2)
                end
            elseif f.label == 3 then    -- 列表
                local subList = metaTb.___subList
                if not subList then
                    subList = {}
                    metaTb.___subList = subList
                end
                if f.type_name then
                    subList[f.name] = string.sub(f.type_name, 2)
                else
                    subList[f.name] = f.name
                end
            end
        end
    end
    local mt = {metaTb = metaTb, __index = function(t, k)
        if metaTb[k] then
            return metaTb[k]
        end
        if metaTb.___subMsg and metaTb.___subMsg[k] then
            local value, _mt = {}, msg_meta[metaTb.___subMsg[k]]
            if _mt then
                setmetatable(value, _mt)
            end
            rawset(t, k, value)
            return value
        elseif metaTb.___subList and metaTb.___subList[k] then
            local value = {}
            rawset(t, k, value)
            return value
        end
        return nil
    end}
    msg_meta[k] = mt
end

function bee.protoDefault(name, msg)
    local _mt = msg_meta[name]
    if _mt then
        setmetatable(msg, _mt)
        if _mt.metaTb.___subMsg then
            for k, v in pairs(_mt.metaTb.___subMsg) do
                local field = rawget(msg, k)
                if field then
                    bee.protoDefault(v, field)
                end
            end
        end
        if _mt.metaTb.___subList then
            for k, v in pairs(_mt.metaTb.___subList) do
                if k ~= v then
                    local fileds = rawget(msg, k)
                    if fileds then
                        for _, v2 in ipairs(fileds) do
                            bee.protoDefault(v, v2)
                        end
                    end
                end
            end
        end
    end
end

-- local ItemClassInfo = {
-- 	item_name = "Item",
-- }

-- local bytes = pb.encode("pb.ItemClassInfo", ItemClassInfo)
-- print(pb.tohex(bytes))
-- local data2 = assert(pb.decode('pb.ItemClassInfo', bytes))
-- print("=== ggg", json.encode(data2))

-- local bytes = pb.encode("pb.OtherEnterRoomBRC", { 
--     user = {
--         uid = 111,
--         name = "abc",
--         icon_url = "ddd",
--     }, num = 2,
-- })
-- print(pb.tohex(bytes))
-- local data2 = assert(pb.decode('pb.OtherEnterRoomBRC', bytes))
