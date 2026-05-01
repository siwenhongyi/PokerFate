-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','code','tip',}
    local bodys = {
{"APPLY_FRIEND",10000,nil},
{"NEW_FRIEND",10001,nil},
{"DRAW_CARD_CONF",10010,nil},
{"NOTICE_CONF",10020,nil},
{"TASK_REFRESH",10030,nil},
{"SEVEN_TASK_REFRESH",10031,nil},
{"THEME_ACTIVITY_TASK_REFRESH",10032,nil},
{"FESTIVAL_ACTIVITY_TASK_REFRESH",10033,nil},
{"CHALLENGE_TASK_REFRESH",10034,nil},
{"ACHIEVEMENT_TASK_REFRESH",10035,nil},
{"MAIL_REFRESH",10040,nil},
{"VIP_LEVEL_UP",10050,nil},
{"SERVER_MAINTAIN_NORMAL",10060,nil},
{"SERVER_MAINTAIN_AFTER_FIVE_MIN",10061,nil},
{"SERVER_UPDATE_PUSH",10062,nil},
{"STOVE_BUY_SUC",10070,nil},
{"THEME_ACTIVITY_START",10080,nil},
{"FESTIVAL_ACTIVITY_START",10081,nil},
{"GAME_REBATE_SETTLE",10082,nil},
{"PAYPAL_BUY_SUC",10091,nil},
{"XSOLLA_BUY_SUC",10092,nil},
{"STEAM_BUY_SUC",10093,nil},
{"AIRWALLEX_BUY_SUC",10094,nil}
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

tpl_PushConsts = P
tpl_PushConsts_list = PL
function tpl_PushConsts_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P