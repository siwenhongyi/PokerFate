-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','tabs','name','icon','limit_type','limit_count','props','time_start','time_end','buy_id','index',}
    local bodys = {
{1001,23,1,"LAB_DISPATCH_102","Icon[icon_dispatch_gift]",0,nil,{10440002,180,10440003,1260,10440004,360},1787796000,1795618800,2100013,5},
{1002,23,1,"LAB_DISPATCH_103","Icon[icon_dispatch_gift]",0,nil,{10440002,75,10440003,525,10440004,150},1787796000,1795618800,2100012,4},
{1003,23,1,"LAB_DISPATCH_104","Icon[icon_dispatch_gift]",0,nil,{10440002,24,10440003,168,10440004,48},1787796000,1795618800,2100011,3},
{1004,23,1,"LAB_DISPATCH_105","Icon[icon_dispatch_gift]",0,nil,{10440002,9,10440003,63,10440004,18},1787796000,1795618800,2100010,2},
{1005,23,1,"LAB_DISPATCH_144","Icon[icon_dispatch_gift]",0,nil,{10440002,3,10440003,21,10440004,6},1787796000,1795618800,2100009,1},
{2002,23,2,"LAB_SHOP_DISPATCH_01","Icon[icon_10440002]",0,nil,{10440002,4},1787796000,1795618800,2100014,1},
{2003,23,2,"LAB_SHOP_DISPATCH_02","Icon[icon_10440003]",0,nil,{10440003,20},1787796000,1795618800,2100015,3},
{2004,23,2,"LAB_SHOP_DISPATCH_03","Icon[icon_10440004]",0,nil,{10440004,12},1787796000,1795618800,2100016,5},
{2005,23,2,"LAB_SHOP_DISPATCH_04","Icon[icon_10440002]",0,nil,{10440002,20},1787796000,1795618800,2100017,2},
{2006,23,2,"LAB_SHOP_DISPATCH_05","Icon[icon_10440003]",0,nil,{10440003,100},1787796000,1795618800,2100018,4},
{2007,23,2,"LAB_SHOP_DISPATCH_06","Icon[icon_10440004]",0,nil,{10440004,60},1787796000,1795618800,2100019,6}
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

tpl_shop_dispatch = P
tpl_shop_dispatch_list = PL
function tpl_shop_dispatch_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P