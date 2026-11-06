-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','image','bg_small',}
    local bodys = {
{1001,"views/Login/LoginSpineKV.prefab","ItemPreview[item_preview_kv_01]"},
{1002,"BackGround/Cg/cg_1_1_1.png","ItemPreview[item_preview_kv_02]"},
{1003,"BackGround/Cg/cg_1_1_2.png","ItemPreview[item_preview_kv_03]"},
{1004,"BackGround/Cg/cg_1_1_3.png","ItemPreview[item_preview_kv_04]"},
{1005,"BackGround/Cg/cg_1_2_1_b.png","ItemPreview[item_preview_kv_05]"},
{1006,"BackGround/Cg/cg_hot_spring_1.png","ItemPreview[item_preview_kv_06]"},
{1007,"BackGround/Cg/cg_hot_spring_2.png","ItemPreview[item_preview_kv_07]"},
{1008,"views/Login/LoginSpineKV2.prefab","ItemPreview[item_preview_kv_08]"}
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

tpl_Illustration = P
tpl_Illustration_list = PL
function tpl_Illustration_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P