-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','group','title','name','res','rewards','unlock_time','unlock_item','character',}
    local bodys = {
{1,10001,"LAB_THEME_STORYS_TITLE_1","LAB_STORY_NAME_S1_1","story_1001",{10410001,80},0,nil,nil},
{2,10001,"LAB_THEME_STORYS_TITLE_2","LAB_STORY_NAME_S1_2","story_1002",{10410001,90},1,nil,nil},
{3,10001,"LAB_THEME_STORYS_TITLE_3","LAB_STORY_NAME_S1_3","story_1003",{10410001,100},2,nil,nil},
{4,10001,"LAB_THEME_STORYS_TITLE_4","LAB_STORY_NAME_S1_4","story_1004",{10410001,110},3,nil,nil},
{5,10001,"LAB_THEME_STORYS_TITLE_5","LAB_STORY_NAME_S1_5","story_1005",{10410001,120},4,nil,nil},
{6,10002,nil,"LAB_STORY_NAME_S2_1","story_2001",{30300003,1},nil,{11100401,1},1009},
{7,10002,nil,"LAB_STORY_NAME_S2_2","story_2002",{30300003,1},nil,{11100402,1},1010},
{8,10002,nil,"LAB_STORY_NAME_S2_3","story_2003",{30300003,1},nil,{11100403,1},1007},
{9,10003,nil,"LAB_STORY_NAME_S3_2","story_3002",{10603003,1},nil,{11100404,1},1012},
{10,10003,nil,"LAB_STORY_NAME_S3_3","story_3003",{10603001,1},nil,{11100405,1},1013},
{11,10003,nil,"LAB_STORY_NAME_S3_1","story_3001",{10603006,1},nil,{11100406,1},1006},
{12,10004,nil,"LAB_STORY_NAME_S4_2","story_4002",{10603001,1},nil,{11100407,1},1001},
{13,10004,nil,"LAB_STORY_NAME_S4_1","story_4001",{10603004,1},nil,{11100408,1},1014},
{14,10004,nil,"LAB_STORY_NAME_S4_3","story_4003",{10603002,1},nil,{11100409,1},1002},
{15,10005,nil,"LAB_STORY_NAME_S5_1","story_5001",{10603006,1},nil,{11100411,1},1015},
{16,10005,nil,"LAB_STORY_NAME_S5_2","story_5002",{10603001,1},nil,{11100412,1},1016},
{17,10005,nil,"LAB_STORY_NAME_S5_3","story_5003",{10603005,1},nil,{11100410,1},1009},
{18,10006,"LAB_THEME_STORYS_TITLE_1","LAB_STORY_NAME_S6_1","story_6001",{10603007,1},0,nil,1007},
{19,10006,"LAB_THEME_STORYS_TITLE_2","LAB_STORY_NAME_S6_2","story_6002",{10603005,1},2,nil,1005},
{20,10006,"LAB_THEME_STORYS_TITLE_3","LAB_STORY_NAME_S6_3","story_6003",{10603002,1},4,nil,1010},
{21,10006,"LAB_THEME_STORYS_TITLE_4","LAB_STORY_NAME_S6_4","story_6004",{10603008,1},6,nil,3001}
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

tpl_theme_storys = P
tpl_theme_storys_list = PL
function tpl_theme_storys_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P