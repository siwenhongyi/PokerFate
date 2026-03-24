-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','reward','sharing_platform','is_open','player_info','game_logo','share_text',}
    local bodys = {
{1,{10200001,10},"1,2,3,4",1,0,2,0},
{2,{10200001,10},"1,2,3,4",1,1,1,0},
{3,{10200001,10},"1,2,3,4",1,1,2,0},
{4,{10200001,10},"1,2,3,4",1,1,2,1},
{5,{10200001,10},"1,2,3,4",1,0,2,0},
{6,{10200001,10},"1,2,3,4",1,0,2,0}
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

tpl_share_config = P
tpl_share_config_list = PL
function tpl_share_config_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

