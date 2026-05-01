-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','time_start','time_end','rewards1','rewards2','rewards3','rewards4','rewards5','rewards6','rewards7','white_list_start','white_list_end',}
    local bodys = {
{1,"LAB_EVENT_CHECK_IN_NAME_1",1766023200,1767121200,{10100001,25000},{30200001,1},{10100001,25000},{30200002,1},{10100001,25000},{30200003,1},{30200004,1,10100001,25000},nil,nil},
{2,"LAB_EVENT_CHECK_IN_NAME_2",1769911200,1771095600,{10100001,25000},{30200001,1},{10100001,25000},{30200002,1},{10100001,25000},{30200003,1},{30200004,1,10100001,25000},nil,nil},
{3,"LAB_EVENT_CHECK_IN_NAME_3",1772676000,1773774000,{10100001,30000},{30200002,1},{10100001,30000},{30200003,1},{10100001,30000},{30200004,1},{10200001,10,10100001,30000},1772121600,1773280800},
{4,"LAB_EVENT_CHECK_IN_NAME_4",1775700000,1776798000,{10100001,30000},{30200002,1},{10100001,30000},{30200003,1},{10100001,30000},{30200004,1},{10200001,10,10100001,30000},1775095200,1775700000}
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

tpl_event_check_in = P
tpl_event_check_in_list = PL
function tpl_event_check_in_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P