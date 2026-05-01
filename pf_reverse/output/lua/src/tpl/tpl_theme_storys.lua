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
{6,10002,nil,nil,"story_2001",{30300003,1},nil,{11100401,1},1009},
{7,10002,nil,nil,"story_2002",{30300003,1},nil,{11100402,1},1010},
{8,10002,nil,nil,"story_2003",{30300003,1},nil,{11100403,1},1007},
{9,10003,nil,nil,"story_3002",{10603003,1},nil,{11100404,1},1012},
{10,10003,nil,nil,"story_3003",{10603001,1},nil,{11100405,1},1013},
{11,10003,nil,nil,"story_3001",{10603006,1},nil,{11100406,1},1006},
{12,10004,nil,nil,"story_4002",{10603001,1},nil,{11100407,1},1001},
{13,10004,nil,nil,"story_4001",{10603004,1},nil,{11100408,1},1014},
{14,10004,nil,nil,"story_4003",{10603002,1},nil,{11100409,1},1002},
{15,10005,nil,nil,"story_4002",{10603001,1},nil,{11100407,1},1001},
{16,10005,nil,nil,"story_4001",{10603004,1},nil,{11100408,1},1014},
{17,10005,nil,nil,"story_4003",{10603002,1},nil,{11100409,1},1002}
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