-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','role_skin','image_offset_main','image_offset_window','index','pri','original_pri','discount','new_tag','limit_type','limit_count','time_start','time_end','tag_bg','tag_text',}
    local bodys = {
{1,3,"LAB_SKIN_1004_3",100405,{-2,60,1.2},{-186,6,1},1,{10300001,590},nil,nil,nil,4,1,1774490400,1777230000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{2,3,"LAB_SKIN_1003_3",100305,{-145,-76,1.2},{-37,-21,0.6},6,{10300001,390},nil,nil,nil,4,1,1774490400,1777230000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{3,3,"LAB_SKIN_1005_3",100505,{-126,1,1.2},{-84,-106,0.8},2,{10300001,390},nil,nil,nil,4,1,1774490400,1777230000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{4,3,"LAB_SKIN_1008_3",100805,{-161,47,1.05},{-85,-15,0.5},7,{10300001,390},nil,nil,nil,4,1,1774490400,1777230000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{5,3,"LAB_SKIN_1009_5",100905,{-67,-57,1.2},{113,-359,1.1},1,{10300001,390},nil,nil,nil,4,1,1770256800,1772910000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{6,3,"LAB_SKIN_1010_5",101005,{-117,-27,1.2},{-37,-130,0.8},2,{10300001,390},nil,nil,nil,4,1,1770256800,1772910000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{7,3,"LAB_SKIN_1007_5",100705,{-110,-28,1.2},{-123,-434,0.9},3,{10300001,390},nil,nil,nil,4,1,1770256800,1772910000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{8,3,"LAB_SKIN_1006_5",100605,{-117,-27,1.2},{-126,-198,0.9},3,{10300001,390},nil,nil,1,4,1,1773280800,1775934000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{9,3,"LAB_SKIN_1012_5",101205,{-198,-66,1.3},{81,-191,1},4,{10300001,390},nil,nil,1,4,1,1773280800,1775934000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{10,3,"LAB_SKIN_1013_5",101305,{-41,-157,1.5},{-163,-296,1},5,{10300001,390},nil,nil,1,4,1,1773280800,1775934000,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"}
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

tpl_shop_role_skin = P
tpl_shop_role_skin_list = PL
function tpl_shop_role_skin_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

