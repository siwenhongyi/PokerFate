-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','image','prefab','up','up_character','up_character_offset','character','des',}
    local bodys = {
{10001,"LAB_GACHA_TAG_1","gacha_list_bg_03","GachaCenter10001",nil,nil,nil,{1008,1003},"LAB_GACHA_DES_2"},
{10002,"LAB_GACHA_TAG_2","gacha_list_bg_01","GachaCenter10002",nil,nil,nil,{1005,1004,1002,1007,1006},"LAB_GACHA_DES_1"},
{10003,"LAB_GACHA_TAG_3","gacha_list_bg_09","GachaCenter10003",nil,nil,nil,{1009,1010},"LAB_GACHA_DES_3"},
{10004,"LAB_GACHA_TAG_4","gacha_list_bg_12","GachaCenter10004",nil,nil,nil,{1013,1012},"LAB_GACHA_DES_4"},
{10005,"LAB_GACHA_TAG_5","gacha_list_bg_14","GachaCenter10005",nil,nil,nil,{1014},"LAB_GACHA_DES_5"},
{20002,"LAB_GACHA_TAG_1002","gacha_list_bg_02","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1002},{72,10,1},{1002},"LAB_GACHA_DES_1"},
{20003,"LAB_GACHA_TAG_1003","gacha_list_bg_03","GachaCenter10001_up","Gacha[gacha_tab_up_frame_20]",{1003},{148,-42,1},{1003},"LAB_GACHA_DES_2"},
{20004,"LAB_GACHA_TAG_1004","gacha_list_bg_04","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1004},{148,0,1},{1004},"LAB_GACHA_DES_1"},
{20005,"LAB_GACHA_TAG_1005","gacha_list_bg_05","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1005},{118,23,1},{1005},"LAB_GACHA_DES_1"},
{20006,"LAB_GACHA_TAG_1006","gacha_list_bg_06","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1006},{120,100,1},{1006},"LAB_GACHA_DES_1"},
{20007,"LAB_GACHA_TAG_1007","gacha_list_bg_07","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1007},{120,-20,1},{1007},"LAB_GACHA_DES_1"},
{20008,"LAB_GACHA_TAG_1008","gacha_list_bg_08","GachaCenter10001_up","Gacha[gacha_tab_up_frame_20]",{1008},{76,0,1},{1008},"LAB_GACHA_DES_2"},
{20009,"LAB_GACHA_TAG_1009","gacha_list_bg_09","GachaCenter10003_up","Gacha[gacha_tab_up_frame_20]",{1009},{160,-400,1},{1009},"LAB_GACHA_DES_3"},
{20010,"LAB_GACHA_TAG_1010","gacha_list_bg_10","GachaCenter10003_up","Gacha[gacha_tab_up_frame_20]",{1010},{91,-200,1},{1010},"LAB_GACHA_DES_3"},
{20012,"LAB_GACHA_TAG_1012","gacha_list_bg_12","GachaCenter10004_up_1","Gacha[gacha_tab_up_frame_20]",{1012},{105,-412,1},{1012},"LAB_GACHA_DES_4"},
{20013,"LAB_GACHA_TAG_1013","gacha_list_bg_13","GachaCenter10004_up_2","Gacha[gacha_tab_up_frame_20]",{1013},{231,-412,1},{1013},"LAB_GACHA_DES_4"},
{20014,"LAB_GACHA_TAG_1014","gacha_list_bg_14","GachaCenter10005","Gacha[gacha_tab_up_frame_20]",{1014},nil,{1014},"LAB_GACHA_DES_5"}
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

tpl_card_pool = P
tpl_card_pool_list = PL
function tpl_card_pool_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P