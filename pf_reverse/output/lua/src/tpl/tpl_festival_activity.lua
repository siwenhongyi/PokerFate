-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','time_start','time_end','activity_item','task','gifts','cost','vip_points','white_list_start','white_list_end',}
    local bodys = {
{20001,"LAB_FESTIVAL_ACTIVITY1_NAME_1",1771034400,1771873200,10420001,{1001,1002,1003,1004,1005,1006,1007,1008,1009,1010,1011,1012},{1001,1002,1003,1004,1005,1006},{10420001,100},50,1772121600,1773280800}
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

tpl_festival_activity = P
tpl_festival_activity_list = PL
function tpl_festival_activity_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P