-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','rewards_group','point','rewards',}
    local bodys = {
{1000901,10009,50,{11300001,1}},
{1000902,10009,100,{10200002,1}},
{1000903,10009,150,{20502010,1}},
{1000904,10009,200,{10100001,100000}},
{1000905,10009,250,{20202020,1}},
{1000906,10009,300,{30200004,1}},
{1000907,10009,400,{20402009,1}}
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

tpl_theme_points_rewards = P
tpl_theme_points_rewards_list = PL
function tpl_theme_points_rewards_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P