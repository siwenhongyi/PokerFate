-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','icon','display_pic','props','buy_id','limit_type','limit_count',}
    local bodys = {
{10001,15,"TAB_ICEBREAKER_PACK_2","Icon[icon_gift_pack_break_ice]","pic_1",{3,100105,1,1,10200002,1,1,10100001,100000},1500001,4,1}
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

tpl_icebreaker_pack = P
tpl_icebreaker_pack_list = PL
function tpl_icebreaker_pack_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

