-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','sex','spine_res','avatar',}
    local bodys = {
{0,nil,3,nil,nil},
{1001,"LAB_CHAR_NAME_1001",1,"RoleSpine/1001_1/Role1001_1",nil},
{1002,"LAB_CHAR_NAME_1002",1,"RoleSpine/1002_1/Role1002_1",nil},
{1003,"LAB_CHAR_NAME_1003",1,"RoleSpine/1003_1/Role1003_1",nil},
{1004,"LAB_CHAR_NAME_1004",1,"RoleSpine/1004_1/Role1004_1",nil},
{1005,"LAB_CHAR_NAME_1005",1,"RoleSpine/1005_1/Role1005_1",nil},
{1006,"LAB_CHAR_NAME_1006",1,"RoleSpine/1006_1/Role1006_1",nil},
{100605,"LAB_CHAR_NAME_1006",1,"RoleSpine/1006_5/Role1006_5",nil},
{1007,"LAB_CHAR_NAME_1007",1,"RoleSpine/1007_1/Role1007_1",nil},
{100705,"LAB_CHAR_NAME_1007",1,"RoleSpine/1007_5/Role1007_5",nil},
{1008,"LAB_CHAR_NAME_1008",1,"RoleSpine/1008_1/Role1008_1",nil},
{5001,"LAB_STORY_ROLE_NAME_6",1,nil,"Hotspring[hotspring_npc]"},
{100904,"LAB_CHAR_NAME_1009",1,"RoleSpine/1009_5/Role1009_5",nil},
{101005,"LAB_CHAR_NAME_1010",1,"RoleSpine/1010_5/Role1010_5",nil},
{101205,"LAB_CHAR_NAME_1012",1,"RoleSpine/1012_5/Role1012_5",nil},
{101305,"LAB_CHAR_NAME_1013",1,"RoleSpine/1013_5/Role1013_5",nil},
{100205,"LAB_CHAR_NAME_1002",1,"RoleSpine/1002_5/Role1002_5",nil},
{100105,"LAB_CHAR_NAME_1001",1,"RoleSpine/1001_6/Role1001_6",nil},
{101405,"LAB_CHAR_NAME_1014",1,"RoleSpine/1014_5/Role1014_5",nil}
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

tpl_story_characters = P
tpl_story_characters_list = PL
function tpl_story_characters_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P