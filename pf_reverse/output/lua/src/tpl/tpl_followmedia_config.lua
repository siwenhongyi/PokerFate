-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','reward','media_platform','lang',}
    local bodys = {
{1,{10100001,10000},{1,2,3},"tw"},
{2,{10100001,10000},{3,4},"jp"},
{3,{10100001,10000},{1,3,4},"en"},
{4,{10100001,10000},{5,6,7},"zh"}
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

tpl_followmedia_config = P
tpl_followmedia_config_list = PL
function tpl_followmedia_config_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P