-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','point','point_1001',}
    local bodys = {
{1,5000,500},
{2,10000,2000},
{3,15000,4500},
{4,20000,8000},
{5,30000,16000}
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

tpl_character_level = P
tpl_character_level_list = PL
function tpl_character_level_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P