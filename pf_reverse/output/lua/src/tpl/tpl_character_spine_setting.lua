-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','hide_attachments',}
    local bodys = {
{100501,{"mao_tail","mao_body"}},
{100204,{"Chair"}},
{100304,{"zhentou","chuang","chuang2","chuantou","xiuqiu1_yy","c_yy1","c_yy2","c_yy3","c_yy4","c_yy5"}},
{100704,{"bj_2","daoju"}},
{100604,{"bj_1jb"}},
{100405,{"bj_f"}},
{100107,{"qianjing"}},
{100505,{"ghost cat"}},
{100506,{"qj","langan","niao"}},
{100706,{"BG_q"}},
{100904,{"maozi1","maozi2","maozi3","maozi","shuye1","shuye2","shuye3","shuye4","glow"}},
{101004,{"sizijia2","suolian_3","suolian_2","sizijia","tielian1","tielian2"}},
{100605,{"chair"}},
{101205,{"jiazi","shuyedai","yizi_yy2","yizi_yy","yizi","yijiao3","yijiao2","yijiao1","dengzi","hushou","xiezi"}},
{101204,{"shuijinqiu"}},
{100106,{"shafa","shafa_yy1","shafa_yy2","shafa_yy4","shafa_yy5","shafa_yy6"}},
{101604,{"hulan2"}},
{300104,{"A7","A275","A275x"}},
{300105,{"H_0","H_1","H_2","H_3","H_4","H_5","H_6","H_7","H_8","H_9","H_10","H_11","H_13","H_14","H_15","H_17","H_18","H_21","H_22","H_23","H_24","H_26","H_27","H_28","H_12","H_16","H_19","H_20","H_25","H_26","H_27","H_28","H_29","H_30","H_31","H_32"}},
{300106,{"A493","A492","A495","A560","A559","A557","A555","A554","A553","A552","A550","A540","A564","A561","zzz2","A23","A22","A498","A21","cccj2","cccj","A24","A25","bgggg4"}},
{101904,{"2","qunjiao"}},
{102004,{"lefthand3b"}},
{100806,{"A17_2","A125","A127"}},
{101306,{"A89","A90","A91","A111","A112","A113"}},
{100606,{"A19"}},
{102205,{"zhuoyi2","bj_tanzi1"}}
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

tpl_character_spine_setting = P
tpl_character_spine_setting_list = PL
function tpl_character_spine_setting_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P