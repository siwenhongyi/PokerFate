-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','icon',}
    local bodys = {
{10010101,"Rankingslist[rankingslist_player_gameplay_icon_0]"},
{10040101,"Rankingslist[rankingslist_player_gameplay_icon_3]"},
{10020101,"Rankingslist[rankingslist_player_gameplay_icon_1]"},
{30030101,"Rankingslist[rankingslist_player_gameplay_icon_2]"},
{30080101,"Rankingslist[rankingslist_player_gameplay_icon_6]"},
{10050301,"Rankingslist[rankingslist_player_gameplay_icon_4]"},
{10060301,"Rankingslist[rankingslist_player_gameplay_icon_5]"}
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

tpl_system_icon = P
tpl_system_icon_list = PL
function tpl_system_icon_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P