-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','image',}
    local bodys = {
{1001,"card"},
{1002,"card_1"},
{1003,"card_2"}
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

tpl_card = P
tpl_card_list = PL
function tpl_card_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P