-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','gameType','bg_color','sb','bb','min_byin','max_byin','recommend','fee','room_add','win_add','bond_add','firepower','quick_buy','level_limit','unlock_id',}
    local bodys = {
{1,40010101,0,1,2,40,400,0,0,-200,200,1,0,0,0,nil}
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

tpl_table_poker_free = P
tpl_table_poker_free_list = PL
function tpl_table_poker_free_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P