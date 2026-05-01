-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','character','bg_small',}
    local bodys = {
{1001,nil,"Avatartitle[avatartitle_test_01]"},
{1002,nil,"Avatartitle[avatartitle_mooncard_01]"},
{1003,nil,"Avatartitle[avatartitle_kol_02]"},
{1004,nil,"Avatartitle[avatartitle_kol_01]"},
{1005,nil,"Avatartitle[avatartitle_ranking_01]"},
{1006,nil,"Avatartitle[avatartitle_suggestion_01]"},
{1007,nil,"Avatartitle[avatartitle_vip_01]"},
{1008,nil,"Avatartitle[avatartitle_vip_02]"},
{1009,nil,"Avatartitle[avatartitle_vip_03]"},
{1010,nil,"Avatartitle[avatartitle_vip_04]"},
{1011,nil,"Avatartitle[avatartitle_vip_05]"},
{1012,nil,"Avatartitle[avatartitle_vip_06]"},
{1013,nil,"Avatartitle[avatartitle_vip_07]"},
{1014,nil,"Avatartitle[avatartitle_vip_08]"},
{2001,nil,"Avatartitle[avatartitle_activity_01]"},
{2002,nil,"Avatartitle[avatartitle_activity_s2_01]"},
{2003,nil,"Avatartitle[avatartitle_activity_s3_01]"},
{2004,nil,"Avatartitle[avatartitle_activity_s4_01]"},
{3001,1001,"Avatartitle[avatartitle_1001_01]"},
{3002,1002,"Avatartitle[avatartitle_1002_01]"},
{3003,1003,"Avatartitle[avatartitle_1003_01]"},
{3004,1004,"Avatartitle[avatartitle_1004_01]"},
{3005,1005,"Avatartitle[avatartitle_1005_01]"},
{3006,1006,"Avatartitle[avatartitle_1006_01]"},
{3007,1007,"Avatartitle[avatartitle_1007_01]"},
{3008,1008,"Avatartitle[avatartitle_1008_01]"},
{3009,1009,"Avatartitle[avatartitle_1009_01]"},
{3010,1010,"Avatartitle[avatartitle_1010_01]"},
{3012,1012,"Avatartitle[avatartitle_1012_01]"},
{3013,1013,"Avatartitle[avatartitle_1013_01]"},
{3014,1014,"Avatartitle[avatartitle_1014_01]"},
{4001,nil,"Avatartitle[avatartitle_sng_01]"},
{5001,nil,"Avatartitle[avatartitle_achievement_01]"},
{5002,nil,"Avatartitle[avatartitle_achievement_02]"},
{5003,nil,"Avatartitle[avatartitle_achievement_03]"}
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