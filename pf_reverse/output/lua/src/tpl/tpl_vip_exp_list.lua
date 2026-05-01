-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','type',}
    local bodys = {
{1,"LAB_PROPS_NAME_102_1",2},
{2,"LAB_PROPS_NAME_103_1",2},
{3,"LAB_PROPS_NAME_101_1",2},
{4,"LAB_PROPS_NAME_111_3",2},
{5,"LAB_VIP_TEXT_20",1}
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

tpl_vip_exp_list = P
tpl_vip_exp_list_list = PL
function tpl_vip_exp_list_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P