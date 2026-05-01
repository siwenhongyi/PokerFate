-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','start_time_1','end_time_1','start_time_2','end_time_2','participate_conditions','factor','effective_time',}
    local bodys = {
{1,"08:00:00","19:59:59","20:00:00","07:59:59",500000,15000,1774569600}
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

tpl_play_rebate_info = P
tpl_play_rebate_info_list = PL
function tpl_play_rebate_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P