-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','title_name','plot_text','plot_time','chapter_task','chapter_rewards',}
    local bodys = {
{1,"LAB_SEVEN_DAY_TASKS_TITLE_1","LAB_SEVEN_DAY_TASKS_PLOT_TEXT_1","LAB_SEVEN_DAY_TASKS_PLOT_TIME_1",{1001,1002,1003,1004},{10200002,1,30200002,1,30200001,1}},
{2,"LAB_SEVEN_DAY_TASKS_TITLE_2","LAB_SEVEN_DAY_TASKS_PLOT_TEXT_2","LAB_SEVEN_DAY_TASKS_PLOT_TIME_2",{2001,2002,2003,2004},{10200001,10,30200002,1,10100001,15000}},
{3,"LAB_SEVEN_DAY_TASKS_TITLE_3","LAB_SEVEN_DAY_TASKS_PLOT_TEXT_3","LAB_SEVEN_DAY_TASKS_PLOT_TIME_3",{3001,3002,3003,3004,3005},{10200001,10,30200002,1,10100001,15000}},
{4,"LAB_SEVEN_DAY_TASKS_TITLE_4","LAB_SEVEN_DAY_TASKS_PLOT_TEXT_4","LAB_SEVEN_DAY_TASKS_PLOT_TIME_4",{4001,4002,4003,4004,4005},{10200001,15,30200002,1,10100001,25000}},
{5,"LAB_SEVEN_DAY_TASKS_TITLE_5","LAB_SEVEN_DAY_TASKS_PLOT_TEXT_5","LAB_SEVEN_DAY_TASKS_PLOT_TIME_5",{5001,5002,5003,5004,5005},{10200001,15,30200002,1,10100001,25000}},
{6,"LAB_SEVEN_DAY_TASKS_TITLE_6","LAB_SEVEN_DAY_TASKS_PLOT_TEXT_6","LAB_SEVEN_DAY_TASKS_PLOT_TIME_6",{6001,6002,6003,6004,6005},{10200001,25,30200002,1,10100001,35000}},
{7,"LAB_SEVEN_DAY_TASKS_TITLE_7","LAB_SEVEN_DAY_TASKS_PLOT_TEXT_7","LAB_SEVEN_DAY_TASKS_PLOT_TIME_7",{7001,7002,7003,7004,7005},{10200001,25,30200002,1,10100001,35000}}
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

tpl_seven_day_tasks_stage = P
tpl_seven_day_tasks_stage_list = PL
function tpl_seven_day_tasks_stage_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

