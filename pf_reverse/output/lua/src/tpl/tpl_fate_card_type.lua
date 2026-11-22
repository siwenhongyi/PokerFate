-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','min',}
    local bodys = {
{1,"LAB_HIGH_CARD",1},
{2,"LAB_ONE_PAIR",2},
{3,"LAB_TWO_PAIRS",4},
{4,"LAB_THREE_KIND",3},
{5,"LAB_STRAIGHT",5},
{6,"LAB_FLUSH",5},
{7,"LAB_FULL_HOUSE",5},
{8,"LAB_QUADS",4},
{9,"LAB_STRAIGHT_FLUSH",5},
{10,"LAB_ROYAL_FLUSH",5}
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

tpl_fate_card_type = P
tpl_fate_card_type_list = PL
function tpl_fate_card_type_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P