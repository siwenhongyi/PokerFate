-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','balance','chips1','chips2','chips3','chips4',}
    local bodys = {
{1,0,1000,10000,30000,100000},
{2,10000000,10000,100000,300000,1000000},
{3,100000000,100000,1000000,3000000,10000000},
{4,1000000000,1000000,10000000,30000000,100000000}
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

tpl_predictor_bet = P
tpl_predictor_bet_list = PL
function tpl_predictor_bet_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P