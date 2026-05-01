-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','level','to_ser','bg','rebate_ratio','rewards_lower_ratio','rewards_upper_ratio','effective_time',}
    local bodys = {
{1,1,0,"Development[development_fund_bg_01]",1200,80,800,1774569600},
{2,2,8000000000,"Development[development_fund_bg_01]",1600,100,1000,1774569600},
{3,3,12000000000,"Development[development_fund_bg_02]",2000,120,1200,1774569600}
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

tpl_play_rebate = P
tpl_play_rebate_list = PL
function tpl_play_rebate_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P