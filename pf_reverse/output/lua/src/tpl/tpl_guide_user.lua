-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','name','level','avatar','frame','title','role_id','skin_id','user_type',}
    local bodys = {
{1,"LAB_GUIDE_NAME_1",10,20110402,0,0,1004,100404,0}
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

tpl_guide_user = P
tpl_guide_user_list = PL
function tpl_guide_user_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P