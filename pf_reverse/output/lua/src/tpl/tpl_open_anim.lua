-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','eff',}
    local bodys = {
{1001,"Prefab/PKTable/Eff_poker_allin_sololight"},
{1002,"views/table/Sayaka2026/SayakaShow"}
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

tpl_open_anim = P
tpl_open_anim_list = PL
function tpl_open_anim_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P