-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','icon','limit_type','limit_count','props','activity','time_start','time_end','condition','buy_id','index',}
    local bodys = {
{1001,19,"LAB_ACTIVITY_GIFTS_1","Icon[icon_activity_gifts_1]",4,1,{10100001,5000000,10200002,6},20001,nil,nil,nil,1900001,10},
{1002,19,"LAB_ACTIVITY_GIFTS_2","Icon[icon_activity_gifts_2]",4,1,{10100001,12000000,10200002,10},20001,nil,nil,1001,1900002,11},
{1003,19,"LAB_ACTIVITY_GIFTS_3","Icon[icon_activity_gifts_3]",4,1,{10100001,5000000,10300001,390},20001,nil,nil,nil,1900003,20},
{1004,19,"LAB_ACTIVITY_GIFTS_4","Icon[icon_activity_gifts_4]",4,1,{10100001,12000000,10300001,390},20001,nil,nil,1003,1900004,21},
{1005,19,"LAB_ACTIVITY_GIFTS_5","Icon[icon_activity_gifts_5]",4,1,{10100001,5000000,30300001,5},20001,nil,nil,nil,1900005,30},
{1006,19,"LAB_ACTIVITY_GIFTS_6","Icon[icon_activity_gifts_6]",4,1,{10100001,12000000,30300001,10},20001,nil,nil,1005,1900006,31}
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

tpl_shop_activity_gifts = P
tpl_shop_activity_gifts_list = PL
function tpl_shop_activity_gifts_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

