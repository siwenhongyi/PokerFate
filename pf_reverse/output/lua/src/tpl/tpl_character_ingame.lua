-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','flip_index6','flip_index3','my_offset','flip_index4','flip_index5',}
    local bodys = {
{101401,{4,5},{3},{0,-45},{3},{4,5}},
{101404,{4,5},{3},nil,{3},{4,5}},
{100706,{4,5},{3},nil,{3},{4,5}},
{100406,{4,5},{3},nil,{3},{4,5}},
{100806,nil,nil,{0,-60},nil,nil},
{102105,{4,5},{3},nil,{3},{4,5}},
{100606,{1,2},{1},{60,-60},{1},{1,2}},
{102204,{4,5},{3},{0,-60},{3},{4,5}}
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

tpl_character_ingame = P
tpl_character_ingame_list = PL
function tpl_character_ingame_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P