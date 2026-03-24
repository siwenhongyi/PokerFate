-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','eff','bg_small',}
    local bodys = {
{1001,"IngameAllin","ItemPreview[item_preview_allin_01]"},
{1002,"GalaSeasonAllin","ItemPreview[item_preview_allin_02]"}
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

tpl_all_in_anim = P
tpl_all_in_anim_list = PL
function tpl_all_in_anim_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

