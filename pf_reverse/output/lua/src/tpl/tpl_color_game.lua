-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','balance','chips1','chips2','chips3','maxbet','push_balance','quick_buy',}
    local bodys = {
{1,0,1000,3000,10000,256000000,30000,1},
{2,1000000,1000,3000,10000,256000000,1000000,2},
{3,10000000,10000,30000,100000,256000000,10000000,5},
{4,100000000,100000,300000,1000000,256000000,100000000,8},
{5,1000000000,1000000,3000000,10000000,256000000,100000000,8}
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

tpl_color_game = P
tpl_color_game_list = PL
function tpl_color_game_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P