-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','props','time_start','time_end','pri','relation_gift','new_tag','index','name',}
    local bodys = {
{10001,12,{20900002,1},nil,nil,{10300001,250},{11,10001},nil,3,"LAB_PROPS_NAME_209_2"},
{10002,12,{20910001,1},1766628000,1769886000,{10300001,250},{11,10002},1,2,"LAB_PROPS_NAME_209_3"},
{10003,12,{20910002,1},1773280800,1775934000,{10300001,250},nil,1,1,"LAB_PROPS_NAME_209_4"},
{20001,13,{20600006,1},nil,nil,{10300001,200},{11,10001},nil,3,"LAB_PROPS_NAME_206_6"},
{20002,13,{20600004,1},nil,nil,{10300001,200},nil,nil,4,"LAB_PROPS_NAME_206_4"},
{20003,13,{20600005,1},nil,nil,{10300001,200},nil,nil,5,"LAB_PROPS_NAME_206_5"},
{20004,13,{20600003,1},nil,nil,{10300001,200},nil,nil,6,"LAB_PROPS_NAME_206_3"},
{20005,13,{20610001,1},1766628000,1769886000,{10300001,200},{11,10002},nil,2,"LAB_PROPS_NAME_206_7"},
{20006,13,{20610002,1},1770256800,1772910000,{10300001,200},nil,1,1,"LAB_PROPS_NAME_206_8"},
{31001,14,{20700002,1},nil,nil,{10300001,180},{11,10001},nil,201,"LAB_PROPS_NAME_207_2"},
{31002,14,{20700003,1},1766628000,1769886000,{10300001,180},{11,10002},1,101,"LAB_PROPS_NAME_207_3"},
{31003,14,{20700004,1},1773280800,1775934000,{10300001,180},nil,1,1,"LAB_PROPS_NAME_207_4"},
{32001,14,{20800002,1},nil,nil,{10300001,180},{11,10001},nil,202,"LAB_PROPS_NAME_208_2"},
{32002,14,{20800003,1},1766628000,1769886000,{10300001,180},{11,10002},1,102,"LAB_PROPS_NAME_208_3"},
{41001,18,{21000002,1},nil,nil,{10300001,250},nil,nil,1,"LAB_PROPS_NAME_210_2"},
{42001,18,{21100002,1},nil,nil,{10300001,120},nil,nil,2,"LAB_PROPS_NAME_211_2"},
{42002,18,{21100003,1},nil,nil,{10300001,120},nil,nil,3,"LAB_PROPS_NAME_211_3"}
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

tpl_shop_decoration = P
tpl_shop_decoration_list = PL
function tpl_shop_decoration_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

