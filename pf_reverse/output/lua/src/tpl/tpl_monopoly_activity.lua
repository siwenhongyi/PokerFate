-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','time_start','time_end','activity_item','mail','mail_tip','mail_rewards','task','white_list_start','white_list_end',}
    local bodys = {
{30001,"LAB_MONOPOLY_ACTIVITY1_NAME_1",1794448800,1795633200,10420002,4001,4002,8001,{1001},1792635294,1794448680}
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

tpl_monopoly_activity = P
tpl_monopoly_activity_list = PL
function tpl_monopoly_activity_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P