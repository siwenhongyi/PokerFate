-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','day','rewards',}
    local bodys = {
{1,1,{{10100001,30000,30200001,1}}},
{2,2,{{10100001,30000,30200001,1}}},
{3,3,{{10100001,30000,30200002,1}}},
{4,4,{{10100001,30000,30200001,1}}},
{5,5,{{10100001,30000,30200001,1}}},
{6,6,{{10100001,30000,30200002,1}}},
{7,7,{{10100001,30000,30200003,1}}}
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

tpl_daily_rewards = P
tpl_daily_rewards_list = PL
function tpl_daily_rewards_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P