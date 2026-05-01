-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','rewards','display_pic','jump',}
    local bodys = {
{1,1,{1,20600002,1,1,10200002,1,1,30300001,1,1,10100001,100000},"pic_1",101002}
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

tpl_first_recharge = P
tpl_first_recharge_list = PL
function tpl_first_recharge_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P