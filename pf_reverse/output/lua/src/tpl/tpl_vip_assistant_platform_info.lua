-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','icon','link',}
    local bodys = {
{1,"Shop[shop_vip_assistant_sns_button_02]","discordapp.com/users/1547551115657089105"},
{2,"Shop[shop_vip_assistant_sns_button_03]","2226313038"},
{3,"Shop[shop_vip_assistant_sns_button_01]","https://lin.ee/6RK5Org"},
{4,"Shop[shop_vip_assistant_sns_button_01]","https://lin.ee/xqqPmHg"}
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

tpl_vip_assistant_platform_info = P
tpl_vip_assistant_platform_info_list = PL
function tpl_vip_assistant_platform_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P