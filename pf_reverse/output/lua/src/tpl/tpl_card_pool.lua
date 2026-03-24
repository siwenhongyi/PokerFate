-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','image','character','des',}
    local bodys = {
{10001,"LAB_GACHA_TAG_1","gacha_list_bg_02",{1008,1003},"LAB_GACHA_DES_2"},
{10002,"LAB_GACHA_TAG_2","gacha_list_bg_01",{1005,1004,1002,1007,1006},"LAB_GACHA_DES_1"},
{10003,"LAB_GACHA_TAG_3","gacha_list_bg_03",{1009,1010},"LAB_GACHA_DES_3"},
{10004,"LAB_GACHA_TAG_4","gacha_list_bg_04",{1013,1012},"LAB_GACHA_DES_4"}
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

