-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','time_start','time_end','skin','cost','rewards','exp_item','mail','white_list_start','white_list_end',}
    local bodys = {
{1001,"TAB_BATTLE_PASS_NAME_1",1794769200,1800212400,100507,{10200001,30},{11000061,1000},11000061,4003,1793349055,1794765600}
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

tpl_battle_pass_info = P
tpl_battle_pass_info_list = PL
function tpl_battle_pass_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P