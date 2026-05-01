-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name',}
    local bodys = {
{10010101,"LAB_POKER_GAME"},
{10040101,"LAB_ALLIN_01"},
{10010202,"LAB_POKER_JP"},
{10020101,"LAB_OMAHA"},
{20010103,"LAB_FRIROOM_001"},
{30030101,"LAB_COLORGAME_001"},
{30080101,"LAB_PINBALL_1"},
{101,"LAB_SHOP"},
{102,"LAB_TASKS_VIEWS_NAME_1"},
{201,"LAB_CHAR_001"},
{301,"LAB_INFO_043"},
{302,"LAB_INFO_043"},
{303,"LAB_TASKS_VIEWS_NAME_2"},
{401,"LAB_GACHA_NAME"},
{501,"LAB_TASKS_VIEWS_NAME_3"},
{601,"LAB_CARD_REPORT"},
{701,"LAB_TOURNAMENT"},
{10001,"LAB_THEME_ACTIVITY1_NAME_1"},
{1,"LAB_TASKS_VIEWS_NAME_4"},
{2,"LAB_TASKS_VIEWS_NAME_5"}
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

tpl_task_type_info = P
tpl_task_type_info_list = PL
function tpl_task_type_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P