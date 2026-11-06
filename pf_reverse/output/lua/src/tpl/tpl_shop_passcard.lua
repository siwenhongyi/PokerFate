-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','limit_type','limit_count','time_start','time_end','buy_id','icon',}
    local bodys = {
{1,22,"LAB_DISPATCH_90",4,1,1787796000,1795618800,2100008,"Icon[icon_dispatch_seasonpass_02]"}
}
    for _, v in pairs(bodys) do
        local m = {}
        for i, k in pairs(keys) do
            m[k] = v[i]
        end
        P[v[1]] = m
        PL[#PL+1] = m
    end
end
_initData()

tpl_shop_passcard = P
tpl_shop_passcard_list = PL
function tpl_shop_passcard_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P