-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'chessboard_id','cost','gird_quantity','param','activity_id','minimum_guarantee',}
    local bodys = {
{3000101,{10420002,1},24,{0,1,6,5,11,10,21,20,51,50,101,100},30001,{1,99999,2,99999,3,99999,4,67,5,200}}
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

tpl_monopoly_chessboard = P
tpl_monopoly_chessboard_list = PL
function tpl_monopoly_chessboard_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P