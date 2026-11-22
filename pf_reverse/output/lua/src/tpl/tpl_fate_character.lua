-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','skin_id','cardname','quality','condition','dec','tag','effect_type','effect_values','trigger','base_value','mark',}
    local bodys = {
{1,100101,"LAB_CHAR_NAME_1001",1,1,"TAB_JOKER_SKILL_DEC_1",nil,1,{2,4},7,nil,nil},
{2,100701,"LAB_CHAR_NAME_1007",1,1,"TAB_JOKER_SKILL_DEC_2",1,2,{1,1,1,2,3},5,nil,nil},
{3,100801,"LAB_CHAR_NAME_1008",1,1,"TAB_JOKER_SKILL_DEC_3",1,2,{3,1,1,2,3},5,nil,nil},
{4,100901,"LAB_CHAR_NAME_1009",1,1,"TAB_JOKER_SKILL_DEC_4",1,2,{4,1,1,2,3},5,nil,nil},
{5,101901,"LAB_CHAR_NAME_1019",1,1,"TAB_JOKER_SKILL_DEC_5",1,2,{2,1,1,2,3},5,nil,nil},
{6,100401,"LAB_CHAR_NAME_1004",1,1,"TAB_JOKER_SKILL_DEC_6",2,3,{2,2,8},7,nil,nil},
{7,100201,"LAB_CHAR_NAME_1002",1,1,"TAB_JOKER_SKILL_DEC_7",2,3,{4,2,12},7,nil,nil},
{8,101801,"LAB_CHAR_NAME_1018",1,1,"TAB_JOKER_SKILL_DEC_8",2,3,{3,2,10},7,nil,nil},
{9,101301,"LAB_CHAR_NAME_1013",1,1,"TAB_JOKER_SKILL_DEC_9",2,3,{5,2,12},7,nil,nil},
{10,100601,"LAB_CHAR_NAME_1006",1,1,"TAB_JOKER_SKILL_DEC_10",2,3,{6,2,10},7,nil,nil},
{11,102101,"LAB_CHAR_NAME_1021",1,1,"TAB_JOKER_SKILL_DEC_11",2,3,{2,1,50},7,nil,nil},
{12,101201,"LAB_CHAR_NAME_1012",1,1,"TAB_JOKER_SKILL_DEC_12",2,3,{4,1,100},7,nil,nil},
{13,100501,"LAB_CHAR_NAME_1005",1,1,"TAB_JOKER_SKILL_DEC_13",2,3,{3,1,80},7,nil,nil},
{14,101401,"LAB_CHAR_NAME_1014",1,1,"TAB_JOKER_SKILL_DEC_14",2,3,{5,1,100},7,nil,nil},
{15,102201,"LAB_CHAR_NAME_1022",1,1,"TAB_JOKER_SKILL_DEC_15",2,3,{6,1,80},7,nil,nil},
{33,101001,"LAB_CHAR_NAME_1010",1,4,"TAB_JOKER_SKILL_DEC_16",3,14,{3,1,1,1,1,30},5,nil,nil},
{39,101501,"LAB_CHAR_NAME_1015",1,2,"TAB_JOKER_SKILL_DEC_17",3,14,{5,1,1,1,2,4},5,nil,nil},
{40,101601,"LAB_CHAR_NAME_1016",1,2,"TAB_JOKER_SKILL_DEC_18",3,14,{6,1,1,1,1,31},5,nil,nil},
{49,100301,"LAB_CHAR_NAME_1003",1,4,"TAB_JOKER_SKILL_DEC_19",2,29,{5,1,15},7,{1,0},6},
{104,102001,"LAB_CHAR_NAME_1020",1,3,"TAB_JOKER_SKILL_DEC_20",3,14,{3,1,1,1,2,5},5,nil,nil},
{31,101006,"LAB_SKIN_1010_6",2,5,"TAB_JOKER_SKILL_DEC_21",3,14,{4,1,1,1,2,8},5,nil,nil},
{98,100505,"LAB_SKIN_1005_3",2,5,"TAB_JOKER_SKILL_DEC_22",3,29,{3,2,2},7,{2,0},6},
{118,100905,"LAB_SKIN_1009_5",2,6,"TAB_JOKER_SKILL_DEC_23",1,2,{4,1,1,1,50},5,nil,nil},
{119,101905,"LAB_SKIN_1019_5",2,6,"TAB_JOKER_SKILL_DEC_24",1,2,{2,1,1,2,7},5,nil,nil},
{131,100405,"LAB_SKIN_1004_4",3,9,"TAB_JOKER_SKILL_DEC_25",2,3,{2,3,15000},7,nil,nil},
{132,100205,"LAB_SKIN_1002_5",3,10,"TAB_JOKER_SKILL_DEC_26",2,3,{4,3,20000},7,nil,nil},
{133,101406,"LAB_SKIN_1014_6",3,11,"TAB_JOKER_SKILL_DEC_27",2,3,{8,3,25000},7,nil,nil},
{134,100306,"LAB_SKIN_1003_6",3,12,"TAB_JOKER_SKILL_DEC_28",2,3,{5,3,20000},7,nil,nil},
{135,102205,"LAB_SKIN_1022_5",3,13,"TAB_JOKER_SKILL_DEC_29",2,3,{6,3,15000},7,nil,nil},
{147,102305,"LAB_SKIN_1023_5",4,14,"TAB_JOKER_SKILL_DEC_30",3,14,{7,1,1,1,3,20000},5,nil,nil}
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

tpl_fate_character = P
tpl_fate_character_list = PL
function tpl_fate_character_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P