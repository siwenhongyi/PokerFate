-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','gameType','bg_color','sb','bb','ante','byin','recommend','fee','room_add','win_add','bond_add','firepower','quick_buy','level_limit','unlock_id',}
    local bodys = {
{1,10040101,1,1000,2000,600,20000,20000,600,1000,300,2,2,1,0,501},
{2,10040101,2,10000,20000,6000,200000,2000000,600,3000,300,10,10,2,5,502},
{3,10040101,3,50000,100000,30000,1000000,10000000,600,4000,300,25,20,4,11,503},
{4,10040101,4,250000,500000,150000,5000000,50000000,600,5000,300,35,30,7,20,504}
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

return P