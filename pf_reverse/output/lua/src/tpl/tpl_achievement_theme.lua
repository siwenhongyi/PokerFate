-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','icon','rewards','order','hide_progress',}
    local bodys = {
{101,"LAB_ACH_THEME_NAME_1","Achievement[achievement_main_theme_icon_01]",{20404001,1},1,nil},
{201,"LAB_ACH_THEME_NAME_2","Achievement[achievement_main_theme_icon_02]",{20404002,1},2,nil},
{301,"LAB_ACH_THEME_NAME_3","Achievement[achievement_main_theme_icon_03]",{20404003,1},3,nil},
{401,"LAB_ACH_THEME_NAME_4","Achievement[achievement_main_theme_icon_04]",nil,4,1},
{501,"LAB_ACH_THEME_NAME_5","Achievement[achievement_main_theme_icon_05]",nil,5,1}
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

tpl_achievement_theme = P
tpl_achievement_theme_list = PL
function tpl_achievement_theme_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P