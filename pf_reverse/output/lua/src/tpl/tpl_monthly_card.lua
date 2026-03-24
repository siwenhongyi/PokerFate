-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','icon','activate_rewards','days','exc_title','exc_frame','buy_id',}
    local bodys = {
{1,2,"LAB_MONTHLY_CARD_30","Icon[icon_11100003]",{10200001,100,10100001,850000},30,{20400002,1},{20200002,1},200001},
{2,2,"LAB_MONTHLY_CARD_31","Icon[icon_11100003]",{10200001,400,10100001,3175000},90,{20400002,1},{20200002,1},200002},
{3,2,"LAB_MONTHLY_CARD_32","Icon[icon_11100003]",{10200001,900,10100001,6975000},180,{20400002,1},{20200002,1},200003}
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

tpl_monthly_card = P
tpl_monthly_card_list = PL
function tpl_monthly_card_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

