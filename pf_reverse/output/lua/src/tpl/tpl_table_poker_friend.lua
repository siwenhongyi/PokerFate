-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','gameType','sb','bb','min_byin','max_byin','recommend_min_byin','recommend_max_byin',}
    local bodys = {
{1,20010103,1,2,40,400,80,200},
{2,20010103,5,10,200,2000,400,1000},
{3,20010103,25,50,1000,10000,2000,5000},
{4,20010103,100,200,4000,40000,8000,20000},
{5,20010103,500,1000,20000,200000,40000,100000}
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

tpl_table_poker_friend = P
tpl_table_poker_friend_list = PL
function tpl_table_poker_friend_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

