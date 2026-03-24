-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','gameType','bg_color','sb','bb','ante','byin','recommend','fee','room_add','win_add','bond_add','firepower','quick_buy',}
    local bodys = {
{1,10040101,2,500,1000,3000,20000,400000,700,1000,300,2,2,1},
{2,10040101,3,5000,10000,30000,200000,4000000,700,3000,300,10,10,2},
{3,10040101,4,50000,100000,300000,2000000,40000000,700,4000,300,30,24,4},
{4,10040101,5,500000,1000000,3000000,20000000,400000000,700,5000,300,45,36,8}
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

tpl_table_poker_allin = P
tpl_table_poker_allin_list = PL
function tpl_table_poker_allin_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

