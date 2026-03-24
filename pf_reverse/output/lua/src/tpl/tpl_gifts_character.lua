-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','gifts_id','image_offset','bg_offset',}
    local bodys = {
{1002,{5,2005},{166,-45,0.8},{137,-42,1.65}},
{1003,{5,2005},{247,-253,1},{239,-11,1}},
{1004,{5,2005},{221,-230,0.9},{160,18,1.1}},
{1005,{5,2005},{172,-123,1},{140,-147,0.97}},
{1006,{5,2005},{227,-158,1},{170.7,-22,1}},
{1007,{5,2005},{233,-152,1},{108,-16.7,1}},
{1008,{5,2005},{213,-313,0.8},{218,-417,1.4}},
{1009,{5,2005},{117,-143,1},{133,-67,0.65}},
{1010,{5,2005},{235,-91,0.9},{238,184,0.9}},
{1012,{5,2005},{258,-211,1},{101,-103,1}},
{1013,{5,2005},{178,-342,0.9},{198,-252,0.9}}
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

tpl_gifts_character = P
tpl_gifts_character_list = PL
function tpl_gifts_character_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

