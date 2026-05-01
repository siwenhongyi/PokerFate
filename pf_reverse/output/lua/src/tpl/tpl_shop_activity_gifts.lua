-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','icon','limit_type','limit_count','props','activity','time_start','time_end','condition','goods_bg','tag_bg','tag_text','buy_id','index',}
    local bodys = {
{1001,19,"LAB_ACTIVITY_GIFTS_1","Icon[icon_activity_gifts_1]",4,1,{10100001,5000000,10200002,6},20001,nil,nil,nil,2,nil,nil,1900001,10},
{1002,19,"LAB_ACTIVITY_GIFTS_2","Icon[icon_activity_gifts_2]",4,1,{10100001,12000000,10200002,10},20001,nil,nil,1001,2,nil,nil,1900002,11},
{1003,19,"LAB_ACTIVITY_GIFTS_3","Icon[icon_activity_gifts_3]",4,1,{10100001,5000000,10300001,390},20001,nil,nil,nil,2,nil,nil,1900003,20},
{1004,19,"LAB_ACTIVITY_GIFTS_4","Icon[icon_activity_gifts_4]",4,1,{10100001,12000000,10300001,390},20001,nil,nil,1003,2,nil,nil,1900004,21},
{1005,19,"LAB_ACTIVITY_GIFTS_5","Icon[icon_activity_gifts_5]",4,1,{10100001,5000000,30300001,5},20001,nil,nil,nil,1,nil,nil,1900005,30},
{1006,19,"LAB_ACTIVITY_GIFTS_6","Icon[icon_activity_gifts_6]",4,1,{10100001,12000000,30300001,10},20001,nil,nil,1005,2,nil,nil,1900006,31},
{1007,19,"LAB_ACTIVITY_GIFTS_101","Icon[icon_activity_gifts_1_1]",4,1,{10100001,1000000,10200002,3},10004,nil,nil,nil,1,"Shop[shop_tag_time_01]","LAB_EVENT",1900007,1},
{1008,19,"LAB_ACTIVITY_GIFTS_102","Icon[icon_activity_gifts_1_2]",4,1,{10100001,4000000,10200002,15},10004,nil,nil,nil,1,"Shop[shop_tag_time_01]","LAB_EVENT",1900008,2},
{1009,19,"LAB_ACTIVITY_GIFTS_103","Icon[icon_activity_gifts_1_3]",4,1,{10100001,12000000,10200002,40},10004,nil,nil,nil,1,"Shop[shop_tag_time_01]","LAB_EVENT",1900009,3},
{1010,19,"LAB_ACTIVITY_GIFTS_201","Icon[icon_activity_gifts_2_1]",4,1,{10100001,1500000,10300001,390},10004,nil,nil,nil,2,"Shop[shop_tag_time_01]","LAB_EVENT",1900010,4},
{1011,19,"LAB_ACTIVITY_GIFTS_202","Icon[icon_activity_gifts_2_2]",4,1,{10100001,3000000,10300001,1170},10004,nil,nil,nil,2,"Shop[shop_tag_time_01]","LAB_EVENT",1900011,5},
{1012,19,"LAB_ACTIVITY_GIFTS_301","Icon[icon_activity_gifts_3_1]",4,1,{10100001,2000000,10800001,6,10700001,20},10004,nil,nil,nil,2,"Shop[shop_tag_time_01]","LAB_EVENT",1900012,6},
{1013,19,"LAB_ACTIVITY_GIFTS_302","Icon[icon_activity_gifts_3_2]",4,1,{10100001,4000000,10800001,15,10700001,50},10004,nil,nil,nil,2,"Shop[shop_tag_time_01]","LAB_EVENT",1900013,7}
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

return P