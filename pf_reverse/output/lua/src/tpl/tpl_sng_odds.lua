-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','multiple','blast_probability',}
    local bodys = {
{1,200,51664},
{2,300,41624},
{3,400,2500},
{4,500,2200},
{5,1000,2000},
{6,5000,8},
{7,10000,4}
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

tpl_sng_odds = P
tpl_sng_odds_list = PL
function tpl_sng_odds_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

