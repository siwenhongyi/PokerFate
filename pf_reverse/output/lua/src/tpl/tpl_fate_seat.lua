-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','fate_character_id','day','weight',}
    local bodys = {
{1,1,nil,{30,30,25,15}},
{2,nil,2,{30,30,25,15}},
{3,nil,3,{30,30,25,15}},
{4,nil,4,{30,30,25,15}},
{5,nil,5,{30,30,25,15}},
{6,nil,6,{30,30,25,15}},
{7,nil,7,{30,30,25,15}},
{8,nil,8,{30,30,25,15}}
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

tpl_fate_seat = P
tpl_fate_seat_list = PL
function tpl_fate_seat_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P