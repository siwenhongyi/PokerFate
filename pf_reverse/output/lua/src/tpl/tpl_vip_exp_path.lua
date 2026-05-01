-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','group','shop','product_id',}
    local bodys = {
{1,1,"shop_recharge",1001},
{2,1,"shop_recharge",1002},
{3,1,"shop_recharge",1003},
{4,1,"shop_recharge",1004},
{5,1,"shop_recharge",1005},
{6,1,"shop_recharge",1006},
{7,2,"shop_recharge",2001},
{8,2,"shop_recharge",2002},
{9,2,"shop_recharge",2003},
{10,2,"shop_recharge",2004},
{11,2,"shop_recharge",2005},
{12,2,"shop_recharge",2006},
{13,3,"shop_recharge",3002},
{14,3,"shop_recharge",3003},
{15,3,"shop_recharge",3004},
{16,3,"shop_recharge",3005},
{17,3,"shop_recharge",3006},
{18,3,"shop_recharge",3007},
{19,3,"shop_recharge",3008},
{20,4,"monthly_card",1},
{21,4,"monthly_card",2},
{22,4,"monthly_card",3},
{23,5,"shop_gifts",1001},
{24,5,"shop_gifts",1002},
{25,5,"shop_gifts",1003},
{26,5,"shop_gifts",1004},
{27,5,"shop_gifts",1006},
{28,5,"shop_gifts",2001},
{29,5,"shop_gifts",2002},
{30,5,"shop_gifts",2003},
{31,5,"shop_gifts",2004},
{32,5,"shop_gifts",2005},
{33,5,"quick_purchase",1},
{34,5,"quick_purchase",2},
{35,5,"quick_purchase",3},
{36,5,"quick_purchase",4},
{37,5,"quick_purchase",6},
{38,5,"quick_purchase",7},
{39,5,"quick_purchase",8},
{40,5,"icebreaker_pack",10001},
{41,5,"shop_activity_gifts",1001},
{42,5,"shop_activity_gifts",1002},
{43,5,"shop_activity_gifts",1003},
{44,5,"shop_activity_gifts",1004},
{45,5,"shop_activity_gifts",1005},
{46,5,"shop_activity_gifts",1006},
{47,5,"shop_activity_gifts",1007},
{48,5,"shop_activity_gifts",1008},
{49,5,"shop_activity_gifts",1009},
{50,5,"shop_activity_gifts",1010},
{51,5,"shop_activity_gifts",1011},
{52,5,"shop_activity_gifts",1012},
{53,5,"shop_activity_gifts",1013}
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

tpl_vip_exp_path = P
tpl_vip_exp_path_list = PL
function tpl_vip_exp_path_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P