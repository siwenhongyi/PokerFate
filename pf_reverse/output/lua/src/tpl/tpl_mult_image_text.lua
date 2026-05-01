-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','zh','tw','en','jp','ko',}
    local bodys = {
{"Title_Settings","CommonNew[Title_Settings]","CommonNew[Title_Settings]","CommonNew[Title_Settings]","CommonNew[Title_Settings]","CommonNew[Title_Settings]"},
{"Preview_Name_1","Backpack[backpack_preview_scene_title_01_zh]","Backpack[backpack_preview_scene_title_01_zh]","Backpack[backpack_preview_scene_title_01_zh]","Backpack[backpack_preview_scene_title_01_zh]","Backpack[backpack_preview_scene_title_01_zh]"},
{"ingame_rules_title_1_cn","IngameRules[ingame_rules_title_1_zh]","IngameRules[ingame_rules_title_1_cn]","IngameRules[ingame_rules_title_1_en]","IngameRules[ingame_rules_title_1_jp]","IngameRules[ingame_rules_title_1_ko]"},
{"ingame_rules_title_2_cn","IngameRules[ingame_rules_title_2_zh]","IngameRules[ingame_rules_title_2_cn]","IngameRules[ingame_rules_title_2_en]","IngameRules[ingame_rules_title_2_jp]","IngameRules[ingame_rules_title_2_ko]"},
{"ingame_rules_title_3_cn","IngameRules[ingame_rules_title_3_zh]","IngameRules[ingame_rules_title_3_cn]","IngameRules[ingame_rules_title_3_en]","IngameRules[ingame_rules_title_3_jp]","IngameRules[ingame_rules_title_3_ko]"},
{"ingame_replay_lose_tw","InGame[ingame_replay_lose_zh]","InGame[ingame_replay_lose_tw]","InGame[ingame_replay_lose_en]","InGame[ingame_replay_lose_jp]","InGame[ingame_replay_lose_ko]"},
{"ingame_replay_win_tw","InGame[ingame_replay_win_zh]","InGame[ingame_replay_win_tw]","InGame[ingame_replay_win_en]","InGame[ingame_replay_win_jp]","InGame[ingame_replay_win_ko]"},
{"bg_activity_sign_in_tw","Activity[bg_activity_sign_in_zh]","Activity[bg_activity_sign_in_tw]","Activity[bg_activity_sign_in_en]","Activity[bg_activity_sign_in_jp]","Activity[bg_activity_sign_in_ko]"},
{"activity_sign_in_monthly_tw","Activity[activity_sign_in_monthly_zh]","Activity[activity_sign_in_monthly_tw]","Activity[activity_sign_in_monthly_en]","Activity[activity_sign_in_monthly_jp]","Activity[activity_sign_in_monthly_ko]"},
{"activity_sign_in_tag_expired_tw","Activity[activity_sign_in_tag_expired_zh]","Activity[activity_sign_in_tag_expired_tw]","Activity[activity_sign_in_tag_expired_en]","Activity[activity_sign_in_tag_expired_jp]","Activity[activity_sign_in_tag_expired_ko]"},
{"activity_sign_in_tag_resign_tw","Activity[activity_sign_in_tag_resign_zh]","Activity[activity_sign_in_tag_resign_tw]","Activity[activity_sign_in_tag_resign_en]","Activity[activity_sign_in_tag_resign_jp]","Activity[activity_sign_in_tag_resign_ko]"},
{"activity_reward_title_tw","Activity[activity_reward_title_zh]","Activity[activity_reward_title_tw]","Activity[activity_reward_title_en]","Activity[activity_reward_title_jp]","Activity[activity_reward_title_ko]"},
{"activity_sign_in_reward_title_01_tw","Activity[activity_sign_in_reward_title_01_zh]","Activity[activity_sign_in_reward_title_01_tw]","Activity[activity_sign_in_reward_title_01_en]","Activity[activity_sign_in_reward_title_01_jp]","Activity[activity_sign_in_reward_title_01_ko]"},
{"activity_sign_in_reward_title_02_tw","Activity[activity_sign_in_reward_title_02_zh]","Activity[activity_sign_in_reward_title_02_tw]","Activity[activity_sign_in_reward_title_02_en]","Activity[activity_sign_in_reward_title_02_jp]","Activity[activity_sign_in_reward_title_02_ko]"},
{"activity_sign_in_reward_title_03_tw","Activity[activity_sign_in_reward_title_03_zh]","Activity[activity_sign_in_reward_title_03_tw]","Activity[activity_sign_in_reward_title_03_en]","Activity[activity_sign_in_reward_title_03_jp]","Activity[activity_sign_in_reward_title_03_ko]"},
{"common_result_title_tw","Common[common_result_title_zh]","Common[common_result_title_tw]","Common[common_result_title_en]","Common[common_result_title_jp]","Common[common_result_title_ko]"},
{"common_result_title_01_tw","Common[common_result_title_01_zh]","Common[common_result_title_01_tw]","Common[common_result_title_01_en]","Common[common_result_title_01_jp]","Common[common_result_title_01_ko]"},
{"common_result_title_02_tw","Common[common_result_title_02_zh]","Common[common_result_title_02_tw]","Common[common_result_title_02_en]","Common[common_result_title_02_jp]","Common[common_result_title_02_ko]"},
{"common_result_title_03_tw","Common[common_result_title_03_zh]","Common[common_result_title_03_tw]","Common[common_result_title_03_en]","Common[common_result_title_03_jp]","Common[common_result_title_03_ko]"},
{"shop_mothly_card_title_01_tw","Shop[shop_mothly_card_title_01_zh]","Shop[shop_mothly_card_title_01_tw]","Shop[shop_mothly_card_title_01_en]","Shop[shop_mothly_card_title_01_jp]","Shop[shop_mothly_card_title_01_ko]"},
{"shop_mothly_card_title_02_tw","Shop[shop_mothly_card_title_02_zh]","Shop[shop_mothly_card_title_02_tw]","Shop[shop_mothly_card_title_02_en]","Shop[shop_mothly_card_title_02_jp]","Shop[shop_mothly_card_title_02_ko]"},
{"shop_mothly_card_privilege_off_tw","Shop[shop_mothly_card_privilege_off_zh]","Shop[shop_mothly_card_privilege_off_tw]","Shop[shop_mothly_card_privilege_off_en]","Shop[shop_mothly_card_privilege_off_jp]","Shop[shop_mothly_card_privilege_off_ko]"},
{"shop_monthly_card_reward_title_01_tw","Shop[shop_monthly_card_reward_title_01_zh]","Shop[shop_monthly_card_reward_title_01_tw]","Shop[shop_monthly_card_reward_title_01_en]","Shop[shop_monthly_card_reward_title_01_jp]","Shop[shop_monthly_card_reward_title_01_ko]"},
{"shop_monthly_card_reward_title_02_tw","Shop[shop_monthly_card_reward_title_02_zh]","Shop[shop_monthly_card_reward_title_02_tw]","Shop[shop_monthly_card_reward_title_02_en]","Shop[shop_monthly_card_reward_title_02_jp]","Shop[shop_monthly_card_reward_title_02_ko]"},
{"shop_monthly_card_reward_title_03_tw","Shop[shop_monthly_card_reward_title_03_zh]","Shop[shop_monthly_card_reward_title_03_tw]","Shop[shop_monthly_card_reward_title_03_en]","Shop[shop_monthly_card_reward_title_03_jp]","Shop[shop_monthly_card_reward_title_03_ko]"},
{"By_chips_ingame_1_cn","IngameBankrupt[By_chips_ingame_1_zh]","IngameBankrupt[By_chips_ingame_1_cn]","IngameBankrupt[By_chips_ingame_1_en]","IngameBankrupt[By_chips_ingame_1_jp]","IngameBankrupt[By_chips_ingame_1_ko]"},
{"By_chips_ingame_2_tw","IngameBankrupt[By_chips_ingame_2_zh]","IngameBankrupt[By_chips_ingame_2_tw]","IngameBankrupt[By_chips_ingame_2_en]","IngameBankrupt[By_chips_ingame_2_jp]","IngameBankrupt[By_chips_ingame_2_ko]"},
{"Bankruptcy_benefits_cn","IngameBankrupt[Bankruptcy_benefits_zh]","IngameBankrupt[Bankruptcy_benefits_cn]","IngameBankrupt[Bankruptcy_benefits_en]","IngameBankrupt[Bankruptcy_benefits_jp]","IngameBankrupt[Bankruptcy_benefits_ko]"},
{"bonds_up_title_tw","Bonds[bonds_up_title_zh]","Bonds[bonds_up_title_tw]","Bonds[bonds_up_title_en]","Bonds[bonds_up_title_jp]","Bonds[bonds_up_title_ko]"},
{"bonds_up_full_title_tw","Bonds[bonds_up_full_title_zh]","Bonds[bonds_up_full_title_tw]","Bonds[bonds_up_full_title_en]","Bonds[bonds_up_full_title_jp]","Bonds[bonds_up_full_title_ko]"},
{"sdt_quiz_title_en","Sdt[sdt_quiz_title_zh]","Sdt[sdt_quiz_title_tw]","Sdt[sdt_quiz_title_en]","Sdt[sdt_quiz_title_jp]","Sdt[sdt_quiz_title_ko]"},
{"sdt_reward_title_en","Sdt[sdt_reward_title_zh]","Sdt[sdt_reward_title_tw]","Sdt[sdt_reward_title_en]","Sdt[sdt_reward_title_jp]","Sdt[sdt_reward_title_ko]"},
{"sdt_reward_fg_01_en","Sdt[sdt_reward_fg_01_zh]","Sdt[sdt_reward_fg_01_tw]","Sdt[sdt_reward_fg_01_en]","Sdt[sdt_reward_fg_01_jp]","Sdt[sdt_reward_fg_01_ko]"},
{"sdt_reward_fg_02_en","Sdt[sdt_reward_fg_02_zh]","Sdt[sdt_reward_fg_02_tw]","Sdt[sdt_reward_fg_02_en]","Sdt[sdt_reward_fg_02_jp]","Sdt[sdt_reward_fg_02_ko]"},
{"sdt_reward_fg_03_en","Sdt[sdt_reward_fg_03_zh]","Sdt[sdt_reward_fg_03_tw]","Sdt[sdt_reward_fg_03_en]","Sdt[sdt_reward_fg_03_jp]","Sdt[sdt_reward_fg_03_ko]"},
{"sdt_certificate_title_en","Sdt[sdt_certificate_title_zh]","Sdt[sdt_certificate_title_tw]","Sdt[sdt_certificate_title_en]","Sdt[sdt_certificate_title_jp]","Sdt[sdt_certificate_title_ko]"},
{"lobby_enter_character_title_tw","Lobby[lobby_enter_character_title_zh]","Lobby[lobby_enter_character_title_tw]","Lobby[lobby_enter_character_title_en]","Lobby[lobby_enter_character_title_jp]","Lobby[lobby_enter_character_title_ko]"},
{"lobby_enter_friend_game_title_tw","Lobby[lobby_enter_friend_game_title_zh]","Lobby[lobby_enter_friend_game_title_tw]","Lobby[lobby_enter_friend_game_title_en]","Lobby[lobby_enter_friend_game_title_jp]","Lobby[lobby_enter_friend_game_title_ko]"},
{"lobby_enter_gacha_title_tw","Lobby[lobby_enter_gacha_title_zh]","Lobby[lobby_enter_gacha_title_tw]","Lobby[lobby_enter_gacha_title_en]","Lobby[lobby_enter_gacha_title_jp]","Lobby[lobby_enter_gacha_title_ko]"},
{"lobby_enter_omaha_title_tw","Lobby[lobby_enter_omaha_title_zh]","Lobby[lobby_enter_omaha_title_tw]","Lobby[lobby_enter_omaha_title_en]","Lobby[lobby_enter_omaha_title_jp]","Lobby[lobby_enter_omaha_title_ko]"},
{"lobby_enter_poker_title_tw","Lobby[lobby_enter_poker_title_zh]","Lobby[lobby_enter_poker_title_tw]","Lobby[lobby_enter_poker_title_en]","Lobby[lobby_enter_poker_title_jp]","Lobby[lobby_enter_poker_title_ko]"},
{"ingame_action_allin_tw","InGame[ingame_action_allin_zh]","InGame[ingame_action_allin_tw]","InGame[ingame_action_allin_en]","InGame[ingame_action_allin_jp]","InGame[ingame_action_allin_ko]"},
{"ingame_action_bb_tw","InGame[ingame_action_bb_zh]","InGame[ingame_action_bb_tw]","InGame[ingame_action_bb_en]","InGame[ingame_action_bb_jp]","InGame[ingame_action_bb_ko]"},
{"ingame_action_sb_tw","InGame[ingame_action_sb_zh]","InGame[ingame_action_sb_tw]","InGame[ingame_action_sb_en]","InGame[ingame_action_sb_jp]","InGame[ingame_action_sb_ko]"},
{"ingame_action_bet_tw","InGame[ingame_action_bet_zh]","InGame[ingame_action_bet_tw]","InGame[ingame_action_bet_en]","InGame[ingame_action_bet_jp]","InGame[ingame_action_bet_ko]"},
{"ingame_action_call_tw","InGame[ingame_action_call_zh]","InGame[ingame_action_call_tw]","InGame[ingame_action_call_en]","InGame[ingame_action_call_jp]","InGame[ingame_action_call_ko]"},
{"ingame_action_raise_tw","InGame[ingame_action_raise_zh]","InGame[ingame_action_raise_tw]","InGame[ingame_action_raise_en]","InGame[ingame_action_raise_jp]","InGame[ingame_action_raise_ko]"},
{"ingame_player_fold_tw","InGame[ingame_player_fold_zh]","InGame[ingame_player_fold_tw]","InGame[ingame_player_fold_en]","InGame[ingame_player_fold_jp]","InGame[ingame_player_fold_ko]"},
{"level_upgrade_title_tw","Level[level_upgrade_title_zh]","Level[level_upgrade_title_tw]","Level[level_upgrade_title_en]","Level[level_upgrade_title_jp]","Level[level_upgrade_title_ko]"},
{"shop_vipupgrade_img_title_en","Shop[shop_vipupgrade_img_title_zh]","Shop[shop_vipupgrade_img_title_tw]","Shop[shop_vipupgrade_img_title_en]","Shop[shop_vipupgrade_img_title_jp]","Shop[shop_vipupgrade_img_title_ko]"},
{"shop_topup_img_title_tw","Shop[shop_topup_img_title_zh]","Shop[shop_topup_img_title_tw]","Shop[shop_topup_img_title_en]","Shop[shop_topup_img_title_jp]","Shop[shop_topup_img_title_ko]"},
{"shop_topup_img_subtitle_en","Shop[shop_topup_img_subtitle_zh]","Shop[shop_topup_img_subtitle_tw]","Shop[shop_topup_img_subtitle_en]","Shop[shop_topup_img_subtitle_jp]","Shop[shop_topup_img_subtitle_ko]"},
{"shop_pledge_title_tw","Shop[shop_pledge_title_zh]","Shop[shop_pledge_title_tw]","Shop[shop_pledge_title_en]","Shop[shop_pledge_title_jp]","Shop[shop_pledge_title_ko]"},
{"shop_pledge_button_through_tw","Character[shop_pledge_button_through_zh]","Character[shop_pledge_button_through_tw]","Character[shop_pledge_button_through_en]","Character[shop_pledge_button_through_jp]","Character[shop_pledge_button_through_ko]"},
{"shop_newcomer_title_tw","Shop[shop_newcomer_title_zh]","Shop[shop_newcomer_title_tw]","Shop[shop_newcomer_title_en]","Shop[shop_newcomer_title_jp]","Shop[shop_newcomer_title_ko]"},
{"character_bond_title_tw","Character[character_bond_title_zh]","Character[character_bond_title_tw]","Character[character_bond_title_en]","Character[character_bond_title_jp]","Character[character_bond_title_ko]"},
{"avatartitle_non_01_tw","Avatartitle[avatartitle_non_01_zh]","Avatartitle[avatartitle_non_01_tw]","Avatartitle[avatartitle_non_01_en]","Avatartitle[avatartitle_non_01_jp]","Avatartitle[avatartitle_non_01_tw]"}
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

tpl_mult_image_text = P
tpl_mult_image_text_list = PL
function tpl_mult_image_text_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P