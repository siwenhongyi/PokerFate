-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','image','preview_res',}
    local bodys = {
{1001,"Card[card_back]","BackGround/Card/card_back.png"},
{1002,"Card[card_back_01]","BackGround/Card/card_back_01.png"},
{1003,"Card[card_back_02]","BackGround/Card/card_back_02.png"},
{1004,"Card[card_back_03]","BackGround/Card/card_back_03.png"},
{1005,"Card[card_back_04]","BackGround/Card/card_back_04.png"},
{1006,"Card[card_back_05]","BackGround/Card/card_back_05.png"},
{1007,"Card[card_back_06]","BackGround/Card/card_back_06.png"},
{1008,"Card[card_back_07]","BackGround/Card/card_back_07.png"},
{1009,"Card[card_back_08]","BackGround/Card/card_back_08.png"},
{1010,"Card[card_back_09]","BackGround/Card/card_back_09.png"},
{1011,"Card[card_back_10]","BackGround/Card/card_back_10.png"},
{1012,"Card[card_back_activity_01_01]","BackGround/Card/card_back_activity_01_01.png"},
{1013,"Card[card_back_activity_02_02]","BackGround/Card/card_back_activity_02_02.png"},
{1014,"Card[card_back_activity_03_02]","BackGround/Card/card_back_activity_03_02.png"},
{2001,"Card[card_back_activity_01_02]","BackGround/Card/card_back_activity_01_02.png"},
{2002,"Card[card_back_activity_02_01]","BackGround/Card/card_back_activity_02_01.png"},
{2003,"Card[card_back_activity_03_01]","BackGround/Card/card_back_activity_03_01.png"},
{3001,"Card[card_back_ranking_01]","BackGround/Card/card_back_ranking_01.png"}
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

tpl_card_back = P
tpl_card_back_list = PL
function tpl_card_back_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

