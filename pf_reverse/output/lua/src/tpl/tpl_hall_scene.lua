-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','bg_image','fg_image','bg_eff','bg_small','preview_name',}
    local bodys = {
{1001,"BackGround/bg_lobby_01.png",nil,nil,"ItemPreview[item_preview_scene_lobby_01]",nil},
{1002,"BackGround/bg_lobby_02.png",nil,nil,"ItemPreview[item_preview_scene_lobby_02]",nil},
{2001,"BackGround/hotspring_bg.png",nil,nil,"ItemPreview[item_preview_scene_lobby_hot_spring_01]",nil},
{2002,"BackGround/bg_lobby_school_01.png",nil,nil,"ItemPreview[item_preview_scene_lobby_school_01]",nil},
{2003,"BackGround/bg_lobby_sayaka_01.png",nil,nil,"ItemPreview[item_preview_scene_lobby_sayaka_01]",nil},
{2004,"RoleSpine/3001_6/ImageLobby","RoleSpine/3001_6/ImageFg",nil,"ItemPreview[item_preview_scene_lobby_300106]",nil}
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

tpl_hall_scene = P
tpl_hall_scene_list = PL
function tpl_hall_scene_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

return P