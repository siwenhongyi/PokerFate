-- create by export_excel.py

local P = {}
local PL = {}
local function _initData()
    local keys = {'id','image','prefab',}
    local bodys = {
{1001,"BackGround/Story/bg_story_1_1_1.png",nil},
{1002,"BackGround/Cg/cg_1_1_1.png",nil},
{1003,"BackGround/Story/bg_story_1_1_2.png",nil},
{1004,"BackGround/Cg/cg_1_1_2.png",nil},
{1005,"BackGround/Cg/cg_1_1_3.png",nil},
{2001,"BackGround/Story/bg_story_1_2_1.png",nil},
{2002,"BackGround/Story/bg_story_1_2_2.png",nil},
{2003,"BackGround/Cg/cg_1_2_1_a.png",nil},
{2004,"BackGround/Cg/cg_1_2_1_b.png",nil},
{3001,"BackGround/Story/bg_story_s_1_1.png",nil},
{3002,"BackGround/Story/bg_story_s_1_2.png",nil},
{3003,"BackGround/Story/bg_story_s_1_3.png",nil},
{3004,"BackGround/Story/bg_story_s_1_4.png",nil},
{3005,"BackGround/Story/bg_story_s_1_5.png",nil},
{3006,"BackGround/Cg/cg_hot_spring_1.png",nil},
{3007,"BackGround/Cg/cg_hot_spring_2.png",nil},
{4001,"BackGround/Story/bg_story_s_2_1.png",nil},
{4002,"BackGround/Story/bg_story_s_2_2.png",nil},
{4003,"BackGround/Story/bg_story_s_2_3.png",nil},
{5001,"BackGround/Story/bg_story_b_1_1.png",nil},
{5002,"BackGround/Story/bg_story_b_1_2.png",nil}
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

tpl_story_scenes = P
tpl_story_scenes_list = PL
function tpl_story_scenes_clone(key)
    if key and P[key] then
        return clone(P[key])
    end
    return nil
end

