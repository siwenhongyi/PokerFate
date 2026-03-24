-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','time_open','time_end','name','icon','icon_1','icon_2','main_bg','title_bg','weekly_num','index',}
    local bodys = {
{1,nil,1769972400,"LAB_LEADERBOARD_TAB_1","Rankings[rankings_tab_icon_01]","Rankings[rankings_title_icon_01]","Rankings[rankings_player_nameplate_chips_icon]","Rankings[rankings_chips_bg]","Rankingslist[rankingslist_contents_frame_02]",100,5},
{2,nil,nil,"LAB_LEADERBOARD_TAB_2","Rankings[rankings_tab_icon_02]","Rankings[rankings_title_icon_02]","Rankings[rankings_player_nameplate_throne_icon]","Rankings[rankings_throne_bg]","Rankingslist[rankingslist_contents_frame_01]",100,2},
{3,1770256800,nil,"LAB_LEADERBOARD_TAB_3","Rankings[rankings_tab_icon_03]","Rankings[rankings_title_icon_03]","Rankings[rankings_player_nameplate_honor_icon]","Rankings[rankings_throne_bg]","Rankingslist[rankingslist_contents_frame_01]",100,1},
{4,1769972400,nil,"LAB_LEADERBOARD_TAB_4","Rankings[rankings_tab_icon_04]","Rankings[rankings_title_icon_04]","Rankings[rankings_player_nameplate_chips_icon]","Rankings[rankings_chips_bg]","Rankingslist[rankingslist_contents_frame_02]",100,3},
{5,1769972400,nil,"LAB_LEADERBOARD_TAB_5","Rankings[rankings_tab_icon_05]","Rankings[rankings_title_icon_05]","Rankings[rankings_player_nameplate_chips_icon]","Rankings[rankings_chips_bg]","Rankingslist[rankingslist_contents_frame_02]",100,4}
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

tpl_leaderboard_info = P
tpl_leaderboard_info_list = PL
function tpl_leaderboard_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

