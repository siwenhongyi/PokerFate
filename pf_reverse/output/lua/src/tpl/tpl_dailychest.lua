-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','reward_point','rewards_list','sort',}
    local bodys = {
{1,30,{10100001,10000,30200001,1},1},
{2,60,{10100001,15000,30200002,1},2},
{3,100,{10100001,25000,30200002,1,30200001,1},3},
{4,150,{10100001,30000,30200002,1,30200001,2},4}
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

tpl_dailychest = P
tpl_dailychest_list = PL
function tpl_dailychest_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

