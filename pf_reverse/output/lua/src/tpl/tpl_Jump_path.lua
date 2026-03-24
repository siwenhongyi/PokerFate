-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','view','sub_page','select','name','button_text','use_button_text','func_id','theme_activity_id',}
    local bodys = {
{1001,"CharacterMainBonds",nil,1,"LAB_PATH_CHARACTER_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_4",nil,nil},
{1002,"CharacterMain",nil,nil,"LAB_PATH_CHARACTER_2","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_4",nil,nil},
{1003,"CharacterMainBonds",nil,2,"LAB_CHAR_085","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{2001,"GachaMain",nil,nil,"LAB_CHAR_084","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{2002,"GachaMain",nil,10001,"LAB_CHAR_117","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{2003,"GachaMain",nil,10003,"LAB_CHAR_117","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{2004,"GachaMain",nil,10004,"LAB_CHAR_117","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{3001,"ActivityMain",{1001},nil,"LAB_PATH_ACTIVITY_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{4001,"LobbyLayer",nil,nil,"LAB_PATH_LOBBY_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{4002,"FriendsRoom",nil,nil,"LAB_PATH_FRIENDSROOM_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_FRIENDSROOM_1",nil,nil},
{4003,"IngameRules",nil,nil,nil,nil,nil,nil,nil},
{4004,"IngameReplay",nil,nil,nil,nil,nil,nil,nil},
{4005,"VIP",nil,nil,"LAB_VIP_NAME","LAB_PATH_BUTTON_TEXT_1",nil,nil,nil},
{4010,"RankingMain",nil,nil,"LAB_PATH_LEADERBOARD_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{5001,"OmahaBlinds",nil,10010101,"LAB_POKER_GAME","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{5002,"HotSpringHallBlind",nil,10040101,"LAB_ALLIN_01","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{5003,"OmahaBlinds",nil,10010202,"LAB_PATH_GAME_ENTER_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{5004,"OmahaBlinds",nil,10020101,"LAB_OMAHA","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",305,nil},
{5101,"SideGameView",nil,30030101,"LAB_PATH_COLORGAME_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",101,nil},
{5102,"SideGameView",nil,30080101,"LAB_PINBALL_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",101,nil},
{6002,"BackpackMain",{2},nil,"LAB_PATH_BACKPACK_2","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BACKPACK_2",nil,nil},
{6004,"BackpackMain",{4},nil,"LAB_PATH_BACKPACK_4","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{6101,"BackpackMain",nil,30300001,"LAB_PROPS_NAME_303_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6102,"BackpackMain",nil,30300002,"LAB_PROPS_NAME_303_2","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6103,"BackpackMain",nil,30300003,"LAB_PROPS_NAME_303_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6104,"BackpackMain",nil,30300004,"LAB_PROPS_NAME_303_4","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6105,"BackpackMain",nil,30300005,"LAB_PROPS_NAME_303_5","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6201,"BackpackMain",nil,30200001,"LAB_PROPS_NAME_302_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6202,"BackpackMain",nil,30200002,"LAB_PROPS_NAME_302_2","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6203,"BackpackMain",nil,30200003,"LAB_PROPS_NAME_302_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{6204,"BackpackMain",nil,30200004,"LAB_PROPS_NAME_302_4","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{7001,"Friend",{2},nil,"LAB_PATH_FRIEND_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{8001,"InformationAvatar",nil,nil,"LAB_PATH_INFO_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_INFO_1",nil,nil},
{8002,"InformationRename",nil,nil,"LAB_PATH_SHOP_6","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{8003,"InformationMain",nil,nil,nil,nil,nil,nil,nil},
{8004,"TaskView",{1},nil,"LAB_TASKS_UI_01","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{8005,"TaskView",{2},nil,"LAB_TASKS_UI_02","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{10001,"HotSpringHall",nil,nil,"LAB_THEME_ACTIVITY1_NAME_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10001},
{10002,"HotSpringShop",nil,nil,"LAB_THEME_ACTIVITY1_NAME_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10001},
{10003,"GalaSeasonMain",nil,nil,"LAB_THEME_ACTIVITY2_NAME_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10002},
{10004,"GalaSeasonShop",nil,nil,"LAB_THEME_ACTIVITY2_NAME_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10002},
{10005,"GalaSeasonActivity",nil,nil,"LAB_THEME_ACTIVITY2_NAME_4","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10002},
{10006,"SchoolMain",nil,nil,"LAB_THEME_ACTIVITY3_NAME_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10003},
{10007,"SchoolShop",nil,nil,"LAB_THEME_ACTIVITY3_NAME_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10003},
{10008,"SchoolTask",nil,nil,"LAB_THEME_ACTIVITY3_NAME_4","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,10003},
{10101,"SpringFestivalMain",nil,nil,"LAB_FESTIVAL_ACTIVITY1_NAME_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{10102,"SpringFestivalShop",nil,nil,"LAB_FESTIVAL_ACTIVITY1_NAME_2","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{10103,"SpringFestivalTask",nil,nil,"LAB_FESTIVAL_ACTIVITY1_NAME_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{11001,"TournamentLobby",{2},nil,"LAB_SNG","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{11002,"TournamentLobby",{3},nil,"LAB_MTT","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{101001,"Shop",{1,101},nil,"LAB_PATH_SHOP_1","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{101002,"Shop",{1,102},nil,"LAB_PATH_SHOP_2","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{101003,"Shop",{1,103},nil,"TAB_ICEBREAKER_PACK_2","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{102001,"Shop",{2},nil,"LAB_PATH_SHOP_3","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_2",nil,nil},
{103001,"Shop",{3,301},nil,"LAB_PATH_SHOP_4","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{103002,"Shop",{3,302},nil,"LAB_PATH_SHOP_5","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{104001,"Shop",{4,401},nil,"LAB_PATH_SHOP_6","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{104002,"Shop",{4,402},nil,"LAB_PATH_SHOP_11","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{104003,"Shop",{4,403},nil,"LAB_PATH_SHOP_15","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{105001,"Shop",{5,501},nil,"LAB_PATH_SHOP_7","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{105002,"Shop",{5,502},nil,"LAB_PATH_SHOP_8","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{105003,"Shop",{5,503},nil,"LAB_PATH_SHOP_9","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_3",nil,nil},
{106001,"Shop",{6,601},nil,"LAB_PATH_SHOP_10","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{106002,"Shop",{6,602},nil,"LAB_PATH_SHOP_12","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{106003,"Shop",{6,603},nil,"LAB_PATH_SHOP_13","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{106004,"Shop",{6,604},nil,"LAB_PATH_SHOP_14","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil},
{106005,"Shop",{6,605},nil,"LAB_PATH_SHOP_16","LAB_PATH_BUTTON_TEXT_1","LAB_PATH_BUTTON_TEXT_1",nil,nil}
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

tpl_Jump_path = P
tpl_Jump_path_list = PL
function tpl_Jump_path_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

