-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','name_level','icon','dec','dec2','level','ui',}
    local bodys = {
{101,"LAB_PINBALL_2","LAB_PINBALL_2","Level[level_unlock_icon_3]","LAB_UNLOCK_DEC_101","LAB_LOCK_DEC_101",3,"AnimRoot/LeftTop/Left/ActivityButton"},
{201,"LAB_SYSTEM_NAME_101","LAB_LEVEL_SYSTEM_NAME_101","Level[level_unlock_icon_0]",nil,"LAB_LOCK_DEC_201",1,"AnimRoot/Right/PokerButton"},
{206,"LAB_SYSTEM_NAME_102","LAB_LEVEL_SYSTEM_NAME_102","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_202","LAB_LOCK_DEC_202",2,"AnimRoot/Right/PokerButton"},
{207,"LAB_SYSTEM_NAME_103","LAB_LEVEL_SYSTEM_NAME_103","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_203","LAB_LOCK_DEC_203",4,"AnimRoot/Right/PokerButton"},
{202,"LAB_SYSTEM_NAME_104","LAB_LEVEL_SYSTEM_NAME_104","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_204","LAB_LOCK_DEC_204",6,"AnimRoot/Right/PokerButton"},
{208,"LAB_SYSTEM_NAME_105","LAB_LEVEL_SYSTEM_NAME_105","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_205","LAB_LOCK_DEC_205",9,nil},
{203,"LAB_SYSTEM_NAME_106","LAB_LEVEL_SYSTEM_NAME_106","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_206","LAB_LOCK_DEC_206",14,nil},
{209,"LAB_SYSTEM_NAME_107","LAB_LEVEL_SYSTEM_NAME_107","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_207","LAB_LOCK_DEC_207",17,nil},
{204,"LAB_SYSTEM_NAME_108","LAB_LEVEL_SYSTEM_NAME_108","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_208","LAB_LOCK_DEC_208",23,nil},
{305,"LAB_SYSTEM_NAME_201","LAB_LEVEL_SYSTEM_NAME_201","Level[level_unlock_icon_1]",nil,"LAB_LOCK_DEC_301",1,"AnimRoot/Right/OmahaButton"},
{301,"LAB_SYSTEM_NAME_202","LAB_LEVEL_SYSTEM_NAME_202","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_302","LAB_LOCK_DEC_302",6,"AnimRoot/Right/OmahaButton"},
{302,"LAB_SYSTEM_NAME_203","LAB_LEVEL_SYSTEM_NAME_203","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_303","LAB_LOCK_DEC_303",15,"AnimRoot/Right/OmahaButton"},
{303,"LAB_SYSTEM_NAME_204","LAB_LEVEL_SYSTEM_NAME_204","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_304","LAB_LOCK_DEC_304",25,nil},
{401,"LAB_SYSTEM_NAME_301","LAB_LEVEL_SYSTEM_NAME_401","Level[level_unlock_icon_4]",nil,"LAB_LOCK_DEC_401",1,nil},
{402,"LAB_SYSTEM_NAME_302","LAB_LEVEL_SYSTEM_NAME_402","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_402","LAB_LOCK_DEC_402",5,nil},
{403,"LAB_SYSTEM_NAME_303","LAB_LEVEL_SYSTEM_NAME_403","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_403","LAB_LOCK_DEC_403",12,nil},
{404,"LAB_SYSTEM_NAME_304","LAB_LEVEL_SYSTEM_NAME_404","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_404","LAB_LOCK_DEC_404",21,nil},
{501,"LAB_SYSTEM_NAME_501","LAB_LEVEL_SYSTEM_NAME_501","Level[level_unlock_icon_6]",nil,"LAB_LOCK_DEC_501",1,nil},
{502,"LAB_SYSTEM_NAME_502","LAB_LEVEL_SYSTEM_NAME_502","Level[level_unlock_icon_6]","LAB_UNLOCK_DEC_501","LAB_LOCK_DEC_501",5,nil},
{503,"LAB_SYSTEM_NAME_503","LAB_LEVEL_SYSTEM_NAME_503","Level[level_unlock_icon_6]","LAB_UNLOCK_DEC_502","LAB_LOCK_DEC_502",11,nil},
{504,"LAB_SYSTEM_NAME_504","LAB_LEVEL_SYSTEM_NAME_504","Level[level_unlock_icon_6]","LAB_UNLOCK_DEC_503","LAB_LOCK_DEC_503",20,nil},
{1001,"LAB_PLAY_REBATE_1","LAB_PLAY_REBATE_1","Level[level_unlock_icon_5]","LAB_UNLOCK_DEC_1","LAB_LOCK_DEC_1",7,nil}
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

tpl_system_info = P
tpl_system_info_list = PL
function tpl_system_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P