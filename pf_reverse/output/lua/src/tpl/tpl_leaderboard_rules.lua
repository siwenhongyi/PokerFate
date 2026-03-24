-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','leaderboard_type','tab_name','rules_dec','index','change_time',}
    local bodys = {
{1,2,"LAB_LEADERBOARD_RULES_TAB_2","LAB_LEADERBOARD_RULES_DEC_2",1,1769972400},
{2,3,"LAB_LEADERBOARD_RULES_TAB_4","LAB_LEADERBOARD_RULES_DEC_6",2,nil},
{3,4,"LAB_LEADERBOARD_RULES_TAB_5","LAB_LEADERBOARD_RULES_DEC_4",3,nil},
{4,5,"LAB_LEADERBOARD_RULES_TAB_6","LAB_LEADERBOARD_RULES_DEC_5",4,nil},
{5,1,"LAB_LEADERBOARD_RULES_TAB_1","LAB_LEADERBOARD_RULES_DEC_1",5,nil},
{6,nil,"LAB_LEADERBOARD_RULES_TAB_3","LAB_LEADERBOARD_RULES_DEC_3",6,nil}
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

tpl_leaderboard_rules = P
tpl_leaderboard_rules_list = PL
function tpl_leaderboard_rules_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

