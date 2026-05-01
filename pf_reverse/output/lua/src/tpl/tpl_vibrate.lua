-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','vibrates','kind',}
    local bodys = {
{"button",{1},1},
{"action",{3,3,2,2,1},2},
{"shock_action",{3},2},
{"shock_warning",{3},2},
{"shock_win",{2},2},
{"shock_colorgame1",{1},2},
{"shock_colorgame2",{2},2},
{"shock_colorgame3",{2,2,2},2},
{"shock_colorgame4",{1},2},
{"shock_award",{2},3},
{"shock_gacha",{2},3},
{"shock_character",{3},3},
{"shock_pledge_start",{2},3},
{"shock_pledge_finish",{2},3},
{"shock_pinball",{1},2}
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

tpl_vibrate = P
tpl_vibrate_list = PL
function tpl_vibrate_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P