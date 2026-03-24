-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','theme_name','theme_des','show_image','name','icon','props','time_start','time_end','discount','new_tag','index',}
    local bodys = {
{10001,11,"TAB_SHOP_THEME_NAME_1","TAB_SHOP_THEME_DEC_1","BackGround/bg_lobby_02.png","TAB_SHOP_THEME_PRODUCT_NAME_1","Icon[icon_gift_pack_theme_1]",{12,10001,14,31001,13,20001,14,32001},nil,nil,800,1,2},
{10002,11,"TAB_SHOP_THEME_NAME_2","TAB_SHOP_THEME_DEC_2","BackGround/hotspring_bg.png","TAB_SHOP_THEME_PRODUCT_NAME_2","Icon[icon_gift_pack_theme_2]",{12,10002,14,31002,13,20005,14,32002},1766628000,1769886000,800,1,1}
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

tpl_shop_theme = P
tpl_shop_theme_list = PL
function tpl_shop_theme_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

