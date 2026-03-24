-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'task_id','ex_id','group','task_type','add_type','value','dec','rewards','jump','sort',}
    local bodys = {
{100101,nil,1001,302,3,{20001,1},"LAB_FESTIVAL_ACTIVITY1_TASK_1",{10420001,10},10101,1},
{100201,nil,1002,302,3,{20002,1},"LAB_FESTIVAL_ACTIVITY1_TASK_2",{10420001,10},10102,2},
{100301,nil,1003,101,3,{10010101,1},"LAB_FESTIVAL_ACTIVITY1_TASK_3",{10420001,20},5001,3},
{100401,nil,1004,101,3,{10020101,1},"LAB_FESTIVAL_ACTIVITY1_TASK_4",{10420001,20},5004,4},
{100501,nil,1005,105,3,{1},"LAB_FESTIVAL_ACTIVITY1_TASK_5",{10420001,20},11001,5},
{100601,nil,1006,101,3,{30030101,1},"LAB_FESTIVAL_ACTIVITY1_TASK_6",{10420001,20},5101,6},
{100701,nil,1007,314,1,{1},"LAB_FESTIVAL_ACTIVITY1_TASK_7",{10420001,100},10102,7},
{100801,100701,1008,314,1,{2},"LAB_FESTIVAL_ACTIVITY1_TASK_7",{10420001,100},10102,7},
{100901,100801,1009,314,1,{3},"LAB_FESTIVAL_ACTIVITY1_TASK_7",{10420001,100},10102,7},
{101001,100901,1010,314,1,{4},"LAB_FESTIVAL_ACTIVITY1_TASK_7",{10420001,100},10102,7},
{101101,101001,1011,314,1,{5},"LAB_FESTIVAL_ACTIVITY1_TASK_7",{10420001,100},10102,7},
{101201,101101,1012,314,1,{6},"LAB_FESTIVAL_ACTIVITY1_TASK_7",{10420001,100},10102,7}
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

tpl_festival_task = P
tpl_festival_task_list = PL
function tpl_festival_task_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

