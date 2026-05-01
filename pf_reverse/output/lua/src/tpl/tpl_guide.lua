-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','guide','kind','guide_type','is_weak','story_id','story_index','show_ui','show_area','click_ui','hide_ui','hide_mask','finger_kind','finger','finger_rotate','tip','tip_pos','delay','waitingTime','p1','v1','start_event','stop_event','effective_time','guide_old',}
    local bodys = {
{1,1010,1,1,nil,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil},
{2,1011,1,1,nil,1,30,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil},
{3,1020,3,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil},
{4,1030,1,1,nil,2,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil},
{5,1040,2,1,nil,nil,nil,{"LobbyLayer/AnimRoot/Right/PokerButton/PokerButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS1",{-80,-250,2,2},0.5,0.5,nil,nil,nil,nil,nil,nil},
{6,1040,2,1,nil,nil,nil,{"OmahaBlinds/AnimRoot/LeftTop/InfoButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS2",{-420,250,2,14},nil,0.0,nil,nil,nil,nil,nil,nil},
{7,1040,2,1,nil,nil,nil,{"IngameRules/AnimRoot/Center/ButtonRight"},nil,nil,{"IngameRules/AnimRoot/RightTop/CloseButton"},1,nil,{0,0},nil,nil,nil,nil,0.0,nil,nil,nil,nil,nil,nil},
{8,1040,2,1,nil,nil,nil,{"IngameRules/AnimRoot/Center/ButtonRight"},nil,nil,{"IngameRules/AnimRoot/RightTop/CloseButton","IngameRules/AnimRoot/Center/ButtonLeft"},1,nil,{0,0},nil,nil,nil,nil,0.0,nil,nil,nil,nil,nil,nil},
{9,1040,2,1,nil,nil,nil,{"IngameRules/AnimRoot/RightTop/CloseButton"},nil,nil,{"IngameRules/AnimRoot/Center/ButtonLeft","IngameRules/AnimRoot/Center/ButtonRight"},1,nil,{0,0},{-1,1,0},nil,nil,nil,nil,nil,nil,nil,nil,nil,nil},
{10,1040,2,1,nil,nil,nil,{"OmahaBlinds/AnimRoot/Center/RoomView/Item1","OmahaBlinds/AnimRoot/Center/RoomList/Viewport/Content/Item1"},nil,nil,nil,nil,nil,{0,-20},nil,"LAB_GUIDE_TIPS3",{0,-365,1},nil,nil,nil,nil,nil,nil,nil,nil},
{11,1040,2,1,nil,nil,nil,{"LobbyByinDialog/AnimRoot/Center/Panel/StartButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS4",{-442,250,2},nil,nil,nil,nil,nil,nil,nil,nil},
{12,1040,6,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,2.0,nil,"GameScene",nil,nil,nil,nil},
{13,1040,4,1,nil,nil,nil,nil,nil,nil,nil,1,nil,nil,nil,nil,nil,nil,3.0,{0,24},nil,nil,nil,nil,nil},
{14,1040,2,1,nil,nil,nil,{"PKActionLayer/ImageBg/BgAction/RaiseButton"},nil,nil,nil,1,nil,{0,0},{-1,1,-100},"LAB_GUIDE_TIPS5",{-400,100,2,2},nil,0.0,nil,nil,nil,nil,nil,nil},
{15,1040,2,1,nil,nil,nil,{"PKActionLayer/ImageBg/BgAction/Raise/BgPotPK/Pot4Button"},nil,nil,nil,1,nil,{0,0},{-1,1,-100},nil,nil,nil,2.0,nil,nil,nil,nil,nil,nil},
{16,1040,5,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,3.0,{0,285},nil,nil,nil,nil,nil},
{17,1040,2,1,nil,nil,nil,{"PKActionLayer/ImageBg/BgAction/BetButton"},nil,nil,nil,1,nil,{0,0},{-1,1,-100},"LAB_GUIDE_TIPS16",{-400,100,2,2},nil,0.0,nil,nil,nil,nil,nil,nil},
{18,1040,2,1,nil,nil,nil,{"PKActionLayer/ImageBg/BgAction/Raise/BgPotPK/Pot4Button"},nil,nil,nil,1,nil,{0,0},{-1,1,-100},nil,nil,nil,3.0,nil,nil,nil,nil,nil,nil},
{19,1040,5,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,0.0,{0,289},nil,nil,nil,nil,nil},
{20,1040,2,1,nil,nil,nil,{"PKActionLayer/ImageBg/BgAction/AllinCallButton"},nil,nil,nil,1,nil,{0,0},{-1,1,-100},"LAB_GUIDE_TIPS6",{-400,100,2,2},nil,15.0,nil,nil,nil,nil,nil,nil},
{21,1040,4,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,3.0,{0,23},nil,nil,nil,nil,nil},
{22,1040,2,1,nil,nil,nil,{"PKUILayer/LeftTop/MenuButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS7",{-400,250,2,14},nil,nil,nil,nil,"evt_guide_show_menu",nil,nil,nil},
{23,1040,2,1,nil,nil,nil,{"PKMenu/Menu/ExitButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS8",{-100,-100,2,14},nil,nil,nil,nil,nil,nil,nil,nil},
{25,1050,2,1,nil,nil,nil,{"LobbyLayer/AnimRoot/Right/CharacterButton/CharacterButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS9",{-80,-200,2,2},0.5,1.0,nil,nil,nil,nil,nil,nil},
{26,1050,2,1,nil,nil,nil,{"CharacterMain/AnimRoot/Left/TabMain/BondsToggle"},nil,nil,nil,nil,nil,{-84,0},nil,"LAB_GUIDE_TIPS10",{-400,100,2,4},nil,1.0,nil,nil,nil,nil,nil,nil},
{27,1050,2,1,nil,nil,nil,{"CharacterMainBonds/AnimRoot/Right/character_bond_bg/GiftsList/Viewport/Content/Item1"},nil,nil,nil,nil,nil,{0,0},nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil},
{28,1050,2,1,nil,nil,nil,{"CharacterMainBonds/AnimRoot/Right/character_bond_bg/GiftButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS11",{-320,100,2,2},nil,1.0,nil,nil,nil,nil,nil,nil},
{29,1050,2,1,nil,nil,nil,{"CharacterMainBonds/AnimRoot/LeftTop/BackButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS12",{-442,250,2,14},nil,1.0,nil,nil,nil,nil,nil,nil},
{30,1050,2,1,nil,nil,nil,{"CharacterMain/AnimRoot/LeftTop/BackButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS17",{-442,250,2,14},nil,1.0,nil,nil,nil,nil,nil,nil},
{31,1060,2,1,1,nil,nil,{"LobbyLayer/AnimRoot/Right/PokerButton/PokerButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_GUIDE_TIPS18",{-80,-250,2,2},0.5,nil,nil,nil,nil,"evt_try_auto_pop",nil,nil},
{1001,nil,2,2,nil,nil,nil,{"CharacterMain/AnimRoot/Right/Characters/CharacterList/Viewport/Content/Item2"},nil,nil,nil,nil,2,{0,0},nil,"LAB_CHAR_096",{-320,100,2,2},nil,1.0,nil,nil,nil,nil,nil,nil},
{2001,nil,2,2,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_2_1",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{2002,nil,2,2,1,nil,nil,{"BackpackMain/AnimRoot/Center/TopOptionCont/MultipleRecycleButton"},{0,0,300, 90},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_2_2",{-480,-150,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{3001,nil,2,2,1,nil,nil,{"BackpackMain/AnimRoot/Center/ItemRecycleScrollList/QualityFilter/FilterButton"},{0,0,326, 60},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_3_1",{120,-200,4,4},nil,nil,nil,nil,nil,nil,nil,nil},
{3002,nil,2,2,1,nil,nil,nil,{},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_3_2",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{3003,nil,2,2,1,nil,nil,{"BackpackMain/AnimRoot/Center/ItemRecycleScrollList/Viewport/GuidePoint"},{0,0,180,170},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_3_3",{200,150,4,4},nil,nil,nil,nil,nil,nil,nil,nil},
{3004,nil,2,2,1,nil,nil,{"BackpackMain/AnimRoot/Right/RecycleDetail/SelectAllButton"},{0,0,300,90},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_3_4",{-100,-200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{3005,nil,2,2,1,nil,nil,{"BackpackMain/AnimRoot/Right/RecycleDetail/ConfirmButton"},{0,0,300,90},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_3_5",{-100,-200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{4001,nil,2,2,nil,nil,nil,{"BackpackMain/AnimRoot/Right/ItemDetail/PreviewButton"},{},nil,nil,nil,nil,{14,7},nil,"LAB_SYSTEM_GUIDE_4_1",{-780,50,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{5001,nil,2,2,1,nil,nil,{"CharacterMainGarments/AnimRoot/Right/Garments/GarmentsList/Viewport/GuidePoint"},{0,-52,210,540},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_5_1",{-800,0,2,2},nil,nil,nil,nil,"evt_refresh_character_pos",nil,nil,nil},
{5002,nil,2,2,1,nil,nil,{"CharacterMainGarments/AnimRoot/Left/GuidePoint"},{-45,0,350,440},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_5_2",{500,-300,4,2},nil,nil,nil,nil,nil,nil,nil,nil},
{6001,nil,2,2,1,nil,nil,nil,{},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_6_1",{-500,0,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{6002,nil,2,2,1,nil,nil,{"CharacterMainProfile/AnimRoot/Right/GuidePoint"},{0,0,886,2000},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_6_2",{-400,-150,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{6003,nil,2,2,1,nil,nil,{"CharacterMainProfile/AnimRoot/Right/GuidePoint"},{0,0,886,2000},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_6_3",{-400,-150,1,2},nil,nil,nil,nil,"evt_guide_profile_voice",nil,nil,nil},
{6004,nil,2,2,1,nil,nil,{"CharacterMainProfile/AnimRoot/Right/GuidePoint"},{0,0,886,2000},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_6_4",{-400,-150,1,2},nil,nil,nil,nil,"evt_guide_profile_file",nil,nil,nil},
{7001,nil,2,2,1,nil,nil,nil,{},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_7_1",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{7002,nil,2,2,1,nil,nil,{"TaskView/AnimRoot/Center/Tab"},{0,0,520,90},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_7_2",{-500,200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{7003,nil,2,2,1,nil,nil,{"TaskView/AnimRoot/Center/TaskList/Viewport/GuidePoint"},{0,0,1150,140},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_7_3",{-300,-120,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{7004,nil,2,2,1,nil,nil,{"CommonPackageTip/ItemList"},{0,0,620,250},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_7_4",{-150,-200,2,2},0.5,nil,nil,nil,"evt_guide_turn_week",nil,nil,nil},
{8001,nil,2,2,1,nil,nil,{"Level/AnimRoot/Center/GuidePointLeft"},{0,0,720,860},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_8_1",{450,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{8002,nil,2,2,1,nil,nil,{"Level/AnimRoot/Center/GuidePointLeft"},{0,0,720,860},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_8_2",{450,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{8003,nil,2,2,1,nil,nil,{"Level/AnimRoot/Center/GuidePointLeft"},{0,0,720,860},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_8_3",{450,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{8004,nil,2,2,1,nil,nil,{"Level/AnimRoot/Center/GuidePointRight"},{0,0,790,626},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_8_4",{-500,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9001,nil,2,2,1,nil,nil,nil,{},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_9_1",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9002,nil,2,2,1,nil,nil,{"InformationMainNew/AnimRoot/Center/Panel/Info1"},{0,0,1080,185},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_9_2",{-340,-100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9003,nil,2,2,1,nil,nil,{"InformationMainNew/AnimRoot/Center/Panel/Info1"},{0,0,1080,185},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_9_3",{-340,-100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9004,nil,2,2,1,nil,nil,{"InformationMainNew/AnimRoot/Center/Panel/Info2/Comment"},{0,0,1050,128},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_9_4",{-340,-200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9005,nil,2,2,1,nil,nil,{"InformationMainNew/AnimRoot/Center/Panel/Info2/Character"},{0,6,1050,127},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_9_5",{-340,200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9006,nil,2,2,1,nil,nil,{"InformationMainNew/AnimRoot/Center/Panel/Info2/Collection"},{0,-100,1050,375},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_9_6",{-340,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9007,nil,2,2,nil,nil,nil,{"InformationMainNew/AnimRoot/Center/Panel/Tab/Tab2Toggle"},nil,nil,nil,nil,nil,{0,0},{-1,1,0},"LAB_SYSTEM_GUIDE_9_7",{-340,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{9008,nil,2,2,1,nil,nil,{"InformationMainNew/AnimRoot/Center/Panel/Info3"},{0,-5,1080,630},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_9_8",{-340,320,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{10001,nil,2,2,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_10_1",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{10002,nil,2,2,1,nil,nil,{"Shop/AnimRoot/Center/CenterCont/ShopTopUp(Clone)/TopUpScrollList"},{-580,160,395,520},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_10_2",{300,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{10003,nil,2,2,1,nil,nil,{"Shop/AnimRoot/Center/CenterCont/ShopTopUp(Clone)/TopUpScrollList"},{-580,160,395,520},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_10_3",{300,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{11001,nil,2,2,1,nil,nil,{"Setting/AnimRoot/Center/Panel/TabAccount/Viewport/ContentAccountItem2/common_panel_black_grid_03"},{0,0,1139,109},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_11_1",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{11002,nil,2,2,nil,nil,nil,{"Setting/AnimRoot/Center/Panel/TabAccount/Viewport/Content/AccountItem2/LinkButton"},nil,nil,nil,nil,nil,{0,0},nil,"LAB_SYSTEM_GUIDE_11_2",{-300,200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{11003,nil,2,2,1,nil,nil,{"SettingBindEmail/AnimRoot/Center/common_input_login"},{0,0,1000,90},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_11_3",{-590,-100,2,2},0.5,nil,nil,nil,nil,nil,nil,nil},
{11004,nil,2,2,1,nil,nil,{"SettingBindEmail/AnimRoot/Center/ButtonCode"},{0,0,378,70},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_11_4",{-290,-200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{11005,nil,2,2,1,nil,nil,{"SettingBindEmail/AnimRoot/Center/InputFieldCode"},{-265,0,480,100},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_11_5",{300,-200,4,2},nil,nil,nil,nil,nil,nil,nil,nil},
{11006,nil,2,2,1,nil,nil,{"SettingBindEmail/AnimRoot/Center/ButtonConfirm"},{0,0,526,104},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_11_6",{-600,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{12001,nil,2,2,1,nil,nil,{"OmahaBlinds/AnimRoot/Center/RoomView/Item0","OmahaBlinds/AnimRoot/Center/RoomList/Viewport/Content/Item0"},nil,nil,nil,nil,nil,{0,-20},nil,"LAB_GAME_056",{549,-58,4,0},nil,nil,nil,nil,nil,nil,nil,nil},
{13001,nil,2,2,1,nil,nil,{"OmahaBlinds/AnimRoot/Center/RoomView/Item0","OmahaBlinds/AnimRoot/Center/RoomList/Viewport/Content/Item0"},nil,nil,nil,nil,nil,{0,-20},nil,"LAB_GAME_057",{549,-58,4,0},nil,nil,nil,nil,nil,nil,nil,nil},
{14001,nil,2,2,1,nil,nil,{"TournamentLobby/AnimRoot/Center/SNG/Item1List/Viewport/Content/ItemTrain"},nil,nil,nil,nil,nil,{0,-20},nil,"LAB_GAME_060",{554,-137,4,0},nil,nil,nil,nil,nil,nil,nil,nil},
{15001,nil,2,2,1,nil,nil,nil,{},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_15_1",{-500,100,2,2},nil,nil,nil,nil,nil,nil,1777834800,7001},
{15002,nil,2,2,1,nil,nil,{"TaskView/AnimRoot/Center/Tab"},{130,5,780,100},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_15_2",{-500,200,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{15003,nil,2,2,1,nil,nil,{"TaskView/AnimRoot/Center/TaskList/Viewport/GuidePoint"},{0,0,1150,140},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_15_3",{-300,-120,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{15004,nil,2,2,1,nil,nil,{"CommonPackageTip/ItemList"},{0,0,620,250},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_15_4",{-150,-200,2,2},0.5,nil,nil,nil,"evt_guide_turn_week",nil,nil,nil},
{15005,nil,2,2,1,nil,nil,{"TaskView/AnimRoot/Center/TaskList"},{222,0,212,580},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_15_5",{-750,100,2,2},0.5,nil,nil,nil,"evt_guide_turn_challenge",nil,nil,nil},
{16001,nil,2,2,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_16_1",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{16002,nil,2,2,1,nil,nil,{"AchievementMain/AnimRoot/Center/AchievementTheme"},{-450,10,850,620},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_16_2",{500,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{16003,nil,2,2,nil,nil,nil,{"AchievementMain/AnimRoot/Center/AchievementTheme/ScrollView/Viewport/Content/Item01(Clone)"},{-660,10,425,620},nil,nil,nil,nil,{0,-100},nil,"LAB_SYSTEM_GUIDE_16_3",{150,-100,1,2},nil,nil,nil,nil,nil,nil,nil,nil},
{16004,nil,2,2,1,nil,nil,{"AchievementDetail/AnimRoot/Center/AchievementDetailTask"},{10,-80,1269,600},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_16_4",{-350,350,2,2},0.5,nil,nil,nil,nil,nil,nil,nil},
{16005,nil,2,2,1,nil,nil,{"AchievementDetail/AnimRoot/Center/AchievementDetailTask"},{10,320,1260,210},nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_16_5",{-328,-54,2,2},nil,nil,nil,nil,nil,nil,nil,nil},
{16006,nil,2,2,1,nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,"LAB_SYSTEM_GUIDE_16_6",{-500,100,2,2},nil,nil,nil,nil,nil,nil,nil,nil}
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

tpl_guide = P
tpl_guide_list = PL
function tpl_guide_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P