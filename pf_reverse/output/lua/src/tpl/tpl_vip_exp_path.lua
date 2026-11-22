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
{23,7,"shop_gifts",1001},
{24,7,"shop_gifts",1002},
{25,7,"shop_gifts",1003},
{26,7,"shop_gifts",1004},
{27,7,"shop_gifts",1006},
{28,7,"shop_gifts",2001},
{29,7,"shop_gifts",2002},
{30,7,"shop_gifts",2003},
{31,7,"shop_gifts",2004},
{32,7,"shop_gifts",2005},
{33,3,"quick_purchase",1},
{34,3,"quick_purchase",2},
{35,3,"quick_purchase",3},
{36,3,"quick_purchase",4},
{37,3,"quick_purchase",5},
{38,3,"quick_purchase",6},
{39,3,"quick_purchase",7},
{40,3,"quick_purchase",8},
{41,3,"quick_purchase",2001},
{42,3,"quick_purchase",2002},
{43,3,"quick_purchase",2003},
{44,3,"quick_purchase",2004},
{45,3,"quick_purchase",2005},
{46,3,"quick_purchase",2006},
{47,3,"quick_purchase",2007},
{48,7,"icebreaker_pack",10001},
{49,7,"shop_activity_gifts",1051},
{50,7,"shop_activity_gifts",1052},
{51,7,"shop_activity_gifts",1053},
{52,7,"shop_activity_gifts",1054},
{53,7,"shop_activity_gifts",1055},
{54,7,"shop_activity_gifts",1056},
{55,7,"shop_activity_gifts",1057},
{56,7,"shop_activity_gifts",1058},
{57,7,"shop_activity_gifts",1059},
{58,7,"shop_activity_gifts",1060},
{59,7,"shop_activity_gifts",1061},
{60,7,"shop_activity_gifts",1062},
{61,7,"shop_activity_gifts",1063},
{62,7,"shop_activity_gifts",1064},
{63,7,"shop_activity_gifts",1065},
{64,7,"shop_activity_gifts",1066},
{65,7,"shop_activity_gifts",1067},
{66,7,"shop_activity_gifts",1068},
{67,7,"shop_activity_gifts",1069},
{68,7,"shop_activity_gifts",1070},
{69,5,"shop_passcard",1},
{70,5,"shop_dispatch",1001},
{71,5,"shop_dispatch",1002},
{72,5,"shop_dispatch",1003},
{73,5,"shop_dispatch",1004},
{74,5,"shop_dispatch",1005},
{75,5,"shop_dispatch",2002},
{76,5,"shop_dispatch",2003},
{77,5,"shop_dispatch",2004},
{78,5,"shop_dispatch",2005},
{79,5,"shop_dispatch",2006},
{80,5,"shop_dispatch",2007},
{81,6,"shop_battle_pass",100101},
{82,6,"shop_battle_pass",100102}
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