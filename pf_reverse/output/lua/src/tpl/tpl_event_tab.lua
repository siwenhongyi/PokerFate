-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'page_id','name','icon','type','event_id','new_tag','index',}
    local bodys = {
{1,"LAB_EVENT_CHECK_IN_NAME_3","Activity[activity_tab_school]",2,2001,1,1},
{2,"LAB_DAILY_SIGN_IN","Activity[activity_tab_7day]",1,1001,0,4},
{3,"LAB_EVENT_MEDIA","Activity[activity_tab_social]",1,1002,1,2},
{4,"LAB_EVENT_LINKEMAIL","Activity[activity_tab_email]",1,1003,1,3}
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

tpl_event_tab = P
tpl_event_tab_list = PL
function tpl_event_tab_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

