-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','hide_attachments',}
    local bodys = {
{100501,{"mao_tail","mao_body"}},
{100204,{"Chair"}},
{100304,{"zhentou","chuang"}},
{100704,{"bj_2"}},
{100604,{"bj_1jb"}},
{100405,{"bj_f"}},
{100107,{"qianjing"}},
{100505,{"ghost cat"}},
{100904,{"maozi1","maozi2","maozi3","maozi","shuye1","shuye2","shuye3","shuye4","glow"}},
{101004,{"sizijia2","suolian_3","suolian_2","sizijia","tielian1","tielian2"}},
{100605,{"chair"}},
{101205,{"jiazi","shuyedai","yizi_yy2","yizi_yy","yizi","yijiao3","yijiao2","yijiao1","dengzi","hushou","xiezi"}},
{101204,{"shuijinqiu"}}
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

