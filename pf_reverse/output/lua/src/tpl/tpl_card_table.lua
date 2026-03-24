-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','image','bg_image','bg_small',}
    local bodys = {
{1001,"BackGround/table_club_01.png","BackGround/scene_club_01.png","ItemPreview[item_preview_table_club_01]"},
{1002,"BackGround/table_park_01.png","BackGround/scene_park_01.png","ItemPreview[item_preview_table_park_01]"},
{1003,"BackGround/table_yacht_01.png","BackGround/scene_yacht_01.png","ItemPreview[item_preview_table_yacht_01]"},
{1004,"BackGround/table_mtt_indoor_01.png","BackGround/scene_mtt_indoor_01.png","ItemPreview[item_preview_table_mtt_indoor_01]"},
{1005,"BackGround/table_mtt_outdoor_01.png","BackGround/scene_mtt_outdoor_01.png","ItemPreview[item_preview_table_mtt_outdoor_01]"},
{1006,"BackGround/table_casino_01.png","BackGround/scene_casino_01.png","ItemPreview[item_preview_table_casino_01]"},
{2001,"BackGround/table_hot_spring_01.png","BackGround/scene_hot_spring_01.png","ItemPreview[item_preview_table_hot_spring_01]"},
{2002,"BackGround/table_activity_dress_01.png","BackGround/scene_activity_dress_01.png","ItemPreview[item_preview_table_activity_dress_01]"}
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

tpl_card_table = P
tpl_card_table_list = PL
function tpl_card_table_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

