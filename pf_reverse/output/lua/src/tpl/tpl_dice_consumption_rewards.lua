-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','activity','quantity','rewards',}
    local bodys = {
{1,30001,50,{11300001,1}},
{2,30001,100,{10100001,50000}},
{3,30001,150,{30300003,1}},
{4,30001,200,{10100001,150000}},
{5,30001,300,{30300002,1}},
{6,30001,400,{10200002,1}},
{7,30001,500,{30300001,1}}
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

tpl_dice_consumption_rewards = P
tpl_dice_consumption_rewards_list = PL
function tpl_dice_consumption_rewards_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P