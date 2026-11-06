-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'level','base_reward_up','time_reduce','reward_bonus','star_exp',}
    local bodys = {
{1,0,0,0,0},
{2,1200,500,0,15000},
{3,3000,1000,0,45000},
{4,5500,1500,100,135000},
{5,8500,2000,200,360000}
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

tpl_character_info = P
tpl_character_info_list = PL
function tpl_character_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P