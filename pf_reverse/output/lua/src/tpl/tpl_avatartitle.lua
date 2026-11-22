-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','character','bg_small','eff',}
    local bodys = {
{1001,nil,"Avatartitle[avatartitle_test_01]",nil},
{1002,nil,"Avatartitle[avatartitle_mooncard_01]",nil},
{1003,nil,"Avatartitle[avatartitle_kol_02]",nil},
{1004,nil,"Avatartitle[avatartitle_kol_01]",nil},
{1005,nil,"Avatartitle[avatartitle_ranking_01]",nil},
{1006,nil,"Avatartitle[avatartitle_suggestion_01]",nil},
{1007,nil,"Avatartitle[avatartitle_vip_01]",nil},
{1008,nil,"Avatartitle[avatartitle_vip_02]",nil},
{1009,nil,"Avatartitle[avatartitle_vip_03]",nil},
{1010,nil,"Avatartitle[avatartitle_vip_04]",nil},
{1011,nil,"Avatartitle[avatartitle_vip_05]",nil},
{1012,nil,"Avatartitle[avatartitle_vip_06]",nil},
{1013,nil,"Avatartitle[avatartitle_vip_07]",nil},
{1014,nil,"Avatartitle[avatartitle_vip_08]",nil},
{1015,nil,"Avatartitle[avatartitle_beatdev_01]",nil},
{1016,nil,"Avatartitle[avatartitle_ranking_02]",nil},
{1017,nil,"Avatartitle[avatartitle_vipasst_01]","Avatartitle/avatartitle_vipasst_01"},
{2001,nil,"Avatartitle[avatartitle_activity_01]",nil},
{2002,nil,"Avatartitle[avatartitle_activity_s2_01]",nil},
{2003,nil,"Avatartitle[avatartitle_activity_s3_01]",nil},
{2004,nil,"Avatartitle[avatartitle_activity_s4_01]",nil},
{2005,nil,"Avatartitle[avatartitle_activity_s5_01]",nil},
{2006,nil,"Avatartitle[avatartitle_activity_s6_01]",nil},
{2007,nil,"Avatartitle[avatartitle_activity_s7_01]",nil},
{2008,nil,"Avatartitle[avatartitle_activity_s8_01]",nil},
{2009,nil,"Avatartitle[avatartitle_activity_s9_01]",nil},
{3001,1001,"Avatartitle[avatartitle_1001_01]",nil},
{3002,1002,"Avatartitle[avatartitle_1002_01]",nil},
{3003,1003,"Avatartitle[avatartitle_1003_01]",nil},
{3004,1004,"Avatartitle[avatartitle_1004_01]",nil},
{3005,1005,"Avatartitle[avatartitle_1005_01]",nil},
{3006,1006,"Avatartitle[avatartitle_1006_01]",nil},
{3007,1007,"Avatartitle[avatartitle_1007_01]",nil},
{3008,1008,"Avatartitle[avatartitle_1008_01]",nil},
{3009,1009,"Avatartitle[avatartitle_1009_01]",nil},
{3010,1010,"Avatartitle[avatartitle_1010_01]",nil},
{3012,1012,"Avatartitle[avatartitle_1012_01]",nil},
{3013,1013,"Avatartitle[avatartitle_1013_01]",nil},
{3014,1014,"Avatartitle[avatartitle_1014_01]",nil},
{3015,1015,"Avatartitle[avatartitle_1015_01]",nil},
{3016,1016,"Avatartitle[avatartitle_1016_01]",nil},
{3017,3001,"Avatartitle[avatartitle_3001_01]",nil},
{3018,1018,"Avatartitle[avatartitle_1018_01]",nil},
{3019,1019,"Avatartitle[avatartitle_1019_01]",nil},
{3020,1020,"Avatartitle[avatartitle_1020_01]",nil},
{3021,1021,"Avatartitle[avatartitle_1021_01]",nil},
{3022,1022,"Avatartitle[avatartitle_1022_01]",nil},
{3023,1023,"Avatartitle[avatartitle_1023_01]",nil},
{4001,nil,"Avatartitle[avatartitle_sng_01]",nil},
{4002,nil,"Avatartitle[avatartitle_mtt_01]",nil},
{5001,nil,"Avatartitle[avatartitle_achievement_01]",nil},
{5002,nil,"Avatartitle[avatartitle_achievement_02]",nil},
{5003,nil,"Avatartitle[avatartitle_achievement_03]",nil},
{6001,nil,"Avatartitle[avatartitle_ranking_03]",nil},
{6002,nil,"Avatartitle[avatartitle_ranking_04]",nil},
{6003,nil,"Avatartitle[avatartitle_ranking_05]",nil},
{7001,nil,"Avatartitle[avatartitle_dispatch_01]",nil},
{8001,nil,"Avatartitle[avatartitle_seasonpass_s1_01]",nil}
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

tpl_avatartitle = P
tpl_avatartitle_list = PL
function tpl_avatartitle_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P