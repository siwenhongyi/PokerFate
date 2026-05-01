-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','code',}
    local bodys = {
{1,"USD"},
{2,"JPY"},
{3,"HKD"},
{4,"TWD"}
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

tpl_shop_cur_type = P
tpl_shop_cur_type_list = PL
function tpl_shop_cur_type_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P