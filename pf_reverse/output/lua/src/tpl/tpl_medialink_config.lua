-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','media_id','lang','link','copytext',}
    local bodys = {
{1,1,"en","https://www.facebook.com/PokerFateEN/",nil},
{2,1,"tw","https://www.facebook.com/PokerFate/",nil},
{3,2,"tw","http://www.pokerfate.com/zh/linegroup",nil},
{4,3,"jp","https://discord.com/invite/acrfBjX8xT",nil},
{5,3,"en","https://discord.com/invite/acrfBjX8xT",nil},
{6,3,"tw","https://discord.com/invite/acrfBjX8xT",nil},
{7,4,"jp","https://x.com/PokerFate_JP",nil},
{8,4,"en","https://x.com/PokerFate_EN",nil},
{9,5,"zh","https://space.bilibili.com/3632315995523599",nil},
{10,6,"zh","https://weibo.com/u/8498066320",nil},
{11,7,"zh","https://qm.qq.com/q/Qj9NRwvYAI",nil}
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

tpl_medialink_config = P
tpl_medialink_config_list = PL
function tpl_medialink_config_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P