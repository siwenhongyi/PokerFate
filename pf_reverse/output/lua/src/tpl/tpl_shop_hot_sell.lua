-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','currency_bar','shop_type','shop_bg','gifts','activity_id','tag_image','tag_tips','order','time_limited','shop_skin_id',}
    local bodys = {
{1,"LAB_PROPS_NAME_111_3",{10100001,0,10200001,0},2,"BackGround/bg_shop_01.png",nil,nil,"Shop[shop_tab_monthlycard]","shop_tag_bestoffer",1001,nil,nil},
{2,"LAB_PROPS_NAME_102_1",{10200001,0},7,"BackGround/Shop/bg_shop_crystal_02.png",nil,nil,"Shop[shop_tab_colorcrystal]","shop_tag_welfare",4001,nil,nil},
{3,"LAB_SHOP_NAME_SUB_17",nil,19,"BackGround/bg_shop_bestseller_01.png",nil,10006,"Shop[shop_tab_summer]",nil,5001,1,nil},
{4,"LAB_SHOP_NAME_SUB_1",{10100001,105003,10200001,105001,10200002,103001},1,"BackGround/shop_topup_bg.png",nil,nil,"Shop[shop_tab_recharge]",nil,6001,nil,nil},
{5,"TAB_ICEBREAKER_PACK_2",nil,15,"BackGround/shop_newcomer_bg_01.png",nil,nil,"Shop[shop_tab_newcomer]",nil,7001,nil,nil},
{10001,"LAB_SHOP_NAME_SUB_18",{10300001,105002},20,"BackGround/Shop/shop_sayaka_bg.png",{1001},nil,"Shop[shop_tab_sayaka]","shop_tag_hot",2001,1,nil},
{20001,"LAB_SHOP_NAME_SUB_17",nil,19,"BackGround/bg_shop_bestseller_02.png",nil,10007,"Shop[shop_tab_matsuri]","shop_tag_hot",5002,1,nil},
{20002,"LAB_SHOP_NAME_SUB_17",nil,19,"BackGround/bg_shop_bestseller_03.png",nil,10008,"Shop[shop_tab_racing]","shop_tag_hot",5003,1,nil},
{20003,"LAB_SHOP_NAME_SUB_17",nil,19,"BackGround/bg_shop_bestseller_04.png",nil,10009,"Shop[shop_tab_fantasy]","shop_tag_hot",5004,1,nil},
{30001,"LAB_SHOP_NAME_SUB_19",nil,3,"BackGround/Fullscreen/bg_fullscreen_01.png",nil,nil,"Shop[shop_tab_costume_hotspring]","shop_tag_tl",3001,1,{1,2,3,4}},
{30002,"LAB_SHOP_NAME_SUB_19",nil,3,"BackGround/Fullscreen/bg_fullscreen_01.png",nil,nil,"Shop[shop_tab_costume_sports]","shop_tag_tl",3002,1,{14,15,16}},
{30003,"LAB_SHOP_NAME_SUB_19",nil,3,"BackGround/Fullscreen/bg_fullscreen_01.png",nil,nil,"Shop[shop_tab_costume_school]","shop_tag_tl",3003,1,{8,9,10}},
{30004,"LAB_SHOP_NAME_SUB_19",nil,3,"BackGround/Fullscreen/bg_fullscreen_01.png",nil,nil,"Shop[shop_tab_costume_bunnygirl]","shop_tag_tl",3004,1,{11,12,13}},
{30005,"LAB_SHOP_NAME_SUB_19",nil,3,"BackGround/Fullscreen/bg_fullscreen_01.png",nil,nil,"Shop[shop_tab_costume_galaseason]","shop_tag_tl",3005,1,{5,6,7}},
{30006,"LAB_SHOP_NAME_SUB_19",nil,3,"BackGround/Fullscreen/bg_fullscreen_01.png",nil,nil,"Shop[shop_tab_costume_sayaka]","shop_tag_tl",3006,1,{17,18,19}},
{30007,"LAB_SHOP_NAME_SUB_19",nil,3,"BackGround/Fullscreen/bg_fullscreen_01.png",nil,nil,"Shop[shop_tab_costume_matsuri]","shop_tag_tl",3007,1,{21,22,23}}
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

tpl_shop_hot_sell = P
tpl_shop_hot_sell_list = PL
function tpl_shop_hot_sell_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P