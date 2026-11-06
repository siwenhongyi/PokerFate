-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','attach_name',}
    local bodys = {
{102004,{"ImageFg/SpineHandcuff"}},
{100606,{"Image/SpineBg","ImageFg/SpineFg"}}
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

tpl_character_scrap = P
tpl_character_scrap_list = PL
function tpl_character_scrap_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P