-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','name_level','icon','dec','dec2','level','ui',}
    local bodys = {
{101,"LAB_PINBALL_2","LAB_PINBALL_2","Level[level_unlock_icon_3]","LAB_UNLOCK_DEC_101","LAB_LOCK_DEC_101",2,"AnimRoot/LeftTop/Left/ActivityButton"},
{201,"LAB_SYSTEM_NAME_101","LAB_LEVEL_SYSTEM_NAME_101","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_201","LAB_LOCK_DEC_201",0,"AnimRoot/Right/PokerButton"},
{202,"LAB_SYSTEM_NAME_102","LAB_LEVEL_SYSTEM_NAME_102","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_202","LAB_LOCK_DEC_202",4,"AnimRoot/Right/PokerButton"},
{203,"LAB_SYSTEM_NAME_103","LAB_LEVEL_SYSTEM_NAME_103","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_203","LAB_LOCK_DEC_203",10,"AnimRoot/Right/PokerButton"},
{204,"LAB_SYSTEM_NAME_104","LAB_LEVEL_SYSTEM_NAME_104","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_204","LAB_LOCK_DEC_204",17,"AnimRoot/Right/PokerButton"},
{205,"LAB_SYSTEM_NAME_105","LAB_LEVEL_SYSTEM_NAME_105","Level[level_unlock_icon_0]","LAB_UNLOCK_DEC_205","LAB_LOCK_DEC_205",25,"AnimRoot/Right/PokerButton"},
{301,"LAB_SYSTEM_NAME_201","LAB_LEVEL_SYSTEM_NAME_206","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_301","LAB_LOCK_DEC_301",6,"AnimRoot/Right/OmahaButton"},
{302,"LAB_SYSTEM_NAME_202","LAB_LEVEL_SYSTEM_NAME_207","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_302","LAB_LOCK_DEC_302",12,"AnimRoot/Right/OmahaButton"},
{303,"LAB_SYSTEM_NAME_203","LAB_LEVEL_SYSTEM_NAME_208","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_303","LAB_LOCK_DEC_303",19,"AnimRoot/Right/OmahaButton"},
{304,"LAB_SYSTEM_NAME_204","LAB_LEVEL_SYSTEM_NAME_209","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_304","LAB_LOCK_DEC_304",27,"AnimRoot/Right/OmahaButton"},
{305,"LAB_SYSTEM_NAME_205","LAB_LEVEL_SYSTEM_NAME_210","Level[level_unlock_icon_1]","LAB_UNLOCK_DEC_305","LAB_LOCK_DEC_305",0,"AnimRoot/Right/OmahaButton"},
{401,"LAB_SYSTEM_NAME_301","LAB_LEVEL_SYSTEM_NAME_401","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_401","LAB_LOCK_DEC_401",0,nil},
{402,"LAB_SYSTEM_NAME_302","LAB_LEVEL_SYSTEM_NAME_402","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_402","LAB_LOCK_DEC_402",5,nil},
{403,"LAB_SYSTEM_NAME_303","LAB_LEVEL_SYSTEM_NAME_403","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_403","LAB_LOCK_DEC_403",11,nil},
{404,"LAB_SYSTEM_NAME_304","LAB_LEVEL_SYSTEM_NAME_404","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_404","LAB_LOCK_DEC_404",18,nil},
{405,"LAB_SYSTEM_NAME_305","LAB_LEVEL_SYSTEM_NAME_405","Level[level_unlock_icon_4]","LAB_UNLOCK_DEC_405","LAB_LOCK_DEC_405",26,nil},
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