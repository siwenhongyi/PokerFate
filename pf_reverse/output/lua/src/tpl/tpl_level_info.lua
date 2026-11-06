-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','icon','name','level_range',}
    local bodys = {
{1,"Icon[icon_level_01]","LAB_LEVEL_NAME_1",{1,9}},
{2,"Icon[icon_level_02]","LAB_LEVEL_NAME_2",{10,19}},
{3,"Icon[icon_level_03]","LAB_LEVEL_NAME_3",{20,29}},
{4,"Icon[icon_level_04]","LAB_LEVEL_NAME_4",{30,39}},
{5,"Icon[icon_level_05]","LAB_LEVEL_NAME_5",{40,49}},
{6,"Icon[icon_level_06]","LAB_LEVEL_NAME_6",{50,59}},
{7,"Icon[icon_level_07]","LAB_LEVEL_NAME_7",{60,69}},
{8,"Icon[icon_level_08]","LAB_LEVEL_NAME_8",{70,79}},
{9,"Icon[icon_level_09]","LAB_LEVEL_NAME_9",{80,89}},
{10,"Icon[icon_level_10]","LAB_LEVEL_NAME_10",{90,99}},
{11,"Icon[icon_level_11]","LAB_LEVEL_NAME_11",{100,109}},
{12,"Icon[icon_level_12]","LAB_LEVEL_NAME_12",{110,119}},
{13,"Icon[icon_level_13]","LAB_LEVEL_NAME_13",{120,129}},
{14,"Icon[icon_level_14]","LAB_LEVEL_NAME_14",{130,139}},
{15,"Icon[icon_level_15]","LAB_LEVEL_NAME_15",{140,149}},
{16,"Icon[icon_level_16]","LAB_LEVEL_NAME_16",{150,159}},
{17,"Icon[icon_level_17]","LAB_LEVEL_NAME_17",{160,169}},
{18,"Icon[icon_level_18]","LAB_LEVEL_NAME_18",{170,179}},
{19,"Icon[icon_level_19]","LAB_LEVEL_NAME_19",{180,189}},
{20,"Icon[icon_level_20]","LAB_LEVEL_NAME_20",{190,199}}
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

tpl_level_info = P
tpl_level_info_list = PL
function tpl_level_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P