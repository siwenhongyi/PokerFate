-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','image','prefab','up','up_character','up_character_offset','character','character_img','des',}
    local bodys = {
{10001,"LAB_GACHA_TAG_1","gacha_list_bg_03","GachaCenter10001",nil,nil,nil,{1008,1003},nil,"LAB_GACHA_DES_2"},
{10002,"LAB_GACHA_TAG_2","gacha_list_bg_01","GachaCenter10002",nil,nil,nil,{1005,1004,1002,1007,1006},nil,"LAB_GACHA_DES_1"},
{10003,"LAB_GACHA_TAG_3","gacha_list_bg_09","GachaCenter10003",nil,nil,nil,{1009,1010},nil,"LAB_GACHA_DES_3"},
{10004,"LAB_GACHA_TAG_4","gacha_list_bg_12","GachaCenter10004",nil,nil,nil,{1013,1012},nil,"LAB_GACHA_DES_4"},
{10005,"LAB_GACHA_TAG_5","gacha_list_bg_14","GachaCenter10005",nil,nil,nil,{1014},nil,"LAB_GACHA_DES_5"},
{10006,"LAB_GACHA_TAG_6","gacha_list_bg_15","GachaCenter10006",nil,nil,nil,{1015,1016},nil,"LAB_GACHA_DES_6"},
{10007,"LAB_GACHA_TAG_7","gacha_list_bg_3001","GachaCenter10007",nil,nil,nil,{3001},nil,nil},
{10008,"LAB_GACHA_TAG_8","gacha_list_bg_17","GachaCenter10008",nil,nil,nil,{1018,1019},nil,"LAB_GACHA_DES_7"},
{10009,"LAB_GACHA_TAG_9","gacha_list_bg_20","GachaCenter10009",nil,nil,nil,{1020,1021},nil,"LAB_GACHA_DES_8"},
{10010,"LAB_GACHA_TAG_10","gacha_list_bg_22","GachaCenter10010",nil,nil,nil,{1022},nil,"LAB_GACHA_DES_9"},
{20002,"LAB_GACHA_TAG_1002","gacha_list_bg_02","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1002},{72,10,1},{1002},nil,"LAB_GACHA_DES_1"},
{20003,"LAB_GACHA_TAG_1003","gacha_list_bg_03","GachaCenter10001_up","Gacha[gacha_tab_up_frame_20]",{1003},{148,-42,1},{1003},nil,"LAB_GACHA_DES_2"},
{20004,"LAB_GACHA_TAG_1004","gacha_list_bg_04","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1004},{148,0,1},{1004},nil,"LAB_GACHA_DES_1"},
{20005,"LAB_GACHA_TAG_1005","gacha_list_bg_05","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1005},{118,23,1},{1005},nil,"LAB_GACHA_DES_1"},
{20006,"LAB_GACHA_TAG_1006","gacha_list_bg_06","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1006},{120,100,1},{1006},nil,"LAB_GACHA_DES_1"},
{20007,"LAB_GACHA_TAG_1007","gacha_list_bg_07","GachaCenter10002_up","Gacha[gacha_tab_up_frame_20]",{1007},{120,-20,1},{1007},nil,"LAB_GACHA_DES_1"},
{20008,"LAB_GACHA_TAG_1008","gacha_list_bg_08","GachaCenter10001_up","Gacha[gacha_tab_up_frame_20]",{1008},{76,0,1},{1008},nil,"LAB_GACHA_DES_2"},
{20009,"LAB_GACHA_TAG_1009","gacha_list_bg_09","GachaCenter10003_up","Gacha[gacha_tab_up_frame_20]",{1009},{160,-400,1},{1009},nil,"LAB_GACHA_DES_3"},
{20010,"LAB_GACHA_TAG_1010","gacha_list_bg_10","GachaCenter10003_up","Gacha[gacha_tab_up_frame_20]",{1010},{91,-200,1},{1010},nil,"LAB_GACHA_DES_3"},
{20012,"LAB_GACHA_TAG_1012","gacha_list_bg_12","GachaCenter10004_up_1","Gacha[gacha_tab_up_frame_20]",{1012},{105,-250,1},{1012},nil,"LAB_GACHA_DES_4"},
{20013,"LAB_GACHA_TAG_1013","gacha_list_bg_13","GachaCenter10004_up_2","Gacha[gacha_tab_up_frame_20]",{1013},{231,-250,1},{1013},nil,"LAB_GACHA_DES_4"},
{20014,"LAB_GACHA_TAG_1014","gacha_list_bg_14","GachaCenter10005","Gacha[gacha_tab_up_frame_20]",{1014},nil,{1014},nil,"LAB_GACHA_DES_5"},
{20015,"LAB_GACHA_TAG_1015","gacha_list_bg_15","GachaCenter10006_up","Gacha[gacha_tab_up_frame_20]",{1015},{158,-352,1},{1015},nil,"LAB_GACHA_DES_6"},
{20016,"LAB_GACHA_TAG_1016","gacha_list_bg_16","GachaCenter10006_up","Gacha[gacha_tab_up_frame_20]",{1016},{37,-304,1},{1016},nil,"LAB_GACHA_DES_6"},
{30001,"LAB_GACHA_TAG_3001","gacha_list_bg_3001","GachaCenter10007_up","Gacha[gacha_tab_up_frame_20]",{3001},nil,{3001},nil,nil},
{20018,"LAB_GACHA_TAG_1018","gacha_list_bg_17","GachaCenter10008_up","Gacha[gacha_tab_up_frame_20]",{1018},{94,-103,1},{1018},{"BackGround/Gacha/bg_gacha_matsuri_1018.png"},"LAB_GACHA_DES_7"},
{20019,"LAB_GACHA_TAG_1019","gacha_list_bg_18","GachaCenter10008_up","Gacha[gacha_tab_up_frame_20]",{1019},{97,-116,1},{1019},{"BackGround/Gacha/bg_gacha_matsuri_1019.png"},"LAB_GACHA_DES_7"},
{20020,"LAB_GACHA_TAG_1020","gacha_list_bg_20","GachaCenter10009_up","Gacha[gacha_tab_up_frame_20]",{1020},{18,-135,1},{1020},{"BackGround/Gacha/bg_gacha_racing_1020.png"},"LAB_GACHA_DES_8"},
{20021,"LAB_GACHA_TAG_1021","gacha_list_bg_21","GachaCenter10009_up","Gacha[gacha_tab_up_frame_20]",{1021},{29,-40,1},{1021},{"BackGround/Gacha/bg_gacha_racing_1021.png"},"LAB_GACHA_DES_8"},
{20022,"LAB_GACHA_TAG_1022","gacha_list_bg_22","GachaCenter10010","Gacha[gacha_tab_up_frame_20]",{1022},nil,{1022},nil,"LAB_GACHA_DES_9"}
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