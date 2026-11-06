-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','gameType','bg_color','sb','bb','min_byin','max_byin','recommend','fee','room_add','win_add','bond_add','firepower','quick_buy','level_limit','unlock_id',}
    local bodys = {
{1,10010101,1,500,1000,20000,200000,20000,900,0,300,2,2,1,0,201},
{2,10010101,1,1000,2000,40000,400000,1000000,900,500,300,3,3,1,2,206},
{3,10010101,1,2500,5000,100000,1000000,2500000,900,1000,300,5,5,2,4,207},
{4,10010101,2,5000,10000,200000,2000000,5000000,900,2000,300,8,8,2,6,202},
{5,10010101,2,10000,20000,400000,4000000,10000000,900,2500,300,12,12,3,9,208},
{6,10010101,3,25000,50000,1000000,10000000,25000000,900,3000,300,20,16,4,14,203},
{7,10010101,3,50000,100000,2000000,20000000,50000000,900,3500,300,25,20,5,17,209},
{8,10010101,4,100000,200000,4000000,40000000,100000000,900,4000,300,30,24,7,23,204}
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

tpl_table_poker = P
tpl_table_poker_list = PL
function tpl_table_poker_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P