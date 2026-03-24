-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','sub_page','props_type','tab_type','show_type','page_icon','red_name','show_num',}
    local bodys = {
{1,"LAB_BACKPACK_TAB_1",nil,{101,102,103,104,105,109,301,112,113},1,1,"Backpack[backpack_tab_icon_01]","BackPackProp",1},
{2,"LAB_BACKPACK_TAB_2",{15,16},nil,1,2,"Backpack[backpack_tab_icon_02]","BackPackGift",nil},
{3,"LAB_BACKPACK_TAB_3",nil,{107,108},1,1,"Backpack[backpack_tab_icon_03]","BackPackAwaken",nil},
{4,"LAB_BACKPACK_TAB_4",{20,5,6,14,7,17},nil,1,1,"Backpack[backpack_tab_icon_04]","BackpackDecorate",nil},
{5,"LAB_BACKPACK_TAB_5",nil,{205},2,1,nil,"BackpackCardBack",nil},
{6,"LAB_BACKPACK_TAB_6",nil,{206},2,1,nil,"BackpackTable",nil},
{7,"LAB_BACKPACK_TAB_7",{8,9},nil,2,2,nil,"BackpackMusic",nil},
{8,"LAB_BACKPACK_TAB_8",nil,{207},3,nil,nil,nil,nil},
{9,"LAB_BACKPACK_TAB_9",nil,{208},3,nil,nil,nil,nil},
{10,nil,nil,{201},0,nil,nil,nil,nil},
{11,nil,nil,{202},0,nil,nil,nil,nil},
{12,nil,nil,{203},0,nil,nil,nil,nil},
{13,nil,nil,{204},0,nil,nil,nil,nil},
{14,"LAB_BACKPACK_TAB_10",nil,{209},2,1,nil,"BackpackScene",nil},
{15,"LAB_BACKPACK_TAB_11",nil,{303,302},3,nil,nil,nil,nil},
{16,"LAB_BACKPACK_TAB_2",nil,{106},3,nil,nil,nil,nil},
{17,"LAB_BACKPACK_TAB_12",{18,19},nil,2,2,nil,"BackpackEff",nil},
{18,"LAB_BACKPACK_TAB_13",nil,{210},3,nil,nil,nil,nil},
{19,"LAB_BACKPACK_TAB_14",nil,{211},3,nil,nil,nil,nil},
{20,"LAB_BACKPACK_TAB_15",nil,{212},2,1,nil,"BackpackCardFace",nil}
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

tpl_backpack = P
tpl_backpack_list = PL
function tpl_backpack_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

