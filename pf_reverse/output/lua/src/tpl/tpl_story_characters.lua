-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','sex','spine_res','avatar','Imagebg',}
    local bodys = {
{0,nil,3,nil,nil,nil},
{5001,"LAB_STORY_ROLE_NAME_6",1,nil,"Hotspring[hotspring_npc]",nil},
{1001,"LAB_CHAR_NAME_1001",1,"RoleSpine/1001_1/Role1001_1",nil,nil},
{100104,"LAB_CHAR_NAME_1001",1,"RoleSpine/1001_2/Role1001_2",nil,nil},
{100105,"LAB_CHAR_NAME_1001",1,"RoleSpine/1001_3/Role1001_3",nil,nil},
{100106,"LAB_CHAR_NAME_1001",1,"RoleSpine/1001_6/Role1001_6",nil,nil},
{1002,"LAB_CHAR_NAME_1002",1,"RoleSpine/1002_1/Role1002_1",nil,nil},
{100204,"LAB_CHAR_NAME_1002",1,"RoleSpine/1002_2/Role1002_2",nil,nil},
{100205,"LAB_CHAR_NAME_1002",1,"RoleSpine/1002_5/Role1002_5",nil,nil},
{1003,"LAB_CHAR_NAME_1003",1,"RoleSpine/1003_1/Role1003_1",nil,nil},
{100304,"LAB_CHAR_NAME_1003",1,"RoleSpine/1003_2/Role1003_2",nil,nil},
{100305,"LAB_CHAR_NAME_1003",1,"RoleSpine/1003_3/Role1003_3",nil,nil},
{1004,"LAB_CHAR_NAME_1004",1,"RoleSpine/1004_1/Role1004_1",nil,nil},
{100404,"LAB_CHAR_NAME_1004",1,"RoleSpine/1004_2/Role1004_2",nil,nil},
{100405,"LAB_CHAR_NAME_1004",1,"RoleSpine/1004_3/Role1004_3",nil,nil},
{100406,"LAB_CHAR_NAME_1004",1,"RoleSpine/1004_6/Role1004_6",nil,nil},
{1005,"LAB_CHAR_NAME_1005",1,"RoleSpine/1005_1/Role1005_1",nil,nil},
{100504,"LAB_CHAR_NAME_1005",1,"RoleSpine/1005_2/Role1005_2",nil,nil},
{100505,"LAB_CHAR_NAME_1005",1,"RoleSpine/1005_3/Role1005_3",nil,nil},
{100506,"LAB_CHAR_NAME_1005",1,"RoleSpine/1005_6/Role1005_6",nil,nil},
{1006,"LAB_CHAR_NAME_1006",1,"RoleSpine/1006_1/Role1006_1",nil,nil},
{100604,"LAB_CHAR_NAME_1006",1,"RoleSpine/1006_2/Role1006_2",nil,nil},
{100605,"LAB_CHAR_NAME_1006",1,"RoleSpine/1006_5/Role1006_5",nil,nil},
{100606,"LAB_CHAR_NAME_1006",1,"RoleSpine/1006_6/Role1006_6",nil,nil},
{1007,"LAB_CHAR_NAME_1007",1,"RoleSpine/1007_1/Role1007_1",nil,nil},
{100704,"LAB_CHAR_NAME_1007",1,"RoleSpine/1007_2/Role1007_2",nil,nil},
{100705,"LAB_CHAR_NAME_1007",1,"RoleSpine/1007_5/Role1007_5",nil,nil},
{100706,"LAB_CHAR_NAME_1007",1,"RoleSpine/1007_6/Role1007_6",nil,1},
{1008,"LAB_CHAR_NAME_1008",1,"RoleSpine/1008_1/Role1008_1",nil,nil},
{100804,"LAB_CHAR_NAME_1008",1,"RoleSpine/1008_2/Role1008_2",nil,nil},
{100805,"LAB_CHAR_NAME_1008",1,"RoleSpine/1008_3/Role1008_3",nil,nil},
{100806,"LAB_CHAR_NAME_1008",1,"RoleSpine/1008_6/Role1008_6",nil,nil},
{1009,"LAB_CHAR_NAME_1009",1,"RoleSpine/1009_1/Role1009_1",nil,nil},
{100904,"LAB_CHAR_NAME_1009",1,"RoleSpine/1009_4/Role1009_4",nil,nil},
{100905,"LAB_CHAR_NAME_1009",1,"RoleSpine/1009_5/Role1009_5",nil,nil},
{100906,"LAB_CHAR_NAME_1009",1,"RoleSpine/1009_6/Role1009_6",nil,nil},
{1010,"LAB_CHAR_NAME_1010",1,"RoleSpine/1010_1/Role1010_1",nil,nil},
{101004,"LAB_CHAR_NAME_1010",1,"RoleSpine/1010_4/Role1010_4",nil,nil},
{101005,"LAB_CHAR_NAME_1010",1,"RoleSpine/1010_5/Role1010_5",nil,nil},
{101006,"LAB_CHAR_NAME_1010",1,"RoleSpine/1010_6/Role1010_6",nil,1},
{1012,"LAB_CHAR_NAME_1012",1,"RoleSpine/1012_1/Role1012_1",nil,nil},
{101204,"LAB_CHAR_NAME_1012",1,"RoleSpine/1012_4/Role1012_4",nil,nil},
{101205,"LAB_CHAR_NAME_1012",1,"RoleSpine/1012_5/Role1012_5",nil,nil},
{1013,"LAB_CHAR_NAME_1013",1,"RoleSpine/1013_1/Role1013_1",nil,nil},
{101304,"LAB_CHAR_NAME_1013",1,"RoleSpine/1013_4/Role1013_4",nil,nil},
{101305,"LAB_CHAR_NAME_1013",1,"RoleSpine/1013_5/Role1013_5",nil,nil},
{101306,"LAB_CHAR_NAME_1013",1,"RoleSpine/1013_6/Role1013_6",nil,nil},
{1014,"LAB_CHAR_NAME_1014",1,"RoleSpine/1014_1/Role1014_1",nil,nil},
{101404,"LAB_CHAR_NAME_1014",1,"RoleSpine/1014_4/Role1014_4",nil,nil},
{101405,"LAB_CHAR_NAME_1014",1,"RoleSpine/1014_5/Role1014_5",nil,nil},
{1015,"LAB_CHAR_NAME_1015",1,"RoleSpine/1015_1/Role1015_1",nil,nil},
{101504,"LAB_CHAR_NAME_1015",1,"RoleSpine/1015_4/Role1015_4",nil,nil},
{101505,"LAB_CHAR_NAME_1015",1,"RoleSpine/1015_5/Role1015_5",nil,nil},
{1016,"LAB_CHAR_NAME_1016",1,"RoleSpine/1016_1/Role1016_1",nil,nil},
{101604,"LAB_CHAR_NAME_1016",1,"RoleSpine/1016_4/Role1016_4",nil,nil},
{101605,"LAB_CHAR_NAME_1016",1,"RoleSpine/1016_5/Role1016_5",nil,nil},
{3001,"LAB_CHAR_NAME_3001",1,"RoleSpine/3001_1/Role3001_1",nil,nil},
{300104,"LAB_CHAR_NAME_3001",1,"RoleSpine/3001_4/Role3001_4",nil,nil},
{300105,"LAB_CHAR_NAME_3001",1,"RoleSpine/3001_5/Role3001_5",nil,nil},
{300106,"LAB_CHAR_NAME_3001",1,"RoleSpine/3001_6/Role3001_6",nil,1},
{1018,"LAB_CHAR_NAME_1018",1,"RoleSpine/1018_1/Role1018_1",nil,nil},
{101804,"LAB_CHAR_NAME_1018",1,"RoleSpine/1018_4/Role1018_4",nil,nil},
{101805,"LAB_CHAR_NAME_1018",1,"RoleSpine/1018_5/Role1018_5",nil,nil},
{1019,"LAB_CHAR_NAME_1019",1,"RoleSpine/1019_1/Role1019_1",nil,nil},
{101904,"LAB_CHAR_NAME_1019",1,"RoleSpine/1019_4/Role1019_4",nil,nil},
{101905,"LAB_CHAR_NAME_1019",1,"RoleSpine/1019_5/Role1019_5",nil,nil},
{1020,"LAB_CHAR_NAME_1020",1,"RoleSpine/1020_1/Role1020_1",nil,nil},
{102004,"LAB_CHAR_NAME_1020",1,"RoleSpine/1020_4/Role1020_4",nil,nil},
{102005,"LAB_CHAR_NAME_1020",1,"RoleSpine/1020_5/Role1020_5",nil,nil},
{1021,"LAB_CHAR_NAME_1021",1,"RoleSpine/1021_1/Role1021_1",nil,nil},
{102104,"LAB_CHAR_NAME_1021",1,"RoleSpine/1021_4/Role1021_4",nil,nil},
{102105,"LAB_CHAR_NAME_1021",1,"RoleSpine/1021_5/Role1021_5",nil,nil},
{1022,"LAB_CHAR_NAME_1022",1,"RoleSpine/1022_1/Role1022_1",nil,nil},
{102204,"LAB_CHAR_NAME_1022",1,"RoleSpine/1022_4/Role1022_4",nil,nil},
{102205,"LAB_CHAR_NAME_1022",1,"RoleSpine/1022_5/Role1022_5",nil,nil}
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