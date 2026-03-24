-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','gameType','bg_color','sb','bb','min_byin','max_byin','recommend','fee','room_add','win_add','bond_add','firepower','quick_buy','level_limit','unlock_id',}
    local bodys = {
{1,10020101,1,500,1000,20000,200000,0,900,0,300,2,2,1,0,305},
{2,10020101,2,5000,10000,200000,2000000,500000,900,2000,300,8,8,2,6,301},
{3,10020101,3,25000,50000,1000000,10000000,25000000,900,3000,300,20,16,4,12,302},
{4,10020101,4,100000,200000,4000000,40000000,100000000,900,4000,300,30,24,7,19,303},
{5,10020101,5,500000,1000000,20000000,200000000,500000000,900,5000,300,40,32,8,27,304}
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

tpl_table_omaha = P
tpl_table_omaha_list = PL
function tpl_table_omaha_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

