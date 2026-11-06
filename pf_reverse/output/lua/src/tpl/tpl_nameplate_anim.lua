-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','eff','eff_bg','bg_small',}
    local bodys = {
{1001,"Prefab/PKTable/Eff_Allin_fire",nil,"Icon[icon_nameplate_01]"},
{1002,"Prefab/PKTable/Eff_Allin_neon",nil,"Icon[icon_nameplate_02]"},
{1003,"Prefab/PKTable/Eff_Allin_feathers",nil,"Icon[icon_nameplate_03]"},
{1004,"views/table/Sayaka2026/SayakaNameplate","views/table/Sayaka2026/SayakaNameplate_bg","Icon[icon_nameplate_s6_01]"}
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

tpl_nameplate_anim = P
tpl_nameplate_anim_list = PL
function tpl_nameplate_anim_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P