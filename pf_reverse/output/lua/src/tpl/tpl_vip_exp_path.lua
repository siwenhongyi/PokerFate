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
{23,6,"shop_gifts",1001},
{24,6,"shop_gifts",1002},
{25,6,"shop_gifts",1003},
{26,6,"shop_gifts",1004},
{27,6,"shop_gifts",1006},
{28,6,"shop_gifts",2001},
{29,6,"shop_gifts",2002},
{30,6,"shop_gifts",2003},
{31,6,"shop_gifts",2004},
{32,6,"shop_gifts",2005},
{33,6,"quick_purchase",1},
{34,6,"quick_purchase",2},
{35,6,"quick_purchase",3},
{36,6,"quick_purchase",4},
{37,6,"quick_purchase",5},
{38,6,"quick_purchase",6},
{39,6,"quick_purchase",7},
{40,6,"quick_purchase",8},
{41,6,"icebreaker_pack",10001},
{42,6,"shop_activity_gifts",1001},
{43,6,"shop_activity_gifts",1002},
{44,6,"shop_activity_gifts",1003},
{45,6,"shop_activity_gifts",1004},
{46,6,"shop_activity_gifts",1005},
{47,6,"shop_activity_gifts",1006},
{48,6,"shop_activity_gifts",1007},
{49,6,"shop_activity_gifts",1008},
{50,6,"shop_activity_gifts",1009},
{51,6,"shop_activity_gifts",1010},
{52,6,"shop_activity_gifts",1011},
{53,6,"shop_activity_gifts",1012},
{54,6,"shop_activity_gifts",1013},
{55,6,"shop_activity_gifts",1014},
{56,6,"shop_activity_gifts",1015},
{57,6,"shop_activity_gifts",1016},
{58,6,"shop_activity_gifts",1017},
{59,6,"shop_activity_gifts",1018},
{60,6,"shop_activity_gifts",1019},
{61,6,"shop_activity_gifts",1020},
{62,6,"shop_activity_gifts",1021},
{63,6,"shop_activity_gifts",1022},
{64,6,"shop_activity_gifts",1023},
{65,6,"shop_activity_gifts",1024},
{66,6,"shop_activity_gifts",1025},
{67,6,"shop_activity_gifts",1026},
{68,6,"shop_activity_gifts",1027},
{69,6,"shop_activity_gifts",1028},
{70,6,"shop_activity_gifts",1029},
{71,6,"shop_activity_gifts",1030},
{72,5,"shop_passcard",1},
{73,5,"shop_dispatch",1001},
{74,5,"shop_dispatch",1002},
{75,5,"shop_dispatch",1003},
{76,5,"shop_dispatch",1004},
{77,5,"shop_dispatch",1005},
{78,5,"shop_dispatch",2002},
{79,5,"shop_dispatch",2003},
{80,5,"shop_dispatch",2004},
{81,5,"shop_dispatch",2005},
{82,5,"shop_dispatch",2006},
{83,5,"shop_dispatch",2007}
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