-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'page_id','name','icon','type','event_id','index',}
    local bodys = {
{1,{LAB_EVENT_CHECK_IN_NAME_1},"activity_newman_icon_01",2,2001,1},
{2,{LAB_DAILY_SIGN_IN},"activity_tab_icon_01",1,1001,2},
{3,{LAB_EVENT_MEDIA},"activity_tab_icon_follow",1,1002,3},
{4,{LAB_EVENT_LINKEMAIL},"activity_tab_icon_linkemail",1,1003,4}
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

tpl_event_page = P
tpl_event_page_list = PL
function tpl_event_page_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

