-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'task_id','group','task_type','value','dec','jump','sort',}
    local bodys = {
{100101,1001,108,{3001,300},"LAB_CHAR_TASKS_3001_1",5001,1},
{100102,1001,126,{3001,30},"LAB_CHAR_TASKS_3001_2",11001,2},
{100103,1001,119,{3001,12,12,1},"LAB_CHAR_TASKS_3001_3",5001,3},
{100104,1001,128,{3001,7,1},"LAB_CHAR_TASKS_3001_4",5001,4}
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

tpl_character_task = P
tpl_character_task_list = PL
function tpl_character_task_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P