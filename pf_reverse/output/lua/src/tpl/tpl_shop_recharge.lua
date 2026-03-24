-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','name_c','icon','props','first_double','buy_id','index','daily_rewards','extra',}
    local bodys = {
{1001,7,"TAB_RECHARGE_NAME_1_1","LAB_SHOP_RECHARGE_3","Icon[icon_roulette_crystals_1]",{10200001,200},1,700001,1,nil,nil},
{1002,7,"TAB_RECHARGE_NAME_1_2","LAB_SHOP_RECHARGE_3","Icon[icon_roulette_crystals_2]",{10200001,500},1,700002,2,nil,nil},
{1003,7,"TAB_RECHARGE_NAME_1_3","LAB_SHOP_RECHARGE_3","Icon[icon_roulette_crystals_3]",{10200001,1000},1,700003,3,nil,nil},
{1004,7,"TAB_RECHARGE_NAME_1_4","LAB_SHOP_RECHARGE_3","Icon[icon_roulette_crystals_4]",{10200001,1600},1,700004,4,nil,nil},
{1005,7,"TAB_RECHARGE_NAME_1_5","LAB_SHOP_RECHARGE_3","Icon[icon_roulette_crystals_5]",{10200001,2500},1,700005,5,nil,nil},
{1006,7,"TAB_RECHARGE_NAME_1_6","LAB_SHOP_RECHARGE_3","Icon[icon_roulette_crystals_6]",{10200001,5000},1,700006,6,nil,nil},
{2001,8,"TAB_RECHARGE_NAME_2_1","LAB_SHOP_RECHARGE_4","Icon[icon_shop_fashioncredit_1]",{10300001,100},0,800001,1,nil,nil},
{2002,8,"TAB_RECHARGE_NAME_2_2","LAB_SHOP_RECHARGE_4","Icon[icon_shop_fashioncredit_2]",{10300001,250},0,800002,2,nil,nil},
{2003,8,"TAB_RECHARGE_NAME_2_3","LAB_SHOP_RECHARGE_4","Icon[icon_shop_fashioncredit_3]",{10300001,500},0,800003,3,nil,nil},
{2004,8,"TAB_RECHARGE_NAME_2_4","LAB_SHOP_RECHARGE_4","Icon[icon_shop_fashioncredit_4]",{10300001,800},0,800004,4,nil,nil},
{2005,8,"TAB_RECHARGE_NAME_2_5","LAB_SHOP_RECHARGE_4","Icon[icon_shop_fashioncredit_5]",{10300001,1250},0,800005,5,nil,nil},
{2006,8,"TAB_RECHARGE_NAME_2_6","LAB_SHOP_RECHARGE_4","Icon[icon_shop_fashioncredit_6]",{10300001,2500},0,800006,6,nil,nil},
{3001,9,"TAB_RECHARGE_NAME_3_1","LAB_SHOP_RECHARGE_5","Icon[icon_chip_1]",{10100001,1000},0,0,1,1,nil},
{3002,9,"TAB_RECHARGE_NAME_3_2","LAB_SHOP_RECHARGE_5","Icon[icon_chip_2]",{10100001,500000},0,900001,2,nil,nil},
{3003,9,"TAB_RECHARGE_NAME_3_3","LAB_SHOP_RECHARGE_5","Icon[icon_chip_3]",{10100001,2000000},0,900002,3,nil,nil},
{3004,9,"TAB_RECHARGE_NAME_3_4","LAB_SHOP_RECHARGE_5","Icon[icon_chip_4]",{10100001,5000000},0,900003,4,nil,nil},
{3005,9,"TAB_RECHARGE_NAME_3_5","LAB_SHOP_RECHARGE_5","Icon[icon_chip_5]",{10100001,10000000},0,900004,5,nil,nil},
{3006,9,"TAB_RECHARGE_NAME_3_6","LAB_SHOP_RECHARGE_5","Icon[icon_chip_6]",{10100001,20000000},0,900005,6,nil,nil},
{3007,9,"TAB_RECHARGE_NAME_3_7","LAB_SHOP_RECHARGE_5","Icon[icon_chip_7]",{10100001,50000000},0,900006,7,nil,nil},
{3008,9,"TAB_RECHARGE_NAME_3_8","LAB_SHOP_RECHARGE_5","Icon[icon_chip_8]",{10100001,100000000},0,900007,8,nil,nil}
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

tpl_shop_recharge = P
tpl_shop_recharge_list = PL
function tpl_shop_recharge_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

