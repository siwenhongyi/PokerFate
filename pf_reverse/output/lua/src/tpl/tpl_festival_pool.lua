-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','rewards','weight_pay','weight','weight_guest','limit','is_publicity','rarity','publicity_pr','index',}
    local bodys = {
{1,{10100001,20000},7354,9081,9887,nil,nil,nil,nil,10},
{2,{10100001,100000},1000,400,50,nil,nil,nil,nil,9},
{3,{10100001,1000000},200,40,5,200,1,1,"1.00",8},
{4,{10100001,10000000},20,4,0,20,1,2,"0.15",7},
{5,{10100001,100000000},3,0,0,2,1,3,"0.02",6},
{6,{10200001,10},900,320,40,nil,nil,nil,nil,5},
{7,{10200001,30},300,107,13,nil,nil,nil,nil,4},
{8,{10200002,1},200,44,5,200,1,1,"1.00",3},
{9,{10200002,10},20,4,0,20,1,2,"0.15",2},
{10,{10200002,62},3,0,0,2,1,3,"0.02",1}
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

tpl_festival_pool = P
tpl_festival_pool_list = PL
function tpl_festival_pool_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

