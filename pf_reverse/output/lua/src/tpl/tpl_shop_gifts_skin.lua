-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','shop_type','name','limit_type','limit_count','role_skin','props_ex','props','time_start','time_end','pri','pri2','original_pri','discount','link','image_offset_window',}
    local bodys = {
{1001,20,"LAB_SKIN_GIFTS_6",4,1,300106,{20910004,1},{21000003,1,21100004,1,21300002,1},1782352800,1785006000,{10300001,1090},{10300001,460},{10300001,1350},nil,102001,{159,-65,0.5}}
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

tpl_shop_gifts_skin = P
tpl_shop_gifts_skin_list = PL
function tpl_shop_gifts_skin_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P