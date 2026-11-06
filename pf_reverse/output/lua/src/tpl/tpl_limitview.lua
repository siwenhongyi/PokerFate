-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','path1','path2','avenues',}
    local bodys = {
{"LoginSpineKV","views/Login/LoginSpineKV.prefab","views/Login/LoginSpineKV_hx.prefab",{6}},
{"avatar_1004_01_full","RoleSpine/1004_1/avatar_1004_01_full.png","RoleSpine/1004_1/avatar_1004_01_full_hx.png",{6}},
{"cg_1_1_1","BackGround/Cg/cg_1_1_1.png","BackGround/Cg/cg_1_1_1_hx.png",{6}},
{"BackGround/Cg/cg_1_1_1.png","BackGround/Cg/cg_1_1_1.png","BackGround/Cg/cg_1_1_1_hx.png",{6}},
{"views/Login/LoginSpineKV.prefab","views/Login/LoginSpineKV.prefab","views/Login/LoginSpineKV_hx.prefab",{6}},
{"LoginSpineKV2","views/Login/LoginSpineKV2.prefab","views/Login/LoginSpineKV_hx.prefab",nil}
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

tpl_limitview = P
tpl_limitview_list = PL
function tpl_limitview_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P