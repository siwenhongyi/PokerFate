-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','icon','limit_type','limit_count','props','time_start','time_end','goods_bg','tag_bg','tag_text','buy_id','auto_use','index',}
    local bodys = {
{1001,4,"LAB_SHOP_GIFTS_1_4","Icon[icon_shop_kismetchip_1]",1,1,{10200002,3},nil,nil,2,nil,nil,400001,nil,4},
{1002,4,"LAB_SHOP_GIFTS_1_5","Icon[icon_shop_kismetchip_2]",2,1,{10200002,6},nil,nil,2,nil,nil,400002,nil,5},
{1003,4,"LAB_SHOP_GIFTS_1_6","Icon[icon_shop_kismetchip_3]",3,1,{10200002,12},nil,nil,2,nil,nil,400003,nil,6},
{1004,4,"LAB_SHOP_GIFTS_1_2","Icon[icon_shop_kismetchip_4]",nil,nil,{10200002,15},nil,nil,2,nil,nil,400004,nil,2},
{1006,4,"LAB_SHOP_GIFTS_1_1","Icon[icon_shop_kismetchip_6]",nil,nil,{10200002,62},nil,nil,1,nil,nil,400006,nil,1},
{1101,4,"LAB_SHOP_GIFTS_1_101","Icon[icon_shop_kismetchip_6]",nil,nil,{10200002,100},nil,nil,2,nil,nil,410001,nil,7},
{1102,4,"LAB_SHOP_GIFTS_1_102","Icon[icon_shop_kismetchip_6]",nil,nil,{10200002,200},nil,nil,2,nil,nil,410002,nil,8},
{1103,4,"LAB_SHOP_GIFTS_1_103","Icon[icon_shop_kismetchip_6]",nil,nil,{10200002,300},nil,nil,2,nil,nil,410003,nil,9},
{2001,5,"LAB_SHOP_GIFTS_2_3","Icon[icon_bondingpack_1]",1,1,{30300001,4,10800001,1,10700001,4},nil,nil,2,nil,nil,500001,1,3},
{2002,5,"LAB_SHOP_GIFTS_2_4","Icon[icon_bondingpack_2]",2,1,{30300001,9,10800001,3,10700001,9},nil,nil,2,nil,nil,500002,1,4},
{2003,5,"LAB_SHOP_GIFTS_2_5","Icon[icon_bondingpack_3]",3,1,{30300001,20,10800001,6,10700001,20},nil,nil,2,nil,nil,500003,1,5},
{2004,5,"LAB_SHOP_GIFTS_2_2","Icon[icon_bondingpack_4]",nil,nil,{30300001,20,10800001,6,10700001,20},nil,nil,2,nil,nil,500004,1,2},
{2005,5,"LAB_SHOP_GIFTS_2_1","Icon[icon_bondingpack_5]",nil,nil,{30300001,50,10800001,15,10700001,50},nil,nil,1,nil,nil,500005,1,1}
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

tpl_shop_gifts = P
tpl_shop_gifts_list = PL
function tpl_shop_gifts_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P