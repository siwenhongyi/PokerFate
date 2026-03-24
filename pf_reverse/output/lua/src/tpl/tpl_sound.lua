-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','path','loop_start','type','cd_image',}
    local bodys = {
{"10001","sound/bgm_hall/bgm_hall_full_01.ogg",20.251,1,"Backpack[backpack_music_cd_lobby_01]"},
{"10002","sound/bgm_hall/bgm_hall_full_02.ogg",8.705,1,"Backpack[backpack_music_cd_lobby_02]"},
{"10003","sound/bgm_hall/bgm_hall_full_03.ogg",7.848,1,"Backpack[backpack_music_cd_hot_spring_01]"},
{"10004","sound/bgm_hall/bgm_hall_full_04.ogg",12.007,1,"Backpack[backpack_music_cd_school_01]"},
{"20001","sound/bgm_battle/bgm_battle_full_01.ogg",11.64,1,"Backpack[backpack_music_cd_club_01]"},
{"20002","sound/bgm_battle/bgm_battle_full_02.ogg",10.588,1,"Backpack[backpack_music_cd_casino_01]"},
{"20003","sound/bgm_battle/bgm_battle_full_03.ogg",8.0,1,"Backpack[backpack_music_cd_hot_spring_02]"},
{"plot001","sound/plot/bgm_plot_01.ogg",nil,nil,nil},
{"plot002","sound/plot/bgm_plot_02.ogg",nil,nil,nil},
{"plot003","sound/plot/bgm_plot_03.ogg",nil,nil,nil},
{"plot004","sound/plot/bgm_plot_04.ogg",3.383,nil,nil},
{"plot005","sound/plot/bgm_plot_05.ogg",nil,nil,nil},
{"plot006","sound/plot/bgm_plot_06.ogg",nil,nil,nil},
{"plot007","sound/plot/bgm_plot_07.ogg",16.012,nil,nil},
{"plot008","sound/plot/bgm_plot_08.ogg",nil,nil,nil},
{"plot009","sound/plot/bgm_plot_09.ogg",nil,nil,nil},
{"plot010","sound/plot/bgm_plot_10.ogg",nil,nil,nil},
{"cacha001","sound/bgm_hall/bgm_cacha.ogg",nil,1,nil},
{"button_click","sound/button_click.ogg",nil,2,nil},
{"action_tip","sound/action_tip.mp3",nil,2,nil},
{"action_warn","sound/action_warn.mp3",nil,2,nil},
{"all_in","sound/all_in.mp3",nil,2,nil},
{"check","sound/check.mp3",nil,2,nil},
{"chip_bet","sound/chip_bet.mp3",nil,2,nil},
{"chip_win","sound/chip_win.mp3",nil,2,nil},
{"deal","sound/deal.mp3",nil,2,nil},
{"fold","sound/fold.mp3",nil,2,nil},
{"slider","sound/slider.mp3",nil,2,nil},
{"ui_button_confirm","sound/sound/ui_close.ogg",nil,2,nil},
{"ui_button_disabled","sound/sound/ui_button_disabled.ogg",nil,2,nil},
{"ui_tab_switch_1","sound/sound/ui_tab_switch_2.ogg",nil,2,nil},
{"ui_tab_switch_2","sound/sound/ui_tab_switch_2.ogg",nil,2,nil},
{"ui_close","sound/sound/ui_button_disabled.ogg",nil,2,nil},
{"ui_toast_message","sound/sound/ui_toast_message.ogg",nil,2,nil},
{"ui_reward_gain","sound/sound/ui_reward_gain.ogg",nil,2,nil},
{"ui_bubble","sound/sound/ui_bubble.ogg",nil,2,nil},
{"ui_shop_open","sound/sound/ui_shop_open.ogg",nil,2,nil},
{"ui_level_upgrade_lobby","sound/sound/ui_level_upgrade_lobby.ogg",nil,2,nil},
{"ui_level_upgrade_ingame","sound/sound/ui_level_upgrade_ingame.ogg",nil,2,nil},
{"ui_level_unlock","sound/sound/ui_level_unlock.ogg",nil,2,nil},
{"ui_vip_upgrade","sound/sound/ui_vip_upgrade.ogg",nil,2,nil},
{"ui_7daytask_answer_correct","sound/sound/ui_7daytask_answer_correct.ogg",nil,2,nil},
{"ui_7daytask_answer_wrong","sound/sound/ui_7daytask_answer_wrong.ogg",nil,2,nil},
{"ui_7daytask_usb_show","sound/sound/ui_7daytask_usb_show.ogg",nil,2,nil},
{"ui_7daytask_plot_show","sound/sound/ui_7daytask_plot_show.ogg",nil,2,nil},
{"ui_7daytask_progress_add_1","sound/sound/ui_7daytask_progress_add_1.ogg",nil,2,nil},
{"ui_7daytask_progress_add_2","sound/sound/ui_7daytask_progress_add_2.ogg",nil,2,nil},
{"ui_7daytask_transition","sound/sound/ui_7daytask_transition.ogg",nil,2,nil},
{"ui_share_screenshot","sound/sound/ui_share_screenshot.ogg",nil,2,nil},
{"ui_all_in_last","sound/sound/ui_all_in_last.ogg",nil,2,nil},
{"ui_dealing_cards_1","sound/sound/ui_dealing_cards_1.ogg",nil,2,nil},
{"ui_dealing_cards_2","sound/sound/ui_dealing_cards_2.ogg",nil,2,nil},
{"ui_chips_bet_1","sound/sound/ui_chips_bet_1.ogg",nil,2,nil},
{"ui_chips_bet_2","sound/sound/ui_chips_bet_2.ogg",nil,2,nil},
{"ui_chips_bet_3","sound/sound/ui_chips_bet_3.ogg",nil,2,nil},
{"ui_chips_win_1","sound/sound/ui_chips_win_1.ogg",nil,2,nil},
{"ui_chips_win_2","sound/sound/ui_chips_win_2.ogg",nil,2,nil},
{"ui_chips_win_3","sound/sound/ui_chips_win_3.ogg",nil,2,nil},
{"sound_recruit_fragment","sound/sound/sound_recruit_fragment.ogg",nil,2,nil},
{"sound_recruit_item","sound/sound/sound_recruit_item.ogg",nil,2,nil},
{"sound_recruit_character","sound/sound/sound_recruit_character.ogg",nil,2,nil},
{"sound_recruit_show","sound/sound/sound_recruit_show.ogg",nil,2,nil},
{"sound_recruit_showall","sound/sound/sound_recruit_showall.ogg",nil,2,nil},
{"sound_oath","sound/sound/sound_oath.ogg",nil,2,nil},
{"sound_recruit_anime_change","sound/sound/sound_recruit_anime_change",nil,2,nil},
{"sound_recruit_anime_character","sound/sound/sound_recruit_anime_character",nil,2,nil},
{"sound_recruit_anime_decoration","sound/sound/sound_recruit_anime_decoration",nil,2,nil},
{"sound_recruit_anime_item","sound/sound/sound_recruit_anime_item",nil,2,nil},
{"ui_fold_cards","sound/sound/ui_fold_cards.ogg",nil,2,nil},
{"ui_showcards_small","sound/sound/ui_showcards_small.ogg",nil,2,nil},
{"ui_showcards_big","sound/sound/ui_showcards_big.ogg",nil,2,nil},
{"sound_allin_01","sound/sound/sound_allin_01.ogg",nil,2,nil},
{"sound_SNG_lose","sound/sng/sound_SNG_lose.ogg",nil,2,nil},
{"sound_SNG_match","sound/sng/sound_SNG_match.ogg",nil,2,nil},
{"sound_SNG_spin","sound/sng/sound_SNG_spin.ogg",nil,2,nil},
{"sound_SNG_win","sound/sng/sound_SNG_win.ogg",nil,2,nil},
{"sound_Pinball_hit","sound/sidegame/sound_Pinball_hit.ogg",nil,2,nil},
{"sound_Pinball_high","sound/sidegame/sound_Pinball_high.ogg",nil,2,nil},
{"sound_Pinball_middle","sound/sidegame/sound_Pinball_middle.ogg",nil,2,nil},
{"sound_Pinball_low","sound/sidegame/sound_Pinball_low.ogg",nil,2,nil},
{"sound_Colorgame_roll","sound/sidegame/sound_Colorgame_roll.ogg",nil,2,nil},
{"sound_Colorgame_drop","sound/sidegame/sound_Colorgame_drop.ogg",nil,2,nil},
{"sound_Colorgame_hit","sound/sidegame/sound_Colorgame_hit.ogg",nil,2,nil},
{"sound_Colorgame_high","sound/sidegame/sound_Colorgame_high.ogg",nil,2,nil},
{"sound_Colorgame_middle","sound/sidegame/sound_Colorgame_middle.ogg",nil,2,nil},
{"sound_Colorgame_lwo","sound/sidegame/sound_Colorgame_lwo.ogg",nil,2,nil}
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

tpl_sound = P
tpl_sound_list = PL
function tpl_sound_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

