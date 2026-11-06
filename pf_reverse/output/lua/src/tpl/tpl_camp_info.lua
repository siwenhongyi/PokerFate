-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'quality_level','event_id','members_limit','base_reward_up','time_reduce','quality_up_cost1','quality_up_cost2',}
    local bodys = {
{1,1,1,0,0,0,20000},
{2,2,1,500,500,30000,60000},
{3,3,1,1200,1200,90000,180000},
{4,4,1,2000,2000,270000,540000},
{5,5,2,3000,3000,810000,1620000}
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

tpl_camp_info = P
tpl_camp_info_list = PL
function tpl_camp_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P