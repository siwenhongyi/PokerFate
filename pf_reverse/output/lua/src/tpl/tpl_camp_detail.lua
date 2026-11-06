-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'campInt','camp_name','camp_icon',}
    local bodys = {
{0,"LAB_DISPATCH_CAMP_0","Dispatch[dispatch_main_camp_0]"},
{1,"LAB_DISPATCH_CAMP_1","Dispatch[dispatch_main_camp_1]"},
{2,"LAB_DISPATCH_CAMP_2","Dispatch[dispatch_main_camp_2]"},
{3,"LAB_DISPATCH_CAMP_3","Dispatch[dispatch_main_camp_3]"},
{4,"LAB_DISPATCH_CAMP_4","Dispatch[dispatch_main_camp_4]"},
{5,"LAB_DISPATCH_CAMP_5","Dispatch[dispatch_main_camp_5]"},
{6,"LAB_DISPATCH_CAMP_6","Dispatch[dispatch_main_camp_6]"}
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

tpl_camp_detail = P
tpl_camp_detail_list = PL
function tpl_camp_detail_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P