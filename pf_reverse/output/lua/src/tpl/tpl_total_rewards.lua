-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','total_days','rewards',}
    local bodys = {
{1,2,{{30200003,1}}},
{2,4,{{30200004,1}}},
{3,6,{{10200002,1}}}
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

tpl_total_rewards = P
tpl_total_rewards_list = PL
function tpl_total_rewards_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

