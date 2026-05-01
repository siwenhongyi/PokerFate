-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','icon','props','buy_id','extra','discount',}
    local bodys = {
{1,10,"TAB_QUICK_PURCHASE_1","Icon[icon_quick_purchase_01]",{10100001,1000000},1000001,nil,200},
{2,10,"TAB_QUICK_PURCHASE_2","Icon[icon_quick_purchase_02]",{10100001,3000000},1000002,nil,240},
{3,10,"TAB_QUICK_PURCHASE_3","Icon[icon_quick_purchase_03]",{10100001,6000000},1000003,nil,240},
{4,10,"TAB_QUICK_PURCHASE_4","Icon[icon_quick_purchase_04]",{10100001,14000000},1000004,nil,280},
{5,10,"TAB_QUICK_PURCHASE_5","Icon[icon_quick_purchase_05]",{10100001,24000000},1000005,nil,320},
{6,10,"TAB_QUICK_PURCHASE_6","Icon[icon_quick_purchase_06]",{10100001,35000000},1000006,nil,350},
{7,10,"TAB_QUICK_PURCHASE_7","Icon[icon_quick_purchase_07]",{10100001,50000000},1000007,nil,400},
{8,10,"TAB_QUICK_PURCHASE_8","Icon[icon_quick_purchase_08]",{10100001,110000000},1000008,nil,440}
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

tpl_quick_purchase = P
tpl_quick_purchase_list = PL
function tpl_quick_purchase_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P