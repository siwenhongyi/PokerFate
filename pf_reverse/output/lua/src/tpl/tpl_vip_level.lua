-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','upgrade_exp','icon','title','rewards','daily_gift_counts','friend_limit','blacklist_limit','sheet_limit','vip_add','exp_hands','friendship_hands','plan_limit','exp_tournament','friendship_tournament','recent_history_limit',}
    local bodys = {
{0,0,"Shop[shop_vip_icon_lv_00]",nil,{10100001,10000,30300005,1},5,20,20,20,0,50,50,5,10,10,100},
{1,50,"Shop[shop_vip_icon_lv_01]",20401001,{10100001,100000,10200001,10,30300004,2},6,25,25,25,100,70,70,6,14,14,125},
{2,300,"Shop[shop_vip_icon_lv_02]",20401002,{10100001,200000,10200001,20,30300003,1,30300004,1},7,30,30,30,250,90,90,8,18,18,150},
{3,1500,"Shop[shop_vip_icon_lv_03]",20401003,{10100001,300000,10200001,30,30300003,2},8,40,40,40,400,120,120,10,24,24,200},
{4,6000,"Shop[shop_vip_icon_lv_04]",20401004,{10100001,500000,10200001,50,30300002,1,30300003,1},10,50,50,50,600,150,150,13,30,30,250},
{5,20000,"Shop[shop_vip_icon_lv_05]",20401005,{10100001,700000,10200002,2,30300002,2},12,70,70,70,800,200,200,16,40,40,350},
{6,50000,"Shop[shop_vip_icon_lv_06]",20401006,{10100001,1000000,10200002,4,30300002,4},14,90,90,90,1000,250,250,20,50,50,450},
{7,100000,"Shop[shop_vip_icon_lv_07]",20401007,{10100001,2000000,10200002,6,30300002,6},17,120,120,120,1250,300,300,25,60,60,600}
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

tpl_vip_level = P
tpl_vip_level_list = PL
function tpl_vip_level_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P