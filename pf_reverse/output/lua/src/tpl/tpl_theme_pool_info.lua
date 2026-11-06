-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','pool_group','cost','type','pre_pool','order',}
    local bodys = {
{1000801,10008,{10410008,200},1,nil,1},
{1000802,10008,{10410008,200},1,1000801,2},
{1000803,10008,{10410008,200},1,1000802,3},
{1000804,10008,{10410008,200},2,1000803,4}
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

tpl_theme_pool_info = P
tpl_theme_pool_info_list = PL
function tpl_theme_pool_info_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P