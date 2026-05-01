-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','balance','chips','push_balance','quick_buy',}
    local bodys = {
{1,0,{1000,2000,4000,8000,16000,32000,64000,128000},30000,1},
{2,1000000,{1000,2000,4000,8000,16000,32000,64000,128000},1000000,2},
{3,10000000,{10000,20000,40000,80000,160000,320000,640000,1280000},10000000,5},
{4,100000000,{100000,200000,400000,800000,1600000,3200000,6400000,12800000},100000000,8},
{5,1000000000,{1000000,2000000,4000000,8000000,16000000,32000000,64000000,128000000},300000000,8}
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

tpl_pinball = P
tpl_pinball_list = PL
function tpl_pinball_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P