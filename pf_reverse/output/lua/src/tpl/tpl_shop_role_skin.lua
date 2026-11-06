-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','role_skin','image_offset_main','image_offset_window','index','pri','original_pri','discount','new_tag','is_rerun','limit_type','limit_count','time_start','time_end','props_ex','gifts_link','tag_bg','tag_text',}
    local bodys = {
{1,3,"LAB_SKIN_1004_3",100405,{0,0,1.25},{-186,6,1},30,{10300001,590},nil,nil,nil,1,4,1,1787623200,1788879600,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{2,3,"LAB_SKIN_1003_3",100305,{-170,-30,1.1},{-37,-21,0.6},40,{10300001,390},nil,nil,nil,1,4,1,1787623200,1788879600,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{3,3,"LAB_SKIN_1005_3",100505,{-70,-4,1.4},{-84,-106,0.8},50,{10300001,390},nil,nil,nil,1,4,1,1787623200,1788879600,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{4,3,"LAB_SKIN_1008_3",100805,{-106,25,1.15},{-85,-15,0.5},60,{10300001,390},nil,nil,nil,1,4,1,1787623200,1788879600,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{5,3,"LAB_SKIN_1009_5",100905,{-199,-55,1.2},{113,-359,1.1},501,{10300001,390},nil,nil,nil,1,4,1,1785808800,1787065200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{6,3,"LAB_SKIN_1010_5",101005,{-249,-25,1.2},{-37,-130,0.8},502,{10300001,390},nil,nil,nil,1,4,1,1785808800,1787065200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{7,3,"LAB_SKIN_1007_5",100705,{-242,-26,1.2},{-123,-434,0.9},503,{10300001,390},nil,nil,nil,1,4,1,1785808800,1787065200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{8,3,"LAB_SKIN_1006_5",100605,{-52,-21,1.1},{-126,-198,0.9},40,{10300001,390},nil,nil,nil,1,4,1,1791252000,1792508400,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{9,3,"LAB_SKIN_1012_5",101205,{-10,-50,1.25},{81,-191,1},50,{10300001,390},nil,nil,nil,1,4,1,1791252000,1792508400,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{10,3,"LAB_SKIN_1013_5",101305,{-100,0,1.2},{-163,-296,1},60,{10300001,390},nil,nil,nil,1,4,1,1791252000,1792508400,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{11,3,"LAB_SKIN_1014_5",101405,{-50,-50,1.2},{-272,-360,0.9},40,{10300001,390},nil,nil,nil,1,4,1,1793066400,1794322800,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{12,3,"LAB_SKIN_1001_6",100106,{-26,-45,1.1},{195,-306,1},3,{10300001,390},nil,nil,nil,1,4,1,1793066400,1794322800,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{13,3,"LAB_SKIN_1002_5",100205,{-50,-17,1.05},{-288,-225,1},2,{10300001,590},nil,nil,nil,1,4,1,1793066400,1794322800,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{14,3,"LAB_SKIN_1015_5",101505,{-196,-62,1.2},{-152,-425,0.9},1,{10300001,390},nil,nil,nil,1,4,1,1789437600,1790694000,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{15,3,"LAB_SKIN_1016_5",101605,{-11,-37,1.1},{6,28,1},2,{10300001,390},nil,nil,nil,1,4,1,1789437600,1790694000,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{16,3,"LAB_SKIN_1009_6",100906,{-217,-24,1.2},{112,-322,0.9},3,{10300001,390},nil,nil,nil,1,4,1,1789437600,1790694000,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{17,3,"LAB_SKIN_1005_6",100506,{-57,25,1.2},{-84,-106,0.8},30,{10300001,390},nil,nil,nil,1,4,1,1782352800,1785006000,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{18,3,"LAB_SKIN_1007_6",100706,{-100,46,1.3},{177,-30,0.9},20,{10300001,390},nil,nil,nil,1,4,1,1782352800,1785006000,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{19,3,"LAB_SKIN_1010_6",101006,{-133,-5,1.1},{-37,-130,0.8},10,{10300001,390},nil,nil,nil,1,4,1,1782352800,1785006000,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{20,3,"LAB_SKIN_3001_6",300106,{-239,-19,1},{200,-32,0.8},1,{10300001,890},nil,nil,nil,1,4,1,1782352800,1785006000,{20910004,1},1001,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{21,3,"LAB_SKIN_1018_5",101805,{-164,-1,1.15},{-87,-183,0.8},1,{10300001,390},nil,nil,nil,1,4,1,1794880800,1796050800,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{22,3,"LAB_SKIN_1019_5",101905,{-221,-22,1.1},{-256,-414,0.9},2,{10300001,390},nil,nil,nil,1,4,1,1794880800,1796050800,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{23,3,"LAB_SKIN_1004_4",100406,{-140,-2,1.05},{-77,-393,0.8},3,{10300001,390},nil,nil,nil,1,4,1,1794880800,1796050800,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{24,3,"LAB_SKIN_1020_5",102005,{-199,43,1.1},{23,-105,0.8},1,{10300001,390},nil,nil,1,nil,4,1,1787796000,1790521200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{25,3,"LAB_SKIN_1021_5",102105,{-173,6,1.1},{12,-158,0.9},2,{10300001,390},nil,nil,1,nil,4,1,1787796000,1790521200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{26,3,"LAB_SKIN_1008_6",100806,{-113,7,1.1},{-155,-154,0.8},3,{10300001,390},nil,nil,1,nil,4,1,1787796000,1790521200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{27,3,"LAB_SKIN_1006_6",100606,{-196,-36,1.1},{-301,-424,0.8},1,{10300001,390},nil,nil,1,nil,4,1,1790647200,1793113200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{28,3,"LAB_SKIN_1013_6",101306,{55,12,1.1},{128,-327,0.9},2,{10300001,390},nil,nil,1,nil,4,1,1790647200,1793113200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"},
{29,3,"LAB_SKIN_1022_5",102205,{-73,7,1.1},{-275,-237,0.8},3,{10300001,590},nil,nil,1,nil,4,1,1790647200,1793113200,nil,nil,"Shop[shop_skin_event_bg]","LAB_SHOP_COMMON_1"}
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

return P