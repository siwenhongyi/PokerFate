-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','battle_pass_id','level_type','name','icon','time_start','time_end','discount','limit_type','limit_count','buy_id','rewards','rewards2','rewards_exp',}
    local bodys = {
{100101,25,1001,1,"TAB_BATTLE_PASS_NAME_3","Icon[icon_battle_pass_2]",1794769200,1800212400,nil,4,1,2500001,{10200001,150,10100001,1500000},nil,nil},
{100102,25,1001,2,"TAB_BATTLE_PASS_NAME_4","Icon[icon_battle_pass_3]",1794769200,1800212400,3236,4,1,2500002,{10200001,150,10100001,1500000},{20407001,1,10200001,550,10100001,5500000},{11000061,10000}},
{100103,25,1001,3,"TAB_BATTLE_PASS_NAME_4","Icon[icon_battle_pass_3]",1794769200,1800212400,nil,4,1,2500003,nil,{20407001,1,10200001,550,10100001,5500000},{11000061,10000}}
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

tpl_shop_battle_pass = P
tpl_shop_battle_pass_list = PL
function tpl_shop_battle_pass_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P