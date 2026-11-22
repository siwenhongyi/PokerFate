-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','platform','lang',}
    local bodys = {
{1,{3},"tw"},
{2,{4},"jp"},
{3,{1},"en"},
{4,{2},"zh"}
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

tpl_vip_assistant_platform = P
tpl_vip_assistant_platform_list = PL
function tpl_vip_assistant_platform_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P