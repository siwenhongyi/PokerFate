-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','page_icon','page_type','sub_page','currency_bar','shop_type','order','is_hide','shop_bg','unselected_color',}
    local bodys = {
{1,"LAB_SHOP_NAME_1","Shop[shop_tab_icon_01]",1,{101,102,103},nil,0,1,nil,nil,nil},
{2,"LAB_SHOP_NAME_2","Shop[shop_tab_icon_02]",1,nil,{10300001,105002},3,2,nil,"BackGround/bg_fullscreen_01.png",nil},
{3,"LAB_SHOP_NAME_3","Shop[shop_tab_icon_03]",1,{301,302},nil,0,3,nil,nil,nil},
{4,"LAB_SHOP_NAME_4","Shop[shop_tab_icon_05]",1,{401,402,403},nil,0,4,nil,nil,nil},
{5,"LAB_SHOP_NAME_5","Shop[shop_tab_icon_06]",1,{501,502,503},nil,0,5,nil,nil,nil},
{6,"LAB_SHOP_NAME_6","Shop[shop_tab_icon_04]",1,{601,602,603,604,605},nil,0,4,nil,nil,nil},
{101,"LAB_SHOP_NAME_SUB_1",nil,2,nil,{10100001,105003,10200001,105001,10200002,103001},1,1,nil,"BackGround/shop_topup_bg.png",{184,187,192}},
{102,"LAB_SHOP_NAME_SUB_2",nil,2,nil,{10100001,0,10200001,0},2,3,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{103,"LAB_SHOP_NAME_SUB_13",nil,2,nil,nil,15,2,nil,"BackGround/shop_newcomer_bg_01.png",{169,169,169}},
{301,"LAB_SHOP_NAME_SUB_3",nil,2,nil,{10200002,0},4,1,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{302,"LAB_SHOP_NAME_SUB_4",nil,2,nil,nil,5,2,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{401,"LAB_SHOP_NAME_SUB_5",nil,2,nil,{10400001,2001},6,1,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{402,"LAB_SHOP_NAME_SUB_14",nil,2,nil,{10500001,6002},16,2,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{403,"LAB_SHOP_NAME_SUB_15",nil,2,nil,{10400002,4010},17,3,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{501,"LAB_SHOP_NAME_SUB_6",nil,2,nil,{10200001,0},7,1,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{502,"LAB_SHOP_NAME_SUB_7",nil,2,nil,{10300001,0},8,2,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{503,"LAB_SHOP_NAME_SUB_8",nil,2,nil,{10100001,0},9,3,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{601,"LAB_SHOP_NAME_SUB_9",nil,2,nil,{10300001,105002},11,1,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{602,"LAB_SHOP_NAME_SUB_10",nil,2,nil,{10300001,105002},12,2,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{603,"LAB_SHOP_NAME_SUB_11",nil,2,nil,{10300001,105002},13,3,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{604,"LAB_SHOP_NAME_SUB_12",nil,2,nil,{10300001,105002},14,4,nil,"BackGround/bg_shop_01.png",{161,151,119}},
{605,"LAB_SHOP_NAME_SUB_16",nil,2,nil,{10300001,105002},18,5,nil,"BackGround/bg_shop_01.png",{161,151,119}}
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

tpl_shop_page = P
tpl_shop_page_list = PL
function tpl_shop_page_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

