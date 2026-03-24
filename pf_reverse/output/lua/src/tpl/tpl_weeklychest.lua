-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','reward_point','rewards_list','sort',}
    local bodys = {
{1,50,{10100001,50000,30200002,1},1},
{2,100,{10100001,60000,30200002,1,30200001,1},2},
{3,150,{10100001,70000,30200003,1,30200002,1},3},
{4,200,{10100001,80000,30200003,1,30200002,1,30200001,1},4},
{5,250,{10100001,100000,30200002,1,30200003,1,10200002,1},5}
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

tpl_weeklychest = P
tpl_weeklychest_list = PL
function tpl_weeklychest_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

