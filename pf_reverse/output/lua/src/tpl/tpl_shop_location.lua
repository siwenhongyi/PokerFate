-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','cur_id','code','payment_method',}
    local bodys = {
{"United States",1,"USD",{302,303,304,216,203,208}},
{"China",1,"USD",{306,302,303,304}},
{"Japan",2,"JPY",{302,303,304,216,209,202,208}},
{"Hong Kong",3,"HKD",{301,302,303,304,216,208}},
{"Macau",3,"HKD",{302,303,304,216,208}},
{"Taiwan",4,"TWD",{302,303,304,208}},
{"Canada",1,"USD",{302,303,304,216,203,208}},
{"The Philippines",1,"USD",{302,303,304,206,204,208}},
{"Singapore",1,"USD",{302,303,304,216,207,208}},
{"Malaysia",1,"USD",{302,303,304,211,205,208}},
{"Thailand",1,"USD",{302,303,304,210,212,208}},
{"Unknown",1,"USD",{306,302,303,304,216,208}}
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

tpl_shop_location = P
tpl_shop_location_list = PL
function tpl_shop_location_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P