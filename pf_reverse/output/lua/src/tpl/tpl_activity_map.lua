-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','activity_gifts','activity_shop','activity_lottery','activity_recruit',}
    local bodys = {
{10006,"SayakaPackage","SayakaShop",nil,"gacha_sayaka_button_gift"},
{10007,"MatsuriPackage","MatsuriShop",nil,"gacha_matsuri_button_gift"},
{10008,"RacingPackage",nil,"RacingLottery","gacha_racing_button_gift"},
{10009,"FantasyPackage","FantasyShop",nil,"gacha_fantasy_button_gift"}
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

tpl_activity_map = P
tpl_activity_map_list = PL
function tpl_activity_map_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P