-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','xp_up','rewards','icon','name',}
    local bodys = {
{1,0,nil,"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{2,430,{10100001,3000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{3,650,{10100001,5000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{4,860,{10100001,6000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{5,1080,{10100001,8000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{6,1890,{10100001,10000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{7,2210,{10100001,11000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{8,2520,{10100001,13000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{9,2840,{10100001,14000},"Icon[icon_level_01]","LAB_LEVEL_NAME_1"},
{10,3150,{10100001,16000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{11,4570,{10100001,18000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{12,4980,{10100001,19000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{13,5400,{10100001,21000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{14,5810,{10100001,22000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{15,6230,{10100001,24000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{16,8240,{10100001,26000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{17,8760,{10100001,27000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{18,9270,{10100001,29000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{19,9790,{10100001,30000},"Icon[icon_level_02]","LAB_LEVEL_NAME_2"},
{20,10300,{10100001,32000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{21,13220,{10100001,34000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{22,14150,{10100001,37000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{23,15070,{10100001,39000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{24,15990,{10100001,42000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{25,16910,{10100001,44000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{26,20740,{10100001,46000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{27,21810,{10100001,49000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{28,22880,{10100001,51000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{29,23950,{10100001,54000},"Icon[icon_level_03]","LAB_LEVEL_NAME_3"},
{30,25030,{10100001,56000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{31,30160,{10100001,59000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{32,31790,{10100001,62000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{33,33420,{10100001,66000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{34,35050,{10100001,69000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{35,36680,{10100001,72000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{36,38310,{10100001,75000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{37,39940,{10100001,78000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{38,41570,{10100001,82000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{39,43200,{10100001,85000},"Icon[icon_level_04]","LAB_LEVEL_NAME_4"},
{40,44830,{10100001,88000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{41,46860,{10100001,92000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{42,48900,{10100001,96000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{43,50940,{10100001,100000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{44,52980,{10100001,104000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{45,55010,{10100001,108000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{46,57050,{10100001,112000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{47,59090,{10100001,116000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{48,61130,{10100001,120000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{49,63160,{10100001,124000},"Icon[icon_level_05]","LAB_LEVEL_NAME_5"},
{50,65200,{10100001,128000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{51,68050,{10100001,134000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{52,70910,{10100001,139000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{53,73760,{10100001,145000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{54,76610,{10100001,150000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{55,79460,{10100001,156000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{56,82320,{10100001,162000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{57,85170,{10100001,167000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{58,88020,{10100001,173000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{59,90870,{10100001,178000},"Icon[icon_level_06]","LAB_LEVEL_NAME_6"},
{60,93730,{10100001,184000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{61,97800,{10100001,192000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{62,101880,{10100001,200000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{63,105950,{10100001,208000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{64,110030,{10100001,216000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{65,114100,{10100001,224000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{66,118180,{10100001,232000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{67,122250,{10100001,240000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{68,126330,{10100001,248000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{69,130400,{10100001,256000},"Icon[icon_level_07]","LAB_LEVEL_NAME_7"},
{70,134480,{10100001,264000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{71,175090,{10100001,276000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{72,182700,{10100001,288000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{73,190310,{10100001,300000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{74,197930,{10100001,312000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{75,205540,{10100001,324000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{76,215690,{10100001,340000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{77,225840,{10100001,356000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{78,235990,{10100001,372000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{79,246140,{10100001,388000},"Icon[icon_level_08]","LAB_LEVEL_NAME_8"},
{80,256290,{10100001,404000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{81,271510,{10100001,428000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{82,286740,{10100001,452000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{83,301960,{10100001,476000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{84,317190,{10100001,500000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{85,332410,{10100001,524000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{86,422210,{10100001,556000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{87,446510,{10100001,588000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{88,470810,{10100001,620000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{89,495110,{10100001,652000},"Icon[icon_level_09]","LAB_LEVEL_NAME_9"},
{90,519410,{10100001,684000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{91,555860,{10100001,732000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{92,592310,{10100001,780000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{93,628760,{10100001,828000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{94,665210,{10100001,876000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{95,701660,{10100001,924000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{96,762410,{10100001,1004000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{97,823160,{10100001,1084000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{98,883910,{10100001,1164000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{99,944660,{10100001,1244000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"},
{100,1005410,{10100001,1324000},"Icon[icon_level_10]","LAB_LEVEL_NAME_10"}
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

tpl_level = P
tpl_level_list = PL
function tpl_level_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P